import streamlit as st

from src.config import RAW_DATA_PATH
from src.document.document_manager import CMSDocumentManager
from src.services.knowledge_base import CMSKnowledgeBase
from src.upload.upload_manager import CMSUploadManager


st.set_page_config(page_title="CMS-RAG Assistant", layout="wide")
st.title("CMS-RAG Assistant")
st.caption("Kaynak gösteren, yerel ve koleksiyon ayrımlı CMS bilgi asistanı")


@st.cache_resource
def knowledge_base() -> CMSKnowledgeBase:
    return CMSKnowledgeBase(RAW_DATA_PATH)


def rebuild() -> int:
    return knowledge_base().build()


if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Bilgi tabanı")
    scope = st.selectbox(
        "Sorgu kapsamı",
        ["all", "havelsan", "open_source"],
        format_func=lambda item: {
            "all": "Birleşik (kaynaklar korunur)",
            "havelsan": "Yalnızca HAVELSAN resmî kaynakları",
            "open_source": "Yalnızca açık / kamu kaynakları",
        }[item],
    )
    uploaded_files = st.file_uploader("Resmî PDF yükle", type=["pdf"], accept_multiple_files=True)
    if uploaded_files and st.button("Yükle ve indeksle", type="primary"):
        added, duplicates = CMSUploadManager().save_files(uploaded_files)
        if added:
            st.success(f"{len(added)} yeni dosya kaydedildi; {rebuild()} parça indekslendi.")
        if duplicates:
            st.warning(f"{len(duplicates)} dosya zaten kayıtlıydı; tekrar eklenmedi.")

    if st.button("Yerel kaynaklardan yeniden indeksle"):
        st.success(f"{rebuild()} parça indekslendi.")
    if st.button("Sohbeti temizle"):
        st.session_state.messages = []
        knowledge_base().clear_memory()
        st.rerun()

    st.divider()
    st.caption("HAVELSAN resmî içerik ve açık/kamu referansları ayrı FAISS indekslerinde tutulur.")
    st.caption(f"Yerel PDF sayısı: {len(CMSDocumentManager().get_documents())}")

if not knowledge_base().collections and any(path.is_file() for path in RAW_DATA_PATH.rglob("*")):
    with st.spinner("Yerel kaynaklar indeksleniyor..."):
        rebuild()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("ADVENT / CMS hakkında soru sorun…")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Kaynaklar aranıyor ve yeniden sıralanıyor..."):
            answer, sources = knowledge_base().ask(question, scope)
        st.markdown(answer)
        if sources:
            with st.expander("Kullanılan kaynaklar"):
                for score, document in sources:
                    st.markdown(
                        f"- **{document.metadata.get('document', 'Bilinmeyen')}** "
                        f"— sayfa {document.metadata.get('page', 0) + 1} "
                        f"— {document.metadata.get('authority', 'bilinmiyor')} "
                        f"— alaka: {float(score):.0%}"
                    )
    st.session_state.messages.append({"role": "assistant", "content": answer})
