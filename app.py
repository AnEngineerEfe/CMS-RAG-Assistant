from embeddings import embedder
from src.document.document_service import CMSDocumentService
from src.document.document_manager import CMSDocumentManager
from src.upload.upload_manager import CMSUploadManager
from src.metadata.metadata_manager import CMSMetadataManager
from src.config import *
import streamlit as st
import os


from src.pipeline.cms_pipeline import CMSPipeline
from src.ingestion.loader import CMSDocumentLoader
from src.ingestion.cleaner import TextCleaner
from src.chunking.chunker import CMSChunker
from src.embeddings.embedder import CMSEmbedder
from src.vectorstore.faiss_store import CMSVectorStore


st.set_page_config(
    page_title="CMS-RAG Assistant",
    page_icon="🛰️",
    layout="wide"
)

st.title("🛰️ CMS-RAG Assistant")
st.write("Combat Management System AI Assistant")

# ------------------------------------------------
# Session State
# ------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# ------------------------------------------------
# Rebuild Vector Database
# ------------------------------------------------

def rebuild_database():

    loader = CMSDocumentLoader(RAW_DATA_PATH)

    documents = loader.load()

    for doc in documents:
        doc.page_content = TextCleaner.clean(doc.page_content)

    chunker = CMSChunker(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )

    chunks = chunker.split(documents)

    if len(chunks) == 0:

        return None

    embedder = CMSEmbedder()

    vectorstore = CMSVectorStore(
        embedder.get_model()
    )

    db = vectorstore.create(chunks)

    vectorstore.save(
        db,
        VECTOR_DB_PATH
    )

    metadata = CMSMetadataManager(
        METADATA_PATH
    )

    metadata.save(
        metadata.build_metadata(
            loader.get_pdf_files()
        )
    )

# ------------------------------------------------
# Load Pipeline
# ------------------------------------------------

@st.cache_resource
def load_pipeline():

    loader = CMSDocumentLoader(RAW_DATA_PATH)

    documents = loader.load()

    for doc in documents:
        doc.page_content = TextCleaner.clean(doc.page_content)

    chunker = CMSChunker(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )

    chunks = chunker.split(documents)

    if len(chunks) == 0:
        return None

    embedder = CMSEmbedder()

    vectorstore = CMSVectorStore(
        embedder.get_model()
    )

    db = vectorstore.load(
        VECTOR_DB_PATH
    )

    return CMSPipeline(
        db,
        chunks
    )



pipeline = load_pipeline()

if pipeline is None:

    st.info("📂 No document uploaded yet.")

    st.stop()

with st.sidebar:

    st.header("🛰️ CMS-RAG Assistant")

    st.success("System Ready")

    st.markdown("---")

    st.write("**LLM**")
    st.write("Llama 3")

    st.write("**Vector DB**")
    st.write("FAISS")

    st.write("**Retriever**")
    st.write("Hybrid Search")

    st.write("**Reranker**")
    st.write("BAAI/bge-reranker-base")

    st.markdown("---")

    st.subheader("📂 Documents")

    doc_manager = CMSDocumentManager()

    documents = doc_manager.get_documents()

    st.caption(f"{len(documents)} document(s)")

    service = CMSDocumentService()

    for document in documents:

        with st.container(border=True):

            st.markdown(f"📄 **{document['name']}**")

            st.caption(f"{document['size']} MB")

            if st.button(
                "🗑 Delete",
                key=f"delete_{document['path']}"
            ):

                deleted = service.delete(
                    str(document["path"])
                )

                if deleted:

                    rebuild_database()

                    st.cache_resource.clear()

                    pipeline = load_pipeline()

                    st.success("Document deleted.")

                    st.rerun()

                else:

                    st.error(
                        "Delete failed."
                    )

    uploaded = False

    uploaded_files = st.file_uploader(
        "Upload PDF Files",
        type=["pdf"],
        accept_multiple_files=True
    )

    os.makedirs(
        "data/raw/uploaded",
        exist_ok=True
    )

    manager = CMSUploadManager()

    if uploaded_files:

        uploaded = False

        for file in uploaded_files:

            if manager.is_duplicate(file):

                st.warning(
                    f"⚠️ {file.name} already exists."
                )

                continue

            manager.save_file(file)

            uploaded = True

    if uploaded:

        st.success("PDF(s) uploaded successfully!")

        st.info("Rebuilding vector database...")

        rebuild_database()

        st.cache_resource.clear()

        pipeline = load_pipeline()

        st.success("Vector database updated successfully!")

    st.markdown("---")

    if st.button("🗑️ Clear Chat"):

        st.session_state.messages = []

        st.rerun()

# ------------------------------------------------
# Show Chat History
# ------------------------------------------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ------------------------------------------------
# Chat Input
# ------------------------------------------------

question = st.chat_input("Ask about ADVENT CMS...")

if question:

    # User Message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": question
        }
    )

    with st.chat_message("user"):
        st.markdown(question)

    # Assistant Message
    with st.chat_message("assistant"):

        with st.spinner("Thinking..."):

            answer, sources = pipeline.ask(question)

            best_score = sources[0][0] if sources else 0

        st.markdown(answer)

        confidence = min(max(best_score * 100, 0), 100)

        if confidence >= 85:
            st.success(f"🟢 Confidence: {confidence:.1f}%")

        elif confidence >= 65:
            st.warning(f"🟡 Confidence: {confidence:.1f}%")

        else:
            st.error(f"🔴 Confidence: {confidence:.1f}%")

        st.divider()

        st.subheader("📚 Sources")

        shown = set()

        for score, doc in sources:

            page = doc.metadata["page"] + 1

            if page in shown:
                continue

            shown.add(page)

            with st.container(border=True):

                document = doc.metadata.get(
                    "document",
                    "Unknown"
                )

                st.markdown(f"**📄 {document}**")
                st.caption(f"Page {page}")

                preview = doc.page_content[:250].strip()

                if len(doc.page_content) > 250:
                    preview += "..."

                st.write(preview)


    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )