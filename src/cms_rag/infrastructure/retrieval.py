"""Semantik ve sözcüksel aramayı yerel yeniden sıralamayla birleştirir."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

from ..domain.models import Chunk, SearchHit


EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL = "BAAI/bge-reranker-base"
SNAPSHOT_SCHEMA_VERSION = 1


@lru_cache(maxsize=2)
def _load_embedder(offline: bool) -> SentenceTransformer:
    """Sorgu embedding modelini süreç boyunca tek örnek olarak bellekte tutar."""

    return SentenceTransformer(EMBEDDING_MODEL, local_files_only=offline)


@lru_cache(maxsize=2)
def _load_reranker(offline: bool) -> CrossEncoder | None:
    """Yerel reranker modelini bir kez yükler; mevcut değilse RRF sonucunu korur."""

    try:
        return CrossEncoder(RERANKER_MODEL, local_files_only=offline)
    except Exception:
        return None


class HybridRetriever:
    """Bellek içi FAISS + BM25 aramasını RRF ve cross-encoder ile birleştirir."""

    def __init__(
        self,
        chunks: list[Chunk],
        *,
        initial_vectors: np.ndarray | None = None,
        enable_reranker: bool = True,
        reranker_mode: str = "gate",
    ) -> None:
        """Hazır vektörleri kullanır ve yalnız eksik chunk embeddinglerini hesaplar."""

        if reranker_mode not in {"rank", "gate"}:
            raise ValueError("Reranker modu 'rank' veya 'gate' olmalıdır.")
        self.chunks = chunks
        self.reranker_mode = reranker_mode
        offline = os.getenv("CMS_RAG_OFFLINE", "1").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        self._embedder = _load_embedder(offline)
        dimension = self._embedder.get_embedding_dimension()
        prepared_count = len(initial_vectors) if initial_vectors is not None else 0
        if prepared_count > len(chunks):
            raise ValueError("Snapshot embedding sayısı chunk sayısını aşamaz.")
        vectors = (
            np.asarray(initial_vectors, dtype=np.float32)
            if initial_vectors is not None
            else np.empty((0, dimension), dtype=np.float32)
        )
        if prepared_count < len(chunks):
            additions = self._embedder.encode(
                [chunk.text for chunk in chunks[prepared_count:]],
                normalize_embeddings=True,
            )
            vectors = np.concatenate(
                [vectors, np.asarray(additions, dtype=np.float32)],
                axis=0,
            )
        self._vectors = vectors
        self._index = faiss.IndexFlatIP(dimension)
        self._index.add(self._vectors)
        self._tokens = [self._tokenise(chunk.text) for chunk in chunks]
        self._bm25 = BM25Okapi(self._tokens)
        self._reranker = _load_reranker(offline) if enable_reranker else None

    @classmethod
    def from_snapshot(
        cls,
        snapshot_dir: Path,
        *,
        supplemental_chunks: list[Chunk] | None = None,
        enable_reranker: bool = True,
        reranker_mode: str = "gate",
    ) -> "HybridRetriever":
        """Önceden hazırlanmış chunk/embeddingleri yükleyip yalnız ek belgeleri işler."""

        metadata = json.loads(
            (snapshot_dir / "snapshot.json").read_text(encoding="utf-8")
        )
        if metadata.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("Desteklenmeyen bilgi tabanı snapshot şeması.")
        if metadata.get("embedding_model") != EMBEDDING_MODEL:
            raise ValueError("Snapshot farklı bir embedding modeliyle hazırlanmış.")
        chunks = [Chunk(**item) for item in metadata["chunks"]]
        vectors = np.load(snapshot_dir / "embeddings.npy", allow_pickle=False)
        chunks.extend(supplemental_chunks or [])
        return cls(
            chunks,
            initial_vectors=vectors,
            enable_reranker=enable_reranker,
            reranker_mode=reranker_mode,
        )

    def save_snapshot(
        self,
        snapshot_dir: Path,
        *,
        source_hashes: list[str],
    ) -> None:
        """Chunk ve embeddingleri çalışma-anı araştırması gerektirmeyen artifact'e yazar."""

        snapshot_dir.mkdir(parents=True, exist_ok=True)
        metadata = {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "embedding_model": EMBEDDING_MODEL,
            "source_sha256": sorted(source_hashes),
            "chunk_count": len(self.chunks),
            "chunks": [asdict(chunk) for chunk in self.chunks],
        }
        temporary_json = snapshot_dir / ".snapshot.json.tmp"
        temporary_vectors = snapshot_dir / ".embeddings.npy.tmp"
        temporary_json.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with temporary_vectors.open("wb") as stream:
            np.save(stream, self._vectors, allow_pickle=False)
        temporary_json.replace(snapshot_dir / "snapshot.json")
        temporary_vectors.replace(snapshot_dir / "embeddings.npy")

    @staticmethod
    def snapshot_source_hashes(snapshot_dir: Path) -> set[str]:
        """Snapshot'a önceden alınmış dosya hashlerini ek belge ayrımı için döndürür."""

        metadata_path = snapshot_dir / "snapshot.json"
        if not metadata_path.exists():
            return set()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return set(metadata.get("source_sha256", []))

    @staticmethod
    def file_sha256(path: Path) -> str:
        """Bir kaynak dosyanın snapshot kimliği olan SHA-256 özetini üretir."""

        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def search(
        self,
        query: str,
        limit: int = 4,
        scope: str = "all",
    ) -> list[SearchHit]:
        """Kapsama uyan adayları iki aramayla bulur, birleştirir ve yeniden sıralar."""

        allowed_ids = [
            item_id
            for item_id, chunk in enumerate(self.chunks)
            if scope == "all" or chunk.collection == scope
        ]
        candidate_count = min(len(allowed_ids), 12)
        if candidate_count == 0:
            return []
        query_vector = self._embedder.encode([query], normalize_embeddings=True)
        _, semantic_all = self._index.search(
            np.asarray(query_vector, dtype=np.float32),
            len(self.chunks),
        )
        allowed = set(allowed_ids)
        semantic_ids = [
            item_id
            for item_id in semantic_all[0].tolist()
            if item_id in allowed
        ][:candidate_count]
        lexical_scores = self._bm25.get_scores(self._tokenise(query))
        lexical_ids = sorted(
            allowed_ids,
            key=lambda item_id: lexical_scores[item_id],
            reverse=True,
        )[:candidate_count]
        fused: dict[int, float] = {}
        for ranking in (semantic_ids, lexical_ids):
            for rank, item_id in enumerate(ranking, start=1):
                fused[item_id] = fused.get(item_id, 0.0) + 1 / (60 + rank)
        candidate_ids = sorted(fused, key=fused.get, reverse=True)[:candidate_count]
        if self._reranker:
            if self.reranker_mode == "gate":
                base_hits = self._deduplicate_by_page(
                    [
                        SearchHit(self.chunks[item_id], fused[item_id])
                        for item_id in candidate_ids
                    ],
                    limit,
                )
                gate_count = min(2, len(base_hits))
                gate_scores = self._reranker.predict(
                    [
                        (query, hit.chunk.text)
                        for hit in base_hits[:gate_count]
                    ]
                )
                scored_prefix = [
                    SearchHit(hit.chunk, float(gate_scores[position]))
                    for position, hit in enumerate(base_hits[:gate_count])
                ]
                # Gate modu yalnız ilk iki adayı pahalı çapraz kodlayıcıdan geçirir.
                # Bu skorları yalnız cevaplanabilirlikte kullanıp RRF sırasını korumak,
                # daha güçlü kanıtı ikinci sırada bırakarak küçük modelin cevabını bozuyordu.
                # Karşılaştırılabilir skorlu ön eki sıralar, ölçülmemiş kuyruğu koruruz.
                return self._order_gate_prefix(
                    scored_prefix,
                    base_hits[gate_count:],
                )
            scores = self._reranker.predict(
                [(query, self.chunks[item_id].text) for item_id in candidate_ids]
            )
            ordered = sorted(
                zip(scores, candidate_ids),
                key=lambda pair: float(pair[0]),
                reverse=True,
            )
            reranked = self._deduplicate_by_page(
                [
                    SearchHit(self.chunks[item_id], float(score))
                    for score, item_id in ordered
                ],
                limit,
            )
            score_by_id = {
                item_id: float(score) for score, item_id in zip(scores, candidate_ids)
            }
            lexical_guards = [
                SearchHit(self.chunks[item_id], score_by_id[item_id])
                for item_id in lexical_ids[:2]
                if lexical_scores[item_id] > 0 and item_id in score_by_id
            ]
            return self._preserve_lexical_pages(reranked, lexical_guards, limit)
        return self._deduplicate_by_page(
            [
                SearchHit(self.chunks[item_id], fused[item_id])
                for item_id in candidate_ids
            ],
            limit,
        )

    def dense_search(
        self,
        query: str,
        limit: int = 4,
        scope: str = "all",
    ) -> list[SearchHit]:
        """FAISS cosine benzerliğini tek başına ölçmek için sayfa-tekilleştirilmiş sonuç döndürür."""

        allowed = {
            item_id
            for item_id, chunk in enumerate(self.chunks)
            if scope == "all" or chunk.collection == scope
        }
        if not allowed:
            return []
        query_vector = self._embedder.encode([query], normalize_embeddings=True)
        scores, identifiers = self._index.search(
            np.asarray(query_vector, dtype=np.float32),
            len(self.chunks),
        )
        hits = [
            SearchHit(self.chunks[item_id], float(score))
            for score, item_id in zip(scores[0], identifiers[0])
            if item_id in allowed
        ]
        return self._deduplicate_by_page(hits, limit)

    def lexical_search(
        self,
        query: str,
        limit: int = 4,
        scope: str = "all",
    ) -> list[SearchHit]:
        """BM25 sözcüksel aramayı diğer bileşenlerden bağımsız karşılaştırır."""

        allowed_ids = [
            item_id
            for item_id, chunk in enumerate(self.chunks)
            if scope == "all" or chunk.collection == scope
        ]
        scores = self._bm25.get_scores(self._tokenise(query))
        ordered = sorted(allowed_ids, key=lambda item_id: scores[item_id], reverse=True)
        hits = [
            SearchHit(self.chunks[item_id], float(scores[item_id]))
            for item_id in ordered
            if scores[item_id] > 0
        ]
        return self._deduplicate_by_page(hits, limit)

    def is_answerable(
        self,
        query: str,
        hits: list[SearchHit],
        *,
        reranker_threshold: float = 0.03,
    ) -> bool:
        """En güçlü kanıtın soruyu gerçekten destekleyip desteklemediğini tutarlı biçimde ölçer."""

        if not hits:
            return False
        from ..domain.query import CMSQueryProcessor

        if CMSQueryProcessor.requests_restricted_information(query):
            return False
        query_terms = self._content_terms(query)
        evidence_terms = set(
            self._tokenise(" ".join(hit.chunk.text for hit in hits))
        )
        required_terms = CMSQueryProcessor.required_attribute_terms(query)
        if required_terms and not any(
            term in evidence_terms for term in required_terms
        ):
            return False
        if self._reranker is not None:
            if max(hit.score for hit in hits[:2]) < reranker_threshold:
                if self.reranker_mode != "gate":
                    return False
                overlap = query_terms & evidence_terms
                return (
                    len(overlap) >= 2
                    or bool(query_terms)
                    and len(overlap) / len(query_terms) >= 0.5
                )

            # Cross-encoder alan benzerliğini iyi ölçer; ancak kaynakta bulunmayan bir
            # nitelik (işletim sistemi, frekans vb.) sorulduğunda yalnızca yüksek alan
            # benzerliği yanlış pozitif üretebilir. Bu nedenle karar, ayırt edici sorgu
            # terimlerinden en az birinin kanıtta gerçekten görülmesini de gerektirir.
            return bool(query_terms & evidence_terms)

        # Reranker yerelde bulunamazsa yalnız RRF puanına güvenilmez. Sorgunun ayırt
        # edici terimlerinin kanıt metninde yeterli oranda bulunması güvenli yedektir.
        ignored = {
            "advent", "cms", "sistem", "sistemi", "system", "nedir", "nelerdir", "nasil",
            "nasıl", "yapar", "hakkinda", "hakkında", "icin", "için", "bir",
            "the", "what", "how", "does", "and", "ve",
        }
        query_terms = {
            token for token in self._tokenise(query)
            if token not in ignored and len(token) > 2
        }
        if not query_terms:
            return False
        evidence_terms = set(self._tokenise(" ".join(hit.chunk.text for hit in hits[:2])))
        overlap = query_terms & evidence_terms
        return len(overlap) >= 2 or len(overlap) / len(query_terms) >= 0.5

    @classmethod
    def _content_terms(cls, query: str) -> set[str]:
        """Cevaplanabilirlik kararında alan adından daha ayırt edici terimleri çıkarır."""

        ignored = {
            "advent", "cms", "sistem", "system", "nedir", "nelerdir", "nasil",
            "nasıl", "hangi", "kullanir", "kullanır", "yapar", "saglar", "sağlar",
            "hakkinda", "hakkında", "icin", "için", "bir", "the", "what", "how",
            "does", "and", "ve", "ile", "olarak", "yonetilir", "yönetilir",
        }
        return {
            token
            for token in cls._tokenise(query)
            if token not in ignored and len(token) > 2
        }

    @staticmethod
    def _order_gate_prefix(
        scored_prefix: list[SearchHit],
        unscored_tail: list[SearchHit],
    ) -> list[SearchHit]:
        """Çapraz kodlayıcıyla ölçülen ön eki sıralar; RRF kuyruğunu değiştirmez."""

        return sorted(
            scored_prefix,
            key=lambda hit: hit.score,
            reverse=True,
        ) + list(unscored_tail)

    @staticmethod
    def _deduplicate_by_page(
        hits: list[SearchHit],
        limit: int,
    ) -> list[SearchHit]:
        """Aynı sayfadaki tamamlayıcı parçaları tek kanıt kartında birleştirir."""

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
                unique[position] = SearchHit(
                    merged,
                    max(current.score, hit.score),
                )
        return unique[:limit]

    @staticmethod
    def _preserve_lexical_pages(
        reranked: list[SearchHit],
        lexical_guards: list[SearchHit],
        limit: int,
    ) -> list[SearchHit]:
        """Reranker'ın kısa ama tam terim eşleşmeli kanıt sayfalarını silmesini önler."""

        selected = list(reranked[:limit])
        selected_pages = {
            (hit.chunk.source_path, hit.chunk.page) for hit in selected
        }
        for guard in lexical_guards:
            key = (guard.chunk.source_path, guard.chunk.page)
            if key in selected_pages:
                continue
            if len(selected) >= limit:
                removed = selected.pop()
                selected_pages.discard(
                    (removed.chunk.source_path, removed.chunk.page)
                )
            selected.append(guard)
            selected_pages.add(key)
        return selected

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        """BM25 için Unicode uyumlu, en az iki karakterli sözcükleri çıkarır."""

        return re.findall(r"\b[\w-]{2,}\b", text.lower(), flags=re.UNICODE)
