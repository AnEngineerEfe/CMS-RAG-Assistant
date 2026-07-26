from pathlib import Path

from langchain_community.vectorstores import FAISS


class CMSVectorStore:

    def __init__(self, embedding_model):

        self.embedding_model = embedding_model

    # -----------------------------------------
    # Create
    # -----------------------------------------

    def create(self, documents):

        return FAISS.from_documents(
            documents,
            self.embedding_model
        )

    # -----------------------------------------
    # Save
    # -----------------------------------------

    def save(self, vectorstore, path):

        Path(path).parent.mkdir(
            parents=True,
            exist_ok=True
        )

        vectorstore.save_local(path)

