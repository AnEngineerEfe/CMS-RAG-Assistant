"""Türkçe sorgu normalizasyonu ve kontrollü CMS terim genişletmesi."""

from __future__ import annotations

import unicodedata


class CMSQueryProcessor:
    """Kullanıcı sorularını alan kontrolü ve retrieval için hazırlar."""

    _GLOSSARY = {
        "savas yonetim sistemi": "combat management system CMS",
        "temel islev": "combat management system command and control mission management",
        "komuta kontrol": "command control C2",
        "durumsal farkindalik": "situational awareness",
        "iz yonetimi": "track management track fusion",
        "izler": "track data fusion track management",
        "ortak taktik resim": "common tactical picture track data fusion",
        "sensorlerden gelen": "sensor track data fusion",
        "taktik veri": "tactical data link TDL",
        "veri baglantisi": "data link TDL",
        "ag destekli yetenek": "network enabled capability distributed execution",
        "ortak angajman": "common engagement capability engagement",
        "silah ve sensor": "weapon and sensor resource pool resource allocation",
        "kaynak havuzu": "resource pool resource allocation",
        "yapay zeka": "artificial intelligence AI",
        "anomali tespiti": "anomaly detection",
        "platform entegrasyonu": "platform systems integration plug-and-play",
        "savas gemisi": "surface platform naval combat system warship",
        "su ustu": "surface platforms central component warship",
        "deniz platformu": "surface platform naval operations",
        "denizalti": "subsurface underwater platform",
        "mayin harbi": "mine warfare post-op analysis",
        "hava platformu": "airborne platform",
        "insansiz": "unmanned platform",
        "egitim": "training ADVENT Academy",
        "akilli operator asistani": "smart operator assistant",
        "gecmis karar": "smart operator assistant recommendations past decisions behaviors",
        "tavsiye veren": "smart operator assistant recommendations past decisions behaviors",
        "ortak sanal": "common training shared virtual environment interactive virtual training",
        "musterek egitim": "common training shared virtual environment interactive virtual training",
        "isletim sistemi cekirdegi": "operating system kernel",
        "calisma frekansi": "operating frequency",
        "muren": "ADVENT MUREN underwater platforms target motion analysis",
        "marti": "ADVENT MARTI airborne command control",
        "rota": "ADVENT ROTA unmanned surface vehicle",
        "ufuk": "ADVENT UFUK maritime security situational awareness",
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

    @classmethod
    def requests_restricted_information(cls, query: str) -> bool:
        """Kamu bilgi tabanının kapsamı dışındaki gizli/özel veri taleplerini belirler."""

        normalized = cls.normalise(query)
        restricted_markers = {
            "gizli",
            "tasnifli",
            "siniflandirilmis",
            "operasyonel konfigurasyon",
            "gorevdeki bir",
        }
        return any(marker in normalized for marker in restricted_markers)

    @classmethod
    def required_attribute_terms(cls, query: str) -> tuple[str, ...]:
        """Cevap için kaynakta açıkça bulunması gereken hassas nitelikleri döndürür."""

        normalized = cls.normalise(query)
        requirements = {
            "isletim sistemi": ("kernel",),
            "cekirdek": ("kernel",),
            "frekans": ("frequency",),
            "fiyat": ("price", "cost"),
            "garanti": ("warranty",),
            "personel sayisi": ("crew", "personnel"),
            "butce": ("budget",),
            "menzil": ("range",),
            "sifreleme algoritmasi": ("encryption algorithm",),
            "koordinat": ("coordinates",),
            "ram": ("ram",),
            "egitim suresi": ("duration", "hours"),
            "parola": ("password",),
        }
        required: list[str] = []
        for marker, terms in requirements.items():
            if marker in normalized:
                required.extend(terms)
        return tuple(dict.fromkeys(required))

    @staticmethod
    def normalise(text: str) -> str:
        """Unicode birleşik işaretlerini kaldırarak karşılaştırmayı kararlı kılar."""

        text = unicodedata.normalize("NFKD", text.lower()).replace("ı", "i")
        return "".join(char for char in text if not unicodedata.combining(char))
