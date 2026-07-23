from sentence_transformers import CrossEncoder
from src.config import RERANKER_MODEL


class CMSReranker:

    def __init__(self, model_name=RERANKER_MODEL):

        print("\nLoading Reranker Model...")

        self.model = CrossEncoder(model_name, local_files_only=True)

        print("Reranker Loaded Successfully!")

    def rerank(self, query, documents, top_k=3):

        if not documents:
            return []

        pairs = [
            (query, doc.page_content)
            for doc in documents
        ]

        scores = self.model.predict(pairs)

        ranked_results = sorted(
            zip(scores, documents),
            key=lambda x: x[0],
            reverse=True
        )

        return ranked_results[:top_k]
