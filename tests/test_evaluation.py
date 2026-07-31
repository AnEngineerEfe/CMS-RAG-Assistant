import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.cms_rag.evaluation import ConfusionMatrix, RetrievalMetrics, load_cases


ROOT = Path(__file__).resolve().parents[1]


class EvaluationDatasetTests(unittest.TestCase):
    def test_gold_dataset_has_balanced_positive_and_negative_cases(self):
        cases = load_cases(ROOT / "evaluation" / "datasets" / "gold_cases.json")
        self.assertEqual(len(cases), 33)
        self.assertEqual(sum(case.data_available for case in cases), 23)
        self.assertEqual(sum(not case.data_available for case in cases), 10)

    def test_every_positive_gold_reference_and_term_exists_in_snapshot(self):
        cases = load_cases(ROOT / "evaluation" / "datasets" / "gold_cases.json")
        snapshot = json.loads(
            (
                ROOT / "data" / "knowledge_base" / "snapshot" / "snapshot.json"
            ).read_text(encoding="utf-8")
        )
        chunks = snapshot["chunks"]
        for case in cases:
            if not case.data_available:
                continue
            evidence = " ".join(
                chunk["text"].lower()
                for chunk in chunks
                if chunk["document"] == case.gold_document
                and chunk["page"] in case.gold_pages
            )
            self.assertTrue(evidence, case.id)
            for term in case.expected_evidence_terms:
                self.assertIn(term.lower(), evidence, case.id)

    def test_loader_rejects_duplicate_case_ids(self):
        payload = {
            "schema_version": 2,
            "cases": [
                {
                    "id": "duplicate",
                    "category": "negative_control",
                    "question": "Birinci soru",
                    "scope": "all",
                    "query_type": "negative",
                    "difficulty": "easy",
                    "data_available": False,
                    "gold_document": None,
                    "gold_pages": [],
                    "expected_evidence_terms": [],
                },
                {
                    "id": "duplicate",
                    "category": "negative_control",
                    "question": "İkinci soru",
                    "scope": "all",
                    "query_type": "negative",
                    "difficulty": "easy",
                    "data_available": False,
                    "gold_document": None,
                    "gold_pages": [],
                    "expected_evidence_terms": [],
                },
            ],
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "benzersiz"):
                load_cases(path)


class EvaluationMetricTests(unittest.TestCase):
    def test_confusion_matrix_metrics_are_computed_from_all_cells(self):
        matrix = ConfusionMatrix()
        for actual, predicted in (
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ):
            matrix.observe(actual, predicted)
        self.assertEqual(matrix.as_dict()["accuracy"], 0.5)
        self.assertEqual(matrix.as_dict()["f1"], 0.5)

    def test_retrieval_metrics_report_hit_rate_mrr_and_latency(self):
        metrics = RetrievalMetrics()
        metrics.observe(1, 10.0)
        metrics.observe(2, 20.0)
        metrics.observe(None, 30.0)
        result = metrics.as_dict()
        self.assertEqual(result["hit_at_k"], 0.6667)
        self.assertEqual(result["mrr"], 0.5)
        self.assertEqual(result["latency_p50_ms"], 20.0)


if __name__ == "__main__":
    unittest.main()
