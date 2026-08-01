"""Gizlilik korumalı audit deposu ve motor entegrasyonu testleri."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.cms_rag.application import CMSRAGEngine
from src.cms_rag.infrastructure.audit import AuditStore


class AuditStoreTests(unittest.TestCase):
    """Audit kaydının ölçülebilirlik sağlarken ham içeriği saklamamasını doğrular."""

    def test_record_contains_hash_and_metrics_but_no_raw_text(self):
        with TemporaryDirectory() as directory:
            store = AuditStore(Path(directory))
            question = "Gizlilik açısından kaydedilmemesi gereken soru"
            store.record(
                question=question,
                scope="official",
                model="test-model",
                outcome="grounded",
                latency_ms=12.5,
                sources=[{"document": "public.pdf", "page": 1}],
                answer_chars=42,
                citation_present=True,
                generation_mode="evidence_rule",
            )
            raw = store.path.read_text(encoding="utf-8")
            event = store.recent(1)[0]

        self.assertNotIn(question, raw)
        self.assertEqual(len(event["query_hash"]), 20)
        self.assertEqual(event["source_count"], 1)
        self.assertNotIn("question", event)
        self.assertNotIn("answer", event)

    def test_summary_skips_malformed_lines(self):
        with TemporaryDirectory() as directory:
            store = AuditStore(Path(directory))
            store.path.write_text("not-json\n", encoding="utf-8")
            store.record(
                question="Soru",
                scope="all",
                model="model",
                outcome="unsupported",
                latency_ms=5,
                sources=[],
                answer_chars=10,
                citation_present=False,
                generation_mode="evidence_gate",
            )
            summary = store.summary()

        self.assertEqual(summary["event_count"], 1)
        self.assertEqual(summary["outcomes"], {"unsupported": 1})

    def test_completed_engine_stream_emits_audit_after_consumption(self):
        with TemporaryDirectory() as directory:
            engine = CMSRAGEngine(Path(directory))
            answer = "Kaynaklı ve tamamlanmış yanıt. [SOURCE 1]"
            list(engine._completed("Denetlenen soru", answer, "official"))
            event = engine.audit.recent(1)[0]

        self.assertEqual(event["outcome"], "grounded")
        self.assertEqual(event["scope"], "official")
        self.assertTrue(event["citation_present"])
        self.assertEqual(event["generation_mode"], "deterministic")

    def test_missing_index_guidance_is_not_counted_as_grounded(self):
        with TemporaryDirectory() as directory:
            engine = CMSRAGEngine(Path(directory))
            list(
                engine._completed(
                    "ADVENT nedir?",
                    "Önce belge yükleyin.",
                    generation_mode="unavailable",
                )
            )
            event = engine.audit.recent(1)[0]

        self.assertEqual(event["outcome"], "unavailable")
