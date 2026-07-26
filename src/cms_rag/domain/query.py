"""Türkçe sorgu normalizasyonu ve kontrollü CMS terim genişletmesi."""

from __future__ import annotations

import unicodedata


class CMSQueryProcessor:
    """Kullanıcı sorularını alan kontrolü ve retrieval için hazırlar."""

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
        """Bilinen Türkçe terimlerin İngilizce teknik karşılıklarını sorguya ekler."""

        normalized = cls.normalise(query)
        additions = [english for turkish, english in cls._GLOSSARY.items() if turkish in normalized]
        return f"{query} {' '.join(additions)}" if additions else query

    @classmethod
    def is_non_domain_chitchat(cls, query: str) -> bool:
        """Kimlik ve gündelik sohbet sorularını kaynak aramasından önce yakalar."""

        normalized = cls.normalise(query).strip(" ?!.")
        return normalized in {
            "ben kimim", "sen kimsin", "merhaba", "selam", "nasilsin", "tesekkurler",
        }

    @staticmethod
    def normalise(text: str) -> str:
        """Unicode birleşik işaretlerini kaldırarak karşılaştırmayı kararlı kılar."""

        text = unicodedata.normalize("NFKD", text.lower())
        return "".join(char for char in text if not unicodedata.combining(char))
