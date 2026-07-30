from pathlib import Path
import unittest

from src.cms_rag.domain import Chunk, SearchHit
from src.cms_rag.infrastructure import HybridRetriever, MarkdownIngestor, PDFIngestor


class PDFIngestorTests(unittest.TestCase):
    def test_chunker_preserves_document_and_page_metadata(self):
        chunks = PDFIngestor(chunk_size=20, overlap=5)._split(
            "A sentence. Another sentence. Third sentence.", Path("official.pdf"), 4
        )
        self.assertTrue(chunks)
        self.assertTrue(all(chunk.document == "official.pdf" for chunk in chunks))
        self.assertTrue(all(chunk.page == 4 for chunk in chunks))
        self.assertTrue(all(chunk.source_path.endswith("official.pdf") for chunk in chunks))

    def test_evidence_deduplicates_multiple_chunks_from_one_page(self):
        first = SearchHit(Chunk("first", "doc.pdf", 2, "doc.pdf"), 0.9)
        duplicate = SearchHit(Chunk("second", "doc.pdf", 2, "doc.pdf"), 0.8)
        next_page = SearchHit(Chunk("third", "doc.pdf", 3, "doc.pdf"), 0.7)
        deduplicated = HybridRetriever._deduplicate_by_page([first, duplicate, next_page], 4)
        self.assertEqual([hit.chunk.page for hit in deduplicated], [2, 3])
        self.assertIn("second", deduplicated[0].chunk.text)

    def test_answerability_gate_separates_strong_and_weak_evidence(self):
        retriever = HybridRetriever.__new__(HybridRetriever)
        retriever._reranker = object()
        strong = [SearchHit(Chunk("relevant", "doc.pdf", 1, "doc.pdf"), 0.62)]
        weak = [SearchHit(Chunk("unrelated", "doc.pdf", 1, "doc.pdf"), 0.005)]
        self.assertTrue(retriever.is_answerable("MAIN nedir?", strong))
        self.assertFalse(
            retriever.is_answerable("Füze menzili kaç kilometredir?", weak)
        )

    def test_invalid_pdf_is_skipped_without_stopping_ingestion(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.pdf"
            invalid.write_bytes(b"%PDF-not-a-real-document")
            self.assertEqual(PDFIngestor().load([invalid]), [])

    def test_reference_front_matter_preserves_collection_and_authority(self):
        text = (
            "---\ncollection: open_source\nauthority: NATO official\n"
            "source_url: https://example.test/source\n---\nInteroperability evidence."
        )
        metadata, body = MarkdownIngestor._parse_front_matter(text)
        self.assertEqual(metadata["collection"], "open_source")
        self.assertEqual(metadata["authority"], "NATO official")
        self.assertIn("Interoperability", body)
