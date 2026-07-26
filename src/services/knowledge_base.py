"""Collection-aware RAG orchestration with guarded answer generation."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from langchain_core.documents import Document

from src.chunking.chunker import CMSChunker
from src.config import CHUNK_OVERLAP, CHUNK_SIZE, MIN_RERANK_RELEVANCE, RETRIEVAL_K, TOP_K, VECTOR_DB_PATH
from src.embeddings.embedder import CMSEmbedder
from src.generation.evidence_answers import CMSEvidenceAnswers
from src.generation.llm import CMSLLM
from src.generation.prompt_builder import CMSPromptBuilder
from src.ingestion.cleaner import TextCleaner
from src.ingestion.loader import CMSDocumentLoader
from src.memory.conversation_memory import CMSConversationMemory
from src.reranking.reranker import CMSReranker
from src.retrieval.hybrid_retriever import CMSHybridRetriever
from src.vectorstore.faiss_store import CMSVectorStore


NO_ANSWER = "Bu soruyu destekleyecek yeterli g\u00fcvenilir kaynak bulunamad\u0131."


class CMSKnowledgeBase:
    def __init__(self, source_root: Path) -> None:
        self.source_root = source_root
        self.embedder = CMSEmbedder()
        self.vectorstore = CMSVectorStore(self.embedder.get_model())
        self.collections: dict[str, CMSHybridRetriever] = {}
        self.reranker = CMSReranker()
        self.llm = CMSLLM()
        self.memory = CMSConversationMemory()

    def build(self) -> int:
        documents = CMSDocumentLoader(self.source_root).load()
        grouped: dict[str, list[Document]] = {}
        for document in documents:
            document.page_content = TextCleaner.clean(document.page_content)
            if document.page_content.strip():
                grouped.setdefault(document.metadata["collection"], []).append(document)

        self.collections.clear()
        indexed = 0
        chunker = CMSChunker(CHUNK_SIZE, CHUNK_OVERLAP)
        for collection, items in grouped.items():
            chunks = chunker.split(items)
            if chunks:
                index = self.vectorstore.create(chunks)
                self.vectorstore.save(index, VECTOR_DB_PATH / collection)
                self.collections[collection] = CMSHybridRetriever(index, chunks)
                indexed += len(chunks)
        self.clear_memory()
        return indexed

    def ask(self, query: str, scope: str = "all") -> tuple[str, list[tuple[float, Document]]]:
        if not query.strip():
            return NO_ANSWER, []
        retrieval_query = self._contextualise_short_query(query)
        candidates = self._retrieve(retrieval_query, scope)
        if not candidates:
            return NO_ANSWER, []

        ranked = self.reranker.rerank(retrieval_query, candidates[: RETRIEVAL_K * 2], TOP_K)
        if not ranked or ranked[0][0] < MIN_RERANK_RELEVANCE:
            return NO_ANSWER, ranked
        evidence_answer = CMSEvidenceAnswers.answer(query, ranked)
        if evidence_answer:
            self.memory.add(query, evidence_answer)
            return evidence_answer, ranked
        try:
            answer = self.llm.generate(
                CMSPromptBuilder.build(query, [doc for _, doc in ranked[:2]], self.memory.get_history())
            )
        except Exception:
            return "Yerel LLM servisine ulaşılamadı. Ollama'nın çalıştığını ve modelin yüklü olduğunu kontrol edin.", ranked
        self.memory.add(query, answer)
        return answer, ranked

    def clear_memory(self) -> None:
        self.memory.clear()

    def _retrieve(self, query: str, scope: str) -> list[Document]:
        scope = {"combined": "all", "birlesik": "all"}.get(scope, scope)
        selected = self.collections.items() if scope == "all" else [(scope, self.collections[scope])] if scope in self.collections else []
        candidates: list[Document] = []
        seen: set[tuple[str, int, str]] = set()
        for _, retriever in selected:
            for document in retriever.search(query):
                key = (document.metadata.get("source_path", ""), document.metadata.get("page", 0), document.page_content[:120])
                if key not in seen:
                    seen.add(key)
                    candidates.append(document)
        return candidates

    def _contextualise_short_query(self, query: str) -> str:
        history = self.memory.get_history()
        if len(query.split()) <= 5 and history:
            query = f"{history[-1]['question']} {query}"
        normalized = unicodedata.normalize("NFKD", query.lower())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = normalized.translate(str.maketrans("\u00e7\u011f\u0131\u00f6\u015f\u00fc", "cgiosu"))
        glossary = {
            "advent": "combat management system naval operations",
            "iz yonetimi": "track management",
            "iz": "track",
            "takip": "tracking",
            "hedef": "target",
            "veri baglantisi": "data link",
            "taktik veri linki": "tactical data link",
            "durumsal farkindalik": "situational awareness",
            "silah yonetimi": "weapon management",
            "sensor fuzyonu": "sensor fusion",
        }
        additions = [english for turkish, english in glossary.items() if turkish in normalized]
        return f"{query} {' '.join(additions)}" if additions else query
