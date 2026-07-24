import unittest

from src.reranking.reranker import CMSReranker
from src.services.knowledge_base import CMSKnowledgeBase


class _Memory:
    def __init__(self, history=None):
        self.history = history or []

    def get_history(self):
        return self.history


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


if __name__ == "__main__":
    unittest.main()
