"""MCP kontrol sonuçlarını kullanıcı komut metnini saklamadan JSONL olarak kaydeder."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock

from ..domain.track_control import TrackState


class McpAuditStore:
    """Doğrulanan, reddedilen ve iptal edilen iz işlemlerini yerel olarak denetlenebilir kılar."""

    _lock = Lock()

    def __init__(self, audit_dir: Path) -> None:
        """Genel audit dizini altında ayrı MCP olay dosyasını seçer."""

        self.audit_dir = audit_dir
        self.path = audit_dir / "mcp_events.jsonl"

    def record(
        self,
        *,
        outcome: str,
        before: TrackState,
        after: TrackState,
        detail: str = "",
    ) -> None:
        """Serbest kullanıcı metni olmadan sonuç ve önce/sonra değerlerini eklemeli yazar."""

        event = {
            "schema_version": 1,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "channel": "mcp_track_control",
            "outcome": outcome,
            "before": before.as_mcp_arguments(),
            "after": after.as_mcp_arguments(),
            "detail": detail[:200],
        }
        payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.audit_dir.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(payload + "\n")

    def recent(self, limit: int = 100) -> list[dict[str, object]]:
        """Bozuk satırları atlayıp son MCP olaylarını en yeniden eskiye döndürür."""

        if limit <= 0 or not self.path.is_file():
            return []
        events: list[dict[str, object]] = []
        for line in reversed(self.path.read_text(encoding="utf-8").splitlines()):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("schema_version") == 1:
                events.append(event)
            if len(events) >= limit:
                break
        return events
