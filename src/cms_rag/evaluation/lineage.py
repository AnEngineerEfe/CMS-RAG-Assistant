"""Chunk-kökenli soru üretimiyle bağımsız uçtan uca RAG değerlendirmesi yürütür."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import re
from time import perf_counter
from typing import Any

from ..application import CMSRAGEngine
from ..application.engine import NO_ANSWER
from ..domain.models import Chunk, SearchHit
from ..domain.query import CMSQueryProcessor
from .judge import OllamaJudge
from .models import ConfusionMatrix


class ChunkLineageEvaluationRunner:
    """Büyük model–küçük RAG–büyük hakem zincirini bağımsız oturumlarla ölçer."""

    def __init__(
        self,
        data_dir: Path,
        dataset_path: Path,
        *,
        evaluator: OllamaJudge,
        rag_model: str = "qwen2.5:3b",
        regenerate_questions: bool = False,
    ) -> None:
        """Veri setini, snapshot chunklarını ve birbirinden farklı model rollerini yükler."""

        self.data_dir = data_dir
        self.dataset_path = dataset_path
        self.evaluator = evaluator
        self.rag_model = rag_model
        self.regenerate_questions = regenerate_questions
        self.cases = self._load_cases(dataset_path)
        self.chunk_records = self._snapshot_chunk_records(data_dir)
        self.chunks_by_id = {
            item["chunk_id"]: item["chunk"] for item in self.chunk_records
        }

    def select_cases(self, case_ids: list[str]) -> None:
        """Hata ayıklama veya seçici tekrar için vaka listesini kimliklerle sınırlar."""

        requested = set(case_ids)
        selected = [case for case in self.cases if str(case["id"]) in requested]
        if len(selected) != len(requested):
            known = {str(case["id"]) for case in self.cases}
            missing = sorted(requested - known)
            raise ValueError(f"Bilinmeyen lineage vaka kimlikleri: {missing}")
        self.cases = selected

    def run(
        self,
        *,
        cache_path: Path | None = None,
        force_case_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        """20 vakayı çalıştırıp confusion matrix ve chunk-köken eşleşmesini raporlar."""

        cache = self._load_cache(cache_path)
        forced = force_case_ids or set()
        engine = CMSRAGEngine(
            self.data_dir,
            model=self.rag_model,
            record_runtime_events=False,
        )
        engine.rebuild()
        matrix = ConfusionMatrix()
        rows: list[dict[str, Any]] = []
        for position, case in enumerate(self.cases, start=1):
            case_id = str(case["id"])
            if (
                case_id not in forced
                and case_id in cache
                and cache[case_id].get("status") == "completed"
                and self._cache_matches_case(cache[case_id], case)
            ):
                row = cache[case_id]
                matrix.observe(
                    bool(row["actual_data_available"]),
                    bool(row["predicted_answerable"]),
                )
                rows.append(row)
                continue
            row = self._run_case(engine, case)
            rows.append(row)
            cache[case_id] = row
            self._write_cache(cache_path, cache)
            matrix.observe(
                bool(row["actual_data_available"]),
                bool(row["predicted_answerable"]),
            )
            print(
                f"Chunk-köken değerlendirmesi: {position}/{len(self.cases)} "
                f"({case_id} · {row['confusion_cell']} · {row['status']})",
                flush=True,
            )
        positives = [row for row in rows if row["actual_data_available"]]
        origin_matches = sum(bool(row["origin_chunk_match"]) for row in positives)
        strict_passes = sum(bool(row["strict_pass"]) for row in positives)
        return {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "method": {
                "case_count": len(rows),
                "positive_chunk_cases": len(positives),
                "negative_controls": len(rows) - len(positives),
                "question_generator_model": (
                    self.evaluator.model
                    if self.regenerate_questions
                    else "OpenAI Codex büyük model · geliştirme zamanı"
                ),
                "rag_answer_model": self.rag_model,
                "chunk_origin_judge_model": self.evaluator.model,
                "questions_prepared_and_versioned": not self.regenerate_questions,
                "independent_chat_per_stage": True,
                "judge_candidate_pool": (
                    "Bağımsız hibrit retrieval sonucundaki en ilgili en fazla 4 chunk"
                ),
                "runtime_web_access": False,
            },
            "confusion_matrix": matrix.as_dict(),
            "lineage": {
                "evaluated_positive_cases": len(positives),
                "origin_chunk_matches": origin_matches,
                "origin_chunk_match_rate": round(
                    origin_matches / len(positives), 4
                ) if positives else 0.0,
                "strict_passes": strict_passes,
                "strict_pass_rate": round(
                    strict_passes / len(positives), 4
                ) if positives else 0.0,
                "invalid_cases": sum(row["status"] != "completed" for row in rows),
            },
            "cases": rows,
        }

    @staticmethod
    def _cache_matches_case(row: dict[str, Any], case: dict[str, Any]) -> bool:
        """Değiştirilen soru veya kaynak chunk için eski sonucu kullanmayı engeller."""

        return bool(
            str(row.get("question", "")).strip()
            == str(case.get("question", "")).strip()
            and str(row.get("source_chunk_id", ""))
            == str(case.get("source_chunk_id", ""))
            and bool(row.get("actual_data_available"))
            == (case.get("kind") == "positive")
        )

    def _run_case(
        self,
        engine: CMSRAGEngine,
        case: dict[str, Any],
    ) -> dict[str, Any]:
        """Tek vakada soru üretimi, RAG yanıtı ve bağımsız chunk seçimini tamamlar."""

        case_id = str(case["id"])
        actual_positive = case.get("kind") == "positive"
        source_chunk_id = str(case.get("source_chunk_id", ""))
        question_generation: dict[str, Any]
        if actual_positive:
            source_chunk = self.chunks_by_id.get(source_chunk_id)
            if source_chunk is None:
                return self._invalid_row(case, "source_chunk_not_found")
            prepared_question = str(case.get("question", "")).strip()
            if prepared_question and not self.regenerate_questions:
                question = prepared_question
                question_generation = {
                    "chunk_id": source_chunk_id,
                    "question": question,
                    "rationale": (
                        "Büyük model geliştirme oturumunda yalnız kaynak chunk kullanılarak "
                        "üretildi ve sürümlü veri setine alınmadan önce doğrulandı."
                    ),
                    "status": "prepared_and_curated",
                }
            else:
                generated = self.evaluator.generate_question(
                    source_chunk_id,
                    source_chunk,
                    focus=str(case.get("topic", "")),
                )
                if generated.status != "completed":
                    generated = self.evaluator.generate_question(
                        source_chunk_id,
                        source_chunk,
                        focus=str(case.get("topic", "")),
                    )
                question = generated.question
                question_generation = generated.as_dict()
                if generated.status != "completed":
                    return self._invalid_row(case, "question_generation_failed")
        else:
            question = str(case.get("question", "")).strip()
            question_generation = {
                "chunk_id": "",
                "question": question,
                "rationale": "Kaynakta bulunmayan bilgiyi ölçen sürümlü negatif kontrol.",
                "status": "not_applicable",
            }
        engine.clear_chat()
        started = perf_counter()
        answer, hits = engine.ask(question, str(case.get("scope", "all")))
        latency_ms = (perf_counter() - started) * 1000
        response_attempted = self._is_positive_answer(answer)
        expected_terms = [
            str(term) for term in case.get("expected_answer_terms", [])
        ]
        normalized_answer = CMSQueryProcessor.normalise(answer)
        matched_terms = [
            term
            for term in expected_terms
            if self._matches_expected_term(normalized_answer, term)
        ]
        term_coverage = (
            len(matched_terms) / len(expected_terms) if expected_terms else 1.0
        )
        retrieved_chunk_ids = self._chunk_ids_for_hits(hits, question)
        candidates = [
            (chunk_id, self.chunks_by_id[chunk_id])
            for chunk_id in retrieved_chunk_ids
            if chunk_id in self.chunks_by_id
        ]
        judge_started = perf_counter()
        if actual_positive and response_attempted and candidates:
            origin_judgment = self.evaluator.judge_chunk_origin(
                case_id=case_id,
                question=question,
                answer=answer,
                candidates=candidates,
            )
            if origin_judgment.status != "completed":
                origin_judgment = self.evaluator.judge_chunk_origin(
                    case_id=case_id,
                    question=question,
                    answer=answer,
                    candidates=candidates,
                )
            judgment = origin_judgment.as_dict()
        elif not actual_positive:
            judgment = {
                "case_id": case_id,
                "answer_supported": not response_attempted,
                "selected_chunk_ids": (),
                "rationale": "Negatif kontrolde beklenen bir kaynak chunk yoktur.",
                "status": "not_applicable",
            }
        elif not response_attempted:
            judgment = {
                "case_id": case_id,
                "answer_supported": False,
                "selected_chunk_ids": (),
                "rationale": "RAG pozitif vakada güvenli ret üretti; chunk hakemi çağrılmadı.",
                "status": "not_applicable",
            }
        else:
            judgment = {
                "case_id": case_id,
                "answer_supported": False,
                "selected_chunk_ids": (),
                "rationale": "RAG herhangi bir aday chunk döndürmedi.",
                "status": "not_applicable" if not actual_positive else "completed",
            }
        judge_latency_ms = (perf_counter() - judge_started) * 1000
        selected = set(judgment["selected_chunk_ids"])
        predicted_positive = bool(
            response_attempted
            if not actual_positive
            else (
                term_coverage >= 1.0
                and judgment["answer_supported"]
            )
        )
        confusion_cell = self._cell(actual_positive, predicted_positive)
        origin_match = bool(
            actual_positive
            and source_chunk_id in retrieved_chunk_ids
            and source_chunk_id in selected
        )
        status = (
            "invalid_judge_output"
            if judgment["status"] == "invalid_judge_output"
            else "completed"
        )
        strict_pass = bool(
            actual_positive
            and predicted_positive
            and judgment["answer_supported"]
            and origin_match
            and term_coverage >= 1.0
            and status == "completed"
        )
        return {
            "case_id": case_id,
            "topic": case.get("topic", ""),
            "case_type": "Chunk-kökenli pozitif" if actual_positive else "Negatif kontrol",
            "source_chunk_id": source_chunk_id,
            "question": question,
            "answer": answer.strip(),
            "question_generator_model": (
                str(case.get("question_generator_model", self.evaluator.model))
                if actual_positive and not self.regenerate_questions
                else self.evaluator.model if actual_positive else "Sürümlü manuel kontrol"
            ),
            "rag_model": self.rag_model,
            "chunk_judge_model": self.evaluator.model,
            "actual_data_available": actual_positive,
            "predicted_answerable": predicted_positive,
            "confusion_cell": confusion_cell,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "judge_selected_chunk_ids": list(judgment["selected_chunk_ids"]),
            "answer_supported_by_judge": judgment["answer_supported"],
            "origin_chunk_match": origin_match,
            "expected_answer_terms": expected_terms,
            "answer_terms_matched": matched_terms,
            "answer_term_coverage": round(term_coverage, 4),
            "strict_pass": strict_pass,
            "latency_ms": round(latency_ms, 3),
            "rag_latency_ms": round(latency_ms, 3),
            "judge_latency_ms": round(judge_latency_ms, 3),
            "total_latency_ms": round(latency_ms + judge_latency_ms, 3),
            "question_generation": question_generation,
            "judge_rationale": judgment["rationale"],
            "status": status,
        }

    def _chunk_ids_for_hits(
        self,
        hits: list[SearchHit],
        question: str,
    ) -> list[str]:
        """Her retrieval sayfasından soruyla en ilgili iki özgün chunk kimliğini seçer."""

        query_terms = set(CMSQueryProcessor.normalise(question).split())
        selected: list[str] = []
        for hit in hits:
            candidates = [
                item
                for item in self.chunk_records
                if item["chunk"].document == hit.chunk.document
                and item["chunk"].page == hit.chunk.page
            ]
            ranked = sorted(
                candidates,
                key=lambda item: len(
                    query_terms
                    & set(CMSQueryProcessor.normalise(item["chunk"].text).split())
                ),
                reverse=True,
            )
            for item in ranked[:2]:
                chunk_id = str(item["chunk_id"])
                if chunk_id not in selected:
                    selected.append(chunk_id)
        return selected[:2]

    @staticmethod
    def _matches_expected_term(normalized_answer: str, expected_group: str) -> bool:
        """Tire ve bağlaç yazımları değişse de aynı kanıt terimlerini eşleştirir."""

        answer_tokens = set(re.findall(r"\w+", normalized_answer))
        for alternative in expected_group.split("|"):
            normalized = CMSQueryProcessor.normalise(alternative.strip())
            if not normalized:
                continue
            if normalized in normalized_answer:
                return True
            required = set(re.findall(r"\w+", normalized)) - {"ve", "and"}
            if required and required <= answer_tokens:
                return True
        return False

    @staticmethod
    def _is_positive_answer(answer: str) -> bool:
        """Güvenli ret ve servis hatasını cevaplanabilir tahmininden ayırır."""

        lowered = answer.lower()
        return bool(answer.strip()) and answer.strip() != NO_ANSWER and not any(
            marker in lowered
            for marker in (
                "yeterli kaynak bulunamadı",
                "ollama servisine ulaşılamadı",
                "önce resmî pdf",
                "bahsedilmemiştir",
                "belirtilmemiştir",
                "yer almamaktadır",
                "kaynaklarda bulunmamaktadır",
            )
        )

    @staticmethod
    def _cell(actual_positive: bool, predicted_positive: bool) -> str:
        """Tek vakayı açık TP/TN/FP/FN hücresine yerleştirir."""

        if actual_positive and predicted_positive:
            return "TP"
        if not actual_positive and not predicted_positive:
            return "TN"
        if not actual_positive and predicted_positive:
            return "FP"
        return "FN"

    @staticmethod
    def _invalid_row(case: dict[str, Any], reason: str) -> dict[str, Any]:
        """Eksik kaynak veya üretim hatasını başarı gibi göstermeyen vaka kaydı üretir."""

        actual_positive = case.get("kind") == "positive"
        return {
            "case_id": case.get("id", ""),
            "topic": case.get("topic", ""),
            "case_type": "Chunk-kökenli pozitif" if actual_positive else "Negatif kontrol",
            "source_chunk_id": case.get("source_chunk_id", ""),
            "question": case.get("question", ""),
            "answer": "",
            "question_generator_model": "",
            "rag_model": "",
            "chunk_judge_model": "",
            "actual_data_available": actual_positive,
            "predicted_answerable": False,
            "confusion_cell": "FN" if actual_positive else "TN",
            "retrieved_chunk_ids": [],
            "judge_selected_chunk_ids": [],
            "answer_supported_by_judge": False,
            "origin_chunk_match": False,
            "expected_answer_terms": case.get("expected_answer_terms", []),
            "answer_terms_matched": [],
            "answer_term_coverage": 0.0,
            "strict_pass": False,
            "latency_ms": 0.0,
            "rag_latency_ms": 0.0,
            "judge_latency_ms": 0.0,
            "total_latency_ms": 0.0,
            "question_generation": {"status": reason},
            "judge_rationale": reason,
            "status": reason,
        }

    @staticmethod
    def _load_cases(path: Path) -> list[dict[str, Any]]:
        """Tam 20 vaka ve geçerli pozitif/negatif türleri içeren veri setini doğrular."""

        payload = json.loads(path.read_text(encoding="utf-8"))
        cases = payload.get("cases", [])
        if len(cases) != 20:
            raise ValueError("Chunk-köken veri seti tam 20 vaka içermelidir.")
        if any(case.get("kind") not in {"positive", "negative"} for case in cases):
            raise ValueError("Her vaka positive veya negative türünde olmalıdır.")
        return cases

    @staticmethod
    def _snapshot_chunk_records(data_dir: Path) -> list[dict[str, Any]]:
        """Snapshot sırasını koruyarak kararlı belge/sayfa/chunk kimlikleri üretir."""

        payload = json.loads(
            (data_dir / "knowledge_base" / "snapshot" / "snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        counters: dict[tuple[str, int], int] = {}
        records: list[dict[str, Any]] = []
        for item in payload["chunks"]:
            chunk = Chunk(**item)
            key = (chunk.document, chunk.page)
            counters[key] = counters.get(key, 0) + 1
            records.append(
                {
                    "chunk_id": f"{chunk.document}:p{chunk.page}:c{counters[key]}",
                    "chunk": chunk,
                }
            )
        return records

    @staticmethod
    def _load_cache(path: Path | None) -> dict[str, dict[str, Any]]:
        """Yalnız tamamlanmış vaka satırlarını yeniden kullanılabilir önbellekten okur."""

        if path is None or not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            str(item["case_id"]): item
            for item in payload
            if isinstance(item, dict) and item.get("case_id")
        }

    @staticmethod
    def _write_cache(
        path: Path | None,
        cache: dict[str, dict[str, Any]],
    ) -> None:
        """Her vaka sonunda ilerlemeyi atomik dosya değişimiyle korur."""

        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(list(cache.values()), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
