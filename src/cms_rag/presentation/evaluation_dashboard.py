"""Doğrulanmış RAG test raporlarını sunuma uygun kontrol panelinde gösterir."""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path
from typing import Any

import streamlit as st

from ..infrastructure.audit import AuditStore
from ..infrastructure.live_evaluation import LiveEvaluationStore
from .config import DATA_DIR, PROJECT_ROOT


REPORT_PATHS = {
    "benchmark": (
        PROJECT_ROOT / "evaluation" / "results" / "latest" / "benchmark_report.json"
    ),
    "quality": (
        PROJECT_ROOT
        / "evaluation"
        / "results"
        / "quality-latest"
        / "quality_evaluation_report.json"
    ),
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
    """Canlı deneyleri ve sürümlü referans raporlarını birbirinden ayırarak çizer."""

    reports = load_evaluation_reports()
    benchmark = reports["benchmark"]
    quality = reports["quality"]
    pgvector = reports["pgvector"]
    live_store = LiveEvaluationStore(DATA_DIR / "evaluation")
    live = live_store.summary()
    st.markdown(
        "<div class='hero evaluation-hero'><div class='eyebrow'>CANLI RAG DOĞRULAMA</div>"
        "<h1>Değerlendirme Merkezi</h1>"
        "<p>Soru-cevap asistanındaki her tamamlanan test burada otomatik kayda dönüşür. "
        "Input, output, model, chunk kararı ve TP/TN/FP/FN sonucu birlikte izlenir.</p></div>",
        unsafe_allow_html=True,
    )
    cells = live.get("cells", {})
    columns = st.columns(4)
    _metric(columns[0], "Canlı test", str(live.get("event_count", 0)))
    _metric(columns[1], "TP / TN", f"{cells.get('TP', 0)} / {cells.get('TN', 0)}")
    _metric(columns[2], "FP / FN", f"{cells.get('FP', 0)} / {cells.get('FN', 0)}")
    _metric(
        columns[3],
        "Doğru chunk",
        f"{live.get('chunk_correct', 0)}/{live.get('event_count', 0)}",
    )

    tests, matrix, references, operations = st.tabs(
        ("Canlı test tablosu", "TP · TN · FP · FN", "Referans raporlar", "İşletim / audit")
    )
    with tests:
        _render_live_tests(live, live_store)
    with matrix:
        _render_live_matrix(live)
    with references:
        _render_reference_reports(benchmark, quality, pgvector)
    with operations:
        _render_audit_summary(AuditStore(DATA_DIR / "audit").summary())

    st.info(
        "Canlı kayıtlar yereldir ve ilk kullanıcı testinden itibaren oluşur. Altın-set "
        "eşleşmesi bulunmayan sorularda gerçek sınıf 'otomatik kanıt denetimi' ile atanır; "
        "bu dayanak her satırda görünür ve insan onayının yerine geçmez."
    )


def _render_live_tests(summary: dict[str, Any], store: LiveEvaluationStore) -> None:
    """Her canlı testi mentörün istediği alanlarla tablo ve dışa aktarma olarak sunar."""

    events = summary.get("events", [])
    heading, action = st.columns([4, 1])
    with heading:
        st.markdown("#### Otomatik senkronize test kayıtları")
        st.caption("Yeni bir soru tamamlandığında ekranı açmanız veya yenilemeniz yeterlidir.")
    with action:
        if st.button(
            "Canlı kayıtları sıfırla",
            use_container_width=True,
            disabled=not events,
            help="Yalnız canlı test tablosunu temizler; altın raporları ve belgeleri etkilemez.",
        ):
            store.clear()
            st.rerun()
    if not events:
        st.markdown(
            "<div class='evaluation-empty'><strong>Henüz canlı test yok</strong>"
            "<span>Soru-cevap asistanında ilk sorunuzu tamamladığınızda "
            "bu alan otomatik dolacak.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        return
    rows = [_live_row(event) for event in events]
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config={
            "Input": st.column_config.TextColumn(width="large"),
            "Output": st.column_config.TextColumn(width="large"),
            "Chunk": st.column_config.TextColumn(width="small"),
            "Sınıf": st.column_config.TextColumn(width="small"),
        },
    )
    st.download_button(
        "Test tablosunu CSV indir",
        data=_events_csv(rows),
        file_name="cms_rag_canli_testler.csv",
        mime="text/csv",
    )
    newest = events[0]
    with st.expander("Son testin değerlendirme ayrıntısı", expanded=False):
        st.write(newest.get("chunk_quality_reason", ""))
        st.caption(
            f"Gerçek sınıf dayanağı: {newest.get('ground_truth_basis', 'Bilinmiyor')} · "
            f"Chunk dayanağı: {newest.get('chunk_quality_basis', 'Bilinmiyor')}"
        )
        sources = newest.get("sources", [])
        if sources:
            st.dataframe(sources, hide_index=True, width="stretch")


def _render_live_matrix(summary: dict[str, Any]) -> None:
    """Canlı kayıtların confusion matrix hücrelerini sayı ve açıklamayla gösterir."""

    cells = summary.get("cells", {})
    st.markdown("#### Canlı confusion matrix")
    st.dataframe(
        [
            {
                "Gerçek / Sistem kararı": "Bilgi mevcut",
                "Cevap verdi": cells.get("TP", 0),
                "Güvenli reddetti": cells.get("FN", 0),
            },
            {
                "Gerçek / Sistem kararı": "Bilgi mevcut değil",
                "Cevap verdi": cells.get("FP", 0),
                "Güvenli reddetti": cells.get("TN", 0),
            },
        ],
        hide_index=True,
        width="stretch",
    )
    st.markdown(
        "<div class='matrix-legend'>"
        "<span><b>TP</b> Bilgi var, doğru biçimde cevaplandı</span>"
        "<span><b>TN</b> Bilgi yok, güvenli biçimde reddedildi</span>"
        "<span><b>FP</b> Bilgi yokken cevap üretildi</span>"
        "<span><b>FN</b> Bilgi varken cevaplanamadı</span>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_reference_reports(
    benchmark: dict[str, Any], quality: dict[str, Any], pgvector: dict[str, Any]
) -> None:
    """Önceden doğrulanmış raporları canlı sayaçlara karıştırmadan erişilebilir tutar."""

    st.caption(
        "Aşağıdaki sonuçlar sürümlü kabul testleridir; üstteki canlı sayaçlara eklenmez."
    )
    gold, judges, backends = st.tabs(("Altın set", "Chunk ve cevap hakemi", "FAISS / pgvector"))
    with gold:
        if benchmark:
            _render_gold_summary(benchmark)
        else:
            st.warning("Altın benchmark raporu bulunamadı.")
    with judges:
        _render_judge_summary(quality)
    with backends:
        _render_backend_summary(pgvector)


def _live_row(event: dict[str, Any]) -> dict[str, Any]:
    """Ham canlı olayı okunur tablo sütunlarına dönüştürür."""

    return {
        "Zaman (UTC)": str(event.get("timestamp_utc", ""))[:19],
        "Input": event.get("input", ""),
        "Output": event.get("output", ""),
        "Model": event.get("model", ""),
        "Üretim yolu": event.get("generation_mode", ""),
        "Chunk": "Doğru" if event.get("chunk_correct") else "Yanlış",
        "Sınıf": event.get("confusion_cell", ""),
        "Gerçek veri": "Var" if event.get("actual_data_available") else "Yok",
        "Sistem kararı": "Cevapladı" if event.get("predicted_answerable") else "Reddetti",
        "Değerlendirme dayanağı": event.get("ground_truth_basis", ""),
        "Kaynak": len(event.get("sources", [])),
        "Gecikme (ms)": event.get("latency_ms", 0),
    }


def _events_csv(rows: list[dict[str, Any]]) -> str:
    """Canlı tabloyu Excel uyumlu UTF-8 CSV metnine dönüştürür."""

    stream = StringIO()
    if rows:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return "\ufeff" + stream.getvalue()


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


def _render_audit_summary(summary: dict[str, Any]) -> None:
    """Gizlilik korumalı yerel çalışma olaylarını ve son sorgu metriklerini gösterir."""

    outcomes = summary.get("outcomes", {})
    columns = st.columns(4)
    _metric(columns[0], "Yerel olay", str(summary.get("event_count", 0)))
    _metric(columns[1], "Kaynaklı", str(outcomes.get("grounded", 0)))
    _metric(columns[2], "Güvenli ret", str(outcomes.get("unsupported", 0)))
    _metric(
        columns[3],
        "Ort. uçtan uca",
        f"{float(summary.get('average_latency_ms', 0)):.0f} ms",
    )
    events = summary.get("events", [])
    if not events:
        st.caption("Henüz audit olayı yok. İlk soru tamamlandığında yerel kayıt oluşur.")
        return
    st.markdown("#### Son çalışma olayları")
    rows = [
        {
            "Zaman (UTC)": event.get("timestamp_utc", "")[:19],
            "Sorgu özeti": event.get("query_hash", ""),
            "Sonuç": event.get("outcome", "unknown"),
            "Kapsam": event.get("scope", "unknown"),
            "Mod": event.get("generation_mode", "unknown"),
            "Kaynak": event.get("source_count", 0),
            "Gecikme ms": event.get("latency_ms", 0),
        }
        for event in events[:50]
    ]
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption(
        "Gizlilik ilkesi: audit kaydı ham soru, ham cevap veya belge metni içermez. "
        "Sorgular yalnız geri döndürülemez SHA-256 özetiyle temsil edilir."
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
