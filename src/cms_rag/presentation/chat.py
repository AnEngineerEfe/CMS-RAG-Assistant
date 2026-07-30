"""Sohbet geçmişini, akışlı yanıtı ve kanıt görünürlüğünü yöneten bileşen."""

from typing import Any

import streamlit as st

from ..application import CMSRAGEngine
from .components import render_message, show_sources, source_payload
from .config import UNSUPPORTED_ANSWER_MARKERS


def initialize_index(engine: CMSRAGEngine) -> None:
    """İlk açılışta yerel belgelerden arama indeksini tembel biçimde kurar."""

    if engine.retriever is not None:
        return
    with st.spinner("Yerel kanıt indeksi hazırlanıyor..."):
        engine.rebuild()


def render_chat(engine: CMSRAGEngine, scope: str) -> None:
    """Geçmişi gösterir ve yeni soruyu akışlı, kaynak kontrollü cevaplar."""

    for message in st.session_state.messages:
        render_message(message)

    question = st.chat_input(
        "CMS / ADVENT hakkında kanıta dayalı soru sorun...",
        disabled=engine.retriever is None,
    )
    if not question:
        return

    user_message: dict[str, Any] = {"role": "user", "content": question}
    st.session_state.messages.append(user_message)
    render_message(user_message)
    answer, sources = _render_answer(engine, question, scope)
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )


def _render_answer(
    engine: CMSRAGEngine,
    question: str,
    scope: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Motor akışını ekrana yazar ve yalnızca desteklenen cevapların kanıtlarını döndürür."""

    with st.chat_message("assistant"):
        answer_label = st.empty()
        answer_label.markdown(
            "<div class='answer-label'>YANIT ÜRETİMİ</div>",
            unsafe_allow_html=True,
        )
        status = st.status(
            "Sorgu bağlamı çözümleniyor ve kanıtlar yeniden sıralanıyor...",
            expanded=False,
        )
        stream, hits = engine.stream_ask(question, scope)
        sources = [source_payload(hit) for hit in hits]
        status.update(
            label=f"{len(sources)} kanıt seçildi · yanıt üretiliyor",
            state="running",
            expanded=False,
        )
        answer = str(
            st.write_stream(stream)
            or "Yanıt üretilemedi; lütfen sorguyu yeniden deneyin."
        )

        # Yetersiz kanıt veya servis hatasında retrieval sonuçlarını kullanıcıya kanıt diye sunmayız.
        if any(marker in answer.lower() for marker in UNSUPPORTED_ANSWER_MARKERS):
            sources = []
        final_status = (
            "Yanıt kaynaklarla birlikte tamamlandı"
            if sources
            else "Bu soru için belge desteği bulunamadı"
        )
        final_label = "KAYNAKLI YANIT" if sources else "GÜVENLİ YANIT"
        answer_label.markdown(
            f"<div class='answer-label'>{final_label}</div>",
            unsafe_allow_html=True,
        )
        status.update(label=final_status, state="complete", expanded=False)
        show_sources(sources)
    return answer, sources
