import os
import hashlib

from src.config import *
from src.metadata.metadata_manager import CMSMetadataManager


class CMSUploadManager:

    def __init__(self):

        self.metadata = CMSMetadataManager(
            METADATA_PATH
        )

    # ----------------------------------------

    def calculate_hash(self, uploaded_file):

        sha = hashlib.sha256()

        sha.update(uploaded_file.getbuffer())

        return sha.hexdigest()

    # ----------------------------------------

    def is_duplicate(self, uploaded_file):

        metadata = self.metadata.load()

        if metadata is None:
            return False

        uploaded_hash = self.calculate_hash(
            uploaded_file
        )

        for document in metadata["documents"]:

            if document["hash"] == uploaded_hash:

                return True

        return False

    # ----------------------------------------

    def save_file(self, uploaded_file):

        os.makedirs(
            UPLOAD_FOLDER,
            exist_ok=True
        )

        save_path = os.path.join(
            UPLOAD_FOLDER,
            uploaded_file.name
        )

        if os.path.exists(save_path):
            return False

        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        return True