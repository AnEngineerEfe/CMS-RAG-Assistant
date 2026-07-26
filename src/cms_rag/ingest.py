from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from .models import Chunk


class PDFIngestor:
    def __init__(self, chunk_size: int = 900, overlap: int = 150) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def load(self, paths: list[Path]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for path in paths:
            reader = PdfReader(str(path))
            for page_number, page in enumerate(reader.pages, start=1):
                text = self._clean(page.extract_text() or "")
                chunks.extend(self._split(text, path, page_number))
        return chunks

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _split(self, text: str, path: Path, page: int) -> list[Chunk]:
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
            result.append(Chunk(text=text[start:end], document=document, page=page, source_path=str(path)))
            if end >= len(text):
                break
            start = max(end - self.overlap, start + 1)
        return result
