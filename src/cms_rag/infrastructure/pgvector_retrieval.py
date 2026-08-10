"""FAISS yoğun aramasını gerçek PostgreSQL pgvector ile değiştiren hibrit adaptör."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from ..domain.models import Chunk
from .retrieval import EMBEDDING_MODEL, SNAPSHOT_SCHEMA_VERSION, HybridRetriever


class PgVectorRetrieverError(RuntimeError):
    """Pgvector sürücüsü, bağlantısı veya uzantısı hazır olmadığında açık hata taşır."""


class PgVectorHybridRetriever(HybridRetriever):
    """Pgvector yoğun adaylarını BM25, RRF ve aynı reranker hattıyla birleştirir."""

    def __init__(
        self,
        chunks: list[Chunk],
        *,
        dsn: str,
        initial_vectors: np.ndarray,
        enable_reranker: bool = True,
        reranker_mode: str = "gate",
    ) -> None:
        """Hazır embeddingleri yükler ve bağlantıya özel geçici pgvector tablosu kurar."""

        super().__init__(
            chunks,
            initial_vectors=initial_vectors,
            enable_reranker=enable_reranker,
            reranker_mode=reranker_mode,
        )
        self._connection: Any | None = None
        self._open_pgvector(dsn)

    @classmethod
    def from_snapshot(
        cls,
        snapshot_dir: Path,
        *,
        dsn: str,
        supplemental_chunks: list[Chunk] | None = None,
        enable_reranker: bool = True,
        reranker_mode: str = "gate",
    ) -> "PgVectorHybridRetriever":
        """Sürümlü snapshot’ı aynı chunk sırası ve vektörlerle pgvector’a hazırlar."""

        metadata = json.loads(
            (snapshot_dir / "snapshot.json").read_text(encoding="utf-8")
        )
        if metadata.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("Desteklenmeyen bilgi tabanı snapshot şeması.")
        if metadata.get("embedding_model") != EMBEDDING_MODEL:
            raise ValueError("Snapshot farklı bir embedding modeliyle hazırlanmış.")
        chunks = [Chunk(**item) for item in metadata["chunks"]]
        vectors = np.load(snapshot_dir / "embeddings.npy", allow_pickle=False)
        additions = supplemental_chunks or []
        if additions:
            # Üst sınıf yalnız eksik ek belgeleri embeddingleyerek snapshot sırasını korur.
            return cls(
                chunks + additions,
                dsn=dsn,
                initial_vectors=vectors,
                enable_reranker=enable_reranker,
                reranker_mode=reranker_mode,
            )
        return cls(
            chunks,
            dsn=dsn,
            initial_vectors=vectors,
            enable_reranker=enable_reranker,
            reranker_mode=reranker_mode,
        )

    def close(self) -> None:
        """Geçici tabloyu taşıyan PostgreSQL oturumunu güvenli biçimde kapatır."""

        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _open_pgvector(self, dsn: str) -> None:
        """Uzantıyı doğrular ve tüm chunk embeddinglerini geçici tabloya yükler."""

        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as error:
            raise PgVectorRetrieverError(
                "Pgvector retrieval için psycopg ve pgvector paketleri gereklidir."
            ) from error
        try:
            connection = psycopg.connect(dsn)
            extension = connection.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
            if extension is None:
                connection.close()
                raise PgVectorRetrieverError(
                    "Bağlanılan veritabanında vector uzantısı etkin değil."
                )
            register_vector(connection)
            dimension = int(self._vectors.shape[1])
            connection.execute(
                f"""
                CREATE TEMP TABLE cms_rag_lineage_vectors (
                    item_id integer PRIMARY KEY,
                    collection text NOT NULL,
                    embedding vector({dimension}) NOT NULL
                )
                """
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO cms_rag_lineage_vectors (item_id, collection, embedding)
                    VALUES (%s, %s, %s)
                    """,
                    [
                        (item_id, chunk.collection, vector)
                        for item_id, (chunk, vector) in enumerate(
                            zip(self.chunks, self._vectors)
                        )
                    ],
                )
            self._connection = connection
        except PgVectorRetrieverError:
            raise
        except Exception as error:
            raise PgVectorRetrieverError(
                f"Gerçek pgvector retrieval hazırlanamadı: {error}"
            ) from error

    def _semantic_candidate_ids(
        self,
        query: str,
        allowed_ids: list[int],
        candidate_count: int,
    ) -> list[int]:
        """Sorgu embeddingini pgvector exact-cosine ile arayıp chunk kimliklerini döndürür."""

        if self._connection is None:
            raise PgVectorRetrieverError("Pgvector bağlantısı kapalı.")
        vector = np.asarray(
            self._embedder.encode([query], normalize_embeddings=True)[0],
            dtype=np.float32,
        )
        records = self._connection.execute(
            """
            SELECT item_id
            FROM cms_rag_lineage_vectors
            WHERE item_id = ANY(%s)
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (allowed_ids, vector, candidate_count),
        ).fetchall()
        return [int(record[0]) for record in records]
