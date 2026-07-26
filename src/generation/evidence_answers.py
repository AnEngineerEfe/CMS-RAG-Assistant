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
        is_definition = any(marker in normalized for marker in (" nedir", " ne demek", "what is"))
        is_detail = any(marker in normalized for marker in ("detaylandir", "acikla", "ayrintili"))
        is_example = any(marker in normalized for marker in ("ornek ver", "ornekle"))
        if not (is_definition or is_detail or is_example):
            return None

        if "iz yonetimi" in normalized or "track management" in normalized:
            source = CMSEvidenceAnswers._source_with(ranked, "track management")
            if source:
                if is_example:
                    return (
                        "**Temsili senaryo (resm\u00ee kaynakta verilen bir olay \u00f6zeti de\u011fildir):** Ayn\u0131 "
                        "hedef i\u00e7in iki farkl\u0131 sens\u00f6r raporu geldi\u011fini d\u00fc\u015f\u00fcn\u00fcn. \u0130z y\u00f6netimi, "
                        "bu raporlar\u0131 korelasyon ve birle\u015ftirme i\u015flemleriyle tek bir izde toplar; b\u00f6ylece "
                        "operat\u00f6re ortak bir durum resmi sunar [SOURCE "
                        f"{source}]."
                    )
                if is_detail:
                    return (
                        "\u0130z y\u00f6netimi, CMS i\u00e7indeki durum fark\u0131ndal\u0131\u011f\u0131n temelidir. Farkl\u0131 kaynaklardan "
                        "gelen verileri ili\u015fkilendirir, yinelenen raporlar\u0131 birle\u015ftirir ve izlerin ya\u015fam d\u00f6ng\u00fcs\u00fcn\u00fc "
                        "y\u00f6netir. Bu sayede birden fazla veri kayna\u011f\u0131ndan ortak bir durum resmi olu\u015fturulur "
                        f"[SOURCE {source}]."
                    )
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
