"""Canlı değerlendirme kaydı, chunk kararı ve confusion etiketi testleri."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.cms_rag.application.live_evaluation import LiveEvaluationAssessor
from src.cms_rag.domain import Chunk, SearchHit
from src.cms_rag.infrastructure.live_evaluation import LiveEvaluationStore


ROOT = Path(__file__).resolve().parents[1]


class LiveEvaluationTests(unittest.TestCase):
    """Kullanıcı testlerinin sıfırdan başlayıp açıklanabilir biçimde birikmesini doğrular."""

    def test_store_starts_empty_and_builds_confusion_summary(self):
        """Yeni depo sıfır değerleriyle açılmalı ve ilk olayı anında özetlemelidir."""

        with TemporaryDirectory() as directory:
            store = LiveEvaluationStore(Path(directory))
            self.assertEqual(store.summary()["event_count"], 0)
            store.record(
                {
                    "input": "ADVENT nedir?",
                    "output": "Kaynaklı cevap",
                    "model": "test-model",
                    "confusion_cell": "TP",
                    "chunk_correct": True,
                }
            )
            summary = store.summary()
            store.clear()
            cleared = store.summary()

        self.assertEqual(summary["event_count"], 1)
        self.assertEqual(summary["cells"]["TP"], 1)
        self.assertEqual(summary["chunk_correct"], 1)
        self.assertEqual(cleared["event_count"], 0)

    def test_gold_question_produces_tp_and_independent_chunk_pass(self):
        """Altın sayfayı bulan kaynaklı yanıt TP ve doğru chunk olarak işaretlenmelidir."""

        assessor = LiveEvaluationAssessor(ROOT)
        hit = SearchHit(
            Chunk(
                text="ADVENT is a Combat Management System with command and control capabilities.",
                document="advent_cms.pdf",
                page=3,
                source_path="advent_cms.pdf",
                collection="official",
            ),
            score=0.91,
        )
        result = assessor.assess(
            question="ADVENT nedir ve hangi temel işlevleri kapsar?",
            answer="ADVENT bir savaş yönetim sistemidir. [SOURCE 1]",
            model="qwen2.5:3b",
            scope="official",
            outcome="grounded",
            hits=[hit],
            latency_ms=100,
            generation_mode="ollama",
        )

        self.assertEqual(result["confusion_cell"], "TP")
        self.assertTrue(result["chunk_correct"])
        self.assertEqual(result["model"], "qwen2.5:3b")
        self.assertIn("Altın set", result["ground_truth_basis"])
        self.assertEqual(result["input"], "ADVENT nedir ve hangi temel işlevleri kapsar?")
        self.assertIn("savaş yönetim", result["output"])

    def test_known_negative_safe_rejection_produces_tn(self):
        """Altın sette bulunmayan nitelik güvenli reddedildiğinde TN oluşmalıdır."""

        assessor = LiveEvaluationAssessor(ROOT)
        negative = next(
            case for case in assessor.gold_cases if not case.get("data_available")
        )
        result = assessor.assess(
            question=str(negative["question"]),
            answer="Bu soruyu destekleyecek yeterli kaynak bulunamadı.",
            model="qwen2.5:3b",
            scope=str(negative["scope"]),
            outcome="unsupported",
            hits=[],
            latency_ms=50,
            generation_mode="evidence_gate",
        )

        self.assertEqual(result["confusion_cell"], "TN")
        self.assertTrue(result["chunk_correct"])
