"""Mevcut CMS servislerini bozmadan LangGraph üzerinde orkestre eden ilk güvenli grafik."""

from __future__ import annotations

from dataclasses import dataclass
import re
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from ...domain.models import SearchHit
from ...domain.track_control import TrackIntent, parse_track_request
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
    interrupted: bool = False
    interrupt_payload: dict[str, Any] | None = None
    generation_mode: str = ""
    verification_passed: bool = False
    repair_count: int = 0
    duration_ms: float = 0.0


@dataclass(frozen=True)
class ConversationTurn:
    """Tamamlanmış bir graph turunu sohbet ekranına geri yüklenebilir biçimde taşır."""

    question: str
    answer: str
    scope: str
    route: AgentRoute
    hits: list[SearchHit]
    created_at: str
    generation_mode: str = ""


@dataclass(frozen=True)
class ConversationSummary:
    """Checkpoint deposundaki bir thread için güvenli ve kısa liste bilgisidir."""

    thread_id: str
    title: str
    turn_count: int
    updated_at: str
    pending_approval: bool = False


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
        self.checkpoint_persistent = (
            False if checkpointer is not None else self._checkpoint_runtime.persistent
        )
        self.checkpoint_backend = (
            "Harici checkpointer" if checkpointer is not None else self._checkpoint_runtime.display_name
        )
        self.graph = self._build_graph()

    def close(self) -> None:
        """Workflow'un sahip olduğu checkpoint bağlantısını kontrollü kapatır."""

        self._checkpoint_runtime.close()

    def invoke(self, question: str, scope: str, thread_id: str) -> AgenticResult:
        """Bir kullanıcı turunu checkpoint'li graph üzerinde çalıştırıp tipli sonuç döndürür."""

        return self._invoke(
            question,
            scope,
            thread_id,
            force_track_control=False,
            force_track_approval=False,
        )

    def invoke_track_context(
        self,
        question: str,
        scope: str,
        thread_id: str,
        *,
        requires_approval: bool,
    ) -> AgenticResult:
        """UI'da çözülen takip bağlamını RAG'a uğratmadan denetimli MCP rotasında çalıştırır."""

        return self._invoke(
            question,
            scope,
            thread_id,
            force_track_control=True,
            force_track_approval=requires_approval,
        )

    def _invoke(
        self,
        question: str,
        scope: str,
        thread_id: str,
        *,
        force_track_control: bool,
        force_track_approval: bool,
    ) -> AgenticResult:
        """Normal ve bağlamdan çözülmüş girdileri ortak başlangıç state'iyle graph'a verir."""

        if scope not in {"all", "official", "open_source"}:
            raise ValueError(f"Desteklenmeyen kaynak kapsamı: {scope}")
        config = {"configurable": {"thread_id": thread_id}}
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
                "force_track_control": force_track_control,
                "force_track_approval": force_track_approval,
            },
            config=config,
        )
        return self._result_from_state(state, config)

    def resume(self, thread_id: str, payload: dict[str, Any]) -> AgenticResult:
        """Operatör kararını aynı checkpoint üzerinden verip bekleyen graph turunu sürdürür."""

        if not thread_id.strip():
            raise ValueError("Devam ettirilecek konuşma kimliği boş olamaz.")
        if payload.get("decision") not in {"approved", "rejected", "failed"}:
            raise ValueError("Geçersiz MCP devam kararı.")
        config = {"configurable": {"thread_id": thread_id}}
        state = self.graph.invoke(Command(resume=dict(payload)), config=config)
        return self._result_from_state(state, config)

    def _result_from_state(
        self,
        state: dict[str, Any],
        config: dict[str, dict[str, str]],
    ) -> AgenticResult:
        """Normal ve interrupt çıktısını aynı güvenli sunum modeline dönüştürür."""

        raw_interrupts = tuple(state.get("__interrupt__", ()))
        interrupted = bool(raw_interrupts)
        if interrupted:
            # Interrupt çıktısı yalnız değişen alanları içerebilir. Kalıcı snapshot,
            # yönlendirme ve açıklama olaylarının eksiksiz kaynağıdır.
            values = dict(self.graph.get_state(config).values)
            values.update({key: value for key, value in state.items() if key != "__interrupt__"})
            state = values
        payload: dict[str, Any] | None = None
        if raw_interrupts:
            candidate = getattr(raw_interrupts[0], "value", None)
            if isinstance(candidate, dict):
                payload = dict(candidate)
        try:
            started_at = float(state.get("started_at", 0.0))
        except (TypeError, ValueError):
            started_at = 0.0
        duration_ms = (
            max((perf_counter() - started_at) * 1000, 0.0)
            if started_at > 0 and not interrupted
            else 0.0
        )
        return AgenticResult(
            route=AgentRoute(state.get("route", AgentRoute.SAFE_REJECT.value)),
            reason=state.get("route_reason", ""),
            answer=state.get("answer", ""),
            hits=deserialize_hits(list(state.get("hits", []))),
            events=tuple(state.get("events", [])),
            error=state.get("error", ""),
            interrupted=interrupted,
            interrupt_payload=payload,
            generation_mode=str(state.get("generation_mode", "")),
            verification_passed=bool(state.get("verification_passed", False)),
            repair_count=int(state.get("repair_count", 0)),
            duration_ms=round(duration_ms, 3),
        )

    def state_history(self, thread_id: str) -> list[Any]:
        """Test, hata ayıklama ve ileride zaman yolculuğu için checkpoint geçmişini döndürür."""

        config = {"configurable": {"thread_id": thread_id}}
        return list(self.graph.get_state_history(config))

    def complete_external_turn(
        self,
        thread_id: str,
        answer: str,
        *,
        generation_mode: str,
        event: str,
    ) -> None:
        """UI'da tamamlanan MCP okuma/doğrulama turunu mevcut terminal checkpoint'e ekler."""

        if not answer.strip():
            raise ValueError("Kalıcılaştırılacak dış yanıt boş olamaz.")
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = self.graph.get_state(config)
        values = snapshot.values
        if snapshot.next or values.get("route") != AgentRoute.TRACK_CONTROL.value:
            raise RuntimeError("Yalnız tamamlanmış MCP devri dış sonuçla güncellenebilir.")
        if str(values.get("answer", "")).strip():
            raise RuntimeError("Tamamlanmış graph yanıtı dış sonuçla değiştirilemez.")
        self.graph.update_state(
            config,
            {
                "answer": answer.strip(),
                "generation_mode": generation_mode,
                "completed": True,
                "events": [*values.get("events", []), event],
            },
            as_node="finalize",
        )

    def conversation_history(self, thread_id: str) -> list[ConversationTurn]:
        """Bir thread'in yalnız tamamlanmış son durumlarından sohbet turlarını kurar."""

        turns: list[ConversationTurn] = []
        for snapshot in reversed(self.state_history(thread_id)):
            values = snapshot.values
            # Sonraki invocation'ın input checkpoint'i önceki `completed=True`
            # değerini kısa süre taşıyabilir. Yalnız terminal snapshot gerçek turdur.
            if not values.get("completed") or snapshot.next:
                continue
            question = str(values.get("question", "")).strip()
            answer = str(values.get("answer", "")).strip()
            if not question or not answer:
                continue
            route_value = str(values.get("route", AgentRoute.KNOWLEDGE.value))
            try:
                route = AgentRoute(route_value)
            except ValueError:
                route = AgentRoute.SAFE_REJECT
            turns.append(
                ConversationTurn(
                    question=question,
                    answer=answer,
                    scope=str(values.get("scope", "all")),
                    route=route,
                    hits=deserialize_hits(list(values.get("hits", []))),
                    created_at=str(snapshot.created_at or ""),
                    generation_mode=str(values.get("generation_mode", "")),
                )
            )
        return turns

    def conversation_summaries(self, *, limit: int = 50) -> list[ConversationSummary]:
        """Tamamlanmış ve operatör onayı bekleyen thread'leri son etkinliğe göre listeler."""

        thread_ids: list[str] = []
        seen: set[str] = set()
        for item in self.checkpointer.list(None, limit=2000):
            thread_id = str(item.config.get("configurable", {}).get("thread_id", ""))
            if thread_id and thread_id not in seen:
                seen.add(thread_id)
                thread_ids.append(thread_id)
        summaries: list[ConversationSummary] = []
        for thread_id in thread_ids:
            turns = self.conversation_history(thread_id)
            pending = self.pending_interrupt(thread_id)
            if not turns and pending is None:
                continue
            first_question = turns[0].question if turns else str(pending.get("question", ""))
            title = " ".join(first_question.split()) or "MCP onayı bekleyen konuşma"
            latest = self.graph.get_state(
                {"configurable": {"thread_id": thread_id}}
            )
            summaries.append(
                ConversationSummary(
                    thread_id=thread_id,
                    title=title[:52] + ("…" if len(title) > 52 else ""),
                    turn_count=len(turns),
                    updated_at=str(latest.created_at or (turns[-1].created_at if turns else "")),
                    pending_approval=pending is not None,
                )
            )
        summaries.sort(key=lambda item: item.updated_at, reverse=True)
        return summaries[:limit]

    def pending_interrupt(self, thread_id: str) -> dict[str, Any] | None:
        """Thread'in bekleyen güvenli interrupt yükünü, uygulama yeniden başlasa da bulur."""

        snapshot = self.graph.get_state({"configurable": {"thread_id": thread_id}})
        for task in snapshot.tasks:
            for item in task.interrupts:
                payload = getattr(item, "value", None)
                if isinstance(payload, dict) and payload.get("kind") == "track_control_approval":
                    return dict(payload)
        return None

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

        if state.get("force_track_control", False):
            return {
                "route": AgentRoute.TRACK_CONTROL.value,
                "route_reason": "Bekleyen MCP konuşma bağlamı kontrollü iz rotasına bağlandı.",
                "events": [
                    *state.get("events", []),
                    "Bekleyen MCP konuşma bağlamı kontrollü iz rotasına bağlandı.",
                ],
            }
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

        try:
            preflight = self.engine.preflight_answer(state["question"], state["scope"])
        except (OSError, RuntimeError, ValueError, TypeError) as exception:
            return self._safe_node_failure(state, "planning_error", "Planlama", exception)
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
        try:
            query = self.engine.plan_retrieval_query(state["question"], state["scope"])
        except (OSError, RuntimeError, ValueError, TypeError) as exception:
            return self._safe_node_failure(state, "planning_error", "Planlama", exception)
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
            try:
                answerable = self.engine.evidence_is_answerable(
                    state["retrieval_query"],
                    deserialize_hits(state.get("hits", [])),
                )
            except (OSError, RuntimeError, ValueError, TypeError) as exception:
                return {
                    **self._safe_node_failure(state, "evidence_gate_error", "Kanıt kapısı", exception),
                    "answerable": False,
                }
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

        try:
            answer = self.engine.generate_grounded_answer(
                state["question"],
                deserialize_hits(state.get("hits", [])),
                state["scope"],
            )
        except (OSError, RuntimeError, ValueError, TypeError) as exception:
            return self._safe_node_failure(state, "generation_error", "Yanıt üretimi", exception)
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
        if mode in {
            "unavailable",
            "safe_rejection",
            "evidence_gate",
            "retrieval_error",
            "service_error",
            "planning_error",
            "evidence_gate_error",
            "generation_error",
            "repair_error",
        }:
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

        try:
            repaired = self.engine.repair_grounded_answer(
                state["question"],
                state.get("answer", ""),
                deserialize_hits(state.get("hits", [])),
            )
        except (OSError, RuntimeError, ValueError, TypeError) as exception:
            return self._safe_node_failure(state, "repair_error", "Yanıt onarımı", exception)
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
        try:
            self.engine.record_completed_answer(
                state["question"],
                state.get("answer", NO_ANSWER),
                deserialize_hits(state.get("hits", [])),
                state["scope"],
                started_at=state.get("started_at"),
                generation_mode=f"agentic_{state.get('generation_mode', 'unknown')}",
            )
        except (OSError, RuntimeError, ValueError, TypeError) as exception:
            return {
                "recorded": False,
                "error": state.get("error") or (str(exception).strip() or exception.__class__.__name__),
                "events": [
                    *state.get("events", []),
                    "Yanıt hazırlandı ancak audit kaydı kullanılamadı; kullanıcı yanıtı korunuyor.",
                ],
            }
        return {
            "recorded": True,
            "events": [
                *state.get("events", []),
                "Doğrulanmış sonuç audit ve konuşma belleğine kaydedildi.",
            ],
        }

    @staticmethod
    def _safe_node_failure(
        state: CMSAgentState,
        mode: str,
        node_label: str,
        exception: Exception,
    ) -> CMSAgentState:
        """Bir düğüm hatasını teknik ayrıntı sızdırmadan güvenli terminal yanıta dönüştürür."""

        detail = str(exception).strip() or exception.__class__.__name__
        return {
            "answer": NO_ANSWER,
            "hits": [],
            "generation_mode": mode,
            "error": detail,
            "events": [
                *state.get("events", []),
                f"{node_label} düğümü hata sınırında durduruldu; belgesiz üretim yapılmadı.",
            ],
        }

    @staticmethod
    def _track_handoff(state: CMSAgentState) -> CMSAgentState:
        """MCP yazmasını checkpoint'te durdurur; okuma ve belirsizliği yan etkisiz devreder."""

        request = parse_track_request(state.get("question", ""))
        if request.intent in {TrackIntent.WRITE, TrackIntent.PARTIAL_WRITE} or state.get(
            "force_track_approval", False
        ):
            resume_payload = interrupt(
                {
                    "kind": "track_control_approval",
                    "question": state.get("question", ""),
                    "message": "MCP yazma işlemi operatör onayı bekliyor.",
                }
            )
            if not isinstance(resume_payload, dict):
                resume_payload = {"decision": "failed", "answer": "Geçersiz operatör kararı."}
            decision = str(resume_payload.get("decision", "failed"))
            answer = str(resume_payload.get("answer", "")).strip()
            if not answer:
                answer = (
                    "İşlem operatör tarafından iptal edildi; hiçbir değer değiştirilmedi."
                    if decision == "rejected"
                    else "MCP işlemi güvenli biçimde tamamlanamadı."
                )
            decision_event = {
                "approved": "Operatör onayı sonrası MCP yazması uygulanıp geri-okumayla doğrulandı.",
                "rejected": "Operatör MCP yazmasını reddetti; herhangi bir değişiklik yapılmadı.",
                "failed": "Onaylanan MCP yazması güvenli biçimde tamamlanamadı.",
            }.get(decision, "MCP devam kararı doğrulanamadı.")
            return {
                "answer": answer,
                "hits": [],
                "generation_mode": f"track_{decision}",
                "events": [*state.get("events", []), decision_event],
            }

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
