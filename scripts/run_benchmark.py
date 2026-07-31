"""Sürümlü altın soru setini üretim retrieval hattında çalıştırır."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.cms_rag.evaluation import BenchmarkRunner, load_cases


def main() -> int:
    """Komut satırı seçenekleriyle benchmark'ı çalıştırıp JSON ve Markdown raporu yazar."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/datasets/gold_cases.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/latest"),
    )
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    report = BenchmarkRunner(Path("data"), limit=args.limit).run(cases)
    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / "benchmark_report.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary_path = args.output / "SUMMARY.md"
    summary_path.write_text(_summary(report), encoding="utf-8")
    print(json.dumps({
        "dataset_cases": report["dataset_cases"],
        "passed": report["passed"],
        "failed": report["failed"],
        "confusion_matrix": report["confusion_matrix"],
        "retrieval": report["retrieval"],
        "report": str(json_path.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 1


def _summary(report: dict) -> str:
    """Benchmark sonuçlarından sunumda kullanılabilecek kısa Markdown özeti üretir."""

    matrix = report["confusion_matrix"]
    retrieval = report["retrieval"]
    return f"""# CMS-RAG Altın Set Benchmark Özeti

| Gösterge | Sonuç |
|---|---:|
| Toplam vaka | {report['dataset_cases']} |
| Başarılı | {report['passed']} |
| Başarısız | {report['failed']} |
| TP / TN / FP / FN | {matrix['true_positive']} / {matrix['true_negative']} / {matrix['false_positive']} / {matrix['false_negative']} |
| Accuracy | {matrix['accuracy']:.2%} |
| Precision | {matrix['precision']:.2%} |
| Recall | {matrix['recall']:.2%} |
| Specificity | {matrix['specificity']:.2%} |
| F1 | {matrix['f1']:.2%} |
| Hit@6 | {retrieval['hit_at_k']:.2%} |
| MRR | {retrieval['mrr']:.4f} |
| Ortalama retrieval gecikmesi | {retrieval['latency_mean_ms']:.1f} ms |

Tam vaka ayrıntıları `benchmark_report.json` dosyasındadır.
"""


if __name__ == "__main__":
    raise SystemExit(main())
