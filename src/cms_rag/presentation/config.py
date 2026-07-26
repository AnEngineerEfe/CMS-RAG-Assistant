"""Sunum katmanının yol, etiket ve görünüm sabitleri."""

from pathlib import Path


# Paket dört seviye aşağıda bulunduğu için proje kökünü tek bir güvenilir yerden çözeriz.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"

# Seçim değerleri çekirdek motorun kabul ettiği koleksiyon adlarıyla birebir eşleşir.
SOURCE_SCOPES = ("all", "official", "open_source")
SOURCE_SCOPE_LABELS = {
    "all": "Birleşik · tüm güvenilir kaynaklar",
    "official": "Yalnızca resmî HAVELSAN",
    "open_source": "Yalnızca açık/kamu referansları",
}

# Bu ifadeler model hatası veya yetersiz kanıt durumunda kaynak kartlarını gizler.
UNSUPPORTED_ANSWER_MARKERS = (
    "yeterli kaynak bulunamadı",
    "ollama servisine ulaşılamadı",
)
