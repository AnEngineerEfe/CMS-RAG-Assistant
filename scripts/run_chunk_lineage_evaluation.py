"""20 vakalık büyük-model/küçük-RAG/büyük-hakem deneyini çalıştırır."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from src.cms_rag.evaluation import ChunkLineageEvaluationRunner, OllamaJudge


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Deneyi yürütür; JSON, CSV ve README'ye eklenebilir Markdown özeti üretir."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "evaluation" / "datasets" / "chunk_lineage_20.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluation" / "results" / "lineage-latest",
    )
    parser.add_argument(
        "--rag-model",
        default=os.getenv("CMS_RAG_MODEL", "qwen2.5:3b"),
    )
    parser.add_argument(
        "--large-model",
        default=os.getenv("CMS_RAG_LARGE_EVAL_MODEL", "qwen2.5:7b"),
    )
    parser.add_argument(
        "--case-ids",
        nargs="+",
        help="Yalnız belirtilen vaka kimliklerini çalıştırır (ör. L01 L02).",
    )
    parser.add_argument(
        "--regenerate-questions",
        action="store_true",
        help="Sürümlü sorular yerine büyük modelden yeniden soru üretir.",
    )
    parser.add_argument(
        "--force-case-ids",
        nargs="+",
        help="Cache'de tamamlansa da yalnız bu vakaları yeniden çalıştırır.",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    runner = ChunkLineageEvaluationRunner(
        ROOT / "data",
        args.dataset,
        evaluator=OllamaJudge(args.large_model, timeout=180.0),
        rag_model=args.rag_model,
        regenerate_questions=args.regenerate_questions,
    )
    if args.case_ids:
        runner.select_cases(args.case_ids)
    report = runner.run(
        cache_path=args.output / "case_cache.json",
        force_case_ids=set(args.force_case_ids or []),
    )
    _write_json(args.output / "lineage_evaluation_report.json", report)
    _write_csv(args.output / "lineage_cases.csv", report["cases"])
    (args.output / "SUMMARY.md").write_text(
        _markdown_summary(report),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "confusion_matrix": report["confusion_matrix"],
                "lineage": report["lineage"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 1 if report["lineage"]["invalid_cases"] else 0


def _write_json(path: Path, payload: dict) -> None:
    """Raporu UTF-8 ve insan tarafından incelenebilir JSON biçiminde yazar."""

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict]) -> None:
    """İç içe alanları JSON hücresine çevirerek açık isimli Excel tablosu üretir."""

    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list, tuple))
                    else value
                    for key, value in row.items()
                }
            )


def _markdown_summary(report: dict) -> str:
    """Confusion matrix ile model rollerini sunuma hazır Markdown'a dönüştürür."""

    matrix = report["confusion_matrix"]
    lineage = report["lineage"]
    method = report["method"]
    return f"""# 20 Vakalık Bağımsız Chunk-Köken RAG Değerlendirmesi

## Model rolleri

- Soru üreten büyük model: `{method['question_generator_model']}`
- RAG cevabını üreten küçük/kapalı model: `{method['rag_answer_model']}`
- Chunk kökenini bağımsız oturumda değerlendiren büyük model: `{method['chunk_origin_judge_model']}`
- Çalışma anında internet: `kapalı`

## Confusion matrix

| Gerçek \\ Tahmin | Pozitif (cevap verdi) | Negatif (güvenli ret) |
|---|---:|---:|
| Pozitif (bilgi mevcut) | TP = **{matrix['true_positive']}** | FN = **{matrix['false_negative']}** |
| Negatif (bilgi mevcut değil) | FP = **{matrix['false_positive']}** | TN = **{matrix['true_negative']}** |

## Sonuçlar

- Toplam vaka: **{matrix['total']}**
- Accuracy: **{matrix['accuracy']:.1%}**
- Precision: **{matrix['precision']:.1%}**
- Recall: **{matrix['recall']:.1%}**
- Specificity: **{matrix['specificity']:.1%}**
- F1: **{matrix['f1']:.1%}**
- Başlangıç chunkıyla bağımsız hakem eşleşmesi: **{lineage['origin_chunk_matches']}/{lineage['evaluated_positive_cases']}**
- Katı uçtan uca başarı: **{lineage['strict_passes']}/{lineage['evaluated_positive_cases']}**
- Geçersiz vaka: **{lineage['invalid_cases']}**

Pozitif vaka soruları, yalnız kaynak chunk verilerek Codex büyük modelle geliştirme
zamanında üretilmiş, insan tarafından kapsam kontrolünden geçirilmiş ve sürümlenmiştir.
Küçük model yalnız yerel RAG bilgi tabanını kullanarak bağımsız oturumda cevaplar.
Büyük hakem yeni bir oturumda yalnız retrieval adaylarını görür ve cevabı destekleyen
chunk kimliklerini seçer. Katı başarı; cevap verilmesi, hakem desteği, retrieval içinde
başlangıç chunkının bulunması ve hakemin aynı chunkı seçmesini birlikte gerektirir.
"""


if __name__ == "__main__":
    raise SystemExit(main())
