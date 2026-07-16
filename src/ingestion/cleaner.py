import re


class TextCleaner:

    @staticmethod
    def clean(text: str) -> str:

        if not text:
            return ""

        # Windows satır sonları
        text = text.replace("\r", "")

        # Sayfanın başındaki tek sayı (sayfa numarası)
        text = re.sub(r"^\s*\d+\s*\n", "", text)

        # "Page 12" gibi ifadeleri kaldır
        text = re.sub(r"Page\s+\d+", "", text, flags=re.IGNORECASE)

        # Fazla boş satırlar
        text = re.sub(r"\n{2,}", "\n", text)

        # Fazla boşluklar
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()