"""Deterministic retrieval acceptance suite for trusted source collections."""

from __future__ import annotations

import json
from pathlib import Path

from src.cms_rag.application import CMSRAGEngine
from src.cms_rag.domain import CMSQueryProcessor


CASES = [
    {
        "id": "official_advent_surface_platform",
        "query": "Sava\u015f gemisinde ADVENT ne yapar?",
        "scope": "official",
        "expected_terms": ["surface platforms", "command and control"],
    },
    {
        "id": "official_track_management",
        "query": "\u0130z y\u00f6netimi nedir?",
        "scope": "official",
        "expected_terms": ["track management", "lifecycle"],
    },
    {
        "id": "official_tactical_data_links",
        "query": "ADVENT hangi taktik veri ba\u011flant\u0131lar\u0131n\u0131 destekler?",
        "scope": "official",
        "expected_terms": ["link 11", "link 16"],
    },
    {
        "id": "open_source_nato_interoperability",
        "query": "NATO interoperability nedir?",
        "scope": "open_source",
        "expected_terms": ["interoperability", "data-centric"],
    },
]


def evaluate() -> dict:
    engine = CMSRAGEngine(Path("data"))
    indexed_chunks = engine.rebuild()
    results = []
    for case in CASES:
        query = CMSQueryProcessor.expand(case["query"])
        hits = engine.retriever.search(query, limit=6, scope=case["scope"])
        context = "\n".join(hit.chunk.text.lower() for hit in hits)
        matched = [term for term in case["expected_terms"] if term in context]
        results.append({
            "id": case["id"],
            "scope": case["scope"],
            "passed": len(matched) == len(case["expected_terms"]),
            "matched_terms": matched,
            "expected_terms": case["expected_terms"],
            "sources": [
                {
                    "document": hit.chunk.document,
                    "page": hit.chunk.page,
                    "collection": hit.chunk.collection,
                    "authority": hit.chunk.authority,
                }
                for hit in hits
            ],
        })
    return {
        "indexed_chunks": indexed_chunks,
        "passed": sum(item["passed"] for item in results),
        "total": len(results),
        "results": results,
    }


if __name__ == "__main__":
    report = evaluate()
    destination = Path("docs/retrieval_evaluation_report.json")
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    raise SystemExit(0 if report["passed"] == report["total"] else 1)
