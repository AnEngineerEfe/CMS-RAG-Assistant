from src.config import RETRIEVAL_K


class CMSRetriever:

    def __init__(self, vectorstore):

        self.retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": RETRIEVAL_K}
        )

    def search(self, query):

        return self.retriever.invoke(query)
