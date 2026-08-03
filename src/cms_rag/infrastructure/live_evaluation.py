"""Kullanıcı tarafından yürütülen canlı RAG deneylerini yerel JSONL dosyasında saklar."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any


class LiveEvaluationStore:
    """Her tamamlanan soru-cevap turunu eklemeli, okunabilir bir deney kaydı olarak tutar."""

    _lock = Lock()

    def __init__(self, evaluation_dir: Path) -> None:
        """Canlı deney dizinini ve tekil JSONL kayıt yolunu hazırlar."""

        self.evaluation_dir = evaluation_dir
        self.path = evaluation_dir / "live_tests.jsonl"

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        """Şema sürümü eklenmiş olayı diske güvenli biçimde ekler."""

        payload = {"schema_version": 1, **event}
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.evaluation_dir.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded + "\n")
        return payload

    def recent(self, limit: int = 500) -> list[dict[str, Any]]:
        """Bozuk satırları atlayarak canlı deneyleri en yeniden eskiye döndürür."""

        if limit <= 0 or not self.path.is_file():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        events: list[dict[str, Any]] = []
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

    def summary(self, limit: int = 500) -> dict[str, Any]:
        """Canlı deneylerden confusion matrix ve chunk kalite özetini hesaplar."""

        events = self.recent(limit)
        cells = {name: 0 for name in ("TP", "TN", "FP", "FN")}
        chunk_correct = 0
        for event in events:
            cell = str(event.get("confusion_cell", ""))
            if cell in cells:
                cells[cell] += 1
            if event.get("chunk_correct") is True:
                chunk_correct += 1
        total = len(events)
        return {
            "event_count": total,
            "cells": cells,
            "chunk_correct": chunk_correct,
            "chunk_accuracy": chunk_correct / total if total else 0.0,
            "events": events,
        }

    def clear(self) -> None:
        """Yalnız canlı deney dosyasını silerek sayacı sıfırlar."""

        with self._lock:
            if self.path.is_file():
                self.path.unlink()
