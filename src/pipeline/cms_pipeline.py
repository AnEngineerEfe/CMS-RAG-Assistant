from src.memory.conversation_memory import CMSConversationMemory
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

        self.memory = CMSConversationMemory()

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

        history = self.memory.get_history()

        prompt = CMSPromptBuilder.build(
            query,
            top_docs,
            history
        )

        # -------------------------
        # LLM
        # -------------------------

        answer = self.llm.generate(prompt)

        self.memory.add(
            query,
            answer
        )

        print("\nConversation History:")
        print(self.memory.get_history())

        return answer, reranked_results
    
    def stream(self, query):

        # Hybrid Retrieval
        hybrid_results = self.hybrid.search(query)

        # Reranking
        reranked_results = self.reranker.rerank(
            query,
            hybrid_results,
            top_k=3
        )

        # Documents
        top_docs = [
            doc
            for score, doc in reranked_results
        ]

        # Prompt
        history = self.memory.get_history()

        prompt = CMSPromptBuilder.build(
            query,
            top_docs,
            history
        )

        answer = ""

        for chunk in self.llm.stream(prompt):

            answer += chunk

            yield chunk

        self.memory.add(
            query,
            answer
        )