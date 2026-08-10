import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.cms_rag.domain import Chunk
from src.cms_rag.evaluation import (
    ChunkLineageEvaluationRunner,
    ConfusionMatrix,
    OllamaJudge,
    RetrievalMetrics,
    load_cases,
)


ROOT = Path(__file__).resolve().parents[1]


class EvaluationDatasetTests(unittest.TestCase):
    def test_lineage_cache_isolated_by_vector_backend(self):
        runner = object.__new__(ChunkLineageEvaluationRunner)
        runner.retrieval_backend = "pgvector"
        case = {
            "question": "ADVENT nedir?",
            "source_chunk_id": "doc:p1:c1",
            "kind": "positive",
        }
        row = {
            "question": "ADVENT nedir?",
            "source_chunk_id": "doc:p1:c1",
            "actual_data_available": True,
            "retrieval_backend": "faiss",
        }

        self.assertFalse(runner._cache_matches_case(row, case))
        row["retrieval_backend"] = "pgvector"
        self.assertTrue(runner._cache_matches_case(row, case))

    def test_gold_dataset_has_balanced_positive_and_negative_cases(self):
        cases = load_cases(ROOT / "evaluation" / "datasets" / "gold_cases.json")
        self.assertEqual(len(cases), 45)
        self.assertEqual(sum(case.data_available for case in cases), 30)
        self.assertEqual(sum(not case.data_available for case in cases), 15)

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
    def test_expected_term_matching_tolerates_punctuation_variants(self):
        answer = "komuta & kontrol gereksinimleri"

        self.assertTrue(
            ChunkLineageEvaluationRunner._matches_expected_term(
                answer,
                "komuta-kontrol|command & control",
            )
        )

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


class LocalJudgeTests(unittest.TestCase):
    def test_origin_judge_uses_query_focused_late_sentence(self):
        text = ("Genel ürün bilgisi. " * 80) + "IFF, ADS-B ve AIS verileri birleştirilir."

        focused = OllamaJudge._focused_candidate_text(
            "Hangi IFF ADS-B AIS kaynakları kullanılır?",
            text,
        )

        self.assertIn("IFF, ADS-B ve AIS", focused)

    def test_large_model_question_generation_requires_exact_chunk_id(self):
        """Soru üreticisi yalnız sözleşmeye uyan, soru işaretli çıktıyı kabul etmelidir."""

        judge = OllamaJudge("large-test-model")
        judge._client = _FakeOllamaClient(
            {
                "chunk_id": "doc.pdf:p1:c1",
                "question": "CMS sensör verisini hangi amaçla birleştirir?",
                "rationale": "Yanıt chunk içinde açıkça bulunuyor.",
            }
        )
        result = judge.generate_question(
            "doc.pdf:p1:c1",
            Chunk("CMS sensör verisini ortak resim için birleştirir.", "doc.pdf", 1, "doc.pdf"),
        )

        self.assertEqual(result.status, "completed")
        self.assertTrue(result.question.endswith("?"))

    def test_chunk_origin_judge_rejects_unknown_chunk_ids(self):
        """Hakem aday havuzunda bulunmayan chunk kimliğini seçememelidir."""

        judge = OllamaJudge("large-test-model")
        judge._client = _FakeOllamaClient(
            {
                "case_id": "L01",
                "answer_supported": True,
                "selected_chunk_ids": ["unknown"],
                "rationale": "Invalid selection.",
            }
        )
        result = judge.judge_chunk_origin(
            case_id="L01",
            question="Soru?",
            answer="Cevap.",
            candidates=[
                ("doc.pdf:p1:c1", Chunk("Kanıt.", "doc.pdf", 1, "doc.pdf"))
            ],
        )

        self.assertEqual(result.status, "invalid_judge_output")
        self.assertEqual(result.selected_chunk_ids, ())

    def test_chunk_acceptance_is_derived_from_all_rubric_scores(self):
        judge = OllamaJudge("independent-test-model")
        judge._client = _FakeOllamaClient(
            {
                "items": [
                    {
                        "id": "chunk-1",
                        "coherence": 5,
                        "self_containment": 4,
                        "boundary_quality": 2,
                        "size_fitness": 4,
                        "acceptable": False,
                        "rationale": "The ending is severed.",
                    }
                ]
            }
        )
        result = judge.judge_chunks(
            [("chunk-1", Chunk("Complete text.", "doc.pdf", 1, "doc.pdf"))]
        )[0]
        self.assertFalse(result.acceptable)
        self.assertEqual(result.status, "completed")

    def test_missing_judge_item_is_not_reported_as_success(self):
        judge = OllamaJudge("independent-test-model")
        judge._client = _FakeOllamaClient({"items": []})
        result = judge.judge_answers(
            [
                {
                    "id": "case-1",
                    "question": "Question",
                    "answer": "Answer",
                    "gold_evidence": "Evidence",
                }
            ]
        )[0]
        self.assertEqual(result.status, "invalid_judge_output")
        self.assertFalse(result.correct)

    def test_malformed_json_is_retried_once(self):
        judge = OllamaJudge("independent-test-model")
        judge._client = _SequenceOllamaClient(
            [
                "{",
                json.dumps(
                    {
                        "items": [
                            {
                                "id": "case-1",
                                "faithfulness": 4,
                                "answer_relevance": 4,
                                "completeness": 4,
                                "rationale": "Supported.",
                            }
                        ]
                    }
                ),
            ]
        )
        result = judge.judge_answers(
            [
                {
                    "id": "case-1",
                    "question": "Question",
                    "answer": "Answer",
                    "gold_evidence": "Evidence",
                }
            ]
        )[0]
        self.assertEqual(result.status, "completed")
        self.assertTrue(result.correct)


class _FakeOllamaClient:
    def __init__(self, payload):
        self.payload = payload

    def chat(self, **_kwargs):
        return {"message": {"content": json.dumps(self.payload)}}


class _SequenceOllamaClient:
    def __init__(self, contents):
        self.contents = iter(contents)

    def chat(self, **_kwargs):
        return {"message": {"content": next(self.contents)}}


if __name__ == "__main__":
    unittest.main()
