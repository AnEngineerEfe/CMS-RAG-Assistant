"""Doğal dildeki sınırlı iz kontrol isteklerini güvenli alan modellerine dönüştürür."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from enum import Enum
import re
import unicodedata


class TrackIntent(str, Enum):
    """Bir kullanıcı iletisinin iz kontrolü açısından taşıdığı niyeti belirtir."""

    NOT_TRACK = "not_track"
    READ = "read"
    WRITE = "write"
    PARTIAL_WRITE = "partial_write"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class TrackState:
    """MCP Swing uygulamasının doğrulanmış, taşıma-bağımsız iz durumudur."""

    speed_knots: float
    heading_degrees: int
    ship_type: str
    ship_type_label: str = ""

    def __post_init__(self) -> None:
        """Sınır dışı veya tanımsız durumların uygulama katmanına geçmesini engeller."""

        if not 0 <= self.speed_knots <= 100:
            raise ValueError("Hız 0 ile 100 knot arasında olmalıdır.")
        if not 0 <= self.heading_degrees <= 360:
            raise ValueError("Yön 0 ile 360 derece arasında olmalıdır.")
        if self.ship_type not in SHIP_TYPE_LABELS:
            raise ValueError(f"Geçersiz gemi tipi: {self.ship_type}")

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "TrackState":
        """MCP aracının JSON sonucunu tipli ve doğrulanmış duruma çevirir."""

        ship_type = str(payload["shipType"])
        return cls(
            speed_knots=float(payload["speedKnots"]),
            heading_degrees=int(payload["headingDegrees"]),
            ship_type=ship_type,
            ship_type_label=str(payload.get("shipTypeLabel") or SHIP_TYPE_LABELS.get(ship_type, ship_type)),
        )

    def as_mcp_arguments(self) -> dict[str, object]:
        """Durumu atomik `set_track_state` aracının beklediği sözleşmeye dönüştürür."""

        return {
            "speedKnots": self.speed_knots,
            "headingDegrees": self.heading_degrees,
            "shipType": self.ship_type,
        }


@dataclass(frozen=True)
class TrackRequest:
    """Kullanıcı metninden çıkarılan niyeti ve yalnızca açıkça verilen alanları taşır."""

    intent: TrackIntent
    speed_knots: float | None = None
    heading_degrees: int | None = None
    ship_type: str | None = None
    reason: str = ""
    warnings: tuple[str, ...] = ()


SHIP_TYPE_LABELS = {
    "BELIRSIZ": "Belirsiz",
    "FIRKATEYN": "Fırkateyn",
    "KORVET": "Korvet",
    "MUHRIP": "Muhrip",
    "DENIZALTI": "Denizaltı",
    "HUCUMBOT": "Hücumbot",
    "TICARI_GEMI": "Ticari Gemi",
    "YARDIMCI_GEMI": "Yardımcı Gemi",
}

_SHIP_ALIASES = {
    "belirsiz": "BELIRSIZ",
    "firkateyn": "FIRKATEYN",
    "korvet": "KORVET",
    "muhrip": "MUHRIP",
    "denizalti": "DENIZALTI",
    "hucumbot": "HUCUMBOT",
    "ticari gemi": "TICARI_GEMI",
    "yardimci gemi": "YARDIMCI_GEMI",
}


def parse_track_request(text: str) -> TrackRequest:
    """Sadece açık ve sınırlandırılmış iz okuma/yazma ifadelerini komut kabul eder."""

    normalized = _normalize(text)
    write_signal = bool(
        re.search(r"\b(yap|ayarla|degistir|guncelle|ata|uygula|olsun)\b", normalized)
    )
    read_signal = bool(
        re.search(
            r"\b(mevcut|simdiki|su anki|kac|nedir|ne|goster|oku|durum)\b",
            normalized,
        )
    )
    explicit_track = bool(
        re.search(
            r"\b(iz durum\w*|iz deger\w*|iz kontrol\w*|mcp|swing|ekrandaki|uygulamadaki)\b",
            normalized,
        )
    )
    field_signal = bool(
        re.search(
            r"\b(hiz|surat|yon|rota|gemi tipi|iz tipi|tipi|tipini|tipin)\w*\b",
            normalized,
        )
    )
    speed_requested = bool(re.search(r"\b(hiz|surat)\w*\b", normalized))
    heading_requested = bool(re.search(r"\b(yon|rota)\w*\b", normalized))
    ship_requested = bool(
        re.search(r"\b(gemi tipi\w*|iz tipi\w*|tipi|tipini|tipin)\b", normalized)
    )

    speed = _extract_decimal(normalized, ("hiz", "surat"))
    heading_decimal = _extract_decimal(normalized, ("yon", "rota"))
    heading: int | None = None
    heading_integer_error = False
    if heading_decimal is not None:
        if not heading_decimal.is_integer():
            heading_integer_error = True
        else:
            heading = int(heading_decimal)
    ship_type = _extract_ship_type(normalized)

    # Geçersiz alanlar sessizce yok sayılmaz. Birleşik komutta başka geçerli alanlar
    # varsa bunlar ayrıca onaya sunulur; sorunlu alanlar değişmeden korunur.
    validation_errors: list[str] = []
    transformation_warnings: list[str] = []
    if write_signal and speed_requested and speed is None:
        validation_errors.append(
            "Hız değiştirilmeyecek: 0 ile 100 arasında sayısal bir knot değeri belirtin."
        )
    if write_signal and heading_requested and heading_decimal is None:
        validation_errors.append(
            "Yön değiştirilmeyecek: tam sayı derece belirtin."
        )
    if heading_integer_error:
        validation_errors.append(
            "Yön değiştirilmeyecek: ondalıklı açı yerine tam sayı derece belirtin."
        )
        heading = None
    if write_signal and ship_requested and ship_type is None:
        candidate = _extract_unknown_ship_candidate(normalized)
        prefix = f"‘{candidate}’ " if candidate else "Belirtilen değer "
        suggestion = _suggest_ship_type(candidate)
        suggestion_text = (
            f" “{SHIP_TYPE_LABELS[suggestion]}” demek istemiş olabilir misiniz?"
            if suggestion
            else ""
        )
        validation_errors.append(
            f"Gemi tipi değiştirilmeyecek: {prefix}tanımlı bir tip değil."
            f"{suggestion_text} İzin verilen tipler: "
            f"{', '.join(SHIP_TYPE_LABELS.values())}."
        )
    if speed is not None and not 0 <= speed <= 100:
        validation_errors.append(
            f"Hız değiştirilmeyecek: {speed:g} knot, izin verilen 0–100 aralığının dışında."
        )
        speed = None
    if heading is not None and (heading < 0 or heading > 360):
        original_heading = heading
        heading %= 360
        transformation_warnings.append(
            f"Yön {original_heading}° değeri esas açıya dönüştürüldü: {heading}°."
        )
    has_values = any(value is not None for value in (speed, heading, ship_type))
    if validation_errors:
        if write_signal and has_values and (field_signal or explicit_track):
            return TrackRequest(
                TrackIntent.PARTIAL_WRITE,
                speed,
                heading,
                ship_type,
                reason="Geçerli alanlar onayınıza sunulacak; uygun olmayan alanlar korunacak.",
                warnings=tuple(validation_errors + transformation_warnings),
            )
        return TrackRequest(
            TrackIntent.AMBIGUOUS,
            reason="Komutun tamamı uygulanmadı. " + " ".join(validation_errors),
        )
    if write_signal and has_values and (field_signal or explicit_track):
        return TrackRequest(
            TrackIntent.WRITE,
            speed,
            heading,
            ship_type,
            warnings=tuple(transformation_warnings),
        )
    if write_signal and (field_signal or explicit_track):
        return TrackRequest(
            TrackIntent.AMBIGUOUS,
            reason="Değiştirilecek hız, yön veya gemi tipi açıkça belirtilmedi.",
        )
    if (explicit_track and read_signal) or (
        field_signal and read_signal and _looks_like_direct_state_question(normalized)
    ):
        return TrackRequest(TrackIntent.READ)
    return TrackRequest(TrackIntent.NOT_TRACK)


def _looks_like_direct_state_question(text: str) -> bool:
    """Genel CMS bilgi sorularını canlı durum okuma komutlarından ayırır."""

    return bool(
        re.search(
            r"\b(hiz\w* kac|yon\w* kac|gemi tipi\w* ne|iz tipi\w* ne|"
            r"mevcut hiz|mevcut yon|mevcut gemi|durumu goster|degerleri goster)\b",
            text,
        )
    )


def _extract_decimal(text: str, fields: tuple[str, ...]) -> float | None:
    """Alan adından sonra gelen nokta veya virgüllü sayıyı güvenle çıkarır."""

    names = "|".join(re.escape(field) for field in fields)
    match = re.search(
        rf"\b(?:{names})\w*\s*(?:deger\w*\s*)?(?:=|:)?\s*(-?\d+(?:[.,]\d+)?)",
        text,
    )
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _extract_ship_type(text: str) -> str | None:
    """Kullanıcı dostu Türkçe gemi adını kapalı MCP enum değerine eşler."""

    for alias in sorted(_SHIP_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return _SHIP_ALIASES[alias]
    return None


def _extract_unknown_ship_candidate(text: str) -> str:
    """Tanınmayan gemi tipi ifadesini yalnız hata mesajında göstermek üzere çıkarır."""

    match = re.search(
        r"\b(?:gemi tipi\w*|iz tipi\w*|tipi|tipini|tipin)\s*"
        r"(?:=|:)?\s*([a-z_]+(?:\s+[a-z_]+)?)\s+"
        r"(?:yap|ayarla|degistir|guncelle|ata|uygula|olsun)\b",
        text,
    )
    return match.group(1).strip() if match else ""


def _suggest_ship_type(candidate: str) -> str | None:
    """Küçük yazım hatalarında en yakın izinli tipi yalnız öneri olarak döndürür."""

    if not candidate:
        return None
    matches = get_close_matches(candidate, list(_SHIP_ALIASES), n=1, cutoff=0.68)
    return _SHIP_ALIASES[matches[0]] if matches else None


def _normalize(text: str) -> str:
    """Türkçe metni eşleme için küçük harfli ve aksansız bir biçime getirir."""

    translated = text.casefold().translate(str.maketrans({"ı": "i", "ğ": "g", "ş": "s"}))
    decomposed = unicodedata.normalize("NFKD", translated)
    return " ".join(
        "".join(character for character in decomposed if not unicodedata.combining(character)).split()
    )
