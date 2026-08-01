"""Doğrulanmış RAG test raporlarını sunuma uygun kontrol panelinde gösterir."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from .config import PROJECT_ROOT


REPORT_PATHS = {
    "benchmark": PROJECT_ROOT / "evaluation" / "results" / "latest" / "benchmark_report.json",
    "quality": PROJECT_ROOT / "evaluation" / "results" / "quality-latest" / "quality_evaluation_report.json",
    "pgvector": PROJECT_ROOT / "evaluation" / "results" / "pgvector-latest.json",
}


def load_evaluation_reports(
    paths: dict[str, Path] = REPORT_PATHS,
) -> dict[str, dict[str, Any]]:
    """Sürüm kontrollü JSON raporlarını eksik dosyaları görünür bırakarak okur."""

    reports: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        if not path.is_file():
            reports[name] = {}
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reports[name] = {}
            continue
        reports[name] = payload if isinstance(payload, dict) else {}
    return reports


def render_evaluation_dashboard() -> None:
    """Altın set, LLM-hakem ve vektör veritabanı sonuçlarını birlikte çizer."""

    reports = load_evaluation_reports()
    benchmark = reports["benchmark"]
    quality = reports["quality"]
    pgvector = reports["pgvector"]
    st.markdown(
        "<div class='hero'><div class='eyebrow'>RAG QUALITY CONTROL</div>"
        "<h1>Değerlendirme Merkezi</h1>"
        "<p>Altın veri seti, bağımsız LLM hakemi ve vektör altyapısı "
        "karşılaştırmalarının son doğrulanmış sonuçları.</p></div>",
        unsafe_allow_html=True,
    )
    if not benchmark:
        st.error("Altın benchmark raporu bulunamadı. `scripts.run_benchmark` çalıştırılmalı.")
        return

    retrieval = benchmark.get("retrieval", {})
    confusion = benchmark.get("confusion_matrix", {})
    columns = st.columns(4)
    _metric(
        columns[0],
        "Başarılı vaka",
        f"{benchmark.get('passed', 0)}/{benchmark.get('dataset_cases', 0)}",
    )
    _metric(columns[1], "Accuracy", _percent(confusion.get("accuracy")))
    _metric(columns[2], "Hit@6", _percent(retrieval.get("hit_at_k")))
    _metric(columns[3], "MRR", f"{float(retrieval.get('mrr', 0)):.3f}")

    overview, judges, backends = st.tabs(
        ("Altın set", "Chunk ve cevap hakemi", "FAISS / pgvector")
    )
    with overview:
        _render_gold_summary(benchmark)
    with judges:
        _render_judge_summary(quality)
    with backends:
        _render_backend_summary(pgvector)

    st.info(
        "Bu ekran kayıtlı ve yeniden üretilebilir test sonuçlarını gösterir. "
        "LLM-as-judge tek başına doğruluk kanıtı değildir; altın sayfa, terim "
        "kontrolü ve confusion matrix ile birlikte değerlendirilir."
    )


def _render_gold_summary(benchmark: dict[str, Any]) -> None:
    """Altın set confusion matrix, gecikme ve kategori kapsamını gösterir."""

    confusion = benchmark.get("confusion_matrix", {})
    retrieval = benchmark.get("retrieval", {})
    left, right = st.columns([1, 1.5])
    with left:
        st.markdown("#### Confusion matrix")
        st.dataframe(
            [
                {
                    "Gerçek / Tahmin": "Pozitif",
                    "Pozitif": confusion.get("true_positive", 0),
                    "Negatif": confusion.get("false_negative", 0),
                },
                {
                    "Gerçek / Tahmin": "Negatif",
                    "Pozitif": confusion.get("false_positive", 0),
                    "Negatif": confusion.get("true_negative", 0),
                },
            ],
            hide_index=True,
            width="stretch",
        )
    with right:
        st.markdown("#### Retrieval performansı")
        st.dataframe(
            [
                {"Gösterge": "Ortalama", "Gecikme (ms)": retrieval.get("latency_mean_ms", 0)},
                {"Gösterge": "P50", "Gecikme (ms)": retrieval.get("latency_p50_ms", 0)},
                {"Gösterge": "P95", "Gecikme (ms)": retrieval.get("latency_p95_ms", 0)},
            ],
            hide_index=True,
            width="stretch",
        )
    categories = benchmark.get("breakdowns", {}).get("category", {})
    if categories:
        st.markdown("#### Kategori kapsamı")
        st.bar_chart(
            {name: values.get("rate", 0) for name, values in categories.items()}
        )


def _render_judge_summary(quality: dict[str, Any]) -> None:
    """Chunk rubriği ve cevap hakeminin katı başarı sonuçlarını gösterir."""

    if not quality:
        st.warning("Kalite hakemi raporu bulunamadı.")
        return
    chunk = quality.get("stage1", {}).get("summary", {})
    answer = quality.get("stage2", {}).get("summary", {})
    columns = st.columns(3)
    _metric(
        columns[0],
        "Chunk kabulü",
        f"{chunk.get('acceptable_count', 0)}/{chunk.get('chunk_count', 0)}",
    )
    _metric(
        columns[1],
        "Cevap katı başarı",
        f"{answer.get('strict_passed', 0)}/{answer.get('evaluated', 0)}",
    )
    _metric(columns[2], "Geçersiz hakem", str(chunk.get("invalid_judge_outputs", 0)))
    means = chunk.get("dimension_means", {})
    if means:
        labels = {
            "coherence": "Tutarlılık",
            "self_containment": "Tek başına anlam",
            "boundary_quality": "Sınır kalitesi",
            "size_fitness": "Boyut uygunluğu",
        }
        st.markdown("#### Chunk rubriği · 5 üzerinden")
        st.bar_chart({labels.get(name, name): score for name, score in means.items()})


def _render_backend_summary(report: dict[str, Any]) -> None:
    """Aynı embeddinglerle ölçülen FAISS ve pgvector sonuçlarını karşılaştırır."""

    if not report:
        st.warning("FAISS / pgvector karşılaştırma raporu bulunamadı.")
        return
    rows = []
    for label, key in (("FAISS", "faiss"), ("pgvector", "pgvector")):
        result = report.get(key, {})
        rows.append(
            {
                "Altyapı": label,
                "Hit@6": _percent(result.get("hit_at_k")),
                "MRR": round(float(result.get("mrr", 0)), 3),
                "Ortalama ms": result.get("latency_mean_ms", 0),
                "P95 ms": result.get("latency_p95_ms", 0),
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch")
    st.success(
        f"Aynı ilk-K sıralama oranı: {_percent(report.get('identical_top_k_rate'))}"
    )


def _metric(container: Any, label: str, value: str) -> None:
    """Panel metriklerini ortak kart görünümüyle oluşturur."""

    container.markdown(
        "<div class='metric-card'>"
        f"<div class='metric-label'>{label}</div>"
        f"<div class='metric-value'>{value}</div></div>",
        unsafe_allow_html=True,
    )


def _percent(value: Any) -> str:
    """Sayılamayan değerleri sıfır kabul ederek yüzde biçimine dönüştürür."""

    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "0.0%"
