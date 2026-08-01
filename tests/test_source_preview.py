"""PDF kanıt önizlemesinin yol güvenliği ve sayfa üretimi testleri."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.cms_rag.presentation.config import DATA_DIR
from src.cms_rag.presentation.source_preview import (
    render_pdf_page,
    resolve_local_pdf,
)


class SourcePreviewTests(unittest.TestCase):
    """Yerel kanıt görüntüleyicisinin veri dizini sınırlarını doğrular."""

    def test_path_outside_data_directory_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            outside = root / "outside.pdf"
            outside.write_bytes(b"%PDF-1.4")

            self.assertIsNone(resolve_local_pdf(str(outside), data))

    def test_packaged_pdf_page_is_rendered_as_png(self):
        source = next((DATA_DIR / "knowledge_base" / "sources").glob("*.pdf"))
        resolved = resolve_local_pdf(str(source), DATA_DIR)

        self.assertEqual(resolved, source.resolve())
        image = render_pdf_page(str(source), 1, source.stat().st_mtime_ns)
        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))
