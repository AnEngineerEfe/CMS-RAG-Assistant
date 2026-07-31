"""Üretim modelinden farklı bir yerel LLM ile bağımsız RAG kalite değerlendirmesi."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from ollama import Client

from ..domain.models import Chunk
from .models import AnswerJudgeResult, ChunkJudgeResult


class JudgeUnavailableError(RuntimeError):
    """Judge servisi veya çıktısı kullanılamadığında sahte sonuç üretimini engeller."""


class OllamaJudge:
    """Chunk ve cevapları sabit rubrikle, sıcaklık sıfırda ve JSON çıktıyla puanlar."""

    def __init__(self, model: str = "llama3.2:3b", timeout: float = 300.0) -> None:
        """Bağımsız model adını ve yerel servis zaman aşımını ayarlar."""

        self.model = model
        self._client = Client(timeout=timeout)

    def judge_chunks(
        self,
        chunks: list[tuple[str, Chunk]],
        *,
        batch_size: int = 2,
    ) -> list[ChunkJudgeResult]:
        """Chunk'ları tutarlılık, öz-yeterlilik, sınır ve boyut bakımından değerlendirir."""

        results: list[ChunkJudgeResult] = []
        for batch in _batched(chunks, batch_size):
            payload = self._chat_json(
                self._chunk_prompt(batch),
                num_predict=100 + 140 * len(batch),
            )
            indexed = _index_items(payload)
            for chunk_id, _ in batch:
                item = indexed.get(chunk_id)
                if item is None and len(batch) == 1 and len(indexed) == 1:
                    item = next(iter(indexed.values()))
                if item is None:
                    results.append(_invalid_chunk_result(chunk_id))
                    continue
                scores = tuple(
                    _bounded_score(item.get(field))
                    for field in (
                        "coherence",
                        "self_containment",
                        "boundary_quality",
                        "size_fitness",
                    )
                )
                derived_acceptance = all(score >= 3 for score in scores)
                reported_acceptance = item.get("acceptable")
                output_consistent = (
                    isinstance(reported_acceptance, bool)
                    and reported_acceptance == derived_acceptance
                )
                results.append(
                    ChunkJudgeResult(
                        chunk_id=chunk_id,
                        coherence=scores[0],
                        self_containment=scores[1],
                        boundary_quality=scores[2],
                        size_fitness=scores[3],
                        acceptable=derived_acceptance,
                        rationale=str(item.get("rationale", ""))[:500],
                        status=(
                            "completed"
                            if all(scores) and output_consistent
                            else "invalid_judge_output"
                        ),
                    )
                )
        return results

    def judge_answers(
        self,
        items: list[dict[str, Any]],
        *,
        batch_size: int = 1,
    ) -> list[AnswerJudgeResult]:
        """Cevapları yalnız altın kanıta göre faithfulness, relevance ve completeness ile puanlar."""

        results: list[AnswerJudgeResult] = []
        for batch in _batched(items, batch_size):
            payload = self._chat_json(
                self._answer_prompt(batch),
                num_predict=500 + 180 * (len(batch) - 1),
            )
            indexed = _index_items(payload)
            for evaluation in batch:
                case_id = str(evaluation["id"])
                item = indexed.get(case_id)
                if item is None and len(batch) == 1 and len(indexed) == 1:
                    item = next(iter(indexed.values()))
                if item is None:
                    results.append(_invalid_answer_result(case_id))
                    continue
                scores = tuple(
                    _bounded_score(item.get(field))
                    for field in (
                        "faithfulness",
                        "answer_relevance",
                        "completeness",
                    )
                )
                results.append(
                    AnswerJudgeResult(
                        case_id=case_id,
                        faithfulness=scores[0],
                        answer_relevance=scores[1],
                        completeness=scores[2],
                        correct=all(score >= 3 for score in scores),
                        rationale=str(item.get("rationale", ""))[:500],
                        status="completed" if all(scores) else "invalid_judge_output",
                    )
                )
        return results

    def _chat_json(self, prompt: str, *, num_predict: int) -> dict[str, Any]:
        """Ollama yanıtını katı JSON nesnesine dönüştürür ve hatayı görünür kılar."""

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self._client.chat(
                    model=self.model,
                    messages=[{
                        "role": "user",
                        "content": (
                            prompt
                            if attempt == 0
                            else prompt + "\nReturn one compact JSON object; no whitespace-heavy formatting."
                        ),
                    }],
                    format="json",
                    options={
                        "temperature": 0.0,
                        "num_ctx": 4096,
                        "num_predict": num_predict * (attempt + 1),
                        "seed": 42,
                    },
                    keep_alive="30m",
                )
                content = response["message"]["content"]
                payload = json.loads(content)
                break
            except Exception as error:
                last_error = error
        else:
            raise JudgeUnavailableError(
                f"Ollama judge modeli '{self.model}' çalıştırılamadı: {last_error}"
            ) from last_error
        if not isinstance(payload, dict):
            raise JudgeUnavailableError("Judge JSON kök değeri nesne olmalıdır.")
        return payload

    @staticmethod
    def _chunk_prompt(batch: list[tuple[str, Chunk]]) -> str:
        """Chunk puanlama rubriğini ve sınırlı girdiyi modele verir."""

        inputs = [
            {
                "id": chunk_id,
                "document": chunk.document,
                "page": chunk.page,
                "characters": len(chunk.text),
                "text": chunk.text,
            }
            for chunk_id, chunk in batch
        ]
        return (
            "You are an independent RAG chunk quality judge. Evaluate only the supplied "
            "text, never outside knowledge. Score 1 (poor) to 5 (excellent): "
            "coherence=one understandable topic; self_containment=enough local context; "
            "boundary_quality=no broken word or clearly severed thought; "
            "size_fitness=appropriate retrieval context, neither fragment nor bloated. "
            "acceptable must equal true only when every score is at least 3. "
            "Return JSON only: {\"items\":[{\"id\":\"exact id\",\"coherence\":3,"
            "\"self_containment\":3,\"boundary_quality\":3,\"size_fitness\":3,"
            "\"acceptable\":true,\"rationale\":\"short evidence-based reason\"}]}. "
            "Do not reward verbosity. INPUT:\n"
            + json.dumps(inputs, ensure_ascii=False)
        )

    @staticmethod
    def _answer_prompt(batch: list[dict[str, Any]]) -> str:
        """Cevabı dış bilgi kullanmadan altın kanıtla karşılaştıran rubriği üretir."""

        bounded = [
            {
                "id": item["id"],
                "question": item["question"],
                "answer": str(item["answer"])[:1400],
                "gold_evidence": str(item["gold_evidence"])[:2600],
            }
            for item in batch
        ]
        return (
            "You are an independent reference-guided RAG answer judge. Use only "
            "gold_evidence. Score 1-5: faithfulness=all claims supported; "
            "answer_relevance=directly answers; completeness=covers requested supported "
            "facts. Return JSON only: {\"items\":[{\"id\":\"exact id\","
            "\"faithfulness\":3,\"answer_relevance\":3,\"completeness\":3,"
            "\"rationale\":\"short evidence-based reason\"}]}. INPUT:\n"
            + json.dumps(bounded, ensure_ascii=False)
        )


