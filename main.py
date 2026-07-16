from src.pipeline.cms_pipeline import CMSPipeline
from src.ingestion.loader import CMSDocumentLoader
from src.ingestion.cleaner import TextCleaner
from src.chunking.chunker import CMSChunker
from src.embeddings.embedder import CMSEmbedder
from src.vectorstore.faiss_store import CMSVectorStore

from src.retrieval.retriever import CMSRetriever
from src.retrieval.bm25_retriever import CMSBM25Retriever
from src.retrieval.hybrid_retriever import CMSHybridRetriever

from src.reranking.reranker import CMSReranker

from src.generation.prompt_builder import CMSPromptBuilder
from src.generation.llm import CMSLLM



def main():

    print("=" * 80)
    print("CMS-RAG Assistant")
    print("=" * 80)

    # ------------------------------------------------
    # Load PDF
    # ------------------------------------------------

    print("\n[1] Loading PDF...")

    loader = CMSDocumentLoader(
    "data/raw"
    )

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
        chunk_size=600,
        chunk_overlap=100
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

    DB_PATH = "data/vectorstore/faiss_index"

    if vectorstore.exists(DB_PATH):

        print("Existing vector database found.")

        db = vectorstore.load(DB_PATH)

        print("Vector database loaded successfully.")

    else:

        print("No vector database found.")

        print("Creating new vector database...")

        db = vectorstore.create(chunks)

        vectorstore.save(db, DB_PATH)

        print("Vector database saved successfully.")

    print(f"Indexed {db.index.ntotal} chunks.")

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

                print(f"• ADVENT CMS | Page {page}")

if __name__ == "__main__":
    main()