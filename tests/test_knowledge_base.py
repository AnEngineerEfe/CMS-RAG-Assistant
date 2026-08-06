"""Önceden hazırlanmış ve çalışma-anında çevrimdışı bilgi tabanı testleri."""

import json
from pathlib import Path
import unittest

from pypdf import PdfReader

from src.cms_rag.application import CMSRAGEngine
from src.cms_rag.infrastructure import HybridRetriever, load_manifest


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
KNOWLEDGE_ROOT = DATA_DIR / "knowledge_base"


class PreparedKnowledgeBaseTests(unittest.TestCase):
    """Paketlenmiş PDF, manifest ve snapshot sözleşmesini korur."""

    def test_manifest_declares_offline_runtime_and_five_public_sources(self):
        """Manifestin ağsız çalışma ve beş kamuya açık kaynak bildirmesini ister."""

        manifest = load_manifest(KNOWLEDGE_ROOT)
        self.assertFalse(manifest["runtime_web_access"])
        self.assertEqual(len(manifest["sources"]), 5)
        self.assertIn("şirket içi", manifest["data_boundary"].lower())

    def test_curated_pdfs_are_extractable_and_contain_scope_boundary(self):
        """Üretilen PDF'lerin metin çıkarımı ve veri sınırı taşımasını doğrular."""

        pdfs = sorted((KNOWLEDGE_ROOT / "sources").glob("*.pdf"))
        self.assertEqual(len(pdfs), 4)
        for path in pdfs:
            text = " ".join(
                page.extract_text() or ""
                for page in PdfReader(str(path)).pages
            )
            self.assertGreater(len(text), 1000)
            self.assertIn("kamuya açık", text.lower())

    def test_snapshot_contains_precomputed_vectors_for_every_chunk(self):
        """Snapshot metadata ve embedding satır sayısının bire bir eşleşmesini ister."""

        metadata = json.loads(
            (KNOWLEDGE_ROOT / "snapshot" / "snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        import numpy as np

        vectors = np.load(
            KNOWLEDGE_ROOT / "snapshot" / "embeddings.npy",
            allow_pickle=False,
        )
        self.assertEqual(metadata["chunk_count"], len(metadata["chunks"]))
        self.assertEqual(metadata["chunk_count"], len(vectors))
        self.assertEqual(len(metadata["source_sha256"]), 5)

    def test_engine_loads_snapshot_and_protects_packaged_brochure(self):
        """Uygulamanın hazır snapshot'ı kullanmasını ve çekirdek PDF'i ek belge saymamasını ister."""

        engine = CMSRAGEngine(DATA_DIR)
        count = engine.rebuild()
        metadata = json.loads(
            (KNOWLEDGE_ROOT / "snapshot" / "snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(engine.snapshot_loaded)
        self.assertEqual(count, metadata["chunk_count"])
        self.assertGreaterEqual(count, 60)
        self.assertEqual(engine.prepared_document_count(), 5)
        self.assertEqual(engine.supplemental_records(), [])
        common_questions = {
            "ADVENT-AI operatöre nasıl destek olur?": "bilişsel yük",
            "MAIN bakım destek asistanı ne yapar?": "bakım adımlarını",
            "NATO sorumlu yapay zekâ ilkeleri nelerdir?": "hukuka uygunluk",
            "ADVENT ROTA ne görev yapar?": "insansız platform",
        }
        for question, expected in common_questions.items():
            with self.subTest(question=question):
                answer, hits = engine.ask(question)
                self.assertIn(expected, answer.lower())
                self.assertTrue(hits)
                self.assertIn("[SOURCE 1]", answer)

    def test_snapshot_hashes_include_packaged_brochure(self):
        """Resmî broşür hash'inin hazır kaynaklar arasında bulunduğunu doğrular."""

        hashes = HybridRetriever.snapshot_source_hashes(
            KNOWLEDGE_ROOT / "snapshot"
        )
        brochure = next((DATA_DIR / "documents").glob("*.pdf"))
        self.assertIn(HybridRetriever.file_sha256(brochure), hashes)


if __name__ == "__main__":
    unittest.main()
