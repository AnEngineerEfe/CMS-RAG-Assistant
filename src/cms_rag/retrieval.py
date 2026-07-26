from __future__ import annotations

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
        self._embedder = SentenceTransformer("BAAI/bge-small-en-v1.5", local_files_only=True)
        self._index = faiss.IndexFlatIP(self._embedder.get_sentence_embedding_dimension())
        vectors = self._embedder.encode([chunk.text for chunk in chunks], normalize_embeddings=True)
        self._index.add(np.asarray(vectors, dtype=np.float32))
        self._tokens = [self._tokenise(chunk.text) for chunk in chunks]
        self._bm25 = BM25Okapi(self._tokens)
        try:
            self._reranker = CrossEncoder("BAAI/bge-reranker-base", local_files_only=True)
        except Exception:
            self._reranker = None

    def search(self, query: str, limit: int = 4) -> list[SearchHit]:
        candidate_count = min(len(self.chunks), 20)
        if candidate_count == 0:
            return []
        query_vector = self._embedder.encode([query], normalize_embeddings=True)
        _, semantic_ids = self._index.search(np.asarray(query_vector, dtype=np.float32), candidate_count)
        lexical_scores = self._bm25.get_scores(self._tokenise(query))
        lexical_ids = np.argsort(lexical_scores)[::-1][:candidate_count]
        fused: dict[int, float] = {}
        for ranking in (semantic_ids[0].tolist(), lexical_ids.tolist()):
            for rank, item_id in enumerate(ranking, start=1):
                fused[item_id] = fused.get(item_id, 0.0) + 1 / (60 + rank)
        candidate_ids = sorted(fused, key=fused.get, reverse=True)[:candidate_count]
        if self._reranker:
            scores = self._reranker.predict([(query, self.chunks[item_id].text) for item_id in candidate_ids])
            ordered = sorted(zip(scores, candidate_ids), key=lambda pair: float(pair[0]), reverse=True)
            return [SearchHit(self.chunks[item_id], float(score)) for score, item_id in ordered[:limit]]
        return [SearchHit(self.chunks[item_id], fused[item_id]) for item_id in candidate_ids[:limit]]

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9]{2,}", text.lower())
