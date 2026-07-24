"""Safe, content-addressed PDF upload handling."""

import hashlib
import re
from pathlib import Path

from src.config import UPLOAD_FOLDER


class CMSUploadManager:
    @staticmethod
    def calculate_hash(uploaded_file) -> str:
        return hashlib.sha256(uploaded_file.getbuffer()).hexdigest()

    @staticmethod
    def _safe_name(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name)
        return cleaned or "document.pdf"

    def is_duplicate(self, uploaded_file) -> bool:
        content_hash = self.calculate_hash(uploaded_file)
        return any(path.name.startswith(content_hash) for path in Path(UPLOAD_FOLDER).glob("*.pdf"))

    def save_file(self, uploaded_file) -> bool:
        destination_dir = Path(UPLOAD_FOLDER)
        destination_dir.mkdir(parents=True, exist_ok=True)
        content_hash = self.calculate_hash(uploaded_file)
        if self.is_duplicate(uploaded_file):
            return False
        destination = destination_dir / f"{content_hash}_{self._safe_name(uploaded_file.name)}"
        destination.write_bytes(uploaded_file.getbuffer())
        return True

    def save_files(self, uploaded_files) -> tuple[list[str], list[str]]:
        added, duplicates = [], []
        for uploaded_file in uploaded_files:
            if self.save_file(uploaded_file):
                added.append(uploaded_file.name)
            else:
                duplicates.append(uploaded_file.name)
        return added, duplicates
