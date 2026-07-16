class CMSRetriever:

    def __init__(self, vectorstore):

        self.retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k":5}
        )

    def search(self, query):

        return self.retriever.invoke(query)