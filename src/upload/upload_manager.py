import hashlib
from pathlib import Path

from src.config import UPLOAD_FOLDER


class CMSUploadManager:
    @staticmethod
    def calculate_hash(uploaded_file) -> str:
        return hashlib.sha256(uploaded_file.getbuffer()).hexdigest()

    def is_duplicate(self, uploaded_file) -> bool:
        candidate_hash = self.calculate_hash(uploaded_file)
        for existing in Path(UPLOAD_FOLDER).glob("*.pdf"):
            if hashlib.sha256(existing.read_bytes()).hexdigest() == candidate_hash:
                return True
        return False

    def save_file(self, uploaded_file) -> bool:
        destination_dir = Path(UPLOAD_FOLDER)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / Path(uploaded_file.name).name
        if destination.exists():
            return False
        destination.write_bytes(uploaded_file.getbuffer())
        return True
