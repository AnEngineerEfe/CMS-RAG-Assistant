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
            result = store.save_uploads([Upload("first.pdf", b"%PDF-same"), Upload("copy.pdf", b"%PDF-same")])
            self.assertEqual(result.added, ["first.pdf"])
            self.assertEqual(result.duplicates, ["copy.pdf"])
            self.assertEqual(len(store.pdfs()), 1)

    def test_new_pdf_is_content_addressed(self):
        with TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            result = store.save_uploads([Upload("ADVENT brochure.pdf", b"%PDF-document")])
            self.assertEqual(result.added, ["ADVENT brochure.pdf"])
            self.assertEqual(len(store.pdfs()[0].name.split("_", 1)[0]), 64)

    def test_display_name_hides_content_hash(self):
        with TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            self.assertEqual(
                store.display_name(Path("a" * 64 + "_advent_cms.pdf")),
                "advent_cms.pdf",
            )

    def test_non_pdf_content_is_rejected_before_storage(self):
        with TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            result = store.save_uploads([Upload("not-really.pdf", b"plain text")])
            self.assertEqual(result.rejected, ["not-really.pdf"])
            self.assertEqual(store.pdfs(), [])

    def test_oversized_pdf_is_rejected_before_storage(self):
        with TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            store.MAX_PDF_BYTES = 8
            result = store.save_uploads([Upload("large.pdf", b"%PDF-more")])
            self.assertEqual(result.rejected, ["large.pdf"])
            self.assertEqual(store.pdfs(), [])

    def test_manifest_records_original_name_and_hash(self):
        with TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            store.save_uploads([Upload("official.pdf", b"%PDF-test")])
            record = store.records()[0]
            self.assertEqual(record["display_name"], "official.pdf")
            self.assertEqual(len(record["sha256"]), 64)

    def test_delete_removes_file_and_manifest_record(self):
        with TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            store.save_uploads([Upload("official.pdf", b"%PDF-test")])
            digest = store.records()[0]["sha256"]
            self.assertTrue(store.delete(digest))
            self.assertEqual(store.pdfs(), [])
            self.assertEqual(store.records(), [])

    def test_delete_rejects_manifest_path_traversal(self):
        with TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            store._write_manifest({
                "schema_version": 1,
                "documents": [{
                    "sha256": "a" * 64,
                    "storage_name": "../outside.pdf",
                    "display_name": "outside.pdf",
                    "size_bytes": 1,
                    "source_type": "test",
                    "ingested_at": "2026-07-26T00:00:00+00:00",
                }],
            })
            with self.assertRaises(ValueError):
                store.delete("a" * 64)
