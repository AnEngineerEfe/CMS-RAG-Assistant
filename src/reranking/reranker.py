from sentence_transformers import CrossEncoder


class CMSReranker:

    def __init__(self, model_name="BAAI/bge-reranker-base"):

        print("\nLoading Reranker Model...")

        self.model = CrossEncoder(model_name)

        print("Reranker Loaded Successfully!")

    def rerank(self, query, documents, top_k=3):

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