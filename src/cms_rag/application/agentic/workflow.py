"""Mevcut CMS servislerini bozmadan LangGraph üzerinde orkestre eden ilk güvenli grafik."""

from __future__ import annotations

from dataclasses import dataclass
import re
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

from ...domain.models import SearchHit
from ..engine import CMSRAGEngine, NO_ANSWER
from .checkpoints import CheckpointRuntime, create_checkpoint_runtime
from .router import AgentRoute, decide_route
from .state import CMSAgentState, deserialize_hits, serialize_hits


RESTRICTED_ANSWER = (
    "Bu çalışma yalnızca kamuya açık ve kullanma yetkisi bulunan kaynaklarla sınırlıdır; "
    "gizli, tasnifli veya kamuya açıklanmamış bilgi talepleri işleme alınmaz."
)


@dataclass(frozen=True)
class AgenticResult:
    """Sunum katmanına graph iç ayrıntılarını sızdırmadan döndürülen çalışma sonucu."""

    route: AgentRoute
    reason: str
    answer: str
    hits: list[SearchHit]
    events: tuple[str, ...]
    error: str = ""


class CMSAgenticWorkflow:
    """Niyet yönlendirmesi, checkpoint ve mevcut RAG motorunu tek graph altında birleştirir."""

    def __init__(
        self,
        engine: CMSRAGEngine,
        *,
        checkpointer: Any | None = None,
        checkpoint_runtime: CheckpointRuntime | None = None,
    ) -> None:
        """Mevcut motoru araç olarak tutar ve thread tabanlı agent grafiğini derler."""

        if checkpointer is not None and checkpoint_runtime is not None:
            raise ValueError("checkpointer ve checkpoint_runtime birlikte verilemez.")
        self.engine = engine
        self._checkpoint_runtime = checkpoint_runtime or create_checkpoint_runtime()
        self.checkpointer = checkpointer or self._checkpoint_runtime.saver
        self.checkpoint_backend = (
            "Harici checkpointer" if checkpointer is not None else self._checkpoint_runtime.display_name
        )
        self.graph = self._build_graph()

    def close(self) -> None:
        """Workflow'un sahip olduğu checkpoint bağlantısını kontrollü kapatır."""

        self._checkpoint_runtime.close()

    def invoke(self, question: str, scope: str, thread_id: str) -> AgenticResult:
        """Bir kullanıcı turunu checkpoint'li graph üzerinde çalıştırıp tipli sonuç döndürür."""

        if scope not in {"all", "official", "open_source"}:
            raise ValueError(f"Desteklenmeyen kaynak kapsamı: {scope}")
        state = self.graph.invoke(
            {
                "question": question,
                "scope": scope,
                "events": [],
                "answer": "",
                "hits": [],
                "retrieval_query": "",
                "answerable": False,
                "verification_passed": False,
                "verification_reason": "",
                "repair_count": 0,
                "generation_mode": "",
                "started_at": perf_counter(),
                "recorded": False,
                "error": "",
                "completed": False,
            },
            config={"configurable": {"thread_id": thread_id}},
        )
        return AgenticResult(
            route=AgentRoute(state["route"]),
            reason=state.get("route_reason", ""),
            answer=state.get("answer", ""),
            hits=deserialize_hits(list(state.get("hits", []))),
            events=tuple(state.get("events", [])),
            error=state.get("error", ""),
        )

    def state_history(self, thread_id: str) -> list[Any]:
        """Test, hata ayıklama ve ileride zaman yolculuğu için checkpoint geçmişini döndürür."""

        config = {"configurable": {"thread_id": thread_id}}
        return list(self.graph.get_state_history(config))

    def _build_graph(self):
        """İlk parity sürümünün düğüm ve koşullu kenarlarını oluşturur."""

        builder = StateGraph(CMSAgentState)
        builder.add_node("validate_input", self._validate_input)
        builder.add_node("route_request", self._route_request)
        builder.add_node("plan_knowledge", self._plan_knowledge)
        builder.add_node("retrieve_evidence", self._retrieve_evidence)
        builder.add_node("gate_evidence", self._gate_evidence)
        builder.add_node("unsupported_answer", self._unsupported_answer)
        builder.add_node("generate_answer", self._generate_answer)
        builder.add_node("verify_answer", self._verify_answer)
        builder.add_node("repair_answer", self._repair_answer)
        builder.add_node("verification_reject", self._verification_reject)
        builder.add_node("record_answer", self._record_answer)
        builder.add_node("track_handoff", self._track_handoff)
        builder.add_node("safe_reject", self._safe_reject)
        builder.add_node("finalize", self._finalize)
        builder.add_edge(START, "validate_input")
        builder.add_edge("validate_input", "route_request")
        builder.add_conditional_edges(
            "route_request",
            self._next_node,
            {
                AgentRoute.KNOWLEDGE.value: "plan_knowledge",
                AgentRoute.TRACK_CONTROL.value: "track_handoff",
                AgentRoute.SAFE_REJECT.value: "safe_reject",
            },
        )
        builder.add_conditional_edges(
            "plan_knowledge",
            self._after_plan,
            {"retrieve": "retrieve_evidence", "verify": "verify_answer"},
        )
        builder.add_edge("retrieve_evidence", "gate_evidence")
        builder.add_conditional_edges(
            "gate_evidence",
            self._after_evidence_gate,
            {"generate": "generate_answer", "unsupported": "unsupported_answer"},
        )
        builder.add_edge("generate_answer", "verify_answer")
        builder.add_edge("unsupported_answer", "verify_answer")
        builder.add_conditional_edges(
            "verify_answer",
            self._after_verification,
            {
                "record": "record_answer",
                "repair": "repair_answer",
                "reject": "verification_reject",
            },
        )
        builder.add_edge("repair_answer", "verify_answer")
        builder.add_edge("verification_reject", "record_answer")
        builder.add_edge("record_answer", "finalize")
        builder.add_edge("track_handoff", "finalize")
        builder.add_edge("safe_reject", "finalize")
        builder.add_edge("finalize", END)
        return builder.compile(checkpointer=self.checkpointer)

    @staticmethod
    def _validate_input(state: CMSAgentState) -> CMSAgentState:
        """Girdiyi normalize eder ve her yeni tur için açıklama olaylarını sıfırlar."""

        question = str(state.get("question", "")).strip()
        return {
            "question": question,
            "events": ["Girdi doğrulandı ve yeni agentic tur başlatıldı."],
        }

    @staticmethod
    def _route_request(state: CMSAgentState) -> CMSAgentState:
        """İsteği bilgi, MCP kontrol veya güvenli ret yoluna deterministik yönlendirir."""

        decision = decide_route(state.get("question", ""))
        return {
            "route": decision.route.value,
            "route_reason": decision.reason,
            "events": [*state.get("events", []), decision.reason],
        }

    @staticmethod
    def _next_node(state: CMSAgentState) -> str:
        """Koşullu kenar için doğrulanmış route değerini bir sonraki düğüm anahtarı yapar."""

        route = state.get("route", AgentRoute.SAFE_REJECT.value)
        if route not in {item.value for item in AgentRoute}:
            return AgentRoute.SAFE_REJECT.value
        return route

    def _plan_knowledge(self, state: CMSAgentState) -> CMSAgentState:
        """Deterministik ön kontrolü çalıştırır veya bağlama göre retrieval sorgusu planlar."""

        preflight = self.engine.preflight_answer(state["question"], state["scope"])
        if preflight is not None:
            return {
                "answer": preflight.answer,
                "hits": serialize_hits(preflight.hits),
                "generation_mode": preflight.generation_mode,
                "events": [
                    *state.get("events", []),
                    f"Ön kontrol isteği {preflight.generation_mode} yolunda tamamladı.",
                ],
            }
        query = self.engine.plan_retrieval_query(state["question"], state["scope"])
        return {
            "retrieval_query": query,
            "events": [
                *state.get("events", []),
                "Sohbet bağlamı ve CMS sözlüğüyle retrieval sorgusu planlandı.",
            ],
        }

    @staticmethod
    def _after_plan(state: CMSAgentState) -> str:
        """Önceden cevaplanan isteği doğrulamaya, diğerini retrieval'a yönlendirir."""

        return "verify" if state.get("generation_mode") else "retrieve"

    def _retrieve_evidence(self, state: CMSAgentState) -> CMSAgentState:
        """Planlanmış sorguyu hibrit retrieval ve mevcut reranker üzerinde çalıştırır."""

        try:
            hits = self.engine.retrieve_planned(state["retrieval_query"], state["scope"])
        except (OSError, RuntimeError, ValueError) as exception:
            return {
                "hits": [],
                "error": str(exception).strip() or exception.__class__.__name__,
                "events": [
                    *state.get("events", []),
                    "Retrieval düğümü güvenli hata sınırında durduruldu.",
                ],
            }
        return {
            "hits": serialize_hits(hits),
            "events": [
                *state.get("events", []),
                f"Hibrit arama ve reranking sonucunda {len(hits)} aday kanıt seçildi.",
            ],
        }

    def _gate_evidence(self, state: CMSAgentState) -> CMSAgentState:
        """Kanıtların cevap üretmeye yeterli olup olmadığını deterministik eşikle ölçer."""

        if state.get("error"):
            answerable = False
        else:
            answerable = self.engine.evidence_is_answerable(
                state["retrieval_query"],
                deserialize_hits(state.get("hits", [])),
            )
        return {
            "answerable": answerable,
            "events": [
                *state.get("events", []),
                "Kanıt yeterlilik kapısı geçildi."
                if answerable
                else "Kanıt yeterlilik kapısı güvenli ret kararı verdi.",
            ],
        }

    @staticmethod
    def _after_evidence_gate(state: CMSAgentState) -> str:
        """Yeterli kanıtı üretime, yetersiz kanıtı güvenli cevaba gönderir."""

        return "generate" if state.get("answerable", False) else "unsupported"

    @staticmethod
    def _unsupported_answer(state: CMSAgentState) -> CMSAgentState:
        """Yetersiz veya hatalı retrieval sonucunu kaynaksız güvenli ret olarak hazırlar."""

        return {
            "answer": NO_ANSWER,
            "hits": [],
            "generation_mode": "retrieval_error" if state.get("error") else "evidence_gate",
            "events": [
                *state.get("events", []),
                "Belgesiz üretim yapılmadan güvenli yanıt hazırlandı.",
            ],
        }

    def _generate_answer(self, state: CMSAgentState) -> CMSAgentState:
        """Yerel modeli yalnız seçilmiş kanıtlarla çağırıp tamamlanmış yanıt üretir."""

        answer = self.engine.generate_grounded_answer(
            state["question"],
            deserialize_hits(state.get("hits", [])),
            state["scope"],
        )
        service_error = "Ollama servisine ulaşılamadı" in answer
        return {
            "answer": answer,
            "hits": [] if service_error else state.get("hits", []),
            "generation_mode": "service_error" if service_error else "ollama",
            "events": [
                *state.get("events", []),
                "Yerel model seçilmiş kanıtlarla yanıt taslağını tamamladı."
                if not service_error
                else "Yerel model servisine erişilemedi; hata kullanıcıya güvenli biçimde aktarıldı.",
            ],
        }

    @staticmethod
    def _verify_answer(state: CMSAgentState) -> CMSAgentState:
        """Yanıtın kaynak kimliklerini, kanıt varlığını ve tamamlanmış cümle bitişini doğrular."""

        answer = state.get("answer", "").strip()
        hits = state.get("hits", [])
        mode = state.get("generation_mode", "")
        if mode in {"unavailable", "safe_rejection", "evidence_gate", "retrieval_error", "service_error"}:
            passed, reason = True, f"{mode} sonucu araçsız/güvenli son durum olarak kabul edildi."
        elif not answer or answer == NO_ANSWER:
            passed, reason = False, "Kanıt bulunduğu hâlde kullanılabilir bir yanıt üretilemedi."
        elif not hits:
            passed, reason = False, "Kaynaklı yanıt için kanıt listesi bulunamadı."
        else:
            source_ids = [
                int(item)
                for item in re.findall(r"\[SOURCE\s+(\d+)\]", answer, flags=re.I)
            ]
            invalid_ids = [item for item in source_ids if item < 1 or item > len(hits)]
            without_citations = re.sub(
                r"\s*\[SOURCE\s+\d+\]\s*",
                "",
                answer,
                flags=re.I,
            ).rstrip()
            complete = without_citations.endswith((".", "!", "?"))
            passed = bool(source_ids) and not invalid_ids and complete
            if not source_ids:
                reason = "Yanıtta kaynak işareti bulunamadı."
            elif invalid_ids:
                reason = f"Yanıt mevcut olmayan kaynak kimliklerini kullandı: {invalid_ids}."
            elif not complete:
                reason = "Yanıt tamamlanmış bir cümleyle bitmedi."
            else:
                reason = "Kaynak kimlikleri ve cümle bütünlüğü doğrulandı."
        return {
            "verification_passed": passed,
            "verification_reason": reason,
            "events": [*state.get("events", []), reason],
        }

    @staticmethod
    def _after_verification(state: CMSAgentState) -> str:
        """Başarılı yanıtı kayda, ilk hatayı onarıma ve tekrarlanan hatayı güvenli reddetmeye yollar."""

        if state.get("verification_passed", False):
            return "record"
        if state.get("hits") and state.get("repair_count", 0) < 1:
            return "repair"
        return "reject"

    def _repair_answer(self, state: CMSAgentState) -> CMSAgentState:
        """Yanıtı yeni model çağrısı yapmadan ve yeni iddia eklemeden tek kez onarır."""

        repaired = self.engine.repair_grounded_answer(
            state["question"],
            state.get("answer", ""),
            deserialize_hits(state.get("hits", [])),
        )
        return {
            "answer": repaired,
            "repair_count": state.get("repair_count", 0) + 1,
            "events": [
                *state.get("events", []),
                "Atıf ve cümle bütünlüğü deterministik olarak bir kez onarıldı.",
            ],
        }

    @staticmethod
    def _verification_reject(state: CMSAgentState) -> CMSAgentState:
        """Doğrulamayı geçemeyen yanıtı ve kanıt kartlarını kullanıcıdan tamamen gizler."""

        return {
            "answer": NO_ANSWER,
            "hits": [],
            "generation_mode": "verification_rejection",
            "events": [
                *state.get("events", []),
                "Onarım sonrasında doğrulanamayan yanıt güvenli biçimde reddedildi.",
            ],
        }

    def _record_answer(self, state: CMSAgentState) -> CMSAgentState:
        """Doğrulanmış agentic sonucu klasik motorla aynı bellek ve audit hattına kaydeder."""

        if state.get("recorded", False):
            return state
        self.engine.record_completed_answer(
            state["question"],
            state.get("answer", NO_ANSWER),
            deserialize_hits(state.get("hits", [])),
            state["scope"],
            started_at=state.get("started_at"),
            generation_mode=f"agentic_{state.get('generation_mode', 'unknown')}",
        )
        return {
            "recorded": True,
            "events": [
                *state.get("events", []),
                "Doğrulanmış sonuç audit ve konuşma belleğine kaydedildi.",
            ],
        }

    @staticmethod
    def _track_handoff(state: CMSAgentState) -> CMSAgentState:
        """MCP isteğini mevcut onaylı kontrol akışına yan etkisiz biçimde devreder."""

        return {
            "answer": "",
            "hits": [],
            "events": [
                *state.get("events", []),
                "İstek operatör onaylı MCP kontrol alt akışına devredildi.",
            ],
        }

    @staticmethod
    def _safe_reject(state: CMSAgentState) -> CMSAgentState:
        """Kapsam dışı veya boş isteği araç çağırmadan güvenli biçimde sonlandırır."""

        answer = RESTRICTED_ANSWER if state.get("question") else "Lütfen işlenecek bir soru yazın."
        return {
            "answer": answer,
            "hits": [],
            "events": [*state.get("events", []), "Herhangi bir araç çağrılmadan güvenli ret üretildi."],
        }

    @staticmethod
    def _finalize(state: CMSAgentState) -> CMSAgentState:
        """Graph sonucunu tamamlandı olarak işaretleyip checkpoint'e hazırlar."""

        return {
            "completed": True,
            "events": [*state.get("events", []), "Agentic tur tamamlandı ve checkpoint oluşturuldu."],
        }
