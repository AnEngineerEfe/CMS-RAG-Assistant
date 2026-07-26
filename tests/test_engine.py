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
