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
        query = knowledge_base._contextualise_short_query("İz yönetimi nedir?")
        self.assertIn("track management", query)

    def test_follow_up_query_contains_previous_question(self):
        knowledge_base = CMSKnowledgeBase.__new__(CMSKnowledgeBase)
        knowledge_base.memory = _Memory([{"question": "İz yönetimi nedir?", "answer": "..."}])
        self.assertIn("İz yönetimi", knowledge_base._contextualise_short_query("Örnek ver."))

    def test_reranker_discards_generic_terms_from_lexical_evidence(self):
        reranker = CMSReranker.__new__(CMSReranker)
        self.assertNotIn("cms", reranker._terms("CMS ADVENT track management"))
        self.assertIn("track", reranker._terms("CMS ADVENT track management"))

    def test_generic_advent_question_uses_model_score_instead_of_false_rejection(self):
        reranker = CMSReranker.__new__(CMSReranker)
        reranker.model = type("Model", (), {"predict": lambda self, pairs: [0.0]})()
        score, _ = reranker.rerank("What is ADVENT?", [Document(page_content="ADVENT CMS overview")], 1)[0]
        self.assertEqual(score, 0.5)

    def test_identical_pdf_is_saved_once_by_content_hash(self):
        with TemporaryDirectory() as directory, patch("src.upload.upload_manager.UPLOAD_FOLDER", Path(directory)):
            manager = CMSUploadManager()
            first = _UploadedFile("advent.pdf", b"same PDF bytes")
            second = _UploadedFile("copied.pdf", b"same PDF bytes")
            added, duplicates = manager.save_files([first, second])
            self.assertEqual(added, ["advent.pdf"])
            self.assertEqual(duplicates, ["copied.pdf"])
            self.assertEqual(len(list(Path(directory).glob("*.pdf"))), 1)


if __name__ == "__main__":
    unittest.main()
