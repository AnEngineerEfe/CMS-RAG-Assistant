import streamlit as st

from src.config import RAW_DATA_PATH
from src.document.document_manager import CMSDocumentManager
from src.services.knowledge_base import CMSKnowledgeBase
from src.upload.upload_manager import CMSUploadManager


st.set_page_config(page_title="CMS-RAG Assistant", layout="wide")
st.title("CMS-RAG Assistant")
st.caption("Kaynak g\u00f6steren, yerel ve koleksiyon ayr\u0131ml\u0131 CMS bilgi asistan\u0131")


@st.cache_resource
def knowledge_base() -> CMSKnowledgeBase:
    return CMSKnowledgeBase(RAW_DATA_PATH)


def rebuild() -> int:
    return knowledge_base().build()


if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Bilgi taban\u0131")
    scope = st.selectbox(
        "Sorgu kapsam\u0131",
        ["all", "havelsan", "open_source"],
        format_func=lambda item: {
            "all": "Birle\u015fik (kaynaklar korunur)",
            "havelsan": "Yaln\u0131zca HAVELSAN resm\u00ee kaynaklar\u0131",
            "open_source": "Yaln\u0131zca a\u00e7\u0131k / kamu kaynaklar\u0131",
        }[item],
    )
    uploaded_files = st.file_uploader("Resm\u00ee PDF y\u00fckle", type=["pdf"], accept_multiple_files=True)
    if uploaded_files and st.button("Y\u00fckle ve indeksle", type="primary"):
        added, duplicates = CMSUploadManager().save_files(uploaded_files)
        if added:
            st.success(f"{len(added)} yeni dosya kaydedildi; {rebuild()} par\u00e7a indekslendi.")
        if duplicates:
            st.warning(f"{len(duplicates)} dosya zaten kay\u0131tl\u0131yd\u0131; tekrar eklenmedi.")

    if st.button("Yerel kaynaklardan yeniden indeksle"):
        st.success(f"{rebuild()} par\u00e7a indekslendi.")
    if st.button("Sohbeti temizle"):
        st.session_state.messages = []
        knowledge_base().clear_memory()
        st.rerun()

    st.divider()
    st.caption(f"Yerel \u00fcretim modeli: {knowledge_base().llm.model_name}")
    st.caption("HAVELSAN resm\u00ee i\u00e7erik ve a\u00e7\u0131k/kamu referanslar\u0131 ayr\u0131 FAISS indekslerinde tutulur.")
    local_documents = CMSDocumentManager().get_documents()
    st.caption(f"Yerel PDF say\u0131s\u0131: {len(local_documents)}")
    for document in local_documents:
        st.caption(f"\u2022 {document['name']} ({document['size']} MB) \u2014 {document['collection']}")

if not knowledge_base().collections and any(path.is_file() for path in RAW_DATA_PATH.rglob("*")):
    with st.spinner("Yerel kaynaklar indeksleniyor..."):
        rebuild()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("ADVENT / CMS hakk\u0131nda soru sorun...")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Kaynaklar aran\u0131yor ve yeniden s\u0131ralan\u0131yor..."):
            answer, sources = knowledge_base().ask(question, scope)
        st.markdown(answer)
        if sources:
            with st.expander("Kullan\u0131lan kaynaklar"):
                for score, document in sources:
                    st.markdown(
                        f"- **{document.metadata.get('document', 'Bilinmeyen')}** "
                        f"\u2014 sayfa {document.metadata.get('page', 0) + 1} "
                        f"\u2014 {document.metadata.get('authority', 'bilinmiyor')} "
                        f"\u2014 alaka: {float(score):.0%}"
                    )
                    if document.metadata.get("source_url"):
                        st.caption(document.metadata["source_url"])
    st.session_state.messages.append({"role": "assistant", "content": answer})
