"""Chunk-köken veri setindeki kanıt tekilliğini yerel snapshot üzerinde denetler."""

from __future__ import annotations

from collections import defaultdict
import argparse
import json
from pathlib import Path
import re

from src.cms_rag.domain.query import CMSQueryProcessor


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Her pozitif vakanın beklenen terimlerinin kaç chunk'ta birlikte geçtiğini yazdırır."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "evaluation" / "datasets" / "chunk_lineage_20.json",
    )
    parser.add_argument("--show-targets", action="store_true")
    parser.add_argument("--show-answers", action="store_true")
    parser.add_argument("--case-ids", nargs="+")
    parser.add_argument("--check-retrieval", action="store_true")
    parser.add_argument("--check-answers", action="store_true")
    args = parser.parse_args()
    cases = json.loads(
        args.dataset.read_text(encoding="utf-8")
    )["cases"]
    if args.case_ids:
        requested = set(args.case_ids)
        cases = [case for case in cases if str(case["id"]) in requested]
        missing = requested - {str(case["id"]) for case in cases}
        if missing:
            raise ValueError(f"Bilinmeyen vaka kimlikleri: {sorted(missing)}")
    chunks = json.loads(
        (
            ROOT / "data" / "knowledge_base" / "snapshot" / "snapshot.json"
        ).read_text(encoding="utf-8")
    )["chunks"]
    counters: defaultdict[tuple[str, int], int] = defaultdict(int)
    records: list[tuple[str, str]] = []
    raw_by_id: dict[str, str] = {}
    for chunk in chunks:
        key = (chunk["document"], int(chunk["page"]))
        counters[key] += 1
        chunk_id = f"{key[0]}:p{key[1]}:c{counters[key]}"
        records.append((chunk_id, CMSQueryProcessor.normalise(chunk["text"])))
        raw_by_id[chunk_id] = chunk["text"]
    ambiguous = 0
    for case in cases:
        if case["kind"] != "positive":
            continue
        groups = [
            [CMSQueryProcessor.normalise(item) for item in term.split("|")]
            for term in case.get("expected_answer_terms", [])
        ]
        matches = [
            chunk_id
            for chunk_id, text in records
            if all(any(alternative in text for alternative in group) for group in groups)
        ]
        if len(matches) != 1 or matches[0] != case["source_chunk_id"]:
            ambiguous += 1
        print(f"{case['id']}: {case['source_chunk_id']} -> {matches}")
        if args.show_targets:
            print(f"  TARGET: {raw_by_id.get(case['source_chunk_id'], 'NOT FOUND')}")
    print(f"Ambiguous or mismatched positive cases: {ambiguous}")
    retrieval_misses = 0
    answer_misses = 0
    if args.check_retrieval or args.check_answers:
        from src.cms_rag.application import CMSRAGEngine
        from src.cms_rag.evaluation.lineage import ChunkLineageEvaluationRunner

        engine = CMSRAGEngine(ROOT / "data", record_runtime_events=False)
        engine.rebuild()
        for case in cases:
            if case["kind"] != "positive":
                continue
            target = re.fullmatch(r"(.+):p(\d+):c\d+", case["source_chunk_id"])
            if target is None:
                retrieval_misses += 1
                continue
            target_page = (target.group(1), int(target.group(2)))
            if args.check_retrieval:
                query = CMSQueryProcessor.expand(case["question"])
                hits = engine.retriever.search(query, scope=case["scope"])
                pages = [(hit.chunk.document, hit.chunk.page) for hit in hits]
                found = target_page in pages
                retrieval_misses += int(not found)
                print(f"{case['id']} retrieval: {'PASS' if found else 'MISS'} -> {pages}")
            if args.check_answers:
                engine.clear_chat()
                answer, answer_hits = engine.ask(case["question"], case["scope"])
                answer_pages = [
                    (hit.chunk.document, hit.chunk.page) for hit in answer_hits
                ]
                normalized_answer = CMSQueryProcessor.normalise(answer)
                matched = sum(
                    ChunkLineageEvaluationRunner._matches_expected_term(
                        normalized_answer, str(term)
                    )
                    for term in case.get("expected_answer_terms", [])
                )
                matched_terms = [
                    str(term)
                    for term in case.get("expected_answer_terms", [])
                    if ChunkLineageEvaluationRunner._matches_expected_term(
                        normalized_answer, str(term)
                    )
                ]
                total = len(case.get("expected_answer_terms", []))
                coverage = matched / total if total else 1.0
                passed = bool(
                    ChunkLineageEvaluationRunner._is_positive_answer(answer)
                    and coverage >= 1.0
                    and target_page in answer_pages
                )
                answer_misses += int(not passed)
                print(
                    f"{case['id']} answer: {'PASS' if passed else 'MISS'} "
                    f"coverage={coverage:.0%} target={target_page in answer_pages}"
                )
                if args.show_answers and not passed:
                    print(f"  MATCHED: {matched_terms}")
                    print(f"  ANSWER: {answer.strip()}")
        if args.check_retrieval:
            print(f"Positive retrieval misses: {retrieval_misses}")
        if args.check_answers:
            print(f"Positive answer preflight misses: {answer_misses}")
    return 1 if ambiguous or retrieval_misses or answer_misses else 0


if __name__ == "__main__":
    raise SystemExit(main())
