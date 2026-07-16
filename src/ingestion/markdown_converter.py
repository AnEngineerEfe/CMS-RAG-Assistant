from pathlib import Path
from langchain_core.documents import Document


class MarkdownConverter:

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_documents(self, documents: list[Document]):

        for doc in documents:

            page = doc.metadata["page"] + 1

            filename = self.output_dir / f"page_{page:02d}.md"

            with open(filename, "w", encoding="utf-8") as f:

                f.write(f"# Page {page}\n\n")
                f.write(doc.page_content)