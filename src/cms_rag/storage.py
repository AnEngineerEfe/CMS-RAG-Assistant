from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .models import UploadResult


class DocumentStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _safe_filename(name: str) -> str:
        clean = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name)
        return clean or "document.pdf"

    def save_uploads(self, files) -> UploadResult:
        existing_hashes = {
            self._hash(path.read_bytes())
            for path in self.root.glob("*.pdf")
        }
        added: list[str] = []
        duplicates: list[str] = []
        for uploaded in files:
            data = uploaded.getvalue()
            digest = self._hash(data)
            if digest in existing_hashes:
                duplicates.append(uploaded.name)
                continue
            target = self.root / f"{digest}_{self._safe_filename(uploaded.name)}"
            target.write_bytes(data)
            existing_hashes.add(digest)
            added.append(uploaded.name)
        return UploadResult(added=added, duplicates=duplicates)

    def pdfs(self) -> list[Path]:
        return sorted(self.root.glob("*.pdf"))

    @staticmethod
    def display_name(path: Path) -> str:
        """Hide the storage hash; users should see the original uploaded name."""
        return re.sub(r"^[a-f0-9]{64}_", "", path.name)
