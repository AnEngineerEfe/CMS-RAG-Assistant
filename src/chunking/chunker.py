from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class CMSChunker:

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 150
    ):

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def split(self, documents: list[Document]) -> list[Document]:

        chunks = self.splitter.split_documents(documents)

        return chunks