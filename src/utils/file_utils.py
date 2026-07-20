import hashlib


class CMSFileUtils:

    @staticmethod
    def calculate_hash(file_path):

        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:

            while True:

                chunk = f.read(4096)

                if not chunk:
                    break

                sha256.update(chunk)

        return sha256.hexdigest()