from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


class CMSDocumentLoader:
    """Load local source files and attach collection/provenance metadata."""

    def __init__(self, data_folder: str | Path):
        self.data_folder = Path(data_folder)

    def load(self) -> list[Document]:
        documents: list[Document] = []
        pdf_files = sorted(self.data_folder.rglob("*.pdf"))
        text_files = sorted(
            path for suffix in ("*.md", "*.txt") for path in self.data_folder.rglob(suffix)
        )
        print(f"Found {len(pdf_files)} PDF and {len(text_files)} text file(s).")

        for pdf_path in pdf_files:
            print(f"Loading: {pdf_path.name}")
            for page in PyPDFLoader(str(pdf_path)).load():
                page.metadata.update(self._metadata(pdf_path, page.metadata.get("page", 0)))
                documents.append(page)

        for text_path in text_files:
            documents.append(
                Document(
                    page_content=text_path.read_text(encoding="utf-8"),
                    metadata=self._metadata(text_path, 0),
                )
            )
        return documents

    def get_pdf_files(self) -> list[Path]:
        return sorted(self.data_folder.rglob("*.pdf"))

    def _metadata(self, path: Path, page: int) -> dict:
        relative = path.relative_to(self.data_folder)
        collection = relative.parts[0] if len(relative.parts) > 1 else "uploaded"
        return {
            "document": path.name,
            "source_path": str(relative).replace("\\", "/"),
            "collection": collection,
            "authority": "official" if collection == "havelsan" else "reference",
            "page": page,
        }
