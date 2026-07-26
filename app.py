from pathlib import Path

import streamlit as st

from src.cms_rag.engine import CMSRAGEngine


ROOT = Path(__file__).parent
st.set_page_config(page_title="CMS-RAG Assistant", layout="wide")
st.title("CMS-RAG Assistant")
st.caption("Yerel, kaynak g\u00f6steren CMS dok\u00fcman asistan\u0131")


@st.cache_resource
def engine() -> CMSRAGEngine:
    return CMSRAGEngine(ROOT / "data")


def show_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander("Kullan\u0131lan kaynaklar"):
        for source in sources:
            st.markdown(f"- **{source['document']}** \u2014 sayfa {source['page']}")


if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Bilgi taban\u0131")
    uploaded = st.file_uploader("Resm\u00ee PDF y\u00fckle", type=["pdf"], accept_multiple_files=True)
    if uploaded and st.button("Y\u00fckle ve indeksle", type="primary"):
        result = engine().store.save_uploads(uploaded)
        if result.added:
            st.success(f"{len(result.added)} yeni dosya eklendi. {engine().rebuild()} par\u00e7a indekslendi.")
        if result.duplicates:
            st.info(f"{len(result.duplicates)} dosya zaten bilgi taban\u0131nda; tekrar eklenmedi.")
    if st.button("Bilgi taban\u0131n\u0131 yeniden indeksle"):
        st.success(f"{engine().rebuild()} par\u00e7a indekslendi.")
    if st.button("Sohbeti temizle"):
        engine().clear_chat()
        st.session_state.messages = []
        st.rerun()
    st.divider()
    files = engine().store.pdfs()
    st.caption(f"Model: {engine().model}")
    st.caption(f"Y\u00fckl\u00fc PDF: {len(files)}")
    for path in files:
        st.caption(f"\u2022 {engine().store.display_name(path)}")

if engine().retriever is None and engine().store.pdfs():
    with st.spinner("Yerel bilgi taban\u0131 haz\u0131rlan\u0131yor..."):
        engine().rebuild()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            show_sources(message.get("sources", []))

question = st.chat_input("CMS / ADVENT hakk\u0131nda soru sorun...")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Kaynaklar aran\u0131yor..."):
            answer, hits = engine().ask(question)
        sources = [{"document": hit.chunk.document, "page": hit.chunk.page} for hit in hits]
        st.markdown(answer)
        show_sources(sources)
    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
