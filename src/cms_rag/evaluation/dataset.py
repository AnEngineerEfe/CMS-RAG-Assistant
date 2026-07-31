"""Sürümlenen altın değerlendirme veri setini şema kontrolleriyle yükler."""

from __future__ import annotations

import json
from pathlib import Path

from .models import EvaluationCase


def load_cases(path: Path) -> list[EvaluationCase]:
    """JSON veri setini doğrular ve benzersiz tip güvenli vakalara dönüştürür."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2 or not isinstance(payload.get("cases"), list):
        raise ValueError("Desteklenmeyen veya bozuk altın değerlendirme veri seti.")
    cases = [
        EvaluationCase(
            id=item["id"],
            category=item["category"],
            question=item["question"],
            scope=item["scope"],
            query_type=item["query_type"],
            difficulty=item["difficulty"],
            data_available=bool(item["data_available"]),
            gold_document=item.get("gold_document"),
            gold_pages=tuple(int(page) for page in item.get("gold_pages", [])),
            expected_evidence_terms=tuple(
                item.get("expected_evidence_terms", [])
            ),
        )
        for item in payload["cases"]
    ]
    identifiers = [case.id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Altın vaka kimlikleri benzersiz olmalıdır.")
    for case in cases:
        if case.scope not in {"all", "official", "open_source"}:
            raise ValueError(f"Geçersiz kaynak kapsamı: {case.scope}")
        if case.query_type not in {"direct", "paraphrase", "negative"}:
            raise ValueError(f"Geçersiz sorgu türü: {case.query_type}")
        if case.difficulty not in {"easy", "medium", "hard"}:
            raise ValueError(f"Geçersiz zorluk: {case.difficulty}")
        if case.data_available and (
            not case.gold_document
            or not case.gold_pages
            or not case.expected_evidence_terms
        ):
            raise ValueError(f"Pozitif vaka eksik altın kanıt taşıyor: {case.id}")
        if not case.data_available and (
            case.gold_document
            or case.gold_pages
            or case.expected_evidence_terms
        ):
            raise ValueError(f"Negatif vaka altın kanıt taşımamalıdır: {case.id}")
    return cases
