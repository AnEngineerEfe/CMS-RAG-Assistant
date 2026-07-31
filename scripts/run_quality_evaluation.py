"""Chunk hakemi, cevap hakemi ve retrieval karşılaştırmasını tek komutla çalıştırır."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter

from src.cms_rag.evaluation import (
    OllamaJudge,
    QualityExperimentRunner,
    load_cases,
)
from src.cms_rag.evaluation.reports import QualityReportWriter


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Seçilen aşamaları yürütür, raporları yazar ve eksik judge sonucunda hata döndürür."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "evaluation" / "datasets" / "gold_cases.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluation" / "results" / "quality-latest",
    )
    parser.add_argument(
        "--generator-model",
        default=os.getenv("CMS_RAG_MODEL", "qwen2.5:3b"),
    )
    parser.add_argument(
        "--judge-model",
        default=os.getenv("CMS_RAG_JUDGE_MODEL", "llama3.2:3b"),
    )
    parser.add_argument("--chunk-sizes", type=int, nargs="+", default=[450, 900, 1350])
    parser.add_argument("--judge-batch-size", type=int, default=1)
    parser.add_argument("--skip-chunk-judge", action="store_true")
    parser.add_argument("--skip-answer-judge", action="store_true")
    parser.add_argument("--skip-comparison", action="store_true")
    args = parser.parse_args()

    started = perf_counter()
    runner = QualityExperimentRunner(
        ROOT / "data",
        load_cases(args.dataset),
        judge=OllamaJudge(args.judge_model),
        generator_model=args.generator_model,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "generator_model": args.generator_model,
            "judge_model": args.judge_model,
            "chunk_sizes": args.chunk_sizes,
        },
    }
    print("Aşama 1/3: chunk kalite değerlendirmesi", flush=True)
    report["stage1"] = (
        runner.evaluate_chunks(
            batch_size=args.judge_batch_size,
            cache_path=args.output / "chunk_judge_cache.json",
        )
        if not args.skip_chunk_judge
        else _skipped_chunks()
    )
    print("Aşama 2/3: gerçek cevapların bağımsız LLM değerlendirmesi", flush=True)
    report["stage2"] = (
        runner.evaluate_answers(
            cache_path=args.output / "answer_judge_cache.json"
        )
        if not args.skip_answer_judge
        else _skipped_answers()
    )
    print("Aşama 3/3: chunk boyutu ve retrieval yaklaşımı karşılaştırması", flush=True)
    report["stage3"] = (
        runner.compare_retrieval(tuple(args.chunk_sizes))
        if not args.skip_comparison
        else {"method": {"status": "skipped"}, "comparisons": []}
    )
    report["runtime_seconds"] = round(perf_counter() - started, 3)
    QualityReportWriter(args.output).write(report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "runtime_seconds": report["runtime_seconds"],
                "chunk_summary": report["stage1"]["summary"],
                "answer_summary": report["stage2"]["summary"],
                "comparisons": report["stage3"]["comparisons"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    invalid = report["stage1"]["summary"].get("invalid_judge_outputs", 0)
    incomplete_answers = (
        report["stage2"]["summary"].get("judge_completed", 0)
        != report["stage2"]["summary"].get("evaluated", 0)
    )
    return 1 if invalid or incomplete_answers else 0


def _skipped_chunks() -> dict:
    """Atlanan chunk aşaması için rapor şemasını korur."""

    return {
        "method": {"status": "skipped"},
        "summary": {
            "chunk_count": 0,
            "judged_count": 0,
            "invalid_judge_outputs": 0,
            "acceptable_count": 0,
            "acceptable_rate": 0.0,
            "average_characters": 0.0,
            "dimension_means": {},
        },
        "chunks": [],
        "judgments": [],
    }


def _skipped_answers() -> dict:
    """Atlanan cevap aşaması için rapor şemasını korur."""

    return {
        "method": {"status": "skipped"},
        "summary": {
            "evaluated": 0,
            "judge_completed": 0,
            "judge_correct": 0,
            "strict_passed": 0,
            "strict_success_rate": 0.0,
        },
        "cases": [],
    }


if __name__ == "__main__":
    raise SystemExit(main())
