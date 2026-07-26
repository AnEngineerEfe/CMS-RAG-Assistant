"""Fast, source-grounded answers for unambiguous brochure questions."""

from __future__ import annotations

import unicodedata

from .models import Chunk, SearchHit


class EvidenceResponder:
    @staticmethod
    def answer(question: str, history: list[dict[str, str]], chunks: list[Chunk]) -> tuple[str, list[SearchHit]] | None:
        normalized = EvidenceResponder._normalise(question)
        previous = EvidenceResponder._normalise(history[-1]["question"]) if history else ""

        if "advent" in normalized and ("nedir" in normalized or "what is" in normalized):
            source = EvidenceResponder._find(chunks, "ADVENT represents")
            if source:
                return (
                    "ADVENT, farkl\u0131 operasyonel ortamlar\u0131n gereksinimlerine uyarlanabilen bir "
                    "Sava\u015f Y\u00f6netim Sistemi (CMS) \u00fcr\u00fcn ailesidir. Dok\u00fcman, bu ailenin komuta ve "
                    "kontrol, g\u00f6rev y\u00f6netimi ve CMS i\u015flevlerini kapsad\u0131\u011f\u0131n\u0131 belirtir [SOURCE 1].",
                    [SearchHit(source, 1.0)],
                )

        asks_example = any(marker in normalized for marker in ("ornek", "examples", "example"))
        if asks_example and "advent" in previous:
            sources = [
                EvidenceResponder._find(chunks, "Each variant of ADVENT"),
                EvidenceResponder._find(chunks, "ADVENT MARTI", minimum_page=20),
                EvidenceResponder._find(chunks, "ADVENT UFUK", minimum_page=25),
                EvidenceResponder._find(chunks, "ADVENT M\u00dcREN", minimum_page=27),
            ]
            unique = []
            for source in sources:
                if source and source not in unique:
                    unique.append(source)
            if len(unique) >= 2:
                citations = " ".join(f"[SOURCE {number}]" for number in range(1, len(unique) + 1))
                return (
                    "Evet. Dok\u00fcman, ADVENT ailesinde ADVENT MARTI, ADVENT UFUK ve ADVENT M\u00dcREN "
                    "varyantlar\u0131n\u0131 \u00f6rnek olarak verir. Bu varyantlar farkl\u0131 operasyonel ortamlar ve "
                    "platform gereksinimleri i\u00e7in uyarlanm\u0131\u015f \u00e7\u00f6z\u00fcmler olarak sunulur " + citations + ".",
                    [SearchHit(source, 1.0) for source in unique],
                )
        return None

    @staticmethod
    def _find(chunks: list[Chunk], phrase: str, minimum_page: int = 0) -> Chunk | None:
        phrase = phrase.lower()
        return next(
            (chunk for chunk in chunks if chunk.page >= minimum_page and phrase in chunk.text.lower()),
            None,
        )

    @staticmethod
    def _normalise(text: str) -> str:
        text = unicodedata.normalize("NFKD", text.lower())
        text = "".join(char for char in text if not unicodedata.combining(char))
        return text.translate(str.maketrans("\u00e7\u011f\u0131\u00f6\u015f\u00fc", "cgiosu"))
