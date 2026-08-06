"""Eski chunk kararlarını koruyup yalnız snapshot'a yeni eklenen chunkları hakemletir."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from src.cms_rag.evaluation import OllamaJudge, QualityExperimentRunner, load_cases
from src.cms_rag.evaluation.reports import QualityReportWriter


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Mevcut rapordan cache üretir, eksikleri değerlendirir ve bütün raporu yeniler."""

    output = ROOT / "evaluation" / "results" / "quality-latest"
    report_path = output / "quality_evaluation_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    cache_path = output / "chunk_judge_cache.json"
    if not cache_path.exists():
        cache_path.write_text(
            json.dumps(
                report.get("stage1", {}).get("judgments", []),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    judge_model = os.getenv("CMS_RAG_JUDGE_MODEL", "llama3.2:3b")
    runner = QualityExperimentRunner(
        ROOT / "data",
        load_cases(ROOT / "evaluation" / "datasets" / "gold_cases.json"),
        judge=OllamaJudge(judge_model, timeout=180.0),
        generator_model=os.getenv("CMS_RAG_MODEL", "qwen2.5:3b"),
    )
    report["stage1"] = runner.evaluate_chunks(
        batch_size=1,
        cache_path=cache_path,
    )
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report.setdefault("configuration", {})["judge_model"] = judge_model
    report["configuration"]["snapshot_chunk_count"] = report["stage1"]["summary"][
        "chunk_count"
    ]
    QualityReportWriter(output).write(report)
    print(json.dumps(report["stage1"]["summary"], ensure_ascii=False, indent=2))
    return 1 if report["stage1"]["summary"]["invalid_judge_outputs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
