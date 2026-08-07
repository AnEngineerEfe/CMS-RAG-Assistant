from pathlib import Path
import unittest

from src.cms_rag.domain import Chunk, SearchHit
from src.cms_rag.infrastructure import HybridRetriever, MarkdownIngestor, PDFIngestor


class PDFIngestorTests(unittest.TestCase):
    def test_chunker_preserves_document_and_page_metadata(self):
        text = "A sentence. Another sentence. Third sentence."
        chunks = PDFIngestor(chunk_size=20, overlap=5)._split(
            text, Path("official.pdf"), 4
        )
        self.assertTrue(chunks)
        self.assertTrue(all(chunk.document == "official.pdf" for chunk in chunks))
        self.assertTrue(all(chunk.page == 4 for chunk in chunks))
        self.assertTrue(all(chunk.source_path.endswith("official.pdf") for chunk in chunks))
        original_words = {word.strip(".") for word in text.split()}
        self.assertTrue(all(
            chunk.text.split()[0].strip(".") in original_words
            for chunk in chunks
        ))

    def test_evidence_deduplicates_multiple_chunks_from_one_page(self):
        first = SearchHit(Chunk("first", "doc.pdf", 2, "doc.pdf"), 0.9)
        duplicate = SearchHit(Chunk("second", "doc.pdf", 2, "doc.pdf"), 0.8)
        next_page = SearchHit(Chunk("third", "doc.pdf", 3, "doc.pdf"), 0.7)
        deduplicated = HybridRetriever._deduplicate_by_page([first, duplicate, next_page], 4)
        self.assertEqual([hit.chunk.page for hit in deduplicated], [2, 3])
        self.assertIn("second", deduplicated[0].chunk.text)

    def test_lexical_guard_preserves_exact_match_page(self):
        reranked = [
            SearchHit(Chunk(f"semantic {page}", "doc.pdf", page, "doc.pdf"), 0.9)
            for page in range(1, 4)
        ]
        lexical = [
            SearchHit(
                Chunk("Target Motion Analysis", "doc.pdf", 9, "doc.pdf"),
                0.01,
            )
        ]
        selected = HybridRetriever._preserve_lexical_pages(
            reranked,
            lexical,
            limit=3,
        )
        self.assertEqual([hit.chunk.page for hit in selected], [1, 2, 9])

    def test_gate_places_stronger_cross_encoder_evidence_first(self):
        weak = SearchHit(Chunk("weak", "doc.pdf", 1, "doc.pdf"), 0.01)
        strong = SearchHit(Chunk("strong", "doc.pdf", 2, "doc.pdf"), 0.92)
        tail = SearchHit(Chunk("tail", "doc.pdf", 3, "doc.pdf"), 0.02)

        ordered = HybridRetriever._order_gate_prefix([weak, strong], [tail])

        self.assertEqual([hit.chunk.text for hit in ordered], ["strong", "weak", "tail"])

    def test_answerability_gate_separates_strong_and_weak_evidence(self):
        retriever = HybridRetriever.__new__(HybridRetriever)
        retriever._reranker = object()
        strong = [SearchHit(Chunk("MAIN maintenance assistant", "doc.pdf", 1, "doc.pdf"), 0.62)]
        weak = [SearchHit(Chunk("unrelated", "doc.pdf", 1, "doc.pdf"), 0.005)]
        self.assertTrue(retriever.is_answerable("MAIN nedir?", strong))
        self.assertFalse(
            retriever.is_answerable("Füze menzili kaç kilometredir?", weak)
        )

    def test_answerability_requires_distinctive_evidence_even_with_high_score(self):
        retriever = HybridRetriever.__new__(HybridRetriever)
        retriever._reranker = object()
        misleading = [
            SearchHit(
                Chunk("ADVENT is a combat management system.", "doc.pdf", 1, "doc.pdf"),
                0.91,
            )
        ]
        self.assertFalse(
            retriever.is_answerable(
                "ADVENT operating system kernel nedir?",
                misleading,
            )
        )

    def test_answerability_rejects_restricted_configuration_requests(self):
        retriever = HybridRetriever.__new__(HybridRetriever)
        retriever._reranker = object()
        evidence = [
            SearchHit(
                Chunk("Sensor configuration for a surface platform.", "doc.pdf", 1, "doc.pdf"),
                0.91,
            )
        ]
        self.assertFalse(
            retriever.is_answerable(
                "Görevdeki bir geminin gizli sensör konfigürasyonu nedir?",
                evidence,
            )
        )
        for question in (
            "Sahadaki üretim veritabanının IP adresi ve yönetim portu nedir?",
            "Kamuya açıklanmamış teslimat takvimi nedir?",
            "Sonar kalibrasyon eşikleri ve ham katsayıları nelerdir?",
        ):
            with self.subTest(question=question):
                self.assertFalse(retriever.is_answerable(question, evidence))

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
