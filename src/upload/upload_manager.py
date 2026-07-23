import hashlib
from pathlib import Path

from src.config import UPLOAD_FOLDER
from src.metadata.metadata_manager import CMSMetadataManager
from src.config import METADATA_PATH


class CMSUploadManager:
    def __init__(self):
        self.metadata = CMSMetadataManager(METADATA_PATH)

    @staticmethod
    def calculate_hash(uploaded_file):
        return hashlib.sha256(uploaded_file.getbuffer()).hexdigest()

    def is_duplicate(self, uploaded_file):
        metadata = self.metadata.load() or {"documents": []}
        uploaded_hash = self.calculate_hash(uploaded_file)
        return any(item.get("hash") == uploaded_hash for item in metadata["documents"])

    def save_file(self, uploaded_file):
        destination_dir = Path(UPLOAD_FOLDER)
        destination_dir.mkdir(parents=True, exist_ok=True)
        # The browser-provided filename is untrusted; discard any path components.
        destination = destination_dir / Path(uploaded_file.name).name
        if destination.exists():
            return False
        destination.write_bytes(uploaded_file.getbuffer())
        return True
