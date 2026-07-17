import json
import hashlib
from pathlib import Path


class CMSMetadataManager:

    def __init__(self, metadata_file):

        self.metadata_file = Path(metadata_file)

    # ----------------------------------------

    def calculate_hash(self, file_path):

        sha = hashlib.sha256()

        with open(file_path, "rb") as f:

            while True:

                data = f.read(8192)

                if not data:
                    break

                sha.update(data)

        return sha.hexdigest()

    # ----------------------------------------

    def build_metadata(self, pdf_files):

        metadata = {
            "documents": []
        }

        for pdf in pdf_files:

            metadata["documents"].append({
                "name": pdf.name,
                "hash": self.calculate_hash(pdf)
            })

        return metadata

    # ----------------------------------------

    def save(self, metadata):

        self.metadata_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(self.metadata_file, "w") as f:

            json.dump(
                metadata,
                f,
                indent=4
            )

    # ----------------------------------------

    def load(self):

        if not self.metadata_file.exists():
            return None

        with open(self.metadata_file, "r") as f:

            return json.load(f)