"""Küratörlü araştırma metinlerini PDF'e ve önceden hesaplanmış RAG snapshot'ına dönüştürür."""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from pypdf import PdfReader

from src.cms_rag.infrastructure.knowledge import load_curated_chunks
from src.cms_rag.infrastructure.retrieval import HybridRetriever


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONTENT_DIR = ROOT / "knowledge_base" / "content"
KNOWLEDGE_DIR = DATA_DIR / "knowledge_base"
SOURCE_DIR = KNOWLEDGE_DIR / "sources"
SNAPSHOT_DIR = KNOWLEDGE_DIR / "snapshot"
PACKAGED_BROCHURE = (
    DATA_DIR
    / "documents"
    / "ec48e76816a4a41e6ee57611e0c755d112443f3411c762b4702c858ee64c4934_advent_cms.pdf"
)

CURATED_DOCUMENTS = (
    {
        "content": "01_advent_cms_public_research.md",
        "output": "advent_cms_kamuya_acik_arastirma.pdf",
        "title": "ADVENT CMS Kamuya Açık Araştırma Özeti",
        "collection": "official",
        "authority": "HAVELSAN public official sources — curated",
        "source_url": "https://www.havelsan.com/en/solutions/advent-combat-management-system",
    },
    {
        "content": "02_advent_ai_public_research.md",
        "output": "advent_ai_kamuya_acik_arastirma.pdf",
        "title": "ADVENT AI Kamuya Açık Araştırma Özeti",
        "collection": "official",
        "authority": "HAVELSAN public official sources — curated",
        "source_url": "https://www.havelsan.com/en/news/havelsan-showcase-advent-ai-and-barkan-3-first-time-saha-expo-2026",
    },
    {
        "content": "03_data_ai_governance_public_research.md",
        "output": "deniz_c2_veri_ai_yonetisim_arastirma.pdf",
        "title": "Deniz C2, Veri ve Sorumlu AI Açık Kaynak Özeti",
        "collection": "open_source",
        "authority": "NATO and U.S. Navy public official sources — curated",
        "source_url": "https://www.nato.int/en/about-us/official-texts-and-resources/official-texts/2024/07/10/summary-of-natos-revised-artificial-intelligence-ai-strategy",
    },
)


def _register_fonts() -> tuple[str, str]:
    """Türkçe karakterleri PDF'e gömmek için sistem fontlarını kaydeder."""

    regular = Path("C:/Windows/Fonts/arial.ttf")
    bold = Path("C:/Windows/Fonts/arialbd.ttf")
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("CorpusSans", str(regular)))
        pdfmetrics.registerFont(TTFont("CorpusSans-Bold", str(bold)))
        return "CorpusSans", "CorpusSans-Bold"
    return "Helvetica", "Helvetica-Bold"


def _styles() -> dict[str, ParagraphStyle]:
    """Kurumsal ve okunabilir bilgi paketi stillerini oluşturur."""

    regular, bold = _register_fonts()
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "CorpusTitle",
            parent=base["Title"],
            fontName=bold,
            fontSize=22,
            leading=27,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0B1F3A"),
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "CorpusH2",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#174A7E"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "CorpusBody",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=10.2,
            leading=15,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=7,
            splitLongWords=True,
        ),
        "small": ParagraphStyle(
            "CorpusSmall",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#5B6573"),
        ),
    }


