"""Tekrar kullanılan mesaj, kanıt ve gösterge bileşenleri."""

from html import escape
from typing import Any

import streamlit as st

from ..domain.models import SearchHit


def source_payload(hit: SearchHit) -> dict[str, Any]:
    """Arama sonucunu arayüzde güvenle saklanabilecek sade bir sözlüğe dönüştürür."""

    # Fazla boşlukları birleştirip uzun alıntıları ekran düzenini koruyacak şekilde kısaltırız.
    excerpt = " ".join(hit.chunk.text.split())
    return {
        "document": hit.chunk.document,
        "page": hit.chunk.page,
        "excerpt": excerpt[:360] + ("..." if len(excerpt) > 360 else ""),
        "collection": hit.chunk.collection,
        "authority": hit.chunk.authority,
        "source_url": hit.chunk.source_url,
    }


def show_sources(sources: list[dict[str, Any]]) -> None:
    """Bir cevabın kanıtlarını XSS'e karşı kaçışlayarak açılır kartlarda gösterir."""

    if not sources:
        return

    with st.expander(f"Kanıt paketi · {len(sources)} kaynak", expanded=False):
        for source in sources:
            url = str(source.get("source_url", ""))
            link = (
                f" · <a href='{escape(url)}' target='_blank' rel='noopener noreferrer'>"
                "Kaynağı aç</a>"
                if url
                else ""
            )
            st.markdown(
                f"<div class='evidence-card'><div class='source-meta'>"
                f"{escape(str(source['document']))} · Sayfa {source['page']} · "
                f"{escape(str(source.get('authority', 'unknown')))}{link}</div>"
                f"<div class='source-quote'>"
                f"{escape(str(source.get('excerpt', 'Sayfa kanıt olarak kullanıldı.')))}"
                f"</div></div>",
                unsafe_allow_html=True,
            )


def render_message(message: dict[str, Any]) -> None:
    """Oturum geçmişindeki kullanıcı veya asistan mesajını kaynaklarıyla çizer."""

    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            label = (
                "KAYNAKLI YANIT"
                if message.get("sources")
                else "GÜVENLİ YANIT"
            )
            st.markdown(
                f"<div class='answer-label'>{label}</div>",
                unsafe_allow_html=True,
            )
        st.markdown(message["content"])
        if message["role"] == "assistant":
            show_sources(message.get("sources", []))


def render_header(document_count: int, chunk_count: int) -> None:
    """Başlık alanını ve canlı belge/kanıt sayaçlarını yan yana gösterir."""

    left, middle, right = st.columns([2.4, 1, 1])
    with left:
        st.markdown(
            "<div class='hero'>"
            "<div class='eyebrow'>CMS-RAG / EVIDENCE-FIRST ASSISTANT</div>"
            "<h1>Komuta Bilgi Keşfi</h1>"
            "<p>Belge kanıtını, çoklu aramayı ve yerel üretimi "
            "tek operasyonda birleştirir.</p></div>",
            unsafe_allow_html=True,
        )
    with middle:
        _render_metric("Yüklü belge", document_count)
    with right:
        _render_metric("Kanıt parçası", chunk_count)


def render_empty_state(has_documents: bool, has_messages: bool) -> None:
    """Yeni oturuma uygun yönlendirmeyi belge durumuna göre seçer."""

    if has_messages:
        return
    if not has_documents:
        st.info(
            "Seçilmiş resmî ve açık kaynaklar hazır. Kendi resmî PDF'inizi eklemek "
            "için sol paneldeki yükleme alanını kullanabilirsiniz."
        )
        return
    st.caption(
        "Önerilen başlangıç soruları: “ADVENT nedir?”, "
        "“Savaş gemisinde ADVENT ne yapar?”, "
        "“Taktik veri bağlantısı nedir?”"
    )


def _render_metric(label: str, value: int) -> None:
    """Tek bir gösterge kartının ortak HTML yapısını üretir."""

    st.markdown(
        "<div class='metric-card'>"
        f"<div class='metric-label'>{escape(label)}</div>"
        f"<div class='metric-value'>{value}</div></div>",
        unsafe_allow_html=True,
    )
