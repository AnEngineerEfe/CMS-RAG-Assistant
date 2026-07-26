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

    scope = render_sidebar(engine)
    initialize_index(engine)

    documents = engine.store.pdfs()
    chunk_count = len(engine.retriever.chunks) if engine.retriever else 0
    render_header(len(documents), chunk_count)
    render_empty_state(bool(documents), bool(st.session_state.messages))
    render_chat(engine, scope)
