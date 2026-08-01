"""Ayrı ve yeniden başlatılabilir deney aşamalarını tek nihai kalite raporunda birleştirir."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from src.cms_rag.evaluation.reports import QualityReportWriter


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Tamamlanmış aşama raporlarını doğrulayıp quality-latest altında yayımlar."""

    base_report = _read(
        ROOT / "evaluation" / "results" / "quality-latest"
        / "quality_evaluation_report.json"
    )
    answer_report = _read(
        ROOT / "evaluation" / "results" / "expanded-answer-preflight"
        / "quality_evaluation_report.json"
    )
    component_report = _read(
        ROOT / "evaluation" / "results" / "expanded-component-preflight"
        / "quality_evaluation_report.json"
    )
    pgvector_report = _read(
        ROOT / "evaluation" / "results" / "pgvector-latest.json"
    )
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "generator_model": "qwen2.5:3b",
            "judge_model": "llama3.2:3b",
            "chunk_sizes": [450, 900, 1350],
            "runtime_web_access": False,
        },
        "stage1": base_report["stage1"],
        "stage2": answer_report["stage2"],
        "stage3": component_report["stage3"],
        "stage4_pgvector": pgvector_report,
        "runtime_seconds": round(
            answer_report.get("runtime_seconds", 0)
            + component_report.get("runtime_seconds", 0),
            3,
        ),
    }
    if report["stage1"]["summary"]["judged_count"] != 67:
        raise ValueError("Chunk judge nüfusu tamamlanmadı.")
    if report["stage2"]["summary"]["judge_completed"] != 30:
        raise ValueError("Cevap judge nüfusu tamamlanmadı.")
    if not report["stage3"]["comparisons"]:
        raise ValueError("Retrieval karşılaştırması tamamlanmadı.")
    if any(
        item.get("evaluated") != 30
        for item in report["stage3"]["comparisons"]
    ):
        raise ValueError("Retrieval karşılaştırması genişletilmiş nüfusu kapsamıyor.")
    QualityReportWriter(
        ROOT / "evaluation" / "results" / "quality-latest"
    ).write(report)
    print(
        json.dumps(
            {
                "stage1": report["stage1"]["summary"],
                "stage2": report["stage2"]["summary"],
                "stage3_rows": len(report["stage3"]["comparisons"]),
                "stage4_identical_top_k": pgvector_report["identical_top_k_rate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _read(path: Path) -> dict:
    """Zorunlu deney JSON dosyasını UTF-8 olarak yükler."""

    if not path.exists():
        raise FileNotFoundError(f"Deney raporu bulunamadı: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
