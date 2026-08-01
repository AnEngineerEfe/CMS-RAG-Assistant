"""Ham içerik saklamadan yerel RAG çalışma olaylarını JSONL olarak kaydeder."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from threading import Lock
from typing import Any


class AuditStore:
    """Gizlilik korumalı audit olaylarını eklemeli ve toleranslı biçimde yönetir."""

    _lock = Lock()

    def __init__(self, audit_dir: Path) -> None:
        """Audit dizini ile tek JSONL olay dosyasının yolunu hazırlar."""

        self.audit_dir = audit_dir
        self.path = audit_dir / "events.jsonl"

    def record(
        self,
        *,
        question: str,
        scope: str,
        model: str,
        outcome: str,
        latency_ms: float,
        sources: list[dict[str, Any]],
        answer_chars: int,
        citation_present: bool,
        generation_mode: str,
    ) -> dict[str, Any]:
        """Soru/cevap metni olmadan izlenebilir bir olay kaydı ekler."""

        event = {
            "schema_version": 1,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "query_hash": sha256(question.strip().encode("utf-8")).hexdigest()[:20],
            "scope": scope,
            "model": model,
            "outcome": outcome,
            "latency_ms": round(max(latency_ms, 0.0), 3),
            "source_count": len(sources),
            "sources": sources,
            "answer_chars": max(answer_chars, 0),
            "citation_present": bool(citation_present),
            "generation_mode": generation_mode,
        }
        payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.audit_dir.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(payload + "\n")
        return event

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Bozuk satırları atlayarak son olayları en yeniden eskiye döndürür."""

        if not self.path.is_file() or limit <= 0:
            return []
        events: list[dict[str, Any]] = []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        for line in reversed(lines):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("schema_version") == 1:
                events.append(event)
            if len(events) >= limit:
                break
        return events

    def summary(self, limit: int = 1000) -> dict[str, Any]:
        """Son olayların sonuç, gecikme ve kapsam dağılımını hesaplar."""

        events = self.recent(limit)
        latencies = [float(event.get("latency_ms", 0)) for event in events]
        outcomes: dict[str, int] = {}
        scopes: dict[str, int] = {}
        for event in events:
            outcome = str(event.get("outcome", "unknown"))
            scope = str(event.get("scope", "unknown"))
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            scopes[scope] = scopes.get(scope, 0) + 1
        return {
            "event_count": len(events),
            "average_latency_ms": round(sum(latencies) / len(latencies), 3)
            if latencies
            else 0.0,
            "outcomes": outcomes,
            "scopes": scopes,
            "events": events,
        }
