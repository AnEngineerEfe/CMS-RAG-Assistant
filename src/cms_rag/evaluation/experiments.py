"""Chunk kalitesi, bağımsız cevap hakemi ve retrieval bileşen deneylerini yürütür."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from ..application import CMSRAGEngine
from ..domain.models import Chunk
from ..domain.query import CMSQueryProcessor
from ..infrastructure.ingest import PDFIngestor
from ..infrastructure.knowledge import load_manifest
from ..infrastructure.retrieval import HybridRetriever
from .judge import OllamaJudge
from .models import EvaluationCase, RetrievalMetrics


class QualityExperimentRunner:
    """Mentörün üç aşamalı ölçümünü mevcut üretim mimarisi üzerinde tekrarlar."""

    def __init__(
        self,
        data_dir: Path,
        cases: list[EvaluationCase],
        *,
        judge: OllamaJudge,
        generator_model: str = "qwen2.5:3b",
    ) -> None:
        """Veri kökü, altın set ve birbirinden farklı üretim/judge modellerini saklar."""

        self.data_dir = data_dir
        self.cases = cases
        self.judge = judge
        self.generator_model = generator_model

    def evaluate_chunks(
        self,
        *,
        batch_size: int = 1,
        cache_path: Path | None = None,
    ) -> dict[str, Any]:
        """Snapshot'taki bütün chunkları sergiler ve bağımsız LLM'e puanlatır."""

        chunks = self._snapshot_chunks()
        counters: dict[tuple[str, int], int] = {}
        records: list[dict[str, Any]] = []
        inputs: list[tuple[str, Chunk]] = []
        for chunk in chunks:
            key = (chunk.document, chunk.page)
            counters[key] = counters.get(key, 0) + 1
            chunk_id = f"{chunk.document}:p{chunk.page}:c{counters[key]}"
            records.append(
                {
                    "chunk_id": chunk_id,
                    "document": chunk.document,
                    "page": chunk.page,
                    "collection": chunk.collection,
                    "characters": len(chunk.text),
                    "estimated_tokens": round(len(chunk.text.split()) * 1.3),
                    "starts_with_word": bool(
                        chunk.text and (chunk.text[0].isalnum() or chunk.text[0] in "•-")
                    ),
                    "ends_with_terminal": chunk.text.rstrip().endswith(
                        (".", "!", "?", ":", "•")
                    ),
                    "text": chunk.text,
                }
            )
            inputs.append((chunk_id, chunk))
        cached: dict[str, dict[str, Any]] = {}
        if cache_path and cache_path.exists():
            cached = {
                item["chunk_id"]: item
                for item in json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(item, dict) and item.get("chunk_id")
            }
        judgments = []
        for position, (chunk_id, chunk) in enumerate(inputs, start=1):
            if chunk_id in cached:
                from .models import ChunkJudgeResult

                judgments.append(ChunkJudgeResult(**cached[chunk_id]))
                continue
            result = self.judge.judge_chunks(
                [(chunk_id, chunk)],
                batch_size=batch_size,
            )[0]
            # Tekil istemde biçim sorunu olursa yalnız o chunk'ı bir kez yeniden deneriz.
            if result.status != "completed":
                result = self.judge.judge_chunks([(chunk_id, chunk)], batch_size=1)[0]
            judgments.append(result)
            cached[chunk_id] = result.as_dict()
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(
                    json.dumps(list(cached.values()), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            print(
                f"Chunk judge ilerleme: {position}/{len(inputs)} "
                f"({result.status})",
                flush=True,
            )
        completed = [item for item in judgments if item.status == "completed"]
        dimensions = (
            "coherence",
            "self_containment",
            "boundary_quality",
            "size_fitness",
        )
        return {
            "method": {
                "judge_model": self.judge.model,
                "production_model": self.generator_model,
                "temperature": 0,
                "evaluated_population": "all_snapshot_chunks",
                "rubric": list(dimensions),
            },
            "summary": {
                "chunk_count": len(records),
                "judged_count": len(completed),
                "invalid_judge_outputs": len(judgments) - len(completed),
                "acceptable_count": sum(item.acceptable for item in completed),
                "acceptable_rate": round(
                    sum(item.acceptable for item in completed) / len(completed),
                    4,
                ) if completed else 0.0,
                "average_characters": round(
                    sum(item["characters"] for item in records) / len(records),
                    2,
                ),
                "dimension_means": {
                    field: round(
                        sum(getattr(item, field) for item in completed) / len(completed),
                        3,
                    ) if completed else 0.0
                    for field in dimensions
                },
            },
            "chunks": records,
            "judgments": [item.as_dict() for item in judgments],
        }

    def evaluate_answers(self, *, cache_path: Path | None = None) -> dict[str, Any]:
        """Pozitif altın sorulara verilen gerçek cevapları bağımsız modele denetletir."""

        engine = CMSRAGEngine(
            self.data_dir,
            model=self.generator_model,
            record_runtime_events=False,
        )
        engine.rebuild()
        snapshot_chunks = self._snapshot_chunks()
        cached: dict[str, dict[str, Any]] = {}
        if cache_path and cache_path.exists():
            cached = {
                item["case_id"]: item
                for item in json.loads(cache_path.read_text(encoding="utf-8"))
                if (
                    isinstance(item, dict)
                    and item.get("case_id")
                    and item.get("strict_pass") is True
                )
            }
        rows: list[dict[str, Any]] = []
        positives = [item for item in self.cases if item.data_available]
        for position, case in enumerate(positives, start=1):
            if case.id in cached:
                rows.append(cached[case.id])
                continue
            engine.clear_chat()
            started = perf_counter()
            answer, hits = engine.ask(case.question, case.scope)
            elapsed_ms = (perf_counter() - started) * 1000
            gold_evidence = "\n".join(
                chunk.text
                for chunk in snapshot_chunks
                if chunk.document == case.gold_document
                and chunk.page in case.gold_pages
            )
            sources = [
                {
                    "document": hit.chunk.document,
                    "page": hit.chunk.page,
                    "score": round(float(hit.score), 4),
                }
                for hit in hits
            ]
            gold_source_used = any(
                hit.chunk.document == case.gold_document
                and hit.chunk.page in case.gold_pages
                for hit in hits
            )
            result = self.judge.judge_answers(
                [{
                    "id": case.id,
                    "question": case.question,
                    "answer": answer,
                    "gold_evidence": gold_evidence,
                }],
                batch_size=1,
            )[0]
            row = {
                "case_id": case.id,
                "question": case.question,
                "answer": answer,
                "gold_document": case.gold_document,
                "gold_pages": list(case.gold_pages),
                "gold_source_used": gold_source_used,
                "sources": sources,
                "latency_ms": round(elapsed_ms, 3),
            }
            row.update(result.as_dict())
            row["strict_pass"] = bool(
                row["gold_source_used"]
                and result.status == "completed"
                and result.correct
            )
            rows.append(row)
            cached[case.id] = row
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(
                    json.dumps(list(cached.values()), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            print(
                f"Cevap judge ilerleme: {position}/{len(positives)} "
                f"({result.status})",
                flush=True,
            )
        return {
            "method": {
                "generator_model": self.generator_model,
                "judge_model": self.judge.model,
                "gold_evidence_only": True,
            },
            "summary": {
                "evaluated": len(rows),
                "judge_completed": sum(
                    row["status"] == "completed" for row in rows
                ),
                "judge_correct": sum(bool(row["correct"]) for row in rows),
                "strict_passed": sum(bool(row["strict_pass"]) for row in rows),
                "strict_success_rate": round(
                    sum(bool(row["strict_pass"]) for row in rows) / len(rows),
                    4,
                ) if rows else 0.0,
            },
            "cases": rows,
        }

    def compare_retrieval(
        self,
        chunk_sizes: tuple[int, ...] = (450, 900, 1350),
        *,
        limit: int = 6,
    ) -> dict[str, Any]:
        """BM25, dense, hybrid ve reranked hybrid yaklaşımlarını aynı altın sette ölçer."""

        positives = [case for case in self.cases if case.data_available]
        comparisons: list[dict[str, Any]] = []
        for chunk_size in chunk_sizes:
            chunks = self._build_chunks(chunk_size)
            started = perf_counter()
            retriever = HybridRetriever(chunks, enable_reranker=False)
            build_seconds = perf_counter() - started
            for approach, method in (
                ("bm25", retriever.lexical_search),
                ("faiss_dense", retriever.dense_search),
                ("hybrid_rrf", retriever.search),
            ):
                comparisons.append(
                    self._measure_retriever(
                        approach,
                        method,
                        positives,
                        chunks,
                        chunk_size,
                        build_seconds,
                        limit,
                    )
                )
            if chunk_size == 900:
                reranked = HybridRetriever(chunks, enable_reranker=True)
                comparisons.append(
                    self._measure_retriever(
                        "hybrid_rrf_reranker",
                        reranked.search,
                        positives,
                        chunks,
                        chunk_size,
                        build_seconds,
                        limit,
                    )
                )
                gated = HybridRetriever(
                    chunks,
                    enable_reranker=True,
                    reranker_mode="gate",
                )
                comparisons.append(
                    self._measure_retriever(
                        "hybrid_rrf_evidence_gate",
                        gated.search,
                        positives,
                        chunks,
                        chunk_size,
                        build_seconds,
                        limit,
                    )
                )
        return {
            "method": {
                "positive_cases": len(positives),
                "limit": limit,
                "chunk_sizes": list(chunk_sizes),
                "same_embedding_model": True,
            },
            "comparisons": comparisons,
        }

    def _measure_retriever(
        self,
        approach: str,
        search: Any,
        cases: list[EvaluationCase],
        chunks: list[Chunk],
        chunk_size: int,
        build_seconds: float,
        limit: int,
    ) -> dict[str, Any]:
        """Tek retrieval yaklaşımının Hit@K, MRR, terim kapsama ve gecikmesini ölçer."""

        metrics = RetrievalMetrics()
        term_rates: list[float] = []
        for case in cases:
            query = CMSQueryProcessor.expand(case.question)
            started = perf_counter()
            hits = search(query, limit=limit, scope=case.scope)
            latency_ms = (perf_counter() - started) * 1000
            rank = _gold_rank(case, hits)
            metrics.observe(rank, latency_ms)
            evidence = "\n".join(hit.chunk.text.lower() for hit in hits)
            term_rates.append(
                sum(
                    term.lower() in evidence
                    for term in case.expected_evidence_terms
                ) / len(case.expected_evidence_terms)
            )
        return {
            "approach": approach,
            "chunk_size": chunk_size,
            "overlap": max(60, round(chunk_size / 6)),
            "chunk_count": len(chunks),
            "build_seconds": round(build_seconds, 3),
            "mean_term_coverage": round(sum(term_rates) / len(term_rates), 4),
            **metrics.as_dict(),
            "status": "completed",
        }

    def _build_chunks(self, chunk_size: int) -> list[Chunk]:
        """Manifestteki aynı PDF'leri verilen boyutta yeniden chunk'layarak deney kümesi kurar."""

        manifest = load_manifest(self.data_dir / "knowledge_base")
        ingestor = PDFIngestor(
            chunk_size=chunk_size,
            overlap=max(60, round(chunk_size / 6)),
        )
        chunks: list[Chunk] = []
        for record in manifest["sources"]:
            path = (self.data_dir / record["path"]).resolve()
            loaded = ingestor.load(
                [path],
                collection=record["collection"],
                authority=record["authority"],
            )
            chunks.extend(
                Chunk(
                    text=item.text,
                    document=item.document,
                    page=item.page,
                    source_path=item.source_path,
                    collection=item.collection,
                    authority=item.authority,
                    source_url=record.get("source_url", ""),
                )
                for item in loaded
            )
        return chunks

    def _snapshot_chunks(self) -> list[Chunk]:
        """Üretim snapshot'ındaki gerçek chunkları sırasını koruyarak yükler."""

        payload = json.loads(
            (
                self.data_dir / "knowledge_base" / "snapshot" / "snapshot.json"
            ).read_text(encoding="utf-8")
        )
        return [Chunk(**item) for item in payload["chunks"]]


def _gold_rank(case: EvaluationCase, hits: list[Any]) -> int | None:
    """İlk doğru belge/sayfa eşleşmesinin bir tabanlı sırasını döndürür."""

    for rank, hit in enumerate(hits, start=1):
        if (
            hit.chunk.document == case.gold_document
            and hit.chunk.page in case.gold_pages
        ):
            return rank
    return None
