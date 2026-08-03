"""Yerel PDF kanıtlarını güvenli biçimde ilgili sayfada önizler."""

from __future__ import annotations

from pathlib import Path
from io import BytesIO
from typing import Any

import streamlit as st

from .config import DATA_DIR


def resolve_local_pdf(source_path: str, data_dir: Path = DATA_DIR) -> Path | None:
    """Yalnız veri dizini içindeki mevcut PDF yollarını kabul eder."""

    if not source_path:
        return None
    candidate = Path(source_path)
    if not candidate.is_absolute():
        candidate = data_dir / candidate
    candidate = candidate.resolve()
    root = data_dir.resolve()
    if root not in candidate.parents or candidate.suffix.lower() != ".pdf":
        return None
    return candidate if candidate.is_file() else None


@st.cache_data(show_spinner=False)
def render_pdf_page(source_path: str, page_number: int, mtime_ns: int) -> bytes:
    """PDF sayfasını PyMuPDF veya taşınabilir PDFium yedeğiyle PNG'ye dönüştürür."""

    del mtime_ns
    try:
        return _render_with_pymupdf(source_path, page_number)
    except (ImportError, OSError):
        return _render_with_pdfium(source_path, page_number)


def _render_with_pymupdf(source_path: str, page_number: int) -> bytes:
    """PyMuPDF kullanılabiliyorsa hızlı sayfa görüntüsü üretir."""

    import fitz

    with fitz.open(source_path) as document:
        if not document.page_count:
            raise ValueError("PDF içinde görüntülenecek sayfa bulunamadı.")
        page_index = min(max(page_number - 1, 0), document.page_count - 1)
        page = document.load_page(page_index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.45, 1.45), alpha=False)
        return pixmap.tobytes("png")


def _render_with_pdfium(source_path: str, page_number: int) -> bytes:
    """Windows DLL sorunu yaşandığında PDFium ile aynı PNG çıktısını üretir."""

    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(source_path)
    if not len(document):
        document.close()
        raise ValueError("PDF içinde görüntülenecek sayfa bulunamadı.")
    page_index = min(max(page_number - 1, 0), len(document) - 1)
    page = document[page_index]
    bitmap = page.render(scale=1.45)
    image = bitmap.to_pil()
    stream = BytesIO()
    image.save(stream, format="PNG")
    bitmap.close()
    page.close()
    document.close()
    return stream.getvalue()


@st.dialog("Kanıt sayfası", width="large")
def show_source_preview(source: dict[str, Any]) -> None:
    """Seçilen kanıtın sayfa görüntüsünü ve indirme seçeneklerini sunar."""

    path = resolve_local_pdf(str(source.get("source_path", "")))
    page_number = max(int(source.get("page", 1)), 1)
    st.markdown(f"**{source.get('document', 'Belge')}** · Sayfa {page_number}")
    if not path:
        st.warning("Bu kanıt için güvenli bir yerel PDF önizlemesi bulunamadı.")
        _render_public_link(source)
        return
    try:
        image = render_pdf_page(str(path), page_number, path.stat().st_mtime_ns)
        st.image(image, width="stretch")
    except (ImportError, ValueError, RuntimeError) as error:
        st.warning(f"PDF sayfası görüntülenemedi: {error}")
    left, right = st.columns(2)
    left.download_button(
        "PDF'i indir",
        data=path.read_bytes(),
        file_name=str(source.get("document", path.name)),
        mime="application/pdf",
        width="stretch",
    )
    with right:
        _render_public_link(source)


def _render_public_link(source: dict[str, Any]) -> None:
    """Varsa kamuya açık özgün kaynak bağlantısını güvenli bileşenle gösterir."""

    url = str(source.get("source_url", ""))
    if url.startswith(("https://", "http://")):
        st.link_button("Kamu kaynağını aç", url, width="stretch")
