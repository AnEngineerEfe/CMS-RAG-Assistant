from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .models import Chunk


class PDFIngestor:
    def __init__(self, chunk_size: int = 900, overlap: int = 150) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def load(
        self,
        paths: list[Path],
        collection: str = "official",
        authority: str = "user_uploaded",
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        for path in paths:
            try:
                reader = PdfReader(str(path))
            except (PdfReadError, OSError):
                continue
            for page_number, page in enumerate(reader.pages, start=1):
                text = self._clean(page.extract_text() or "")
                chunks.extend(self._split(text, path, page_number, collection, authority))
        return chunks

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _split(
        self,
        text: str,
        path: Path,
        page: int,
        collection: str = "official",
        authority: str = "user_uploaded",
        source_url: str = "",
    ) -> list[Chunk]:
        if not text:
            return []
        result: list[Chunk] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.chunk_size)
            if end < len(text):
                boundary = text.rfind(". ", start, end)
                if boundary > start + self.chunk_size // 2:
                    end = boundary + 1
            document = re.sub(r"^[a-f0-9]{64}_", "", path.name)
            result.append(Chunk(
                text=text[start:end], document=document, page=page, source_path=str(path),
                collection=collection, authority=authority, source_url=source_url,
            ))
            if end >= len(text):
                break
            start = max(end - self.overlap, start + 1)
        return result


class MarkdownIngestor(PDFIngestor):
    """Loads curated public web references with lightweight front matter."""

    def load_directory(self, root: Path) -> list[Chunk]:
        chunks: list[Chunk] = []
        if not root.exists():
            return chunks
        for path in sorted(root.rglob("*.md")):
            metadata, body = self._parse_front_matter(path.read_text(encoding="utf-8"))
            chunks.extend(self._split(
                self._clean(body), path, 1,
                metadata.get("collection", "open_source"),
                metadata.get("authority", "public_reference"),
                metadata.get("source_url", ""),
            ))
        return chunks

    @staticmethod
    def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
        if not text.startswith("---\n"):
            return {}, text
        _, header, body = text.split("---\n", 2)
        metadata = {}
        for line in header.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()
        return metadata, body
