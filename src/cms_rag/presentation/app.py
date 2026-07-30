"""Sunum katmanındaki bileşenleri doğru sırayla çalıştıran orkestratör."""

import streamlit as st

from .chat import initialize_index, render_chat
from .components import render_empty_state, render_header
from .services import get_engine
from .sidebar import render_sidebar
from .theme import apply_theme


def run() -> None:
    """CMS-RAG Streamlit ekranını tek ve test edilebilir bir akışta oluşturur."""

    apply_theme()
    engine = get_engine()
    st.session_state.setdefault("messages", [])

    initialize_index(engine)
    scope = render_sidebar(engine)

    chunk_count = len(engine.retriever.chunks) if engine.retriever else 0
    document_count = engine.active_document_count()
    render_header(document_count, chunk_count)
    render_empty_state(bool(engine.retriever), bool(st.session_state.messages))
    render_chat(engine, scope)
