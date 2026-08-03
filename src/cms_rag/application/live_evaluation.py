"""Canlı soru-cevap turlarını altın veri ve chunk hakemiyle değerlendirir."""

from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
from pathlib import Path
from typing import Any

from ..domain.models import SearchHit
from ..domain.query import CMSQueryProcessor


class LiveEvaluationAssessor:
    """Çalışma anındaki bir turun doğruluk etiketini açıklanabilir kurallarla üretir."""

    def __init__(self, project_root: Path) -> None:
        """Altın set ve bağımsız chunk-hakem raporlarını bir kez belleğe alır."""

        self.gold_cases = self._read_cases(
            project_root / "evaluation" / "datasets" / "gold_cases.json"
        )
        self.chunk_judgments = self._read_chunk_judgments(
            project_root
            / "evaluation"
            / "results"
            / "quality-latest"
            / "quality_evaluation_report.json"
        )

    def assess(
        self,
        *,
        question: str,
        answer: str,
        model: str,
        scope: str,
        outcome: str,
        hits: list[SearchHit],
        latency_ms: float,
        generation_mode: str,
    ) -> dict[str, Any]:
        """Tek tur için input/output, chunk ve confusion-matrix alanlarını oluşturur."""

        matched_case, match_score = self._match_gold_case(question, scope)
        predicted_positive = outcome == "grounded"
        if matched_case is not None:
            actual_positive = bool(matched_case.get("data_available"))
            ground_truth_basis = f"Altın set · {matched_case.get('id', 'unknown')}"
        else:
            actual_positive = self._automatic_availability(question, hits)
            ground_truth_basis = "Otomatik kanıt denetimi"
        confusion_cell = self._confusion_cell(actual_positive, predicted_positive)
        chunk_correct, chunk_basis, chunk_reason = self._chunk_quality(
            hits, matched_case
        )
        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "input": question.strip(),
            "output": answer.strip(),
            "model": model if generation_mode == "ollama" else "deterministik-kanıt-motoru",
            "configured_model": model,
            "scope": scope,
            "outcome": outcome,
            "generation_mode": generation_mode,
            "latency_ms": round(max(latency_ms, 0.0), 3),
            "actual_data_available": actual_positive,
            "predicted_answerable": predicted_positive,
            "confusion_cell": confusion_cell,
            "ground_truth_basis": ground_truth_basis,
            "gold_match_score": round(match_score, 3),
            "chunk_correct": chunk_correct,
            "chunk_quality_basis": chunk_basis,
            "chunk_quality_reason": chunk_reason,
            "sources": [
                {
                    "document": hit.chunk.document,
                    "page": hit.chunk.page,
                    "collection": hit.chunk.collection,
                    "score": round(float(hit.score), 4),
                }
                for hit in hits
            ],
        }

    def _match_gold_case(
        self, question: str, scope: str
    ) -> tuple[dict[str, Any] | None, float]:
        """Aynı veya güçlü biçimde benzer soruyu sürümlü altın sette arar."""

        normalized = CMSQueryProcessor.normalise(question)
        question_terms = set(normalized.split())
        best_case: dict[str, Any] | None = None
        best_score = 0.0
        for case in self.gold_cases:
            if scope != "all" and case.get("scope") not in {scope, "all"}:
                continue
            candidate = CMSQueryProcessor.normalise(str(case.get("question", "")))
            candidate_terms = set(candidate.split())
            union = question_terms | candidate_terms
            jaccard = len(question_terms & candidate_terms) / len(union) if union else 0.0
            sequence = SequenceMatcher(None, normalized, candidate).ratio()
            score = max(jaccard, sequence)
            if score > best_score:
                best_case, best_score = case, score
        return (best_case, best_score) if best_score >= 0.78 else (None, best_score)

    @staticmethod
    def _automatic_availability(question: str, hits: list[SearchHit]) -> bool:
        """Altın-set dışı sorularda ayırt edici terim ve aday kanıt örtüşmesini denetler."""

        if not hits or CMSQueryProcessor.requests_restricted_information(question):
            return False
        query_terms = {
            term
            for term in CMSQueryProcessor.normalise(question).split()
            if len(term) > 2
            and term not in {"advent", "cms", "nedir", "nasil", "hangi", "icin", "sistem"}
        }
        evidence_terms = set(
            CMSQueryProcessor.normalise(" ".join(hit.chunk.text for hit in hits[:2])).split()
        )
        overlap = query_terms & evidence_terms
        return bool(overlap) and (
            len(overlap) >= 2 or len(overlap) / max(len(query_terms), 1) >= 0.4
        )

    def _chunk_quality(
        self,
        hits: list[SearchHit],
        matched_case: dict[str, Any] | None,
    ) -> tuple[bool, str, str]:
        """Seçilen chunkları bağımsız hakem, altın sayfa ve yapısal kurallarla sınar."""

        if not hits:
            if matched_case is not None and not matched_case.get("data_available"):
                return True, "Altın negatif vaka", "Kaynakta bulunmayan bilgi için chunk seçilmedi."
            return False, "Kanıt seçimi", "Sorgu için değerlendirilebilir chunk seçilmedi."
        if matched_case is not None and matched_case.get("data_available"):
            gold_document = matched_case.get("gold_document")
            gold_pages = set(matched_case.get("gold_pages", []))
            gold_hit = any(
                hit.chunk.document == gold_document and hit.chunk.page in gold_pages
                for hit in hits
            )
            if not gold_hit:
                return (
                    False,
                    "Altın kaynak/sayfa",
                    "Seçilen chunklar doğrulanmış altın sayfayı içermiyor.",
                )
        judged: list[bool] = []
        for hit in hits:
            key = (hit.chunk.document, hit.chunk.page)
            if key in self.chunk_judgments:
                judged.append(self.chunk_judgments[key])
            else:
                text = hit.chunk.text.strip()
                judged.append(120 <= len(text) <= 2200 and not text.endswith((",", ";", ":")))
        correct = all(judged)
        basis = "Bağımsız LLM chunk hakemi" if all(
            (hit.chunk.document, hit.chunk.page) in self.chunk_judgments for hit in hits
        ) else "LLM hakemi + yapısal kontrol"
        reason = (
            "Seçilen chunklar anlam bütünlüğü ve sınır kalitesi kontrolünü geçti."
            if correct
            else "En az bir chunk boyut veya cümle sınırı kontrolünü geçemedi."
        )
        return correct, basis, reason

    @staticmethod
    def _confusion_cell(actual_positive: bool, predicted_positive: bool) -> str:
        """Gerçek bilgi mevcudiyeti ile sistem kararını TP/TN/FP/FN hücresine dönüştürür."""

        if actual_positive and predicted_positive:
            return "TP"
        if not actual_positive and not predicted_positive:
            return "TN"
        if not actual_positive and predicted_positive:
            return "FP"
        return "FN"

    @staticmethod
    def _read_cases(path: Path) -> list[dict[str, Any]]:
        """Altın-set dosyası yoksa canlı uygulamayı bozmadan boş liste döndürür."""

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        cases = payload.get("cases", []) if isinstance(payload, dict) else []
        return [case for case in cases if isinstance(case, dict)]

    @staticmethod
    def _read_chunk_judgments(path: Path) -> dict[tuple[str, int], bool]:
        """Chunk hakem raporunu belge/sayfa bazlı kabul haritasına indirger."""

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        stage = payload.get("stage1", {}) if isinstance(payload, dict) else {}
        chunks = stage.get("chunks", [])
        judgments = {
            str(item.get("chunk_id")): bool(item.get("acceptable"))
            for item in stage.get("judgments", [])
            if isinstance(item, dict)
        }
        result: dict[tuple[str, int], bool] = {}
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            key = (str(chunk.get("document", "")), int(chunk.get("page", 0)))
            accepted = judgments.get(str(chunk.get("chunk_id")), False)
            result[key] = result.get(key, True) and accepted
        return result
