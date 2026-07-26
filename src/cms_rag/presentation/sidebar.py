"""Kaynak kapsamı, PDF yükleme ve belge yönetimi kenar paneli."""

import streamlit as st

from ..application import CMSRAGEngine
from .config import SOURCE_SCOPE_LABELS, SOURCE_SCOPES


def render_sidebar(engine: CMSRAGEngine) -> str:
    """Kenar panelini çizer, kullanıcı işlemlerini uygular ve seçili kapsamı döndürür."""

    with st.sidebar:
        st.markdown("### ◆ Knowledge Operations")
        st.caption("Yerel, kaynak kontrollü CMS bilgi katmanı")
        st.divider()
        scope = st.selectbox(
            "Sorgu kapsamı",
            SOURCE_SCOPES,
            format_func=SOURCE_SCOPE_LABELS.__getitem__,
        )
        _render_upload(engine)
        _render_session_actions(engine)
        _render_status(engine, scope)
        _render_document_management(engine)
    return scope


def _render_upload(engine: CMSRAGEngine) -> None:
    """PDF'leri doğrular; yeni, yinelenen ve reddedilen dosyaları ayrı bildirir."""

    uploaded = st.file_uploader(
        "Resmî PDF yükle",
        type=["pdf"],
        accept_multiple_files=True,
    )
    if not uploaded or not st.button(
        "Belgeyi doğrula ve indeksle",
        type="primary",
        use_container_width=True,
    ):
        return

    result = engine.store.save_uploads(uploaded)
    if result.added:
        with st.spinner("Sayfalar ayrıştırılıyor ve hibrit indeks kuruluyor..."):
            chunk_count = engine.rebuild()
        st.success(
            f"{len(result.added)} belge doğrulandı · "
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
    """İndeks yenileme ve sohbet temizleme komutlarını merkezi olarak işler."""

    if st.button("İndeksi yenile", use_container_width=True):
        with st.spinner("Yerel indeks yenileniyor..."):
            st.success(f"{engine.rebuild()} kanıt parçası hazır")
    if st.button("Oturumu temizle", use_container_width=True):
        engine.clear_chat()
        st.session_state.messages = []
        st.rerun()


def _render_status(engine: CMSRAGEngine, scope: str) -> None:
    """Aktif model, belge, koleksiyon ve arama yöntemini görünür kılar."""

    st.divider()
    documents = engine.store.pdfs()
    st.caption("ÇALIŞMA DURUMU")
    st.caption(f"Model · {engine.model}")
    st.caption(f"Belge · {len(documents)}")
    st.caption(f"Koleksiyon · {scope}")
    st.caption("Arama · Semantic + BM25 + Reranking")
    for path in documents:
        st.caption(f"• {engine.store.display_name(path)}")


def _render_document_management(engine: CMSRAGEngine) -> None:
    """Manifest kayıtlarını listeler ve seçilen belgeyi güvenli API üzerinden kaldırır."""

    with st.expander("Belge yönetimi"):
        records = engine.store.records()
        if not records:
            st.caption("Yüklenmiş yerel PDF yok.")
        for record in records:
            st.caption(
                f"{record['display_name']} · "
                f"{record['size_bytes'] / 1024 / 1024:.1f} MB"
            )
            if st.button(
                "Belgeyi kaldır",
                key=f"delete_{record['sha256']}",
                use_container_width=True,
            ) and engine.store.delete(record["sha256"]):
                engine.rebuild()
                st.session_state.messages = []
                st.rerun()
