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
    """Agentic modda yeni konuşma ve checkpoint'ten geri yükleme kontrollerini çizer."""

    if not st.session_state.get("agentic_mode", False):
        return
    workflow = get_agentic_workflow()
    if st.button("Yeni konuşma", use_container_width=True):
        _activate_conversation(engine, uuid4().hex, [])
        st.session_state.pop("conversation_selector", None)
        st.rerun()

    summaries = workflow.conversation_summaries()
    active_thread = st.session_state.agentic_thread_id
    summary_by_id = {item.thread_id: item for item in summaries}
    options = [active_thread] + [
        item.thread_id for item in summaries if item.thread_id != active_thread
    ]

    def _label(thread_id: str) -> str:
        """Thread kimliğini ham değeri göstermeden kısa konuşma etiketine çevirir."""

        summary = summary_by_id.get(thread_id)
        if summary is None:
            return "Yeni konuşma · henüz mesaj yok"
        suffix = " · onay bekliyor" if summary.pending_approval else ""
        return f"{summary.title} · {summary.turn_count} tur{suffix}"

    selected = st.selectbox(
        "Konuşmalar",
        options,
        format_func=_label,
        key="conversation_selector",
    )
    if selected != active_thread:
        turns = workflow.conversation_history(selected)
        _activate_conversation(engine, selected, turns)
        pending = workflow.pending_interrupt(selected)
        if pending is not None:
            question = str(pending.get("question", "")).strip()
            if question:
                st.session_state.messages.append({"role": "user", "content": question})
                st.session_state[PENDING_AGENTIC_THREAD_KEY] = selected
                handle_track_question(question)
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
                    "AGENTIC · KAYNAKLI YANIT"
                    if turn.hits
                    else "AGENTIC · GÜVENLİ YANIT"
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
    ):
        st.session_state.pop(key, None)
    engine.restore_chat(
        [
            {"question": turn.question, "answer": turn.answer, "scope": turn.scope}
            for turn in turns
        ]
    )
