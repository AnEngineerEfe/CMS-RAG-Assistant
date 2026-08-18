"""CMS agent grafiğinin düğümler arasında taşıdığı tipli çalışma durumu."""

from __future__ import annotations

from typing import TypedDict

from ...domain.models import Chunk, SearchHit


class EvidenceHitState(TypedDict):
    """Checkpoint'e güvenle yazılabilen JSON uyumlu kanıt temsili."""

    text: str
    document: str
    page: int
    source_path: str
    collection: str
    authority: str
    source_url: str
    score: float


class CMSAgentState(TypedDict, total=False):
    """Tek graph çalışmasının girdisini, kararlarını, kanıtlarını ve sonucunu taşır."""

    question: str
    scope: str
    route: str
    route_reason: str
    retrieval_query: str
    answer: str
    hits: list[EvidenceHitState]
    answerable: bool
    verification_passed: bool
    verification_reason: str
    repair_count: int
    generation_mode: str
    started_at: float
    recorded: bool
    events: list[str]
    error: str
    completed: bool


def serialize_hits(hits: list[SearchHit]) -> list[EvidenceHitState]:
    """Alan modellerini özel Python türü içermeyen checkpoint kayıtlarına dönüştürür."""

    return [
        {
            "text": hit.chunk.text,
            "document": hit.chunk.document,
            "page": hit.chunk.page,
            "source_path": hit.chunk.source_path,
            "collection": hit.chunk.collection,
            "authority": hit.chunk.authority,
            "source_url": hit.chunk.source_url,
            "score": hit.score,
        }
        for hit in hits
    ]


def deserialize_hits(items: list[EvidenceHitState]) -> list[SearchHit]:
    """Checkpoint kanıtlarını uygulamanın değişmez Chunk ve SearchHit modellerine döndürür."""

    return [
        SearchHit(
            Chunk(
                text=item["text"],
                document=item["document"],
                page=int(item["page"]),
                source_path=item["source_path"],
                collection=item["collection"],
                authority=item["authority"],
                source_url=item["source_url"],
            ),
            float(item["score"]),
        )
        for item in items
    ]
