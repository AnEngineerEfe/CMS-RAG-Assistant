from langchain_community.document_loaders import PyPDFLoader


class LangChainPDFLoader:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

    def load(self):
        loader = PyPDFLoader(self.pdf_path)
        documents = loader.load()
        return documents