"""Kalıcı LangGraph thread'lerini Streamlit sohbetlerine bağlayan sunum yardımcıları."""

from __future__ import annotations

from uuid import uuid4

import streamlit as st

from ..application import CMSRAGEngine
from ..application.agentic import ConversationTurn
from .components import source_payload
from .services import get_agentic_workflow
from .track_chat import PENDING_AGENTIC_THREAD_KEY, handle_track_question


def render_conversation_controls(engine: CMSRAGEngine) -> None:
    """Yeni sohbeti ve kullanıcı isteğiyle açılan kalıcı geçmiş listesini kenar panelde çizer."""

    if not st.session_state.get("agentic_mode", False):
        return
    workflow = get_agentic_workflow()
    if st.button("＋ Yeni sohbet", use_container_width=True):
        _activate_conversation(engine, uuid4().hex, [])
        st.session_state.show_conversation_history = False
        st.rerun()

    summaries = workflow.conversation_summaries()
    history_label = f"☰ Sohbet geçmişi ({len(summaries)})"
    if st.button(history_label, use_container_width=True):
        st.session_state.show_conversation_history = not st.session_state.get(
            "show_conversation_history", False
        )
        st.rerun()

    if not st.session_state.get("show_conversation_history", False):
        return
    st.caption("SOHBET GEÇMİŞİ")
    if not summaries:
        st.caption("Henüz kaydedilmiş bir sohbet yok.")
        return
    for summary in summaries:
        suffix = " · onay bekliyor" if summary.pending_approval else ""
        label = f"{summary.title} · {summary.turn_count} tur{suffix}"
        if st.button(
            label,
            key=f"open_conversation_{summary.thread_id}",
            use_container_width=True,
        ):
            turns = workflow.conversation_history(summary.thread_id)
            _activate_conversation(engine, summary.thread_id, turns)
            _restore_pending_approval(workflow, summary.thread_id)
            st.session_state.show_conversation_history = False
            st.rerun()


def _activate_conversation(
    engine: CMSRAGEngine,
    thread_id: str,
    turns: list[ConversationTurn],
) -> None:
    """Seçilen thread'i mesajları, kanıtları ve kısa RAG belleğiyle etkinleştirir."""

    messages: list[dict] = []
    for turn in turns:
        messages.append({"role": "user", "content": turn.question})
        messages.append(
            {
                "role": "assistant",
                "content": turn.answer,
                "sources": [source_payload(hit) for hit in turn.hits],
                "label": (
                    "MCP · KAYITLI İŞLEM"
                    if turn.generation_mode.startswith("track_")
                    else "AGENTIC · KAYNAKLI YANIT"
                    if turn.hits
                    else "AGENTIC · GÜVENLİ YANIT"
                ),
                "channel": (
                    "mcp" if turn.generation_mode.startswith("track_") else "agentic"
                ),
            }
        )
    st.session_state.agentic_thread_id = thread_id
    st.session_state.messages = messages
    for key in (
        "pending_track_action",
        "pending_track_suggestion",
        "pending_track_correction",
        "pending_track_agentic_thread",
        "pending_track_agentic_completion",
        "processing_question",
    ):
        st.session_state.pop(key, None)
    engine.restore_chat(
        [
            {"question": turn.question, "answer": turn.answer, "scope": turn.scope}
            for turn in turns
        ]
    )


def _restore_pending_approval(workflow, thread_id: str) -> None:
    """Checkpoint'teki yarım MCP yazmasını aynı konuşmada yeniden onaya hazırlar."""

    pending = workflow.pending_interrupt(thread_id)
    if pending is None:
        return
    question = str(pending.get("question", "")).strip()
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        st.session_state[PENDING_AGENTIC_THREAD_KEY] = thread_id
        handle_track_question(question)
