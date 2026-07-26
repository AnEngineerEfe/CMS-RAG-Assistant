from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.cms_rag.storage import DocumentStore


class Upload(BytesIO):
    def __init__(self, name: str, data: bytes) -> None:
        super().__init__(data)
        self.name = name


class DocumentStoreTests(unittest.TestCase):
    def test_duplicate_pdf_content_is_stored_once(self):
        with TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            result = store.save_uploads([Upload("first.pdf", b"same"), Upload("copy.pdf", b"same")])
            self.assertEqual(result.added, ["first.pdf"])
            self.assertEqual(result.duplicates, ["copy.pdf"])
            self.assertEqual(len(store.pdfs()), 1)

    def test_new_pdf_is_content_addressed(self):
        with TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            result = store.save_uploads([Upload("ADVENT brochure.pdf", b"document")])
            self.assertEqual(result.added, ["ADVENT brochure.pdf"])
            self.assertEqual(len(store.pdfs()[0].name.split("_", 1)[0]), 64)
