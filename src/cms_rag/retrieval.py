from __future__ import annotations

import os
import re

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

from .models import Chunk, SearchHit


class HybridRetriever:
    """In-memory hybrid search with RRF fusion and a local cross-encoder reranker."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        offline = os.getenv("CMS_RAG_OFFLINE", "").strip().lower() in {"1", "true", "yes"}
        self._embedder = SentenceTransformer(
            "BAAI/bge-small-en-v1.5",
            local_files_only=offline,
        )
        self._index = faiss.IndexFlatIP(self._embedder.get_embedding_dimension())
        vectors = self._embedder.encode([chunk.text for chunk in chunks], normalize_embeddings=True)
        self._index.add(np.asarray(vectors, dtype=np.float32))
        self._tokens = [self._tokenise(chunk.text) for chunk in chunks]
        self._bm25 = BM25Okapi(self._tokens)
        try:
            self._reranker = CrossEncoder(
                "BAAI/bge-reranker-base",
                local_files_only=offline,
            )
        except Exception:
            self._reranker = None

    def search(self, query: str, limit: int = 4, scope: str = "all") -> list[SearchHit]:
        allowed_ids = [
            item_id for item_id, chunk in enumerate(self.chunks)
            if scope == "all" or chunk.collection == scope
        ]
        candidate_count = min(len(allowed_ids), 20)
        if candidate_count == 0:
            return []
        query_vector = self._embedder.encode([query], normalize_embeddings=True)
        _, semantic_all = self._index.search(np.asarray(query_vector, dtype=np.float32), len(self.chunks))
        allowed = set(allowed_ids)
        semantic_ids = [item_id for item_id in semantic_all[0].tolist() if item_id in allowed][:candidate_count]
        lexical_scores = self._bm25.get_scores(self._tokenise(query))
        lexical_ids = sorted(allowed_ids, key=lambda item_id: lexical_scores[item_id], reverse=True)[:candidate_count]
        fused: dict[int, float] = {}
        for ranking in (semantic_ids, lexical_ids):
            for rank, item_id in enumerate(ranking, start=1):
                fused[item_id] = fused.get(item_id, 0.0) + 1 / (60 + rank)
        candidate_ids = sorted(fused, key=fused.get, reverse=True)[:candidate_count]
        if self._reranker:
            scores = self._reranker.predict([(query, self.chunks[item_id].text) for item_id in candidate_ids])
            ordered = sorted(zip(scores, candidate_ids), key=lambda pair: float(pair[0]), reverse=True)
            return self._deduplicate_by_page(
                [SearchHit(self.chunks[item_id], float(score)) for score, item_id in ordered], limit
            )
        return self._deduplicate_by_page(
            [SearchHit(self.chunks[item_id], fused[item_id]) for item_id in candidate_ids], limit
        )

    @staticmethod
    def _deduplicate_by_page(hits: list[SearchHit], limit: int) -> list[SearchHit]:
        """Merge complementary chunks from one page into one evidence item."""
        unique: list[SearchHit] = []
        positions: dict[tuple[str, int], int] = {}
        for hit in hits:
            key = (hit.chunk.source_path, hit.chunk.page)
            if key not in positions:
                positions[key] = len(unique)
                unique.append(hit)
                continue
            position = positions[key]
            current = unique[position]
            if hit.chunk.text not in current.chunk.text:
                merged = Chunk(
                    text=f"{current.chunk.text}\n{hit.chunk.text}",
                    document=current.chunk.document,
                    page=current.chunk.page,
                    source_path=current.chunk.source_path,
                    collection=current.chunk.collection,
                    authority=current.chunk.authority,
                    source_url=current.chunk.source_url,
                )
                unique[position] = SearchHit(merged, max(current.score, hit.score))
        return unique[:limit]

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        return re.findall(r"\b[\w-]{2,}\b", text.lower(), flags=re.UNICODE)
