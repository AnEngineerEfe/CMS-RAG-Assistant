from src.config import *
from src.pipeline.cms_pipeline import CMSPipeline
from src.ingestion.loader import CMSDocumentLoader
from src.ingestion.cleaner import TextCleaner
from src.chunking.chunker import CMSChunker
from src.embeddings.embedder import CMSEmbedder
from src.vectorstore.faiss_store import CMSVectorStore
from src.metadata.metadata_manager import CMSMetadataManager


def main():

    print("=" * 80)
    print("CMS-RAG Assistant")
    print("=" * 80)

    # ------------------------------------------------
    # Load PDF
    # ------------------------------------------------

    print("\n[1] Loading PDF...")

    loader = CMSDocumentLoader(RAW_DATA_PATH)

    metadata_manager = CMSMetadataManager(
    METADATA_PATH
    ) 

    current_metadata = metadata_manager.build_metadata(
        loader.get_pdf_files()
    )

    old_metadata = metadata_manager.load()

    if old_metadata == current_metadata:

        print("\nMetadata unchanged.")

    else:

        print("\nDocuments changed.")

        metadata_manager.save(current_metadata)

    documents = loader.load()

    print(f"Loaded {len(documents)} pages.")

    # ------------------------------------------------
    # Cleaning
    # ------------------------------------------------

    print("\n[2] Cleaning documents...")

    for doc in documents:
        doc.page_content = TextCleaner.clean(doc.page_content)

    # ------------------------------------------------
    # Chunking
    # ------------------------------------------------

    print("\n[3] Chunking documents...")

    chunker = CMSChunker(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )

    chunks = chunker.split(documents)

    print(f"Created {len(chunks)} chunks.")

    # ------------------------------------------------
    # Embedding Model
    # ------------------------------------------------

    print("\n[4] Loading Embedding Model...")

    embedder = CMSEmbedder()

    # ------------------------------------------------
    # Vector Database
    # ------------------------------------------------

    print("\n[5] Loading Vector Database...")

    vectorstore = CMSVectorStore(
        embedder.get_model()
    )

    db = None

    # ------------------------------------------------
    # Try Loading Existing Database
    # ------------------------------------------------

    if old_metadata == current_metadata and vectorstore.exists(VECTOR_DB_PATH):

        print("Existing vector database found.")

        db = vectorstore.load(VECTOR_DB_PATH)

        print("Vector database loaded successfully.")

    # ------------------------------------------------
    # Create New Database
    # ------------------------------------------------

    else:

        print("Creating new vector database...")

        # Load documents only when needed
        documents = loader.load()

        print(f"Loaded {len(documents)} pages.")

        # Cleaning
        for doc in documents:
            doc.page_content = TextCleaner.clean(doc.page_content)

        # Chunking
        chunker = CMSChunker(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )

        chunks = chunker.split(documents)

        print(f"Created {len(chunks)} chunks.")

        # Create DB
        db = vectorstore.create(chunks)

        # Save DB
        vectorstore.save(db, VECTOR_DB_PATH)

        # Save metadata
        metadata_manager.save(current_metadata)

        print("Vector database saved successfully.")

    print(f"Indexed {db.index.ntotal} chunks.")

    # Ensure chunks exist when DB is loaded from disk
    if 'chunks' not in locals():

        documents = loader.load()

        for doc in documents:
            doc.page_content = TextCleaner.clean(doc.page_content)

        chunker = CMSChunker(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )

        chunks = chunker.split(documents)

    # ------------------------------------------------
    # Initialize Components (Only Once)
    # ------------------------------------------------

    pipeline = CMSPipeline(
        db,
        chunks
    )

    print("\nSystem Ready!")
    print("Type 'exit' to quit.")

    # ==========================================================
    # CHAT LOOP
    # ==========================================================

    while True:

        print("\n" + "=" * 80)

        query = input("You : ")

        if query.lower() in ["exit", "quit"]:

            print("\nGoodbye!")
            break
    
        print("\nProcessing...")

        answer, reranked_results = pipeline.ask(query)

        # ------------------------------------------------
        # Final Answer
        # ------------------------------------------------

        print("\n" + "=" * 80)
        print("CMS ASSISTANT")
        print("=" * 80)

        print("\nAnswer:\n")
        print(answer)

        # ------------------------------------------------
        # Sources
        # ------------------------------------------------

        print("\n" + "-" * 80)
        print("Sources")
        print("-" * 80)

        shown_pages = set()

        for score, doc in reranked_results:

            page = doc.metadata["page"] + 1

            if page not in shown_pages:

                shown_pages.add(page)

                document = doc.metadata.get(
                    "document",
                    "Unknown"
                )

                print(f"• {document} | Page {page}")

if __name__ == "__main__":
    main()