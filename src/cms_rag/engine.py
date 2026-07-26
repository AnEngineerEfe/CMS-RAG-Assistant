from __future__ import annotations

from pathlib import Path

from ollama import chat

from .ingest import PDFIngestor
from .models import SearchHit
from .retrieval import HybridRetriever
from .storage import DocumentStore


NO_ANSWER = "Bu soruyu destekleyecek yeterli kaynak bulunamadı."


class CMSRAGEngine:
    def __init__(self, data_dir: Path, model: str = "qwen2.5:7b") -> None:
        self.store = DocumentStore(data_dir / "documents")
        self.model = model
        self.retriever: HybridRetriever | None = None
        self.history: list[dict[str, str]] = []

    def rebuild(self) -> int:
        chunks = PDFIngestor().load(self.store.pdfs())
        self.retriever = HybridRetriever(chunks) if chunks else None
        self.history.clear()
        return len(chunks)

    def ask(self, question: str) -> tuple[str, list[SearchHit]]:
        if not self.retriever:
            return "Once resmi PDF dokumanini yukleyip indeksleyin.", []
        hits = self.retriever.search(question)
        if not hits:
            return NO_ANSWER, []
        context = "\n\n".join(
            f"[SOURCE {number}: {hit.chunk.document}, page {hit.chunk.page}]\n{hit.chunk.text}"
            for number, hit in enumerate(hits, start=1)
        )
        prompt = f"""You are a careful CMS documentation assistant. Answer only from CONTEXT.
Write fluent Turkish. Do not invent examples, systems, capabilities, or facts.
If evidence is insufficient, answer exactly: {NO_ANSWER}
Use [SOURCE n] after every factual paragraph.

CONTEXT
{context}

QUESTION
{question}
"""
        try:
            response = chat(model=self.model, messages=[{"role": "user", "content": prompt}])
            answer = response["message"]["content"].strip()
        except Exception:
            answer = "Yerel Ollama servisine ulaşılamadı. `ollama serve` komutunu çalıştırın."
        self.history = (self.history + [{"question": question, "answer": answer}])[-3:]
        return answer or NO_ANSWER, hits

    def clear_chat(self) -> None:
        self.history.clear()
