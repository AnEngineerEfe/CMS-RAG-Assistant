from pathlib import Path

import streamlit as st

from src.cms_rag.engine import CMSRAGEngine


ROOT = Path(__file__).parent
st.set_page_config(page_title="CMS-RAG Assistant", layout="wide")
st.title("CMS-RAG Assistant")
st.caption("Yerel, kaynak gösteren CMS doküman asistanı")


@st.cache_resource
def engine() -> CMSRAGEngine:
    return CMSRAGEngine(ROOT / "data")


if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Bilgi tabanı")
    uploaded = st.file_uploader("Resmî PDF yükle", type=["pdf"], accept_multiple_files=True)
    if uploaded and st.button("Yükle ve indeksle", type="primary"):
        result = engine().store.save_uploads(uploaded)
        if result.added:
            st.success(f"{len(result.added)} yeni dosya eklendi. {engine().rebuild()} parça indekslendi.")
        if result.duplicates:
            st.info(f"{len(result.duplicates)} dosya zaten bilgi tabanında; tekrar eklenmedi.")
    if st.button("Bilgi tabanını yeniden indeksle"):
        st.success(f"{engine().rebuild()} parça indekslendi.")
    if st.button("Sohbeti temizle"):
        engine().clear_chat()
        st.session_state.messages = []
        st.rerun()
    st.divider()
    files = engine().store.pdfs()
    st.caption(f"Model: {engine().model}")
    st.caption(f"Yüklü PDF: {len(files)}")
    for path in files:
        st.caption(f"• {path.name}")

if engine().retriever is None and engine().store.pdfs():
    with st.spinner("Yerel bilgi tabanı hazırlanıyor..."):
        engine().rebuild()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("CMS / ADVENT hakkında soru sorun...")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Kaynaklar aranıyor..."):
            answer, hits = engine().ask(question)
        st.markdown(answer)
        if hits:
            with st.expander("Kullanılan kaynaklar"):
                for hit in hits:
                    st.markdown(f"- **{hit.chunk.document}** — sayfa {hit.chunk.page}")
    st.session_state.messages.append({"role": "assistant", "content": answer})
