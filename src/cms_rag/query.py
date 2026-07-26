"""Turkish-aware query normalisation and controlled CMS terminology expansion."""

from __future__ import annotations

import unicodedata


class CMSQueryProcessor:
    _GLOSSARY = {
        "savas yonetim sistemi": "combat management system CMS",
        "komuta kontrol": "command control C2",
        "durumsal farkindalik": "situational awareness",
        "iz yonetimi": "track management track fusion",
        "taktik veri": "tactical data link TDL",
        "veri baglantisi": "data link TDL",
        "savas gemisi": "surface platform naval combat system warship",
        "deniz platformu": "surface platform naval operations",
        "denizalti": "subsurface underwater platform",
        "hava platformu": "airborne platform",
        "insansiz": "unmanned platform",
    }

    @classmethod
    def expand(cls, query: str) -> str:
        normalized = cls.normalise(query)
        additions = [english for turkish, english in cls._GLOSSARY.items() if turkish in normalized]
        return f"{query} {' '.join(additions)}" if additions else query

    @classmethod
    def is_non_domain_chitchat(cls, query: str) -> bool:
        normalized = cls.normalise(query).strip(" ?!.")
        return normalized in {
            "ben kimim", "sen kimsin", "merhaba", "selam", "nasilsin", "tesekkurler",
        }

    @staticmethod
    def normalise(text: str) -> str:
        text = unicodedata.normalize("NFKD", text.lower())
        return "".join(char for char in text if not unicodedata.combining(char))
