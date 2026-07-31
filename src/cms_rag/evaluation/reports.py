"""Üç aşamalı değerlendirmeyi JSON, CSV ve sunumluk Markdown olarak yayımlar."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


class QualityReportWriter:
    """Deney sonuçlarını tek klasörde makine ve insan tarafından okunabilir tutar."""

    def __init__(self, output_dir: Path) -> None:
        """Rapor hedef klasörünü oluşturur."""

        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, report: dict[str, Any]) -> None:
        """Ana JSON, aşama CSV'leri ve Markdown yönetici özetini yazar."""

        self._json("quality_evaluation_report.json", report)
        self._csv("stage1_chunks.csv", report["stage1"]["chunks"])
        self._csv("stage1_chunk_judgments.csv", report["stage1"]["judgments"])
        self._csv("stage2_answer_judgments.csv", report["stage2"]["cases"])
        self._csv(
            "stage3_retrieval_comparison.csv",
            report["stage3"]["comparisons"],
        )
        (self.output_dir / "QUALITY_SUMMARY.md").write_text(
            self._summary(report),
            encoding="utf-8",
        )

    def _json(self, name: str, payload: dict[str, Any]) -> None:
        """Sözlüğü girintili UTF-8 JSON dosyasına yazar."""

        (self.output_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _csv(self, name: str, rows: list[dict[str, Any]]) -> None:
        """Değişken alanlı kayıtları Excel uyumlu UTF-8 CSV'ye dönüştürür."""

        path = self.output_dir / name
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        key: json.dumps(value, ensure_ascii=False)
                        if isinstance(value, (list, dict, tuple))
                        else value
                        for key, value in row.items()
                    }
                )

    @staticmethod
    def _summary(report: dict[str, Any]) -> str:
        """Mentör sunumunda kullanılabilecek sonuç tablolarını üretir."""

        chunk = report["stage1"]["summary"]
        answer = report["stage2"]["summary"]
        lines = [
            "# CMS-RAG Kalite ve Bileşen Karşılaştırması",
            "",
            "## 1. Aşama — Chunk Kalitesi",
            "",
            f"- Değerlendirilen: **{chunk['judged_count']}/{chunk['chunk_count']}**",
            f"- Kabul oranı: **{chunk['acceptable_rate']:.1%}**",
            f"- Geçersiz judge çıktısı: **{chunk['invalid_judge_outputs']}**",
            "",
            "## 2. Aşama — Bağımsız Cevap Hakemi",
            "",
            f"- Değerlendirilen pozitif cevap: **{answer['evaluated']}**",
            f"- Katı başarı: **{answer['strict_passed']}/{answer['evaluated']}**",
            f"- Katı başarı oranı: **{answer['strict_success_rate']:.1%}**",
            "",
            "## 3. Aşama — Retrieval Karşılaştırması",
            "",
            "| Yaklaşım | Chunk | Adet | Hit@6 | MRR | Terim | P50 ms |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for item in report["stage3"]["comparisons"]:
            lines.append(
                f"| {item['approach']} | {item['chunk_size']} | "
                f"{item['chunk_count']} | {item['hit_at_k']:.1%} | "
                f"{item['mrr']:.3f} | {item['mean_term_coverage']:.1%} | "
                f"{item['latency_p50_ms']:.1f} |"
            )
        pgvector = report.get("stage4_pgvector")
        if pgvector:
            lines.extend(
                [
                    "",
                    "## 4. Aşama — FAISS / pgvector",
                    "",
                    f"- Aynı ilk-K sıralama oranı: **{pgvector['identical_top_k_rate']:.1%}**",
                    f"- FAISS Hit@6 / MRR: **{pgvector['faiss']['hit_at_k']:.1%} / "
                    f"{pgvector['faiss']['mrr']:.3f}**",
                    f"- pgvector Hit@6 / MRR: **{pgvector['pgvector']['hit_at_k']:.1%} / "
                    f"{pgvector['pgvector']['mrr']:.3f}**",
                    f"- Ortalama yalnız-arama gecikmesi: FAISS "
                    f"**{pgvector['faiss']['latency_mean_ms']:.2f} ms**, pgvector "
                    f"**{pgvector['pgvector']['latency_mean_ms']:.2f} ms**",
                ]
            )
        lines.extend(
            [
                "",
                "LLM hakemi tek başına mutlak doğruluk değildir; altın belge/sayfa, "
                "deterministik terim kontrolleri ve confusion matrix ile birlikte yorumlanır.",
            ]
        )
        return "\n".join(lines) + "\n"
