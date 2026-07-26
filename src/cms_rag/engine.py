from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ollama import Client

from .evidence import EvidenceResponder
from .ingest import MarkdownIngestor, PDFIngestor
from .models import SearchHit
from .query import CMSQueryProcessor
from .retrieval import HybridRetriever
from .storage import DocumentStore


NO_ANSWER = "Bu soruyu destekleyecek yeterli kaynak bulunamad\u0131."


class CMSRAGEngine:
    def __init__(self, data_dir: Path, model: str = "qwen2.5:7b") -> None:
        self.store = DocumentStore(data_dir / "documents")
        self.data_dir = data_dir
        self.model = model
        self._ollama = Client(timeout=90.0)
        self.retriever: HybridRetriever | None = None
        self.history: list[dict[str, str]] = []

    def rebuild(self) -> int:
        chunks = PDFIngestor().load(self.store.pdfs(), collection="official", authority="uploaded_official")
        chunks.extend(MarkdownIngestor().load_directory(self.data_dir / "references"))
        self.retriever = HybridRetriever(chunks) if chunks else None
        self.history.clear()
        return len(chunks)

    def ask(self, question: str, scope: str = "all") -> tuple[str, list[SearchHit]]:
        stream, hits = self.stream_ask(question, scope)
        return "".join(stream), hits

    def stream_ask(self, question: str, scope: str = "all") -> tuple[Iterator[str], list[SearchHit]]:
        if not self.retriever:
            return self._completed(question, "\u00d6nce resm\u00ee PDF dok\u00fcman\u0131n\u0131 y\u00fckleyip indeksleyin."), []

        if CMSQueryProcessor.is_non_domain_chitchat(question):
            return self._completed(question, NO_ANSWER), []
        evidence_chunks = [chunk for chunk in self.retriever.chunks if scope == "all" or chunk.collection == scope]
        evidence_answer = EvidenceResponder.answer(question, self.history, evidence_chunks)
        if evidence_answer:
            answer, hits = evidence_answer
            return self._completed(question, answer), hits

        retrieval_query = CMSQueryProcessor.expand(self.build_retrieval_query(question))
        hits = self.retriever.search(retrieval_query, scope=scope)
        if not hits:
            return self._completed(question, NO_ANSWER), []
        prompt = self._prompt(question, hits)
        return self._ollama_stream(question, prompt), hits

    def clear_chat(self) -> None:
        self.history.clear()

    def build_retrieval_query(self, question: str) -> str:
        """Resolve short references using the complete bounded conversation."""
        reference_words = ("bunlar", "bunun", "onlar", "detay", "ornek", "baska", "gorev")
        is_follow_up = len(question.split()) <= 7 or any(word in question.lower() for word in reference_words)
        if is_follow_up and self.history:
            conversation = "\n".join(
                f"{item['question']} {item['answer']}" for item in self.history[-3:]
            )
            return f"{conversation}\nTakip sorusu: {question}"
        return question

    def _prompt(self, question: str, hits: list[SearchHit]) -> str:
        context = "\n\n".join(
            f"[SOURCE {number}: {hit.chunk.document}, page {hit.chunk.page}]\n{hit.chunk.text}"
            for number, hit in enumerate(hits, start=1)
        )
        return f"""You are a careful CMS documentation assistant. Answer only from CONTEXT.
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

    def _completed(self, question: str, answer: str) -> Iterator[str]:
        def iterator() -> Iterator[str]:
            for word in answer.split(" "):
                yield f"{word} "
            self._remember(question, answer)
        return iterator()

    def _ollama_stream(self, question: str, prompt: str) -> Iterator[str]:
        def iterator() -> Iterator[str]:
            parts: list[str] = []
            try:
                for response in self._ollama.chat(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    options={"temperature": 0.1, "num_predict": 180},
                ):
                    token = response["message"]["content"]
                    if token:
                        parts.append(token)
                        yield token
                answer = "".join(parts).strip() or NO_ANSWER
            except Exception:
                answer = "Yerel Ollama servisine ula\u015f\u0131lamad\u0131. `ollama serve` komutunu \u00e7al\u0131\u015ft\u0131r\u0131n."
                yield answer
            self._remember(question, answer)
        return iterator()

    def _remember(self, question: str, answer: str) -> None:
        self.history = (self.history + [{"question": question, "answer": answer}])[-3:]

    def _format_history(self) -> str:
        if not self.history:
            return "(Yok)"
        return "\n".join(
            f"Kullan\u0131c\u0131: {item['question']}\nAsistan: {item['answer']}"
            for item in self.history[-3:]
        )
