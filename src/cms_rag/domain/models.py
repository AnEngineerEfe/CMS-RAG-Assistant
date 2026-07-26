"""CMS-RAG alanında katmanlar arasında taşınan veri modelleri."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    """Kaynak ve sayfa izlenebilirliğini koruyan bir belge metni parçası."""

    text: str
    document: str
    page: int
    source_path: str
    collection: str = "official"
    authority: str = "user_uploaded"
    source_url: str = ""


@dataclass(frozen=True)
class SearchHit:
    """Hibrit arama sonucunu birleşik alaka puanıyla taşır."""

    chunk: Chunk
    score: float


@dataclass(frozen=True)
class UploadResult:
    """Toplu yüklemedeki yeni, yinelenen ve reddedilen dosyaları ayırır."""

    added: list[str]
    duplicates: list[str]
    rejected: list[str] = field(default_factory=list)


def document_label(path: Path) -> str:
    """Depolama yolundan kullanıcıya gösterilecek dosya adını üretir."""

    return path.name
