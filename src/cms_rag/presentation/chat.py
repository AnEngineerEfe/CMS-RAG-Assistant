"""Sohbet geçmişini, akışlı yanıtı ve kanıt görünürlüğünü yöneten bileşen."""

from typing import Any

import streamlit as st

from ..application import CMSRAGEngine
from ..application.agentic import AgentRoute, AgenticResult
from .components import render_message, show_sources, source_payload
from .config import UNSUPPORTED_ANSWER_MARKERS
from .track_chat import (
    PENDING_AGENTIC_THREAD_KEY,
    handle_track_question,
    render_pending_track_action,
)
from .services import get_agentic_workflow


def initialize_index(engine: CMSRAGEngine) -> None:
    """İlk açılışta yerel belgelerden arama indeksini tembel biçimde kurar."""

    if engine.retriever is not None:
        return
    with st.spinner("Yerel kanıt indeksi hazırlanıyor..."):
        engine.rebuild()


def render_chat(engine: CMSRAGEngine, scope: str) -> None:
    """Geçmişi gösterir ve yeni soruyu akışlı, kaynak kontrollü cevaplar."""

    for index, message in enumerate(st.session_state.messages):
        render_message(message, key_prefix=f"history_{index}")

    has_pending_action = render_pending_track_action()

    question = st.chat_input(
        "CMS sorusu sorun veya iz durumunu okuyup değiştirmek için komut verin...",
        # MCP canlı kontrolü RAG indeksinden bağımsızdır; yalnız bekleyen onay yeni
        # bir iletinin aynı anda işlenmesini engeller.
        disabled=has_pending_action,
    )
    if not question:
        return

    user_message: dict[str, Any] = {"role": "user", "content": question}
    st.session_state.messages.append(user_message)
    render_message(user_message, key_prefix=f"user_{len(st.session_state.messages)}")
    if st.session_state.get("agentic_mode", False):
        workflow = get_agentic_workflow()
        prior_turns = workflow.conversation_history(
            st.session_state.agentic_thread_id
        )
        engine.restore_chat(
            [
                {
                    "question": turn.question,
                    "answer": turn.answer,
                    "scope": turn.scope,
                }
                for turn in prior_turns
            ]
        )
        result = workflow.invoke(
            question,
            scope,
            st.session_state.agentic_thread_id,
        )
        if result.route == AgentRoute.TRACK_CONTROL:
            if result.interrupted:
                st.session_state[PENDING_AGENTIC_THREAD_KEY] = (
                    st.session_state.agentic_thread_id
                )
            if handle_track_question(question):
                st.rerun()
                return
            answer, sources = _render_agentic_result(result)
        else:
            answer, sources = _render_agentic_result(result)
    else:
        if handle_track_question(question):
            st.rerun()
            return
        answer, sources = _render_answer(engine, question, scope)
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )


def _render_agentic_result(result: AgenticResult) -> tuple[str, list[dict[str, Any]]]:
    """Checkpoint'li graph sonucunu adım özeti, yanıt ve kanıt kartlarıyla gösterir."""

    sources = [source_payload(hit) for hit in result.hits]
    with st.chat_message("assistant"):
        label = "AGENTIC · KAYNAKLI YANIT" if sources else "AGENTIC · GÜVENLİ YANIT"
        st.markdown(f"<div class='answer-label'>{label}</div>", unsafe_allow_html=True)
        with st.status("Agentic çalışma adımları tamamlandı", expanded=False) as status:
            for event in result.events:
                st.write(f"✓ {event}")
            status.update(state="complete")
        st.caption(
            f"Rota: {result.route.value} · Üretim: {result.generation_mode or 'uygulanamaz'} · "
            f"Doğrulama: {'geçti' if result.verification_passed else 'uygulanamaz'} · "
            f"Onarım: {result.repair_count} · {result.duration_ms:.0f} ms"
        )
        answer = str(st.write_stream(_stream_words(result.answer)) or result.answer)
        show_sources(sources, key_prefix=f"agentic_{len(st.session_state.messages)}")
    return answer, sources


def _stream_words(answer: str):
    """Tamamlanmış graph yanıtını mevcut yazım animasyonuyla uyumlu parçalara böler."""

    for word in answer.split(" "):
        yield f"{word} "


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
        show_sources(sources, key_prefix=f"live_{len(st.session_state.messages)}")
    return answer, sources