def _index_items(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Judge listesini kimlik tabanlı güvenli sözlüğe dönüştürür."""

    return {
        str(item.get("id")): item
        for item in payload.get("items", [])
        if isinstance(item, dict) and item.get("id") is not None
    }


def _bounded_score(value: Any) -> int:
    """Puanı 1–5 aralığında doğrular; geçersiz değeri sıfırla işaretler."""

    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return score if 1 <= score <= 5 else 0


def _batched(items: list[Any], size: int) -> Iterable[list[Any]]:
    """Uzun istemleri sınırlamak için girdileri sabit gruplara böler."""

    if size <= 0:
        raise ValueError("Batch boyutu pozitif olmalıdır.")
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _invalid_chunk_result(chunk_id: str) -> ChunkJudgeResult:
    """Eksik judge kaydını başarılıymış gibi göstermeyen açık sonuç üretir."""

    return ChunkJudgeResult(
        chunk_id, 0, 0, 0, 0, False,
        "Judge çıktısında bu chunk için kayıt bulunamadı.",
        "invalid_judge_output",
    )


def _invalid_answer_result(case_id: str) -> AnswerJudgeResult:
    """Eksik cevap değerlendirmesini açık geçersiz sonuç olarak kaydeder."""

    return AnswerJudgeResult(
        case_id, 0, 0, 0, False,
        "Judge çıktısında bu vaka için kayıt bulunamadı.",
        "invalid_judge_output",
    )
