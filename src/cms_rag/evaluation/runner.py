"""Altın soruları üretim retrieval hattında çalıştırıp ölçülebilir rapor üretir."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from time import perf_counter
from typing import Any

from ..application import CMSRAGEngine
from ..domain import CMSQueryProcessor
from .models import (
    BenchmarkCaseResult,
    ConfusionMatrix,
    EvaluationCase,
    RetrievalMetrics,
)


class BenchmarkRunner:
    """Üretim snapshot'ını kullanarak altın kaynak, terim ve karar doğruluğunu ölçer."""

    def __init__(self, data_dir: Path, *, limit: int = 6) -> None:
        """Uygulama motorunu ve Hit@K için kullanılacak sonuç sınırını hazırlar."""

        self.engine = CMSRAGEngine(data_dir)
        self.limit = limit

    def run(self, cases: list[EvaluationCase]) -> dict[str, Any]:
        """Tüm vakaları çalıştırıp confusion matrix, Hit@K, MRR ve kırılımları döndürür."""

        indexed_chunks = self.engine.rebuild()
        if self.engine.retriever is None:
            raise RuntimeError("Değerlendirilecek retrieval indeksi bulunamadı.")
        confusion = ConfusionMatrix()
        retrieval = RetrievalMetrics()
        results: list[BenchmarkCaseResult] = []
        for case in cases:
            query = CMSQueryProcessor.expand(case.question)
            started = perf_counter()
            hits = self.engine.retriever.search(
                query,
                limit=self.limit,
                scope=case.scope,
            )
            latency_ms = (perf_counter() - started) * 1000
            predicted = self.engine.retriever.is_answerable(query, hits)
            cell = confusion.observe(case.data_available, predicted)
            rank = self._gold_rank(case, hits)
            context = "\n".join(hit.chunk.text.lower() for hit in hits)
            matched = tuple(
                term
                for term in case.expected_evidence_terms
                if term.lower() in context
            )
            if case.data_available:
                retrieval.observe(rank, latency_ms)
                passed = (
                    predicted
                    and rank is not None
                    and len(matched) == len(case.expected_evidence_terms)
                )
            else:
                passed = not predicted
            results.append(
                BenchmarkCaseResult(
                    case_id=case.id,
                    category=case.category,
                    question=case.question,
                    query_type=case.query_type,
                    difficulty=case.difficulty,
                    actual_data_available=case.data_available,
                    predicted_answerable=predicted,
                    confusion_cell=cell,
                    gold_rank=rank,
                    evidence_terms_matched=matched,
                    evidence_terms_expected=case.expected_evidence_terms,
                    retrieval_passed=passed,
                    latency_ms=round(latency_ms, 3),
                    sources=tuple(
                        {
                            "document": hit.chunk.document,
                            "page": hit.chunk.page,
                            "score": round(float(hit.score), 4),
                        }
                        for hit in hits
                    ),
                )
            )
        return {
            "schema_version": 1,
            "dataset_cases": len(cases),
            "indexed_chunks": indexed_chunks,
            "snapshot_loaded": self.engine.snapshot_loaded,
            "passed": sum(item.retrieval_passed for item in results),
            "failed": sum(not item.retrieval_passed for item in results),
            "confusion_matrix": confusion.as_dict(),
            "retrieval": retrieval.as_dict(),
            "breakdowns": self._breakdowns(results),
            "results": [item.as_dict() for item in results],
        }

    @staticmethod
    def _gold_rank(case: EvaluationCase, hits: list[Any]) -> int | None:
        """Beklenen belge ve sayfanın sonuçlar içindeki bir tabanlı ilk sırasını bulur."""

        if not case.data_available:
            return None
        for rank, hit in enumerate(hits, start=1):
            if (
                hit.chunk.document == case.gold_document
                and hit.chunk.page in case.gold_pages
            ):
                return rank
        return None

    @staticmethod
    def _breakdowns(results: list[BenchmarkCaseResult]) -> dict[str, Any]:
        """Başarıyı kategori, sorgu türü ve zorluk kırılımlarında özetler."""

        groups: dict[str, dict[str, list[bool]]] = {
            "category": defaultdict(list),
            "query_type": defaultdict(list),
            "difficulty": defaultdict(list),
        }
        for item in results:
            groups["category"][item.category].append(item.retrieval_passed)
            groups["query_type"][item.query_type].append(item.retrieval_passed)
            groups["difficulty"][item.difficulty].append(item.retrieval_passed)
        return {
            dimension: {
                name: {
                    "passed": sum(values),
                    "total": len(values),
                    "rate": round(sum(values) / len(values), 4),
                }
                for name, values in sorted(entries.items())
            }
            for dimension, entries in groups.items()
        } | {
            "confusion_cells": dict(
                sorted(Counter(item.confusion_cell for item in results).items())
            )
        }
