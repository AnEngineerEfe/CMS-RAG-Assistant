from src.retrieval.hybrid_retriever import CMSHybridRetriever
from src.reranking.reranker import CMSReranker
from src.generation.prompt_builder import CMSPromptBuilder
from src.generation.llm import CMSLLM


class CMSPipeline:

    def __init__(self, db, chunks):

        self.hybrid = CMSHybridRetriever(
            db,
            chunks
        )

        self.reranker = CMSReranker()

        self.llm = CMSLLM()

    def ask(self, query):

        # -------------------------
        # Hybrid Retrieval
        # -------------------------

        hybrid_results = self.hybrid.search(query)

        # -------------------------
        # Reranking
        # -------------------------

        reranked_results = self.reranker.rerank(
            query,
            hybrid_results,
            top_k=3
        )

        # -------------------------
        # Documents
        # -------------------------

        top_docs = [
            doc
            for score, doc in reranked_results
        ]

        # -------------------------
        # Prompt
        # -------------------------

        prompt = CMSPromptBuilder.build(
            query,
            top_docs
        )

        # -------------------------
        # LLM
        # -------------------------

        answer = self.llm.generate(prompt)

        return answer, reranked_results