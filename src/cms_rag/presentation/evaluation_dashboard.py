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
    "lineage": (
        PROJECT_ROOT
        / "evaluation"
        / "results"
        / "lineage-latest"
        / "lineage_evaluation_report.json"
    ),
    "lineage_round2": (
        PROJECT_ROOT
        / "evaluation"
        / "results"
        / "lineage-round2"
        / "lineage_evaluation_report.json"
    ),
    "pgvector_lineage": (
        PROJECT_ROOT
        / "evaluation"
        / "results"
        / "pgvector-lineage-latest"
        / "lineage_evaluation_report.json"
    ),
    "pgvector_lineage_round2": (
        PROJECT_ROOT
        / "evaluation"
        / "results"
        / "pgvector-lineage-round2"
        / "lineage_evaluation_report.json"
    ),
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
    lineage = reports["lineage"]
    lineage_round2 = reports["lineage_round2"]
    pgvector_lineage = reports["pgvector_lineage"]
    pgvector_lineage_round2 = reports["pgvector_lineage_round2"]
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

    lineage_tab, tests, matrix, references, operations = st.tabs(
        (
            "80 backend koşusu · FAISS + pgvector",
            "Canlı test tablosu",
            "Canlı TP · TN · FP · FN",
            "Referans raporlar",
            "İşletim / audit",
        )
    )
    with lineage_tab:
        _render_lineage_workspace(
            lineage,
            lineage_round2,
            pgvector_lineage,
            pgvector_lineage_round2,
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
    _render_confusion_grid(
        {
            "true_positive": cells.get("TP", 0),
            "false_negative": cells.get("FN", 0),
            "false_positive": cells.get("FP", 0),
            "true_negative": cells.get("TN", 0),
        },
        title="Canlı confusion matrix",
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


def _render_lineage_workspace(
    first_report: dict[str, Any],
    second_report: dict[str, Any],
    pgvector_first_report: dict[str, Any],
    pgvector_second_report: dict[str, Any],
) -> None:
    """Aynı iki 20-vaka serisini FAISS ve pgvector sonuçlarıyla gösterir."""

    faiss_tab, pgvector_tab = st.tabs(
        ("FAISS · 40 vaka", "pgvector · 40 vaka")
    )
    with faiss_tab:
        _render_backend_lineage_pair(
            first_report,
            second_report,
            backend_label="FAISS",
        )
    with pgvector_tab:
        _render_backend_lineage_pair(
            pgvector_first_report,
            pgvector_second_report,
            backend_label="pgvector",
        )


def _render_backend_lineage_pair(
    first_report: dict[str, Any],
    second_report: dict[str, Any],
    *,
    backend_label: str,
) -> None:
    """Tek backend'e ait iki bağımsız serinin matrislerini ve tablolarını çizer."""

    if not second_report:
        _render_lineage_evaluation(
            first_report,
            series_label=f"{backend_label} · Seri 1 · L01–L20",
        )
        st.info(
            f"{backend_label} ikinci 20-vaka serisi henüz çalıştırılmadı."
        )
        return
    st.markdown(
        f"#### {backend_label} · iki bağımsız serinin confusion matrix karşılaştırması"
    )
    matrices = st.columns(2)
    with matrices[0]:
        _render_confusion_grid(
            first_report.get("confusion_matrix", {}),
            title=f"{backend_label} · Seri 1 · L01–L20",
        )
    with matrices[1]:
        _render_confusion_grid(
            second_report.get("confusion_matrix", {}),
            title=f"{backend_label} · Seri 2 · N01–N20",
        )
    first_tab, second_tab = st.tabs(
        (f"{backend_label} · Seri 1 tablosu", f"{backend_label} · Seri 2 tablosu")
    )
    with first_tab:
        _render_lineage_evaluation(
            first_report,
            series_label=f"{backend_label} · Seri 1 · L01–L20",
            show_matrix=False,
        )
    with second_tab:
        _render_lineage_evaluation(
            second_report,
            series_label=f"{backend_label} · Seri 2 · N01–N20",
            show_matrix=False,
        )


def _render_lineage_evaluation(
    report: dict[str, Any],
    *,
    series_label: str,
    show_matrix: bool = True,
) -> None:
    """20 vakalık bağımsız soru–RAG–chunk hakemi deneyini açık adlarla gösterir."""

    if not report:
        st.warning(
            "20 vakalık bağımsız deney henüz çalıştırılmadı. "
            "`python -m scripts.run_chunk_lineage_evaluation` komutunu çalıştırın."
        )
        return
    method = report.get("method", {})
    matrix = report.get("confusion_matrix", {})
    lineage = report.get("lineage", {})
    st.markdown(f"#### {series_label} · model görevleri ve bağımsızlık sınırı")
    roles = st.columns(3)
    _metric(roles[0], "Soruyu üreten büyük model", str(method.get("question_generator_model", "—")))
    _metric(roles[1], "RAG cevabını veren küçük model", str(method.get("rag_answer_model", "—")))
    _metric(roles[2], "Chunk'ı seçen büyük hakem", str(method.get("chunk_origin_judge_model", "—")))
    st.caption(
        "Sorular Codex büyük model tarafından yalnız başlangıç chunkı görülerek geliştirme "
        "zamanında hazırlanmış ve sürümlenmiştir. Küçük model her vakayı yalnız yerel RAG "
        "ile cevaplar; 7B hakem ayrı ve durumsuz çağrıda retrieval adaylarından cevabı "
        "destekleyen chunkları seçer."
    )
    if show_matrix:
        _render_confusion_grid(matrix, title=f"{series_label} confusion matrix sonucu")
    metrics = st.columns(4)
    _metric(metrics[0], "Accuracy", _percent(matrix.get("accuracy")))
    _metric(metrics[1], "Precision", _percent(matrix.get("precision")))
    _metric(metrics[2], "Recall", _percent(matrix.get("recall")))
    _metric(
        metrics[3],
        "Kaynak chunk eşleşmesi",
        f"{lineage.get('origin_chunk_matches', 0)}/{lineage.get('evaluated_positive_cases', 0)}",
    )
    st.markdown(f"#### {series_label} · vaka bazında izlenebilir değerlendirme tablosu")
    rows = [_lineage_row(case) for case in report.get("cases", [])]
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config={
            "Üretilen soru / input": st.column_config.TextColumn(width="large"),
            "RAG cevabı / output": st.column_config.TextColumn(width="large"),
            "Başlangıç chunk": st.column_config.TextColumn(width="medium"),
            "Hakemin seçtiği chunklar": st.column_config.TextColumn(width="medium"),
        },
    )


def _render_confusion_grid(matrix: dict[str, Any], *, title: str) -> None:
    """Gerçek ve tahmin eksenleri sabit, sunumluk 2×2 confusion matrix çizer."""

    st.markdown(f"#### {title}")
    st.markdown(
        "<div class='confusion-wrap'>"
        "<div class='confusion-predicted'>TAHMİN EDİLEN</div>"
        "<div class='confusion-col positive'>Pozitif · cevap verdi</div>"
        "<div class='confusion-col negative'>Negatif · güvenli ret</div>"
        "<div class='confusion-actual'>GERÇEK</div>"
        "<div class='confusion-row actual-positive'>Pozitif<br><small>bilgi mevcut</small></div>"
        f"<div class='confusion-cell correct'><b>TP</b><strong>{int(matrix.get('true_positive', 0))}</strong>"
        "<span>Doğru cevap</span></div>"
        f"<div class='confusion-cell error'><b>FN</b><strong>{int(matrix.get('false_negative', 0))}</strong>"
        "<span>Kaçırılan bilgi</span></div>"
        "<div class='confusion-row actual-negative'>Negatif<br><small>bilgi mevcut değil</small></div>"
        f"<div class='confusion-cell error'><b>FP</b><strong>{int(matrix.get('false_positive', 0))}</strong>"
        "<span>Kaynak dışı cevap</span></div>"
        f"<div class='confusion-cell correct'><b>TN</b><strong>{int(matrix.get('true_negative', 0))}</strong>"
        "<span>Doğru güvenli ret</span></div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _lineage_row(case: dict[str, Any]) -> dict[str, Any]:
    """Tek lineage vakasını kafa karıştırmayan Türkçe tablo alanlarına dönüştürür."""

    return {
        "Vaka": case.get("case_id", ""),
        "Vektör backend'i": case.get("retrieval_backend", "faiss"),
        "Tür": case.get("case_type", ""),
        "Konu": case.get("topic", ""),
        "Üretilen soru / input": case.get("question", ""),
        "RAG cevabı / output": case.get("answer", ""),
        "Soru üreten model": case.get("question_generator_model", ""),
        "RAG modeli": case.get("rag_model", ""),
        "Chunk hakemi": case.get("chunk_judge_model", ""),
        "Başlangıç chunk": case.get("source_chunk_id", "—") or "—",
        "RAG'ın bulduğu chunklar": " · ".join(case.get("retrieved_chunk_ids", [])) or "—",
        "Hakemin seçtiği chunklar": " · ".join(case.get("judge_selected_chunk_ids", [])) or "—",
        "Aynı başlangıç chunkı mı?": "Evet" if case.get("origin_chunk_match") else "Hayır / uygulanamaz",
        "Gerçekte bilgi": "Var" if case.get("actual_data_available") else "Yok",
        "Sistem kararı": "Cevap verdi" if case.get("predicted_answerable") else "Güvenli ret",
        "Matris sonucu": case.get("confusion_cell", ""),
        "Beklenen terim kapsaması": _percent(case.get("answer_term_coverage")),
        "Hakem cevabı destekliyor mu?": "Evet" if case.get("answer_supported_by_judge") else "Hayır / uygulanamaz",
        "RAG süresi (ms)": case.get("rag_latency_ms", 0),
        "Hakem süresi (ms)": case.get("judge_latency_ms", 0),
        "Katı başarı": "Geçti" if case.get("strict_pass") else "Geçmedi / uygulanamaz",
        "Durum": case.get("status", ""),
    }


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
