import tempfile
import unittest
from pathlib import Path

from src.ingestion.loader import CMSDocumentLoader


class DocumentLoaderTests(unittest.TestCase):
    def test_text_document_receives_collection_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "havelsan" / "advent.md"
            path.parent.mkdir()
            path.write_text("ADVENT test content", encoding="utf-8")
            documents = CMSDocumentLoader(root).load()
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].metadata["collection"], "havelsan")
        self.assertEqual(documents[0].metadata["authority"], "official")

    def test_front_matter_is_exposed_as_source_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "open_source" / "nato.md"
            path.parent.mkdir()
            path.write_text("---\nsource_url: https://example.test\nauthority: primary-public\n---\n\nNATO content", encoding="utf-8")
            documents = CMSDocumentLoader(root).load()
        self.assertEqual(documents[0].metadata["source_url"], "https://example.test")
        self.assertEqual(documents[0].page_content, "NATO content")
