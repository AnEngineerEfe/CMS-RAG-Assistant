"""Değerlendirme veri seti ve ölçüm sonuçları için tip güvenli modeller."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvaluationCase:
    """Tek bir altın sorunun kaynak, sayfa, kapsam ve zorluk etiketlerini taşır."""

    id: str
    category: str
    question: str
    scope: str
    query_type: str
    difficulty: str
    data_available: bool
    gold_document: str | None
    gold_pages: tuple[int, ...]
    expected_evidence_terms: tuple[str, ...]


@dataclass(frozen=True)
class ChunkJudgeResult:
    """Bağımsız yerel LLM'in tek chunk için verdiği açıklanabilir kalite puanıdır."""

    chunk_id: str
    coherence: int
    self_containment: int
    boundary_quality: int
    size_fitness: int
    acceptable: bool
    rationale: str
    status: str = "completed"

    def as_dict(self) -> dict[str, Any]:
        """Chunk değerlendirmesini JSON/CSV için sözlüğe dönüştürür."""

        return asdict(self)


@dataclass(frozen=True)
class AnswerJudgeResult:
    """Üretilen cevabın altın kanıta bağlılık ve yeterlilik puanlarını taşır."""

    case_id: str
    faithfulness: int
    answer_relevance: int
    completeness: int
    correct: bool
    rationale: str
    status: str = "completed"

    def as_dict(self) -> dict[str, Any]:
        """Cevap değerlendirmesini JSON/CSV için sözlüğe dönüştürür."""

        return asdict(self)


@dataclass(frozen=True)
class QuestionGenerationResult:
    """Büyük değerlendirme modelinin tek bir chunk'tan ürettiği bağımsız soruyu taşır."""

    chunk_id: str
    question: str
    rationale: str
    status: str = "completed"

    def as_dict(self) -> dict[str, Any]:
        """Soru üretim sonucunu raporlanabilir sözlüğe dönüştürür."""

        return asdict(self)


@dataclass(frozen=True)
class ChunkOriginJudgeResult:
    """Bağımsız hakemin cevabı destekleyen chunk kimlikleri hakkındaki kararını taşır."""

    case_id: str
    answer_supported: bool
    selected_chunk_ids: tuple[str, ...]
    rationale: str
    status: str = "completed"

    def as_dict(self) -> dict[str, Any]:
        """Chunk-kökeni kararını JSON ve CSV için sözlüğe dönüştürür."""

        return asdict(self)


@dataclass
class ConfusionMatrix:
    """Bilgi mevcudiyeti ile cevaplanabilirlik kararını TP/TN/FP/FN olarak sayar."""

    true_positive: int = 0
    true_negative: int = 0
    false_positive: int = 0
    false_negative: int = 0

    def observe(self, actual_positive: bool, predicted_positive: bool) -> str:
        """Tek vakayı uygun confusion-matrix hücresine ekler ve hücre adını döndürür."""

        if actual_positive and predicted_positive:
            self.true_positive += 1
            return "TP"
        if not actual_positive and not predicted_positive:
            self.true_negative += 1
            return "TN"
        if not actual_positive and predicted_positive:
            self.false_positive += 1
            return "FP"
        self.false_negative += 1
        return "FN"

    @property
    def total(self) -> int:
        """Matristeki toplam vaka sayısını döndürür."""

        return (
            self.true_positive
            + self.true_negative
            + self.false_positive
            + self.false_negative
        )

    @property
    def precision(self) -> float:
        """Cevaplanabilir denilen vakaların ne kadarının gerçekten pozitif olduğunu ölçer."""

        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        """Gerçek pozitif vakaların ne kadarının cevaplanabilir bulunduğunu ölçer."""

        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def specificity(self) -> float:
        """Gerçek negatif vakaların ne kadarının doğru reddedildiğini ölçer."""

        denominator = self.true_negative + self.false_positive
        return self.true_negative / denominator if denominator else 0.0

    @property
    def accuracy(self) -> float:
        """Tüm cevaplanabilirlik kararlarının doğruluk oranını hesaplar."""

        if not self.total:
            return 0.0
        return (self.true_positive + self.true_negative) / self.total

    @property
    def f1(self) -> float:
        """Precision ve recall değerlerinin harmonik ortalamasını hesaplar."""

        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator else 0.0

    def as_dict(self) -> dict[str, float | int]:
        """Matris hücrelerini ve türetilmiş ölçümleri JSON uyumlu sözlüğe çevirir."""

        return {
            "true_positive": self.true_positive,
            "true_negative": self.true_negative,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "total": self.total,
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "specificity": round(self.specificity, 4),
            "f1": round(self.f1, 4),
        }


@dataclass
class RetrievalMetrics:
    """Pozitif vakalar için Hit@K, MRR ve sorgu gecikmelerini biriktirir."""

    evaluated: int = 0
    hits: int = 0
    reciprocal_rank_sum: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)

    def observe(self, rank: int | None, latency_ms: float) -> None:
        """Tek sorgunun altın kaynak sırası ile gecikmesini ölçümlere ekler."""

        self.evaluated += 1
        self.latencies_ms.append(latency_ms)
        if rank is not None:
            self.hits += 1
            self.reciprocal_rank_sum += 1.0 / rank

    def as_dict(self) -> dict[str, float | int]:
        """Retrieval doğruluğunu ve gecikme özetini JSON uyumlu sözlüğe çevirir."""

        ordered = sorted(self.latencies_ms)
        return {
            "evaluated": self.evaluated,
            "hit_at_k": round(self.hits / self.evaluated, 4)
            if self.evaluated
            else 0.0,
            "mrr": round(self.reciprocal_rank_sum / self.evaluated, 4)
            if self.evaluated
            else 0.0,
            "latency_mean_ms": round(
                sum(ordered) / len(ordered) if ordered else 0.0,
                3,
            ),
            "latency_p50_ms": round(_percentile(ordered, 0.50), 3),
            "latency_p95_ms": round(_percentile(ordered, 0.95), 3),
        }


@dataclass(frozen=True)
class BenchmarkCaseResult:
    """Tek altın vakanın retrieval, karar ve terim eşleşmesi sonucunu saklar."""

    case_id: str
    category: str
    question: str
    query_type: str
    difficulty: str
    actual_data_available: bool
    predicted_answerable: bool
    confusion_cell: str
    gold_rank: int | None
    evidence_terms_matched: tuple[str, ...]
    evidence_terms_expected: tuple[str, ...]
    retrieval_passed: bool
    latency_ms: float
    sources: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        """Vaka sonucunu rapor serileştirmesi için sözlüğe dönüştürür."""

        return asdict(self)


def _percentile(values: list[float], quantile: float) -> float:
    """Küçük örneklemlerde en yakın sıra tabanlı yüzdelik değerini döndürür."""

    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, round((len(values) - 1) * quantile)))
    return values[index]
