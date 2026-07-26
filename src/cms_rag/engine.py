from __future__ import annotations

from pathlib import Path

from ollama import chat

from .evidence import EvidenceResponder
from .ingest import PDFIngestor
from .models import SearchHit
from .retrieval import HybridRetriever
from .storage import DocumentStore


NO_ANSWER = "Bu soruyu destekleyecek yeterli kaynak bulunamad\u0131."


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
            return "\u00d6nce resm\u00ee PDF dok\u00fcman\u0131n\u0131 y\u00fckleyip indeksleyin.", []
        evidence_answer = EvidenceResponder.answer(question, self.history, self.retriever.chunks)
        if evidence_answer:
            answer, hits = evidence_answer
            self.history = (self.history + [{"question": question, "answer": answer}])[-3:]
            return answer, hits
        retrieval_query = self.build_retrieval_query(question)
        hits = self.retriever.search(retrieval_query)
        if not hits:
            return NO_ANSWER, []
        context = "\n\n".join(
            f"[SOURCE {number}: {hit.chunk.document}, page {hit.chunk.page}]\n{hit.chunk.text}"
            for number, hit in enumerate(hits, start=1)
        )
        prompt = f"""You are a careful CMS documentation assistant. Answer only from CONTEXT.
Write fluent Turkish in at most two short paragraphs. Do not invent examples, systems, capabilities, or facts.
If the user asks for an example and the context does not contain one, say that
the documents do not provide a concrete example; never create a fictional case.
If evidence is insufficient, answer exactly: {NO_ANSWER}
Use [SOURCE n] after every factual paragraph. Conversation history resolves
follow-up questions but is not evidence.

CONVERSATION HISTORY
{self._format_history()}

CONTEXT
{context}

QUESTION
{question}
"""
        try:
            response = chat(model=self.model, messages=[{"role": "user", "content": prompt}])
            answer = response["message"]["content"].strip()
        except Exception:
            answer = "Yerel Ollama servisine ula\u015f\u0131lamad\u0131. `ollama serve` komutunu \u00e7al\u0131\u015ft\u0131r\u0131n."
        self.history = (self.history + [{"question": question, "answer": answer}])[-3:]
        return answer or NO_ANSWER, hits

    def clear_chat(self) -> None:
        self.history.clear()

    def build_retrieval_query(self, question: str) -> str:
        """Attach the previous subject to short follow-up questions."""
        if len(question.split()) <= 6 and self.history:
            return f"{self.history[-1]['question']}\nTakip sorusu: {question}"
        return question

    def _format_history(self) -> str:
        if not self.history:
            return "(Yok)"
        return "\n".join(
            f"Kullan\u0131c\u0131: {item['question']}\nAsistan: {item['answer']}"
            for item in self.history[-2:]
        )
