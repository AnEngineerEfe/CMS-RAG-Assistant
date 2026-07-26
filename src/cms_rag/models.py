from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    text: str
    document: str
    page: int
    source_path: str
    collection: str = "official"
    authority: str = "user_uploaded"
    source_url: str = ""


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class UploadResult:
    added: list[str]
    duplicates: list[str]
    rejected: list[str] = field(default_factory=list)


def document_label(path: Path) -> str:
    return path.name
