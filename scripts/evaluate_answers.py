"""Gerçek uygulama yanıtlarını beklenen kavram, ret ve kaynak davranışıyla kıyaslar."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from src.cms_rag.application import CMSRAGEngine
from src.cms_rag.application.engine import NO_ANSWER
from src.cms_rag.domain import CMSQueryProcessor


CASES = [
    {
        "id": "advent_definition",
        "question": "ADVENT tam olarak nedir?",
        "expected_terms": ["savaş yönetim sistemi", "ürün ailesi"],
        "answerable": True,
        "reset": True,
    },
    {
        "id": "platform_follow_up",
        "question": "Başka hangi platformlarda kullanılır?",
        "expected_terms": ["advent müren", "advent marti", "advent rota"],
        "answerable": True,
        "reset": False,
    },
    {
        "id": "variant_duty_follow_up",
        "question": "Bunların görevleri nelerdir?",
        "expected_terms": ["advent marti", "advent ufuk", "advent müren"],
        "answerable": True,
        "reset": False,
    },
    {
        "id": "advent_ai_paraphrase",
        "question": "ADVENT-AI karar verirken operatöre ne kazandırıyor?",
        "expected_terms": ["bilişsel yük", "karar süreçlerini"],
        "answerable": True,
        "reset": True,
    },
    {
        "id": "main_paraphrase",
        "question": "MAIN personelin bakım işine nasıl yardım ediyor?",
        "expected_terms": ["bakım adımlarını", "kapalı ağlarda"],
        "answerable": True,
        "reset": True,
    },
    {
        "id": "responsible_ai_paraphrase",
        "question": "Sorumlu yapay zekâ için hangi ilkeler esas alınıyor?",
        "expected_terms": ["hukuka uygunluk", "açıklanabilirlik"],
        "answerable": True,
        "reset": True,
    },
    {
        "id": "unsupported_range",
        "question": "ADVENT hava savunma füzesinin menzili kaç kilometredir?",
        "expected_terms": [],
        "answerable": False,
        "reset": True,
    },
]


def evaluate() -> dict:
    """Soruları uygulama motoruna sorup kavram kapsamı, atıf ve kaynakları birlikte ölçer."""

    engine = CMSRAGEngine(Path("data"))
    indexed_chunks = engine.rebuild()
    results = []
    for case in CASES:
        if case["reset"]:
            engine.clear_chat()
        started = perf_counter()
        answer, hits = engine.ask(case["question"], scope="all")
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        normalized_answer = CMSQueryProcessor.normalise(answer)
        expected = [
            CMSQueryProcessor.normalise(term)
            for term in case["expected_terms"]
        ]
        matched = [
            term for term in expected
            if term in normalized_answer
        ]
        if case["answerable"]:
            decision_ok = answer.strip() != NO_ANSWER and bool(hits)
            citation_ok = "[source " in answer.lower()
            concepts_ok = len(matched) == len(expected)
        else:
            decision_ok = answer.strip() == NO_ANSWER and not hits
            citation_ok = "[source " not in answer.lower()
            concepts_ok = True
        results.append(
            {
                "id": case["id"],
                "question": case["question"],
                "answerable_expected": case["answerable"],
                "answer": answer.strip(),
                "expected_terms": case["expected_terms"],
                "matched_terms": matched,
                "decision_ok": decision_ok,
                "citation_ok": citation_ok,
                "concepts_ok": concepts_ok,
                "elapsed_ms": elapsed_ms,
                "sources": [
                    {
                        "document": hit.chunk.document,
                        "page": hit.chunk.page,
                        "score": round(float(hit.score), 4),
                    }
                    for hit in hits
                ],
                "passed": decision_ok and citation_ok and concepts_ok,
            }
        )
    return {
        "indexed_chunks": indexed_chunks,
        "snapshot_loaded": engine.snapshot_loaded,
        "passed": sum(item["passed"] for item in results),
        "total": len(results),
        "results": results,
    }


if __name__ == "__main__":
    report = evaluate()
    destination = Path("docs/answer_evaluation_report.json")
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))
    raise SystemExit(0 if report["passed"] == report["total"] else 1)
