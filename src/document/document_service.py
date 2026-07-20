import os

from src.document.document_manager import CMSDocumentManager


class CMSDocumentService:

    def __init__(self):

        self.manager = CMSDocumentManager()

    # -----------------------------------------

    def delete(self, path):

        if os.path.exists(path):

            os.remove(path)

            return True

        return False