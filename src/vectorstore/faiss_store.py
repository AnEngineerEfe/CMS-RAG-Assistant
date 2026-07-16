import os
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

        vectorstore.save_local(path)

    # -----------------------------------------
    # Load
    # -----------------------------------------

    def load(self, path):

        return FAISS.load_local(
            path,
            self.embedding_model,
            allow_dangerous_deserialization=True
        )

    # -----------------------------------------
    # Exists
    # -----------------------------------------

    def exists(self, path):

        return os.path.exists(path)