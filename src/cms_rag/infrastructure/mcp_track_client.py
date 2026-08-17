"""Java Swing MCP sunucusuna yerel STDIO JSON-RPC üzerinden bağlanan istemci."""

from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
from queue import Empty, Queue
import shutil
import subprocess
from threading import RLock, Thread
from typing import Any

from ..domain.track_control import TrackState


class McpTrackError(RuntimeError):
    """MCP başlatma, protokol veya araç hatalarını kullanıcı katmanına taşır."""


class StdioMcpTrackClient:
    """Tek Java sürecinin yaşam döngüsünü ve sıralı MCP araç çağrılarını yönetir."""

    def __init__(
        self,
        project_root: Path,
        *,
        timeout_seconds: float = 10.0,
        server_only: bool = False,
    ) -> None:
        """Jar, Java komutu ve bağlantı davranışını yapılandırır; süreci tembel başlatır."""

        self.project_root = project_root
        self.timeout_seconds = timeout_seconds
        self.server_only = server_only
        self._process: subprocess.Popen[str] | None = None
        self._messages: Queue[dict[str, Any]] = Queue()
        self._stderr: deque[str] = deque(maxlen=20)
        self._request_id = 0
        # Başlangıç anlaşması ilk araç çağrısının kilidi içinden yürütülebildiği için
        # aynı iş parçacığının yeniden girebildiği kilit kullanılır.
        self._lock = RLock()

    def get_state(self) -> TrackState:
        """Canlı iz durumunu tek MCP aracıyla okuyup alan modeline dönüştürür."""

        return TrackState.from_payload(self.call_tool("get_track_state"))

    def get_write_policy(self) -> bool:
        """Yazma yetkisinin yalnızca operatör ekranından belirlenen durumunu okur."""

        result = self.call_tool("get_write_policy")
        return bool(result.get("mcpWritesEnabled", False))

    def set_state(self, state: TrackState) -> TrackState:
        """Üç iz alanını sunucuda tek atomik MCP çağrısıyla günceller."""

        result = self.call_tool("set_track_state", state.as_mcp_arguments())
        return TrackState.from_payload(result)

    def get_history(self) -> dict[str, Any]:
        """Java tarafındaki kaynak etiketli son değişiklikleri döndürür."""

        return self.call_tool("get_change_history")

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> dict[str, Any]:
        """İzinli MCP aracını çağırır ve yapılandırılmış sonucunu doğrular."""

        result = self._request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        if bool(result.get("isError", False)):
            raise McpTrackError(_content_text(result) or f"MCP aracı başarısız: {name}")
        structured = result.get("structuredContent")
        if not isinstance(structured, dict):
            raise McpTrackError(f"MCP aracı yapılandırılmış sonuç döndürmedi: {name}")
        return structured

    def is_running(self) -> bool:
        """Alt Java sürecinin halen çalışıp çalışmadığını yan etkisiz bildirir."""

        return self._process is not None and self._process.poll() is None

    def close(self) -> None:
        """Yerel MCP sürecini uygulama kapanışında güvenli biçimde sonlandırır."""

        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()

    def _ensure_started(self) -> None:
        """Java sürecini başlatır ve MCP başlangıç anlaşmasını bir kez tamamlar."""

        if self.is_running():
            return
        self.close()
        self._messages = Queue()
        command = self._server_command()
        try:
            self._process = subprocess.Popen(
                command,
                cwd=self.project_root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exception:
            raise McpTrackError(f"MCP Swing uygulaması başlatılamadı: {exception}") from exception
        Thread(target=self._read_stdout, name="mcp-stdout", daemon=True).start()
        Thread(target=self._read_stderr, name="mcp-stderr", daemon=True).start()
        self._initialize()

    def _initialize(self) -> None:
        """MCP sürüm ve istemci yetenekleri üzerinde standart JSON-RPC anlaşması yapar."""

        self._request(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "cms-rag-assistant", "version": "1.0.0"},
            },
            ensure_started=False,
        )
        self._notify("notifications/initialized", {})

    def _request(
        self,
        method: str,
        params: dict[str, object],
        *,
        ensure_started: bool = True,
    ) -> dict[str, Any]:
        """Bir JSON-RPC isteğini kilit altında gönderip eşleşen cevabı süreli olarak bekler."""

        with self._lock:
            if ensure_started:
                self._ensure_started()
            process = self._process
            if process is None or process.stdin is None:
                raise McpTrackError("MCP süreci kullanılabilir değil.")
            self._request_id += 1
            request_id = self._request_id
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
            try:
                process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError) as exception:
                raise McpTrackError("MCP süreciyle bağlantı kesildi.") from exception
            while True:
                try:
                    response = self._messages.get(timeout=self.timeout_seconds)
                except Empty as exception:
                    details = " | ".join(self._stderr) or "sunucudan ayrıntı alınamadı"
                    raise McpTrackError(f"MCP yanıt zaman aşımı: {details}") from exception
                if response.get("id") != request_id:
                    continue
                if "error" in response:
                    error = response.get("error")
                    message = error.get("message") if isinstance(error, dict) else str(error)
                    raise McpTrackError(f"MCP protokol hatası: {message}")
                result = response.get("result")
                if not isinstance(result, dict):
                    raise McpTrackError("MCP cevabı geçerli bir sonuç içermiyor.")
                return result

    def _notify(self, method: str, params: dict[str, object]) -> None:
        """Cevap beklemeyen MCP bildirimini çalışan sürece iletir."""

        process = self._process
        if process is None or process.stdin is None:
            raise McpTrackError("MCP süreci kullanılabilir değil.")
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        process.stdin.flush()

    def _read_stdout(self) -> None:
        """STDOUT üzerindeki JSON-RPC cevaplarını protokol kuyruğuna aktarır."""

        process = self._process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                self._messages.put(message)

    def _read_stderr(self) -> None:
        """Tanılama satırlarını protokol kanalından ayrı ve sınırlı bellekte tutar."""

        process = self._process
        if process is None or process.stderr is None:
            return
        for line in process.stderr:
            cleaned = line.strip()
            if cleaned:
                self._stderr.append(cleaned)

    def _server_command(self) -> list[str]:
        """Ortam değişkenlerine izin vererek güvenilir Java ve jar yollarını çözer."""

        java_command = os.getenv("CMS_MCP_JAVA") or shutil.which("java")
        if not java_command:
            raise McpTrackError("Java bulunamadı. Java 21 PATH üzerinde olmalıdır.")
        jar = Path(
            os.getenv(
                "CMS_MCP_SWING_JAR",
                str(self.project_root / "mcp-swing-demo" / "target" / "mcp-swing-demo.jar"),
            )
        )
        if not jar.is_file():
            raise McpTrackError(
                "MCP Swing jar bulunamadı. Önce `mcp-swing-demo\\mvnw.cmd clean verify` çalıştırın."
            )
        command = [java_command, "-jar", str(jar)]
        if self.server_only:
            command.append("--server-only")
        return command


def _content_text(result: dict[str, Any]) -> str:
    """MCP hata sonucundaki ilk metin içeriğini kullanıcı dostu biçimde çıkarır."""

    content = result.get("content")
    if not isinstance(content, list):
        return ""
    for item in content:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            return item["text"]
    return ""
