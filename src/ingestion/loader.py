import os

from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


class CMSDocumentLoader:

    def __init__(self, data_folder: str):

        self.data_folder = data_folder

    def load(self) -> list[Document]:

        documents = []

        pdf_files = list(
            Path(self.data_folder).rglob("*.pdf")
        )

        print(f"Found {len(pdf_files)} PDF file(s).")

        for pdf_path in pdf_files:

            print(f"Loading: {pdf_path.name}")

            loader = PyPDFLoader(str(pdf_path))

            pages = loader.load()

            for page in pages:

                page.metadata["document"] = pdf_path.name

            documents.extend(pages)

        return documents