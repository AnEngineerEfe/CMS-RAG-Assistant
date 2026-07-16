from langchain_community.retrievers import BM25Retriever


class CMSBM25Retriever:

    def __init__(self, documents):

        self.retriever = BM25Retriever.from_documents(documents)

        self.retriever.k = 5

    def search(self, query):

        return self.retriever.invoke(query)