def _story(markdown: str, title: str) -> list:
    """Sınırlı Markdown başlık, paragraf ve listelerini ReportLab akışına çevirir."""

    styles = _styles()
    lines = markdown.splitlines()
    story: list = [
        Spacer(1, 18 * mm),
        Paragraph(escape(title), styles["title"]),
        Paragraph(
            "Kürasyon tarihi: 30 Temmuz 2026 · Yalnız kamuya açık kaynaklar",
            styles["small"],
        ),
        Spacer(1, 10 * mm),
    ]
    paragraph: list[str] = []
    bullets: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            story.append(Paragraph(escape(" ".join(paragraph)), styles["body"]))
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            story.append(
                ListFlowable(
                    [
                        ListItem(Paragraph(escape(item), styles["body"]))
                        for item in bullets
                    ],
                    bulletType="bullet",
                    leftIndent=16,
                    bulletFontName=styles["body"].fontName,
                )
            )
            bullets.clear()

    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            flush_paragraph()
            flush_bullets()
            story.append(Paragraph(escape(line[3:]), styles["h2"]))
        elif line.startswith("- "):
            flush_paragraph()
            bullets.append(line[2:])
        elif not line:
            flush_paragraph()
            flush_bullets()
        else:
            paragraph.append(line)
    flush_paragraph()
    flush_bullets()
    return story


def _render_pdf(markdown_path: Path, output_path: Path, title: str) -> None:
    """Bir küratörlü araştırma metnini metin çıkarımı yapılabilir PDF'e dönüştürür."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".tmp.pdf")
    document = SimpleDocTemplate(
        str(temporary_path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="CMS-RAG Public Research Pipeline",
        subject="Kamuya açık ve önceden küratörlenmiş RAG bilgi paketi",
    )

    def decorate(canvas, doc) -> None:
        """Her sayfaya bilgi sınırı ve sayfa numarası ekler."""

        canvas.saveState()
        regular, _ = _register_fonts()
        canvas.setFont(regular, 7.5)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(
            20 * mm,
            10 * mm,
            "Kamuya açık ön çalışma · Şirket içi/tasnifli veri içermez",
        )
        canvas.drawRightString(
            A4[0] - 20 * mm,
            10 * mm,
            f"Sayfa {doc.page}",
        )
        canvas.restoreState()

    document.build(
        _story(markdown_path.read_text(encoding="utf-8"), title),
        onFirstPage=decorate,
        onLaterPages=decorate,
    )
    if output_path.exists():
        current_text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(str(output_path)).pages
        )
        generated_text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(str(temporary_path)).pages
        )
        if current_text == generated_text:
            temporary_path.unlink()
            return
    temporary_path.replace(output_path)


def _write_manifest() -> list[Path]:
    """Üretilen PDF'lerin koleksiyon ve kaynak metadata manifestini yazar."""

    sources = [
        {
            "path": f"knowledge_base/sources/{record['output']}",
            "collection": record["collection"],
            "authority": record["authority"],
            "source_url": record["source_url"],
        }
        for record in CURATED_DOCUMENTS
    ]
    sources.insert(
        0,
        {
            "path": f"documents/{PACKAGED_BROCHURE.name}",
            "collection": "official",
            "authority": "HAVELSAN public official brochure",
            "source_url": "https://www.havelsan.com/uploads/docs/cozumler/komuta-kontrol/1753946379_advent-cms.pdf",
        },
    )
    manifest = {
        "schema_version": 1,
        "knowledge_cutoff": "2026-07-30",
        "runtime_web_access": False,
        "data_boundary": (
            "Yalnız kamuya açık kaynaklar; şirket içi, tasnifli veya kişisel veri yok."
        ),
        "sources": sources,
    }
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    (KNOWLEDGE_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return [DATA_DIR / item["path"] for item in sources]


def main() -> int:
    """PDF paketlerini üretir, chunklar ve belge embedding snapshot'ını kaydeder."""

    for record in CURATED_DOCUMENTS:
        _render_pdf(
            CONTENT_DIR / record["content"],
            SOURCE_DIR / record["output"],
            record["title"],
        )
    source_paths = _write_manifest()
    chunks = load_curated_chunks(DATA_DIR)
    retriever = HybridRetriever(chunks, enable_reranker=False)
    retriever.save_snapshot(
        SNAPSHOT_DIR,
        source_hashes=[
            HybridRetriever.file_sha256(path)
            for path in source_paths
        ],
    )
    print(
        json.dumps(
            {
                "pdf_count": len(source_paths),
                "chunk_count": len(chunks),
                "snapshot": str(SNAPSHOT_DIR),
                "runtime_web_access": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
