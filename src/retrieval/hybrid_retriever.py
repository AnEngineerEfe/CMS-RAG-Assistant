from langchain_classic.retrievers import EnsembleRetriever

from src.retrieval.retriever import CMSRetriever
from src.retrieval.bm25_retriever import CMSBM25Retriever


class CMSHybridRetriever:

    def __init__(self, vectorstore, documents):

        semantic = CMSRetriever(vectorstore).retriever
        keyword = CMSBM25Retriever(documents).retriever

        self.retriever = EnsembleRetriever(
            retrievers=[semantic, keyword],
            weights=[0.7, 0.3]
        )

    def search(self, query):

        return self.retriever.invoke(query)