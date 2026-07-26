from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.cms_rag.engine import CMSRAGEngine
from src.cms_rag.evidence import EvidenceResponder
from src.cms_rag.models import Chunk


class CMSRAGEngineTests(unittest.TestCase):
    def test_engine_requires_document_before_question(self):
        with TemporaryDirectory() as directory:
            engine = CMSRAGEngine(Path(directory))
            answer, sources = engine.ask("ADVENT nedir?")
            self.assertIn("PDF", answer)
            self.assertEqual(sources, [])

    def test_short_follow_up_inherits_the_last_question(self):
        with TemporaryDirectory() as directory:
            engine = CMSRAGEngine(Path(directory))
            engine.history = [{"question": "ADVENT nedir?", "answer": "Bir CMS \u00e7\u00f6z\u00fcm\u00fcd\u00fcr."}]
            query = engine.build_retrieval_query("\u00d6rnekleri var m\u0131?")
            self.assertIn("ADVENT nedir?", query)
            self.assertIn("\u00d6rnekleri var m\u0131?", query)

    def test_advent_follow_up_examples_are_source_grounded(self):
        chunks = [
            Chunk("ADVENT represents a CMS family.", "official.pdf", 4, "official.pdf"),
            Chunk("ADVENT MARTI is an airborne system.", "official.pdf", 22, "official.pdf"),
            Chunk("ADVENT UFUK supports maritime security.", "official.pdf", 26, "official.pdf"),
            Chunk("ADVENT M\u00dcREN is for underwater platforms.", "official.pdf", 28, "official.pdf"),
        ]
        result = EvidenceResponder.answer("\u00d6rnekleri var m\u0131?", [{"question": "ADVENT nedir?", "answer": "..."}], chunks)
        self.assertIsNotNone(result)
        answer, sources = result
        self.assertIn("ADVENT MARTI", answer)
        self.assertEqual([source.chunk.page for source in sources], [22, 26, 28])

    def test_variant_duties_follow_the_example_turn(self):
        chunks = [
            Chunk("ADVENT MARTI is for special mission aircraft.", "official.pdf", 22, "official.pdf"),
            Chunk("ADVENT UFUK supports maritime security.", "official.pdf", 26, "official.pdf"),
            Chunk("ADVENT M\u00dcREN is for underwater platforms.", "official.pdf", 28, "official.pdf"),
        ]
        history = [{
            "question": "\u00d6rnek ver",
            "answer": "ADVENT MARTI, ADVENT UFUK ve ADVENT M\u00dcREN varyantlar\u0131 bulunur.",
        }]
        result = EvidenceResponder.answer("Bunlar\u0131n g\u00f6revleri neler?", history, chunks)
        self.assertIsNotNone(result)
        answer, sources = result
        self.assertIn("su alt\u0131", answer)
        self.assertEqual([source.chunk.page for source in sources], [22, 26, 28])

    def test_completed_stream_remembers_answer_after_consumption(self):
        with TemporaryDirectory() as directory:
            engine = CMSRAGEngine(Path(directory))
            answer = "Kaynakl\u0131 yan\u0131t."
            self.assertEqual("".join(engine._completed("Soru", answer)).strip(), answer)
            self.assertEqual(engine.history[-1]["question"], "Soru")
