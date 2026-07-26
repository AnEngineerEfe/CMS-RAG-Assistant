"""Deterministic retrieval evaluation for the project acceptance suite."""

import json
from pathlib import Path

from src.config import RAW_DATA_PATH, RETRIEVAL_K, TOP_K
from src.services.knowledge_base import CMSKnowledgeBase


CASES = [
    {
        "id": "advent_overview",
        "query": "What is ADVENT?",
        "scope": "havelsan",
        "expected_terms": ["advent"],
    },
    {
        "id": "track_management_turkish",
        "query": "İz yönetimi nedir?",
        "scope": "havelsan",
        "expected_terms": ["track management", "lifecycle"],
    },
    {
        "id": "tactical_data_links",
        "query": "Which tactical data links does ADVENT support?",
        "scope": "havelsan",
        "expected_terms": ["link 11", "link 16"],
    },
    {
        "id": "nato_interoperability",
        "query": "What does NATO interoperability mean?",
        "scope": "open_source",
        "expected_terms": ["interoperability", "allies"],
    },
]


def evaluate() -> dict:
    knowledge_base = CMSKnowledgeBase(RAW_DATA_PATH)
    indexed_chunks = knowledge_base.build()
    results = []
    for case in CASES:
        expanded = knowledge_base._contextualise_short_query(case["query"])
        candidates = knowledge_base._retrieve(expanded, case["scope"])
        ranked = knowledge_base.reranker.rerank(expanded, candidates[: RETRIEVAL_K * 2], TOP_K)
        context_text = "\n".join(document.page_content.lower() for _, document in ranked)
        matched = [term for term in case["expected_terms"] if term in context_text]
        results.append({
            "id": case["id"],
            "passed": len(matched) == len(case["expected_terms"]),
            "matched_terms": matched,
            "expected_terms": case["expected_terms"],
            "top_source": ranked[0][1].metadata.get("source_path") if ranked else None,
            "context_sources": [document.metadata.get("source_path") for _, document in ranked],
            "top_score": round(float(ranked[0][0]), 3) if ranked else None,
        })
    return {
        "indexed_chunks": indexed_chunks,
        "passed": sum(result["passed"] for result in results),
        "total": len(results),
        "results": results,
    }


if __name__ == "__main__":
    report = evaluate()
    destination = Path("docs/retrieval_evaluation_report.json")
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] == report["total"] else 1)
