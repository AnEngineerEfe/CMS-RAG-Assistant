from pathlib import Path
import unittest

from src.cms_rag.ingest import PDFIngestor


class PDFIngestorTests(unittest.TestCase):
    def test_chunker_preserves_document_and_page_metadata(self):
        chunks = PDFIngestor(chunk_size=20, overlap=5)._split(
            "A sentence. Another sentence. Third sentence.", Path("official.pdf"), 4
        )
        self.assertTrue(chunks)
        self.assertTrue(all(chunk.document == "official.pdf" for chunk in chunks))
        self.assertTrue(all(chunk.page == 4 for chunk in chunks))
        self.assertTrue(all(chunk.source_path.endswith("official.pdf") for chunk in chunks))
