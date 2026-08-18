"""Türkçe sorgu normalizasyonu ve kontrollü CMS terim genişletmesi."""

from __future__ import annotations

import unicodedata


class CMSQueryProcessor:
    """Kullanıcı sorularını alan kontrolü ve retrieval için hazırlar."""

    _OVERVIEW_INTENT_MARKERS = (
        "amac",
        "hizmet et",
        "ise yar",
        "islev",
        "gorev",
        "ne yapar",
        "ne saglar",
    )
    _OVERVIEW_SUBJECTS = {
        "advent": ("advent",),
        "advent-ai": ("advent-ai", "advent",),
        "main": ("main",),
        "kalyon": ("kalyon",),
        "muren": ("muren",),
        "marti": ("marti",),
        "rota": ("rota",),
        "ufuk": ("ufuk",),
        "savas yonetim sistemi": ("cms", "combat", "management",),
        "combat management system": ("cms", "combat", "management",),
        "cms": ("cms", "combat", "management",),
    }

    _GLOSSARY = {
        "savas yonetim sistemi": "combat management system CMS",
        "temel islev": "combat management system command and control mission management",
        "komuta kontrol": "command control C2",
        "durumsal farkindalik": "situational awareness",
        "iz yonetimi": "track management track fusion",
        "iz verilerini": "track data correlation merging algorithms unified view",
        "izler": "track data fusion track management",
        "ortak taktik resim": "common tactical picture track data fusion",
        "sensorlerden gelen": "sensor track data fusion",
        "taktik veri": "tactical data link TDL",
        "link turlerini": "link types additional software hardware link data processor",
        "veri baglantisi": "data link TDL",
        "ag destekli yetenek": "network enabled capability distributed execution",
        "arastirma merkezi": "Turkish Naval Forces Research Center Command ARMERKOM command control requirements",
        "ortak harekat": "common operation centralized operational planning coordinated controlled execution",
        "ortak operasyon": "common operations centralized planning distribution simultaneous execution search rescue navigation",
        "seyir destegi": "navigation support swept-channel navigation safety anchoring",
        "tek gemi": "individual ships collaborative training network-enabled capability",
        "ozel konsol": "dedicated consoles SONAR ESM TDL weapon systems",
        "mcm hizmet": "MCM services planning preparation realization post-op analysis",
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
        "muren": "ADVENT MUREN underwater platforms Preveze Class Submarines target motion analysis",
        "marti": "ADVENT MARTI airborne command control data collection analysis fusion tactical data links",
        "rota": "ADVENT ROTA unmanned platform navigation system modular flexible interfaces",
        "ufuk": "ADVENT UFUK maritime security radars IFF ADSB AIS electronic support systems",
        "bakim destek": "maintenance support instructions question answering natural language",
        "bilgi zinciri": "sensor data decision support mission resources information chain",
        "bilgi katmani": "topographic oceanographic meteorology imagery intelligence common operational picture",
        "kimlik dogrulama": "zero trust authentication authorization before enterprise resource access",
        "risk yonetimini": "NIST AI RMF Govern Map Measure Manage lifecycle risk management",
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
            "uretim veritabani",
            "ip adresi",
            "yonetim portu",
            "kamuya aciklanmamis",
            "teslimat takvimi",
            "musteri gemi eslestirme",
            "yetki kod",
            "kalibrasyon esik",
            "ham katsayi",
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

    @classmethod
    def is_overview_intent(cls, query: str) -> bool:
        """Bir ürün veya sistemin genel amaç, görev ya da işlevinin sorulduğunu belirler."""

        normalized = cls.normalise(query)
        return any(marker in normalized for marker in cls._OVERVIEW_INTENT_MARKERS)

    @classmethod
    def overview_subject_terms(cls, query: str) -> tuple[str, ...]:
        """Genel bakış sorusunda kanıtta da bulunması gereken kontrollü konu adlarını verir."""

        normalized = cls.normalise(query)
        subjects: list[str] = []
        for marker, aliases in cls._OVERVIEW_SUBJECTS.items():
            if marker in normalized:
                subjects.extend(aliases)
        return tuple(dict.fromkeys(subjects))

    @staticmethod
    def normalise(text: str) -> str:
        """Unicode birleşik işaretlerini kaldırarak karşılaştırmayı kararlı kılar."""

        text = unicodedata.normalize("NFKD", text.lower()).replace("ı", "i")
        return "".join(char for char in text if not unicodedata.combining(char))
