"""Collection-aware RAG orchestration.

HAVELSAN and public/reference corpora are indexed independently, retrieved
independently, then merged only for a user query.  This gives the caller a
clear, auditable choice of source scope.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from src.chunking.chunker import CMSChunker
from src.config import CHUNK_OVERLAP, CHUNK_SIZE, RETRIEVAL_K, TOP_K, VECTOR_DB_PATH
from src.embeddings.embedder import CMSEmbedder
from src.generation.llm import CMSLLM
from src.generation.prompt_builder import CMSPromptBuilder
from src.ingestion.cleaner import TextCleaner
from src.ingestion.loader import CMSDocumentLoader
from src.reranking.reranker import CMSReranker
from src.retrieval.hybrid_retriever import CMSHybridRetriever
from src.vectorstore.faiss_store import CMSVectorStore


class CMSKnowledgeBase:
    def __init__(self, source_root: Path) -> None:
        self.source_root = source_root
        self.embedder = CMSEmbedder()
        self.vectorstore = CMSVectorStore(self.embedder.get_model())
        self.collections: dict[str, CMSHybridRetriever] = {}
        self.reranker = CMSReranker()
        self.llm = CMSLLM()

    def build(self) -> int:
        """Build independent indexes from the current local source corpus."""
        documents = CMSDocumentLoader(self.source_root).load()
        grouped: dict[str, list[Document]] = {}
        for document in documents:
            document.page_content = TextCleaner.clean(document.page_content)
            if document.page_content.strip():
                grouped.setdefault(document.metadata["collection"], []).append(document)

        chunker = CMSChunker(CHUNK_SIZE, CHUNK_OVERLAP)
        self.collections.clear()
        indexed = 0
        for collection, items in grouped.items():
            chunks = chunker.split(items)
            if not chunks:
                continue
            index = self.vectorstore.create(chunks)
            self.vectorstore.save(index, VECTOR_DB_PATH / collection)
            self.collections[collection] = CMSHybridRetriever(index, chunks)
            indexed += len(chunks)
        return indexed

    def ask(self, query: str, scope: str = "all") -> tuple[str, list[tuple[float, Document]]]:
        selected = self.collections.items() if scope == "all" else [
            (scope, self.collections[scope])
        ] if scope in self.collections else []
        candidates: list[Document] = []
        seen: set[tuple[str, int, str]] = set()
        for _, retriever in selected:
            for document in retriever.search(query):
                key = (
                    document.metadata.get("source_path", document.metadata.get("document", "")),
                    document.metadata.get("page", 0),
                    document.page_content[:120],
                )
                if key not in seen:
                    seen.add(key)
                    candidates.append(document)

        if not candidates:
            return "Bu kapsamda sorgulanabilir bir kaynak bulunamadı.", []

        ranked = self.reranker.rerank(query, candidates[: RETRIEVAL_K * 2], top_k=TOP_K)
        answer = self.llm.generate(CMSPromptBuilder.build(query, [doc for _, doc in ranked], []))
        return answer, ranked
