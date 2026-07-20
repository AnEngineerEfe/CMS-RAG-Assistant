from pathlib import Path

from src.config import *


class CMSDocumentManager:

    def get_documents(self):

        pdfs = list(
            Path(RAW_DATA_PATH).rglob("*.pdf")
        )

        documents = []

        for pdf in pdfs:

            documents.append(
                {
                    "name": pdf.name,
                    "path": pdf,
                    "size": round(
                        pdf.stat().st_size / 1024 / 1024,
                        2
                    )
                }
            )

        return sorted(
            documents,
            key=lambda x: x["name"].lower()
        )