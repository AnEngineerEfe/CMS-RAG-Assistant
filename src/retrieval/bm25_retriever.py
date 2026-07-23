from langchain_community.retrievers import BM25Retriever
from src.config import RETRIEVAL_K


class CMSBM25Retriever:

    def __init__(self, documents):

        self.retriever = BM25Retriever.from_documents(documents)

        self.retriever.k = RETRIEVAL_K

    def search(self, query):

        return self.retriever.invoke(query)
