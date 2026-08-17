"""Hazır bilgi tabanı durumu ve isteğe bağlı ek belge yönetimi kenar paneli."""

import streamlit as st

from ..application import CMSRAGEngine
from .config import SOURCE_SCOPE_LABELS, SOURCE_SCOPES


def render_sidebar(engine: CMSRAGEngine) -> tuple[str, str]:
    """Kenar panelini çizer; görünüm ile seçili kaynak kapsamını döndürür."""

    with st.sidebar:
        st.markdown(
            "<div class='sidebar-brand'><strong>◆ CMS Knowledge Ops</strong>"
            "<span>Yerel · kaynak kontrollü · çevrimdışı</span></div>",
            unsafe_allow_html=True,
        )
        st.divider()
        page = st.radio(
            "Çalışma alanı",
            ("assistant", "evaluation"),
            format_func={
                "assistant": "Soru-cevap asistanı",
                "evaluation": "Değerlendirme merkezi",
            }.__getitem__,
        )
        scope = st.selectbox(
            "Sorgu kapsamı",
            SOURCE_SCOPES,
            format_func=SOURCE_SCOPE_LABELS.__getitem__,
        )
        with st.expander("İsteğe bağlı ek belge"):
            st.caption(
                "Çekirdek bilgi tabanı önceden hazırdır. Yalnız kamuya açık "
                "veya kullanma yetkiniz olan ek PDF'leri buradan ekleyin."
            )
            _render_upload(engine)
        _render_session_actions(engine)
        _render_status(engine, scope)
        _render_document_management(engine)
    return page, scope


def _render_upload(engine: CMSRAGEngine) -> None:
    """Ek PDF'leri doğrular; yeni, yinelenen ve reddedilenleri ayrı bildirir."""

    uploaded = st.file_uploader(
        "Ek PDF yükle",
        type=["pdf"],
        accept_multiple_files=True,
    )
    if not uploaded or not st.button(
        "Ek belgeyi doğrula ve indeksle",
        type="primary",
        use_container_width=True,
    ):
        return

    result = engine.store.save_uploads(uploaded)
    if result.added:
        with st.spinner("Yalnız yeni belge parçalanıyor ve yerel indekse ekleniyor..."):
            chunk_count = engine.rebuild()
        st.success(
            f"{len(result.added)} ek belge doğrulandı · "
            f"{chunk_count} kanıt parçası hazır"
        )
    if result.duplicates:
        st.info(
            f"{len(result.duplicates)} belge zaten kayıtlı; "
            "yinelenen kopya eklenmedi."
        )
    if result.rejected:
        st.error(
            f"{len(result.rejected)} dosya geçerli PDF imzası taşımıyor "
            "veya boyut sınırını aşıyor; kabul edilmedi."
        )


def _render_session_actions(engine: CMSRAGEngine) -> None:
    """Hazır indeks yükleme ve sohbet temizleme komutlarını işler."""

    if st.button("Hazır indeksi yeniden yükle", use_container_width=True):
        with st.spinner("Önceden hazırlanmış yerel indeks yükleniyor..."):
            st.success(f"{engine.rebuild()} kanıt parçası hazır")
    if st.button("Oturumu temizle", use_container_width=True):
        engine.clear_chat()
        st.session_state.messages = []
        st.session_state.pop("pending_track_action", None)
        st.session_state.pop("pending_track_suggestion", None)
        st.rerun()


def _render_status(engine: CMSRAGEngine, scope: str) -> None:
    """Hazır kaynak, snapshot, model ve çalışma-anı ağ durumunu görünür kılar."""

    st.divider()
    st.caption("ÇALIŞMA DURUMU")
    st.caption(f"Model · {engine.model}")
    st.caption(f"Hazır kaynak · {engine.prepared_document_count()}")
    st.caption(f"Toplam aktif belge · {engine.active_document_count()}")
    st.caption(
        f"Snapshot · {'Hazır' if engine.snapshot_loaded else 'Yeniden oluşturuldu'}"
    )
    st.caption("Çalışma anında web erişimi · Kapalı")
    st.caption("MCP iz kontrolü · İstek üzerine yerel başlatılır")
    st.caption(f"Koleksiyon · {scope}")
    st.caption("Arama · Semantic + BM25 + Reranking")
    for record in engine.supplemental_records():
        st.caption(f"Ek belge · {record['display_name']}")


def _render_document_management(engine: CMSRAGEngine) -> None:
    """Yalnız sonradan eklenen belgeleri listeler; çekirdek kaynakları korur."""

    with st.expander("Ek belge yönetimi"):
        records = engine.supplemental_records()
        if not records:
            st.caption(
                "Sonradan eklenmiş PDF yok. Hazır çekirdek kaynaklar korunur."
            )
        for record in records:
            st.caption(
                f"{record['display_name']} · "
                f"{record['size_bytes'] / 1024 / 1024:.1f} MB"
            )
            if st.button(
                "Ek belgeyi kaldır",
                key=f"delete_{record['sha256']}",
                use_container_width=True,
            ) and engine.store.delete(record["sha256"]):
                engine.rebuild()
                st.session_state.messages = []
                st.rerun()
