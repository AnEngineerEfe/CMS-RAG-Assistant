import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from langchain_core.documents import Document

from src.reranking.reranker import CMSReranker
from src.services.knowledge_base import CMSKnowledgeBase
from src.upload.upload_manager import CMSUploadManager


class _Memory:
    def __init__(self, history=None):
        self.history = history or []

    def get_history(self):
        return self.history


class _UploadedFile(BytesIO):
    def __init__(self, name, content):
        super().__init__(content)
        self.name = name

    def getbuffer(self):
        return memoryview(self.getvalue())


class RetrievalQualityTests(unittest.TestCase):
    def test_turkish_track_management_query_is_expanded_locally(self):
        knowledge_base = CMSKnowledgeBase.__new__(CMSKnowledgeBase)
        knowledge_base.memory = _Memory()
        query = knowledge_base._contextualise_short_query("\u0130z y\u00f6netimi nedir?")
        self.assertIn("track management", query)

    def test_follow_up_query_contains_previous_question(self):
        knowledge_base = CMSKnowledgeBase.__new__(CMSKnowledgeBase)
        knowledge_base.memory = _Memory([{"question": "\u0130z y\u00f6netimi nedir?", "answer": "..."}])
        self.assertIn("\u0130z y\u00f6netimi", knowledge_base._contextualise_short_query("\u00d6rnek ver."))

    def test_reranker_discards_generic_terms_from_lexical_evidence(self):
        reranker = CMSReranker.__new__(CMSReranker)
        self.assertNotIn("cms", reranker._terms("CMS ADVENT track management"))
        self.assertIn("track", reranker._terms("CMS ADVENT track management"))

    def test_reranker_rewards_exact_technical_phrase(self):
        reranker = CMSReranker.__new__(CMSReranker)
        reranker.model = type("Model", (), {"predict": lambda self, pairs: [0.0, 0.0]})()
        ranked = reranker.rerank(
            "Which tactical data links does ADVENT support?",
            [Document(page_content="data communication support"), Document(page_content="Tactical Data Links: Link 11, Link 16")],
            2,
        )
        self.assertIn("Link 16", ranked[0][1].page_content)

    def test_generic_advent_question_uses_model_score_instead_of_false_rejection(self):
        reranker = CMSReranker.__new__(CMSReranker)
        reranker.model = type("Model", (), {"predict": lambda self, pairs: [0.0]})()
        score, _ = reranker.rerank("What is ADVENT?", [Document(page_content="ADVENT CMS overview")], 1)[0]
        self.assertEqual(score, 0.5)

    def test_identical_pdf_is_saved_once_by_content_hash(self):
        with TemporaryDirectory() as directory, patch("src.upload.upload_manager.UPLOAD_FOLDER", Path(directory)):
            added, duplicates = CMSUploadManager().save_files([
                _UploadedFile("advent.pdf", b"same PDF bytes"),
                _UploadedFile("copied.pdf", b"same PDF bytes"),
            ])
            self.assertEqual(added, ["advent.pdf"])
            self.assertEqual(duplicates, ["copied.pdf"])
            self.assertEqual(len(list(Path(directory).glob("*.pdf"))), 1)

    def test_existing_unprefixed_pdf_is_detected_as_duplicate(self):
        with TemporaryDirectory() as directory, patch("src.upload.upload_manager.UPLOAD_FOLDER", Path(directory)):
            Path(directory, "official-brochure.pdf").write_bytes(b"same PDF bytes")
            added, duplicates = CMSUploadManager().save_files([_UploadedFile("uploaded.pdf", b"same PDF bytes")])
            self.assertEqual(added, [])
            self.assertEqual(duplicates, ["uploaded.pdf"])

    def test_combined_scope_is_an_alias_for_all_collections(self):
        class Retriever:
            def __init__(self, content):
                self.content = content

            def search(self, query):
                return [Document(page_content=self.content)]

        knowledge_base = CMSKnowledgeBase.__new__(CMSKnowledgeBase)
        knowledge_base.collections = {
            "havelsan": Retriever("official"),
            "open_source": Retriever("reference"),
        }
        self.assertEqual(len(knowledge_base._retrieve("test", "combined")), 2)


if __name__ == "__main__":
    unittest.main()
