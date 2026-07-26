from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    text: str
    document: str
    page: int
    source_path: str


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class UploadResult:
    added: list[str]
    duplicates: list[str]


def document_label(path: Path) -> str:
    return path.name
