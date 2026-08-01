"""Belge hazırlama, retrieval ve yerel üretim adımlarını yöneten uygulama servisi."""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from time import perf_counter

from ollama import Client

from ..domain.evidence import EvidenceResponder
from ..domain.models import SearchHit
from ..domain.query import CMSQueryProcessor
from ..infrastructure.ingest import MarkdownIngestor, PDFIngestor
from ..infrastructure.audit import AuditStore
from ..infrastructure.knowledge import (
    load_curated_chunks,
    supplemental_document_paths,
)
from ..infrastructure.retrieval import HybridRetriever
from ..infrastructure.storage import DocumentStore


NO_ANSWER = "Bu soruyu destekleyecek yeterli kaynak bulunamad\u0131."
DEFAULT_MAX_NEW_TOKENS = 160
CONTINUATION_MAX_NEW_TOKENS = 96


class CMSRAGEngine:
    """CMS-RAG kullanım senaryolarını tek bir durumlu servis üzerinden yürütür."""

    def __init__(self, data_dir: Path, model: str | None = None) -> None:
        """Veri deposunu ve Ollama istemcisini hazırlar; indekslemeyi tembel bırakır."""

        self.store = DocumentStore(data_dir / "documents")
        self.data_dir = data_dir
        self.model = model or os.getenv("CMS_RAG_MODEL", "qwen2.5:3b")
        self._ollama = Client(timeout=120.0)
        self.audit = AuditStore(data_dir / "audit")
        self.retriever: HybridRetriever | None = None
        self.history: list[dict[str, str]] = []
        self.snapshot_loaded = False

    def rebuild(self) -> int:
        """PDF ve Markdown kaynaklarını okuyup hibrit indeksi baştan kurar."""

        # Resmî yüklemeler ile açık referanslar aynı modelde, ayrı koleksiyonlarda tutulur.
        snapshot_dir = self.data_dir / "knowledge_base" / "snapshot"
        if (snapshot_dir / "snapshot.json").exists():
            supplemental = PDFIngestor().load(
                supplemental_document_paths(self.data_dir, snapshot_dir),
                collection="official",
                authority="user_uploaded_public_document",
            )
            self.retriever = HybridRetriever.from_snapshot(
                snapshot_dir,
                supplemental_chunks=supplemental,
            )
            self.snapshot_loaded = True
        else:
            chunks = []
            if (self.data_dir / "knowledge_base" / "manifest.json").exists():
                chunks.extend(load_curated_chunks(self.data_dir))
            else:
                chunks.extend(
                    PDFIngestor().load(
                        self.store.pdfs(),
                        collection="official",
                        authority="uploaded_official",
                    )
                )
                chunks.extend(
                    MarkdownIngestor().load_directory(
                        self.data_dir / "references"
                    )
                )
            self.retriever = HybridRetriever(chunks) if chunks else None
            self.snapshot_loaded = False
        self.history.clear()
        return len(self.retriever.chunks) if self.retriever else 0

    def prepared_document_count(self) -> int:
        """Önceden hazırlanmış bilgi tabanındaki benzersiz belge sayısını döndürür."""

        if not self.retriever:
            return 0
        return len(
            {
                chunk.document
                for chunk in self.retriever.chunks
                if chunk.authority != "user_uploaded_public_document"
            }
        )

    def active_document_count(self) -> int:
        """Hazır ve sonradan eklenmiş tüm aktif benzersiz belge sayısını döndürür."""

        if not self.retriever:
            return 0
        return len({chunk.document for chunk in self.retriever.chunks})

    def supplemental_records(self) -> list[dict]:
        """Hazır snapshot dışında kalan, kullanıcı tarafından yönetilebilir kayıtları döndürür."""

        snapshot_dir = self.data_dir / "knowledge_base" / "snapshot"
        included = HybridRetriever.snapshot_source_hashes(snapshot_dir)
        return [
            record
            for record in self.store.records()
            if record.get("sha256") not in included
        ]

    def ask(self, question: str, scope: str = "all") -> tuple[str, list[SearchHit]]:
        """Akışlı yanıtı tüketerek klasik metin ve kaynak listesi arayüzü sağlar."""

        stream, hits = self.stream_ask(question, scope)
        return "".join(stream), hits

    def stream_ask(self, question: str, scope: str = "all") -> tuple[Iterator[str], list[SearchHit]]:
        """Soruyu kanıt kuralları, retrieval ve Ollama sırasıyla akışlı cevaplar."""

        started_at = perf_counter()
        if not self.retriever:
            return self._completed(
                question,
                "\u00d6nce resm\u00ee PDF dok\u00fcman\u0131n\u0131 y\u00fckleyip indeksleyin.",
                scope,
                started_at=started_at,
                generation_mode="unavailable",
            ), []

        # Alan dışı sohbeti erken reddetmek gecikmeyi ve belgesiz üretim riskini azaltır.
        if CMSQueryProcessor.is_non_domain_chitchat(question):
            return self._completed(
                question,
                NO_ANSWER,
                scope,
                started_at=started_at,
                generation_mode="safe_rejection",
            ), []
        scoped_history = self._history_for(scope)
        evidence_chunks = [chunk for chunk in self.retriever.chunks if scope == "all" or chunk.collection == scope]
        # Açıkça belgelenmiş sık sorular model belirsizliğine bırakılmadan cevaplanır.
        evidence_answer = EvidenceResponder.answer(question, scoped_history, evidence_chunks)
        if evidence_answer:
            answer, hits = evidence_answer
            return self._completed(
                question,
                answer,
                scope,
                hits=hits,
                started_at=started_at,
                generation_mode="evidence_rule",
            ), hits

        retrieval_query = CMSQueryProcessor.expand(self.build_retrieval_query(question, scope))
        hits = self.retriever.search(retrieval_query, scope=scope)
        if not self.retriever.is_answerable(retrieval_query, hits):
            return self._completed(
                question,
                NO_ANSWER,
                scope,
                started_at=started_at,
                generation_mode="evidence_gate",
            ), []
        prompt = self._prompt(question, hits, scope)
        return self._ollama_stream(
            question,
            prompt,
            hits,
            scope,
            started_at=started_at,
        ), hits

    def clear_chat(self) -> None:
        """Motorun kapsam etiketli kısa konuşma belleğini temizler."""

        self.history.clear()

    def build_retrieval_query(self, question: str, scope: str = "all") -> str:
        """Resolve short references using the complete bounded conversation."""
        reference_words = ("bunlar", "bunun", "onlar", "detay", "ornek", "baska", "gorev")
        is_follow_up = len(question.split()) <= 7 or any(word in question.lower() for word in reference_words)
        scoped_history = self._history_for(scope)
        if is_follow_up and scoped_history:
            conversation = "\n".join(
                f"{item['question']} {item['answer']}" for item in scoped_history[-3:]
            )
            return f"{conversation}\nTakip sorusu: {question}"
        return question

    def _prompt(self, question: str, hits: list[SearchHit], scope: str = "all") -> str:
        """Kaynakları numaralandırıp modeli yalnızca bu bağlamdan cevap vermeye zorlar."""

        # Uzun ve aynı sayfadan birleşmiş kanıt kartlarının tamamını modele göndermek yerel
        # donanımda ilk token süresini büyütür. En güçlü üç kanıtın sınırlı bir bölümünü
        # kullanmak kaynak kapsamını korurken üretimi belirgin biçimde hızlandırır.
        prompt_hits = hits[:3]
        expanded_question = CMSQueryProcessor.expand(question)
        context = "\n\n".join(
            f"[SOURCE {number}: {hit.chunk.document}, page {hit.chunk.page}]\n"
            f"{self._evidence_excerpt(expanded_question, hit.chunk.text)}"
            for number, hit in enumerate(prompt_hits, start=1)
        )
        return f"""You are a careful CMS documentation assistant. Answer only from CONTEXT.
Write fluent Turkish in one concise paragraph of at most 55 words.
Do not invent examples, systems, capabilities, or facts.
Treat statements describing this research package as a public preliminary study
as scope metadata; never describe ADVENT itself as a preliminary study.
If the user asks for an example and the context does not contain one, say that
the documents do not provide a concrete example; never create a fictional case.
If evidence is insufficient, answer exactly: {NO_ANSWER}
Use [SOURCE n] after every factual paragraph. Conversation history resolves
follow-up questions but is not evidence.

CONVERSATION HISTORY
{self._format_history(scope)}

CONTEXT
{context}

QUESTION
{question}
"""

    @staticmethod
    def _evidence_excerpt(query: str, text: str, limit: int = 900) -> str:
        """Uzun chunk içinden soruyla en fazla örtüşen cümleleri bağlam bütçesine sığdırır."""

        if len(text) <= limit:
            return text
        ignored = {
            "advent", "cms", "sistem", "system", "nedir", "nelerdir", "nasil",
            "nasıl", "yapar", "hakkinda", "hakkında", "icin", "için", "bir",
            "the", "what", "how", "does", "and", "ve",
        }
        query_terms = {
            token
            for token in HybridRetriever._tokenise(CMSQueryProcessor.normalise(query))
            if token not in ignored and len(token) > 2
        }
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", text)
            if sentence.strip()
        ]
        ranked = sorted(
            enumerate(sentences),
            key=lambda item: (
                len(
                    query_terms
                    & set(
                        HybridRetriever._tokenise(
                            CMSQueryProcessor.normalise(item[1])
                        )
                    )
                ),
                -item[0],
            ),
            reverse=True,
        )
        selected_indexes = sorted(index for index, _ in ranked[:4])
        excerpt = " ".join(sentences[index] for index in selected_indexes)
        if not excerpt:
            excerpt = text
        return excerpt[:limit].rstrip()

    def _grounded_fallback(self, question: str, hits: list[SearchHit]) -> str:
        """Model yanlış ret verirse en güçlü kanıttan izlenebilir bir çıkarımsal yedek üretir."""

        excerpt = self._evidence_excerpt(
            CMSQueryProcessor.expand(question),
            hits[0].chunk.text,
            limit=450,
        )
        return f"Kaynakta soruyla ilgili şu bilgi yer alıyor: {excerpt} [SOURCE 1]"

    def _completed(
        self,
        question: str,
        answer: str,
        scope: str = "all",
        *,
        hits: list[SearchHit] | None = None,
        started_at: float | None = None,
        generation_mode: str = "deterministic",
    ) -> Iterator[str]:
        """Hazır cevabı kelime kelime yayınlayan ve sonunda belleğe alan akış kurar."""

        def iterator() -> Iterator[str]:
            """Streamlit yazım animasyonu için cevabı küçük parçalar hâlinde üretir."""

            for word in answer.split(" "):
                yield f"{word} "
            self._remember(question, answer, scope)
            self._record_audit(
                question,
                answer,
                hits or [],
                scope,
                started_at,
                generation_mode,
            )
        return iterator()

    def _ollama_stream(
        self,
        question: str,
        prompt: str,
        hits: list[SearchHit],
        scope: str = "all",
        *,
        started_at: float | None = None,
    ) -> Iterator[str]:
        """Ollama akışını yayınlar, kaynak işaretini garanti eder ve hatayı anlaşılır kılar."""

        def iterator() -> Iterator[str]:
            """Model tokenlarını iletir ve tamamlanan yanıtı kapsamıyla kaydeder."""

            parts: list[str] = []
            pending: list[str] = []
            released = False
            stop_reason = ""
            try:
                for response in self._ollama.chat(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    # 64 token, Türkçe cevaplarda cümlenin ortasında kesilmeye yol açıyordu.
                    # 160 token; istemdeki 55 kelimelik üst sınırı güvenli biçimde tamamlar.
                    options={
                        "temperature": 0.1,
                        "num_predict": DEFAULT_MAX_NEW_TOKENS,
                        "num_ctx": 2048,
                    },
                    keep_alive="30m",
                ):
                    stop_reason = str(response.get("done_reason", stop_reason))
                    token = response["message"]["content"]
                    if token:
                        parts.append(token)
                        if released:
                            yield token
                            continue
                        pending.append(token)
                        candidate = "".join(pending).strip()
                        # Tam güvenli-ret cümlesi oluşana kadar kısa başlangıcı tamponlarız.
                        # Model başka bir yanıta saparsa tampon anında akışa bırakılır.
                        if not NO_ANSWER.startswith(candidate):
                            released = True
                            yield "".join(pending)
                            pending.clear()

                # Model token bütçesinde durmuşsa eksik cümleyi aynı kanıt bağlamıyla
                # tek kez tamamlatırız; ikinci çağrı yeni paragraf veya iddia üretemez.
                if stop_reason == "length" and parts:
                    draft = "".join(parts).strip()
                    continuation_started = False
                    for response in self._ollama.chat(
                        model=self.model,
                        messages=[
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": draft},
                            {
                                "role": "user",
                                "content": (
                                    "Yanıt token sınırında kesildi. Yalnızca yarım kalan "
                                    "Türkçe cümleyi mevcut CONTEXT'e dayanarak tamamla; "
                                    "yeni paragraf veya yeni iddia ekleme."
                                ),
                            },
                        ],
                        stream=True,
                        options={
                            "temperature": 0.0,
                            "num_predict": CONTINUATION_MAX_NEW_TOKENS,
                            "num_ctx": 2048,
                        },
                        keep_alive="30m",
                    ):
                        token = response["message"]["content"]
                        if not token:
                            continue
                        if (
                            not continuation_started
                            and draft[-1:].isalnum()
                            and token[:1].isalnum()
                        ):
                            token = f" {token}"
                        continuation_started = True
                        parts.append(token)
                        if released:
                            yield token
                        else:
                            pending.append(token)
                answer = "".join(parts).strip() or NO_ANSWER
                if answer == NO_ANSWER and hits:
                    answer = self._grounded_fallback(question, hits)
                    yield answer
                elif pending:
                    yield "".join(pending)
                # Model etiketi atlarsa retrieval'ın ilk kanıtını deterministik biçimde ekleriz.
                if hits and "[SOURCE" not in answer.upper() and answer != NO_ANSWER:
                    citation = " [SOURCE 1]"
                    answer += citation
                    yield citation
            except Exception:
                answer = "Yerel Ollama servisine ula\u015f\u0131lamad\u0131. `ollama serve` komutunu \u00e7al\u0131\u015ft\u0131r\u0131n."
                yield answer
            self._remember(question, answer, scope)
            self._record_audit(
                question,
                answer,
                hits if "ula\u015f\u0131lamad\u0131" not in answer else [],
                scope,
                started_at,
                "ollama",
            )
        return iterator()

    def _record_audit(
        self,
        question: str,
        answer: str,
        hits: list[SearchHit],
        scope: str,
        started_at: float | None,
        generation_mode: str,
    ) -> None:
        """Yanıt akışını bozmadan gizlilik korumalı işletim olayını kaydeder."""

        if generation_mode == "unavailable":
            outcome = "unavailable"
        elif answer == NO_ANSWER:
            outcome = "unsupported"
        elif "Ollama servisine ula\u015f\u0131lamad\u0131" in answer:
            outcome = "service_error"
        else:
            outcome = "grounded"
        sources = [
            {
                "document": hit.chunk.document,
                "page": hit.chunk.page,
                "collection": hit.chunk.collection,
            }
            for hit in hits
        ]
        latency_ms = (
            (perf_counter() - started_at) * 1000 if started_at is not None else 0.0
        )
        try:
            self.audit.record(
                question=question,
                scope=scope,
                model=self.model,
                outcome=outcome,
                latency_ms=latency_ms,
                sources=sources,
                answer_chars=len(answer),
                citation_present="[SOURCE" in answer.upper(),
                generation_mode=generation_mode,
            )
        except OSError:
            # Audit diski kullanılamazsa kullanıcı yanıtı yine tamamlanır.
            return

    def _remember(self, question: str, answer: str, scope: str = "all") -> None:
        """Son üç turu kapsamıyla saklayarak sınırsız bağlam büyümesini önler."""

        self.history = (
            self.history
            + [{"question": question, "answer": answer, "scope": scope}]
        )[-3:]

    def _history_for(self, scope: str) -> list[dict[str, str]]:
        """Yalnız aynı kapsamdaki turları döndürerek koleksiyon sızıntısını önler."""

        return [
            item
            for item in self.history
            if item.get("scope", "all") == scope
        ]

    def _format_history(self, scope: str = "all") -> str:
        """Uygun geçmişi model isteminde kullanılacak okunur metne dönüştürür."""

        scoped_history = self._history_for(scope)
        if not scoped_history:
            return "(Yok)"
        return "\n".join(
            f"Kullan\u0131c\u0131: {item['question']}\nAsistan: {item['answer']}"
            for item in scoped_history[-3:]
        )
