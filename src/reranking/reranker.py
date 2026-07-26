import re
from math import exp

from sentence_transformers import CrossEncoder

from src.config import RERANKER_MODEL


class CMSReranker:
    """Cross-encoder reranking strengthened with transparent term evidence."""

    _STOP_WORDS = {
        "advent", "cms", "combat", "management", "system", "what", "with",
        "that", "this", "from", "about", "nedir", "ver", "örnek", "example",
        "the", "and", "for", "bir", "ile", "olan", "nasıl", "does",
    }

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        self.model = CrossEncoder(model_name, local_files_only=True)

    def rerank(self, query, documents, top_k=3):
        if not documents:
            return []
        pairs = [(query, document.page_content) for document in documents]
        model_scores = [1 / (1 + exp(-float(value))) for value in self.model.predict(pairs)]
        query_terms = set(self._terms(query))
        ranked = []
        for model_score, document in zip(model_scores, documents):
            document_terms = set(self._terms(document.page_content))
            lexical_score = len(query_terms & document_terms) / len(query_terms) if query_terms else 0.0
            phrase_score = self._phrase_score(query, document.page_content)
            # Explicit terminology is vital for CMS/TDL questions. The model is
            # still retained as a secondary semantic signal.
            combined_score = model_score if not query_terms else (
                0.65 * lexical_score + 0.15 * model_score + 0.20 * phrase_score
            )
            ranked.append((combined_score, document))
        return sorted(ranked, key=lambda item: item[0], reverse=True)[:top_k]

    def _terms(self, text: str) -> list[str]:
        return [
            term for term in re.findall(r"[a-zA-ZçÇğĞıİöÖşŞüÜ0-9]{3,}", text.lower())
            if term not in self._STOP_WORDS
        ]

    @staticmethod
    def _phrase_score(query: str, document: str) -> float:
        """Reward exact multi-word technical concepts over generic word overlap."""
        normalized_query = query.lower()
        normalized_document = document.lower()
        phrases = ("tactical data link", "track management", "situational awareness")
        requested = [phrase for phrase in phrases if phrase in normalized_query]
        if not requested:
            return 0.0
        return sum(phrase in normalized_document for phrase in requested) / len(requested)
