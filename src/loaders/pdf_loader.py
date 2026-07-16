from pypdf import PdfReader

class PDFLoader:

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

    def load(self):
        reader = PdfReader(self.pdf_path)

        pages = []

        for page_number, page in enumerate(reader.pages, start=1):

            text = page.extract_text()

            pages.append({
                "page": page_number,
                "text": text
            })

        return pages