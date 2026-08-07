"""Aynı embeddingleri gerçek PostgreSQL pgvector üzerinde ölçen deney adaptörü."""

from __future__ import annotations

from time import perf_counter
from typing import Any

import numpy as np

from ..domain.models import Chunk


class PgVectorUnavailableError(RuntimeError):
    """PostgreSQL, pgvector uzantısı veya sürücü hazır olmadığında açık hata taşır."""


class PgVectorBenchmark:
    """Geçici tabloda exact cosine araması yaparak FAISS ile eş koşul oluşturur."""

    def __init__(self, dsn: str) -> None:
        """Yalnız değerlendirme veritabanına ait bağlantı dizesini saklar."""

        self.dsn = dsn

    def run(
        self,
        chunks: list[Chunk],
        vectors: np.ndarray,
        queries: list[tuple[str, str, np.ndarray]],
        *,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        """Vektörleri geçici tabloya yükler ve sayfa-tekilleştirilmiş sorguları ölçer."""

        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as error:
            raise PgVectorUnavailableError(
                "pgvector deneyi için psycopg ve pgvector paketleri gereklidir."
            ) from error
        if len(chunks) != len(vectors):
            raise ValueError("Chunk ve embedding sayıları eşit olmalıdır.")
        try:
            with psycopg.connect(self.dsn) as connection:
                extension = connection.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                ).fetchone()
                if extension is None:
                    raise PgVectorUnavailableError(
                        "Bağlanılan veritabanında vector uzantısı etkin değil."
                    )
                register_vector(connection)
                dimension = int(vectors.shape[1])
                connection.execute(
                    f"""
                    CREATE TEMP TABLE cms_rag_eval_vectors (
                        item_id integer PRIMARY KEY,
                        document text NOT NULL,
                        page integer NOT NULL,
                        collection text NOT NULL,
                        embedding vector({dimension}) NOT NULL
                    ) ON COMMIT DROP
                    """
                )
                rows = [
                    (
                        item_id,
                        chunk.document,
                        chunk.page,
                        chunk.collection,
                        vector,
                    )
                    for item_id, (chunk, vector) in enumerate(zip(chunks, vectors))
                ]
                with connection.cursor() as cursor:
                    cursor.executemany(
                        """
                        INSERT INTO cms_rag_eval_vectors
                        (item_id, document, page, collection, embedding)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        rows,
                    )
                output = [
                    self._query(connection, case_id, scope, vector, limit)
                    for case_id, scope, vector in queries
                ]
                return output
        except Exception as error:
            raise PgVectorUnavailableError(
                f"Gerçek pgvector deneyi çalıştırılamadı: {error}"
            ) from error

    @staticmethod
    def _query(
        connection: Any,
        case_id: str,
        scope: str,
        vector: np.ndarray,
        limit: int,
    ) -> dict[str, Any]:
        """Tek sorguyu exact cosine ile çalıştırıp süre ve kaynak sırasını döndürür."""

        started = perf_counter()
        records = connection.execute(
            """
            WITH page_best AS (
                SELECT DISTINCT ON (document, page)
                       item_id, document, page, collection,
                       1 - (embedding <=> %s) AS similarity
                FROM cms_rag_eval_vectors
                WHERE (%s = 'all' OR collection = %s)
                ORDER BY document, page, embedding <=> %s
            )
            SELECT item_id, document, page, collection, similarity
            FROM page_best
            ORDER BY similarity DESC
            LIMIT %s
            """,
            (vector, scope, scope, vector, limit),
        ).fetchall()
        return {
            "case_id": case_id,
            "latency_ms": round((perf_counter() - started) * 1000, 3),
            "hits": [
                {
                    "item_id": int(record[0]),
                    "document": record[1],
                    "page": int(record[2]),
                    "collection": record[3],
                    "score": round(float(record[4]), 6),
                }
                for record in records
            ],
        }
