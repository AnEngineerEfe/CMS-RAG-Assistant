from langchain_huggingface import HuggingFaceEmbeddings

from src.config import EMBEDDING_MODEL


class CMSEmbedder:
    def __init__(self) -> None:
        self.model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu", "local_files_only": True},
            encode_kwargs={"normalize_embeddings": True},
        )

    def get_model(self):
        return self.model
