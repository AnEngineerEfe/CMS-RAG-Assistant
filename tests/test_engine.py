from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.cms_rag.engine import CMSRAGEngine
from src.cms_rag.evidence import EvidenceResponder
from src.cms_rag.models import Chunk, SearchHit
from src.cms_rag.query import CMSQueryProcessor


class CMSRAGEngineTests(unittest.TestCase):
    def test_stream_appends_a_missing_source_marker(self):
        class FakeOllama:
            @staticmethod
            def chat(**kwargs):
                del kwargs
                yield {"message": {"content": "Kaynaklı kısa yanıt."}}

        with TemporaryDirectory() as directory:
            engine = CMSRAGEngine(Path(directory))
            engine._ollama = FakeOllama()
            hit = SearchHit(Chunk("kanıt", "official.pdf", 1, "official.pdf"), 1.0)
            answer = "".join(engine._ollama_stream("Soru", "İstem", [hit]))
            self.assertEqual(answer, "Kaynaklı kısa yanıt. [SOURCE 1]")

    def test_model_can_be_selected_from_environment(self):
        with TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"CMS_RAG_MODEL": "qwen2.5:3b"}):
                engine = CMSRAGEngine(Path(directory))
            self.assertEqual(engine.model, "qwen2.5:3b")

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

    def test_naval_platform_question_has_a_fast_grounded_answer(self):
        chunks = [Chunk(
            "ADVENT CMS serves as the central component within naval combat systems for surface platforms.",
            "official.pdf", 18, "official.pdf"
        )]
        result = EvidenceResponder.answer("Sava\u015f gemisinde ADVENT ne yapar?", [], chunks)
        self.assertIsNotNone(result)
        answer, sources = result
        self.assertIn("y\u00fczey platformlar\u0131", answer)
        self.assertEqual(sources[0].chunk.page, 18)

    def test_follow_up_platform_question_uses_documented_product_tree(self):
        chunks = [Chunk(
            "Surface platforms benefit from ADVENT KALYON. Subsurface platforms use ADVENT M\u00dcREN. "
            "ADVENT MARTI supports naval air platforms, ADVENT UFUK land installations and ADVENT ROTA unmanned platforms.",
            "official.pdf", 4, "official.pdf"
        )]
        history = [{"question": "Sava\u015f gemisinde ADVENT ne yapar?", "answer": "ADVENT bir CMS'tir."}]
        result = EvidenceResponder.answer("Ba\u015fka hangi platformlarda kullan\u0131l\u0131r?", history, chunks)
        self.assertIsNotNone(result)
        answer, sources = result
        self.assertIn("ADVENT ROTA", answer)
        self.assertEqual(sources[0].chunk.page, 4)

    def test_naval_question_overrides_variant_duty_follow_up(self):
        chunks = [
            Chunk("ADVENT CMS serves as the central component within naval combat systems for surface platforms.", "official.pdf", 18, "official.pdf"),
            Chunk("ADVENT MARTI is for aircraft.", "official.pdf", 22, "official.pdf"),
            Chunk("ADVENT UFUK supports maritime security.", "official.pdf", 26, "official.pdf"),
            Chunk("ADVENT M\u00dcREN is for underwater platforms.", "official.pdf", 28, "official.pdf"),
        ]
        history = [{"question": "\u00d6rnek ver", "answer": "ADVENT MARTI ADVENT UFUK ADVENT M\u00dcREN"}]
        result = EvidenceResponder.answer("Sava\u015f Gemisi ADVENT'te ne yapar?", history, chunks)
        self.assertIn("y\u00fczey platformlar\u0131", result[0])
        self.assertEqual(result[1][0].chunk.page, 18)

    def test_chitchat_is_rejected_without_retrieval(self):
        self.assertTrue(CMSQueryProcessor.is_non_domain_chitchat("Ben kimim?"))

    def test_completed_stream_remembers_answer_after_consumption(self):
        with TemporaryDirectory() as directory:
            engine = CMSRAGEngine(Path(directory))
            answer = "Kaynakl\u0131 yan\u0131t."
            self.assertEqual("".join(engine._completed("Soru", answer)).strip(), answer)
            self.assertEqual(engine.history[-1]["question"], "Soru")

    def test_turkish_cms_terminology_is_expanded_for_retrieval(self):
        expanded = CMSQueryProcessor.expand("Taktik veri baglantisi nedir?")
        self.assertIn("tactical data link", expanded)
