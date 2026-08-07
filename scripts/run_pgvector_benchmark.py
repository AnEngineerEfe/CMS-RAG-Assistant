"""FAISS ve gerçek PostgreSQL pgvector exact-cosine sonuçlarını aynı vektörlerle kıyaslar."""

from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
from time import perf_counter

import numpy as np

from src.cms_rag.domain import CMSQueryProcessor, SearchHit
from src.cms_rag.evaluation import (
    PgVectorBenchmark,
    RetrievalMetrics,
    load_cases,
)
from src.cms_rag.infrastructure import HybridRetriever


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """İki backend'i aynı chunk, embedding, sorgu ve K değeriyle çalıştırır."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dsn",
        default=os.getenv("PGVECTOR_DSN"),
        help="Tam bağlantı dizesi. Verilmezse yerel bağlantı alanları kullanılır.",
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="cms_rag_eval")
    parser.add_argument("--user", default="postgres")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluation" / "results" / "pgvector-latest.json",
    )
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument(
        "--json-stdout",
        action="store_true",
        help="Özet yerine tam JSON raporunu terminale de yazdırır.",
    )
    args = parser.parse_args()

    dsn = args.dsn or _local_dsn(args)

    cases = [
        case
        for case in load_cases(
            ROOT / "evaluation" / "datasets" / "gold_cases.json"
        )
        if case.data_available
    ]
    retriever = HybridRetriever.from_snapshot(
        ROOT / "data" / "knowledge_base" / "snapshot",
        enable_reranker=False,
    )
    queries = []
    for case in cases:
        query = CMSQueryProcessor.expand(case.question)
        vector = retriever._embedder.encode([query], normalize_embeddings=True)[0]
        queries.append((case.id, case.scope, np.asarray(vector, dtype=np.float32)))
    pg_rows = PgVectorBenchmark(dsn).run(
        retriever.chunks,
        retriever._vectors,
        queries,
        limit=args.limit,
    )
    pg_by_id = {row["case_id"]: row for row in pg_rows}
    faiss_metrics = RetrievalMetrics()
    pg_metrics = RetrievalMetrics()
    rows = []
    for case, (_, _, query_vector) in zip(cases, queries):
        faiss_started = perf_counter()
        faiss_hits = _faiss_vector_search(
            retriever,
            query_vector,
            case.scope,
            args.limit,
        )
        faiss_latency_ms = (perf_counter() - faiss_started) * 1000
        pg_row = pg_by_id[case.id]
        faiss_rank = _faiss_rank(case, faiss_hits)
        pg_rank = _pg_rank(case, pg_row["hits"])
        faiss_metrics.observe(faiss_rank, faiss_latency_ms)
        pg_metrics.observe(pg_rank, pg_row["latency_ms"])
        faiss_pages = [
            (hit.chunk.document, hit.chunk.page) for hit in faiss_hits
        ]
        pg_pages = [
            (hit["document"], hit["page"]) for hit in pg_row["hits"]
        ]
        rows.append(
            {
                "case_id": case.id,
                "faiss_gold_rank": faiss_rank,
                "pgvector_gold_rank": pg_rank,
                "top_k_identical": faiss_pages == pg_pages,
                "faiss_pages": faiss_pages,
                "pgvector_pages": pg_pages,
                "pgvector_latency_ms": pg_row["latency_ms"],
                "faiss_latency_ms": round(faiss_latency_ms, 3),
            }
        )
    report = {
        "schema_version": 2,
        "method": {
            "distance": "exact_cosine",
            "same_precomputed_embeddings": True,
            "postgres_target": f"{args.host}:{args.port}/{args.database}",
            "temporary_table": True,
            "corpus_chunk_count": len(retriever.chunks),
            "limit": args.limit,
            "case_count": len(cases),
        },
        "faiss": faiss_metrics.as_dict(),
        "pgvector": pg_metrics.as_dict(),
        "identical_top_k_rate": round(
            sum(row["top_k_identical"] for row in rows) / len(rows),
            4,
        ),
        "cases": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if args.json_stdout:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_summary(report, args.output)
    return 0 if report["faiss"]["hit_at_k"] == report["pgvector"]["hit_at_k"] else 1


def _local_dsn(args: argparse.Namespace) -> str:
    """Yerel parolayı ekranda göstermeden güvenli psycopg bağlantısı oluşturur."""

    try:
        from psycopg.conninfo import make_conninfo
    except ImportError as error:
        raise SystemExit(
            "Önce değerlendirme bağımlılıklarını kurun: "
            "pip install -r requirements-evaluation.txt"
        ) from error
    password = os.getenv("PGVECTOR_PASSWORD") or getpass.getpass(
        f"PostgreSQL parolası ({args.user}@{args.host}:{args.port}/{args.database}): "
    )
    return make_conninfo(
        host=args.host,
        port=args.port,
        dbname=args.database,
        user=args.user,
        password=password,
        connect_timeout=10,
    )


def _print_summary(report: dict, output: Path) -> None:
    """Karşılaştırmanın karar metriklerini okunaklı ve parolasız gösterir."""

    faiss = report["faiss"]
    pgvector = report["pgvector"]
    print("\nFAISS / pgvector karşılaştırması tamamlandı")
    print(f"Vaka / chunk: {report['method']['case_count']} / "
          f"{report['method']['corpus_chunk_count']}")
    print(f"FAISS    Hit@K={faiss['hit_at_k']:.1%}  MRR={faiss['mrr']:.4f}  "
          f"ortalama={faiss['latency_mean_ms']:.3f} ms")
    print(f"pgvector Hit@K={pgvector['hit_at_k']:.1%}  MRR={pgvector['mrr']:.4f}  "
          f"ortalama={pgvector['latency_mean_ms']:.3f} ms")
    print(f"Aynı ilk-K sıralama: {report['identical_top_k_rate']:.1%}")
    print(f"Rapor: {output.resolve()}")


def _faiss_rank(case, hits) -> int | None:
    """FAISS sonuçlarında ilk altın belge/sayfa sırasını bulur."""

    for rank, hit in enumerate(hits, start=1):
        if hit.chunk.document == case.gold_document and hit.chunk.page in case.gold_pages:
            return rank
    return None


def _faiss_vector_search(retriever, vector, scope, limit):
    """Önceden hesaplanmış sorgu vektörüyle yalnız FAISS arama süresini ölçer."""

    scores, identifiers = retriever._index.search(
        np.asarray([vector], dtype=np.float32),
        len(retriever.chunks),
    )
    hits = [
        SearchHit(retriever.chunks[item_id], float(score))
        for score, item_id in zip(scores[0], identifiers[0])
        if scope == "all" or retriever.chunks[item_id].collection == scope
    ]
    return retriever._deduplicate_by_page(hits, limit)


def _pg_rank(case, hits) -> int | None:
    """pgvector sonuçlarında ilk altın belge/sayfa sırasını bulur."""

    for rank, hit in enumerate(hits, start=1):
        if hit["document"] == case.gold_document and hit["page"] in case.gold_pages:
            return rank
    return None


if __name__ == "__main__":
    raise SystemExit(main())
