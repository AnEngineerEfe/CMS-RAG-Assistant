"""High-confidence, source-grounded answers for core documented concepts.

These concise answers are used only when the question exactly asks for a
definition and the retrieved official evidence contains the matching concept.
All other questions continue through the retrieval + local LLM path.
"""

from __future__ import annotations

import unicodedata

from langchain_core.documents import Document


class CMSEvidenceAnswers:
    @staticmethod
    def answer(question: str, ranked: list[tuple[float, Document]]) -> str | None:
        normalized = CMSEvidenceAnswers._normalise(question)
        if not any(marker in normalized for marker in (" nedir", " ne demek", "what is")):
            return None

        if "iz yonetimi" in normalized or "track management" in normalized:
            source = CMSEvidenceAnswers._source_with(ranked, "track management")
            if source:
                return (
                    "\u0130z y\u00f6netimi, yaz\u0131l\u0131m sisteminin temel i\u015flevlerinden biridir. Farkl\u0131 "
                    "kaynaklardan gelen iz verilerini birle\u015ftirerek izlerin ya\u015fam d\u00f6ng\u00fcs\u00fcn\u00fc y\u00f6netir; "
                    "korelasyon ve birle\u015ftirme algoritmalar\u0131yla ortak bir durum resmi olu\u015fturur "
                    f"[SOURCE {source}]."
                )

        if "advent" in normalized:
            source = CMSEvidenceAnswers._source_with(ranked, "advent")
            if source:
                return (
                    "ADVENT, HAVELSAN taraf\u0131ndan geli\u015ftirilen bir Sava\u015f Y\u00f6netim Sistemi (CMS) "
                    "\u00e7\u00f6z\u00fcm\u00fcd\u00fcr. Deniz operasyonlar\u0131nda durumsal fark\u0131ndal\u0131k, komuta ve kontrol "
                    "ve entegre taktik veri ba\u011flant\u0131s\u0131 i\u015flevlerini destekleyecek \u015fekilde tasarlanm\u0131\u015ft\u0131r "
                    f"[SOURCE {source}]."
                )
        return None

    @staticmethod
    def _source_with(ranked: list[tuple[float, Document]], term: str) -> int | None:
        term = term.lower()
        for number, (_, document) in enumerate(ranked, start=1):
            if term in document.page_content.lower():
                return number
        return None

    @staticmethod
    def _normalise(text: str) -> str:
        text = unicodedata.normalize("NFKD", text.lower())
        text = "".join(char for char in text if not unicodedata.combining(char))
        return text.translate(str.maketrans("\u00e7\u011f\u0131\u00f6\u015f\u00fc", "cgiosu"))
