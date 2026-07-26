"""Local corpus loader with provenance and duplicate protection."""

from __future__ import annotations

import hashlib
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


class CMSDocumentLoader:
    def __init__(self, data_folder: str | Path):
        self.data_folder = Path(data_folder)

    def load(self) -> list[Document]:
        documents: list[Document] = []
        seen_hashes: set[str] = set()
        for pdf_path in sorted(self.data_folder.rglob("*.pdf")):
            file_hash = self._file_hash(pdf_path)
            if file_hash in seen_hashes:
                continue
            seen_hashes.add(file_hash)
            for page in PyPDFLoader(str(pdf_path)).load():
                page.metadata.update(self._metadata(pdf_path, page.metadata.get("page", 0), file_hash))
                documents.append(page)

        for text_path in sorted(path for pattern in ("*.md", "*.txt") for path in self.data_folder.rglob(pattern)):
            file_hash = self._file_hash(text_path)
            if file_hash in seen_hashes:
                continue
            seen_hashes.add(file_hash)
            content = text_path.read_text(encoding="utf-8")
            body, front_matter = self._split_front_matter(content)
            metadata = self._metadata(text_path, 0, file_hash)
            metadata.update(front_matter)
            documents.append(Document(page_content=body, metadata=metadata))
        return documents

    def get_source_files(self) -> list[Path]:
        return sorted(path for pattern in ("*.pdf", "*.md", "*.txt") for path in self.data_folder.rglob(pattern))

    def _metadata(self, path: Path, page: int, file_hash: str) -> dict:
        relative = path.relative_to(self.data_folder)
        collection = relative.parts[0] if len(relative.parts) > 1 else "uploaded"
        if path.stem.startswith("page_") and path.stem[5:].isdigit():
            page = int(path.stem[5:]) - 1
        return {
            "document": path.name,
            "source_path": str(relative).replace("\\", "/"),
            "source_id": file_hash,
            "source_type": path.suffix.lower().lstrip("."),
            "collection": collection,
            "authority": "official" if collection == "havelsan" else "reference",
            "page": page,
        }

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _split_front_matter(content: str) -> tuple[str, dict[str, str]]:
        if not content.startswith("---\n"):
            return content, {}
        header, separator, body = content[4:].partition("\n---\n")
        if not separator:
            return content, {}
        metadata = {}
        for line in header.splitlines():
            key, marker, value = line.partition(":")
            if marker and key.strip():
                metadata[key.strip()] = value.strip()
        return body.lstrip("\n"), metadata
