from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.cms_rag.engine import CMSRAGEngine


class CMSRAGEngineTests(unittest.TestCase):
    def test_engine_requires_document_before_question(self):
        with TemporaryDirectory() as directory:
            engine = CMSRAGEngine(Path(directory))
            answer, sources = engine.ask("ADVENT nedir?")
            self.assertIn("PDF", answer)
            self.assertEqual(sources, [])
