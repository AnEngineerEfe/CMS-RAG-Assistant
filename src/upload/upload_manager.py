"""Content-addressed PDF upload handling."""

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
        return re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name) or "document.pdf"

    def is_duplicate(self, uploaded_file) -> bool:
        expected_hash = self.calculate_hash(uploaded_file)
        for existing in Path(UPLOAD_FOLDER).glob("*.pdf"):
            if hashlib.sha256(existing.read_bytes()).hexdigest() == expected_hash:
                return True
        return False

    def save_files(self, uploaded_files) -> tuple[list[str], list[str]]:
        destination_dir = Path(UPLOAD_FOLDER)
        destination_dir.mkdir(parents=True, exist_ok=True)
        added, duplicates = [], []
        for uploaded_file in uploaded_files:
            content_hash = self.calculate_hash(uploaded_file)
            if self.is_duplicate(uploaded_file):
                duplicates.append(uploaded_file.name)
                continue
            destination = destination_dir / f"{content_hash}_{self._safe_name(uploaded_file.name)}"
            destination.write_bytes(uploaded_file.getbuffer())
            added.append(uploaded_file.name)
        return added, duplicates
