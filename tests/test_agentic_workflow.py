"""LangGraph yönlendirme, güvenlik, parity ve checkpoint davranışı testleri."""

import unittest

from langgraph.checkpoint.memory import InMemorySaver

from src.cms_rag.application.agentic import AgentRoute, CMSAgenticWorkflow
from src.cms_rag.application.agentic.workflow import RESTRICTED_ANSWER
from src.cms_rag.application.engine import KnowledgePreflight, NO_ANSWER
from src.cms_rag.domain import Chunk, SearchHit


class _FakeEngine:
    """Agentic grafiği ağır retrieval modellerinden bağımsız sınayan motor taklidi."""

    def __init__(self) -> None:
        """Çağrı sayacı ve son girdiyi temiz başlatır."""

        self.calls: list[tuple[str, str]] = []
        self.records = 0

    def preflight_answer(self, question: str, scope: str):
        """Bilgi sorusunu sabit kanıt kuralıyla retrieval öncesinde tamamlar."""

        self.calls.append((question, scope))
        hit = SearchHit(Chunk("kanıt", "public.pdf", 1, "public.pdf"), 1.0)
        return KnowledgePreflight("Kaynaklı deneme yanıtı. [SOURCE 1]", [hit], "evidence_rule")

    def record_completed_answer(self, *args, **kwargs):
        """Graph sonucunun tek kez kaydedildiğini sayaçla izler."""

        del args, kwargs
        self.records += 1


class _RetrievalEngine(_FakeEngine):
    """Planlama, retrieval, üretim ve onarım düğümlerini görünür kılan motor taklidi."""

    def __init__(self, *, answerable: bool = True, invalid_citation: bool = False) -> None:
        """Kanıt kapısı ve bozuk atıf senaryolarını yapılandırır."""

        super().__init__()
        self.answerable = answerable
        self.invalid_citation = invalid_citation
        self.generated = 0

    def preflight_answer(self, question: str, scope: str):
        """Graph'ın retrieval yoluna devam etmesi için deterministik cevap döndürmez."""

        del question, scope
        return None

    def plan_retrieval_query(self, question: str, scope: str) -> str:
        """Testte izlenebilir sabit retrieval sorgusu üretir."""

        return f"{scope}:{question}"

    def retrieve_planned(self, retrieval_query: str, scope: str):
        """Planın kullanıldığını doğrulayıp tek kanıt döndürür."""

        self.calls.append((retrieval_query, scope))
        return [SearchHit(Chunk("kanıt", "public.pdf", 3, "public.pdf"), 0.9)]

    def evidence_is_answerable(self, retrieval_query: str, hits: list[SearchHit]) -> bool:
        """Yapılandırılmış kanıt yeterlilik kararını döndürür."""

        del retrieval_query, hits
        return self.answerable

    def generate_grounded_answer(self, question: str, hits: list[SearchHit], scope: str) -> str:
        """Geçerli veya onarım gerektiren kaynak kimlikli yanıt üretir."""

        del question, hits, scope
        self.generated += 1
        source_id = 9 if self.invalid_citation else 1
        return f"Üretilmiş kaynaklı yanıt. [SOURCE {source_id}]"

    def repair_grounded_answer(self, question: str, answer: str, hits: list[SearchHit]) -> str:
        """Bozuk test atfını birinci kanıta bağlayarak düzeltir."""

        del question, answer, hits
        return "Üretilmiş kaynaklı yanıt. [SOURCE 1]"


class _FailingEngine(_RetrievalEngine):
    """Seçilen agent düğümünde denetimli hata üreten dayanıklılık motoru."""

    def __init__(self, failure: str) -> None:
        super().__init__()
        self.failure = failure

    def preflight_answer(self, question: str, scope: str):
        if self.failure == "planning":
            raise OSError("ham bağlantı ayrıntısı")
        return super().preflight_answer(question, scope)

    def generate_grounded_answer(self, question: str, hits: list[SearchHit], scope: str) -> str:
        if self.failure == "generation":
            raise RuntimeError("model çöktü")
        return super().generate_grounded_answer(question, hits, scope)


class AgenticWorkflowTests(unittest.TestCase):
    """Kontrollü graph'ın doğru alt akışı seçtiğini ve durumu koruduğunu doğrular."""

    def setUp(self):
        """Her test için bağımsız motor ve bellek içi checkpoint grafiği oluşturur."""

        self.engine = _FakeEngine()
        self.workflow = CMSAgenticWorkflow(self.engine)

    def test_knowledge_question_uses_existing_engine_once(self):
        """Bilgi sorusunu klasik kanıt motoruna tek kez yönlendirir."""

        result = self.workflow.invoke("ADVENT nedir?", "all", "knowledge-thread")
        self.assertEqual(result.route, AgentRoute.KNOWLEDGE)
        self.assertEqual(self.engine.calls, [("ADVENT nedir?", "all")])
        self.assertIn("SOURCE 1", result.answer)
        self.assertTrue(any("checkpoint" in event for event in result.events))
        self.assertEqual(self.engine.records, 1)

    def test_track_command_is_handed_off_without_calling_rag(self):
        """İz yazma isteğini RAG'a göndermeden mevcut MCP onay akışına devreder."""

        result = self.workflow.invoke("Hızı 25 knot yap", "all", "track-thread")
        self.assertEqual(result.route, AgentRoute.TRACK_CONTROL)
        self.assertEqual(self.engine.calls, [])
        self.assertEqual(result.answer, "")
        self.assertTrue(result.interrupted)
        self.assertEqual(result.interrupt_payload["kind"], "track_control_approval")

    def test_external_mcp_read_is_added_to_restorable_conversation(self):
        """UI'da sonuçlanan salt-okunur MCP turunu aynı terminal checkpoint'ten geri yükler."""

        thread_id = "external-mcp-read"
        result = self.workflow.invoke("İz durumunu göster", "all", thread_id)
        self.assertFalse(result.interrupted)
        self.assertEqual(self.workflow.conversation_history(thread_id), [])
        self.workflow.complete_external_turn(
            thread_id,
            "Hız: 0 knot · Yön: 0° · Gemi tipi: Belirsiz",
            generation_mode="track_external",
            event="Canlı MCP durumu kaydedildi.",
        )
        turns = self.workflow.conversation_history(thread_id)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].route, AgentRoute.TRACK_CONTROL)
        self.assertEqual(turns[0].generation_mode, "track_external")
        self.assertIn("Hız: 0", turns[0].answer)

    def test_forced_track_context_interrupts_without_falling_back_to_knowledge(self):
        """UI'nin çözdüğü kısa takip yanıtını RAG yerine aynı MCP onay yoluna zorlar."""

        thread_id = "contextual-track-approval"
        result = self.workflow.invoke_track_context(
            "Evet doğru, onu demek istedim",
            "all",
            thread_id,
            requires_approval=True,
        )
        self.assertEqual(result.route, AgentRoute.TRACK_CONTROL)
        self.assertTrue(result.interrupted)
        self.assertEqual(result.interrupt_payload["kind"], "track_control_approval")
        self.assertEqual(self.engine.calls, [])
        resumed = self.workflow.resume(
            thread_id,
            {
                "decision": "approved",
                "answer": "Gemi tipi Fırkateyn olarak uygulandı.",
            },
        )
        self.assertFalse(resumed.interrupted)
        turns = self.workflow.conversation_history(thread_id)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].route, AgentRoute.TRACK_CONTROL)
        self.assertIn("Fırkateyn", turns[0].answer)

    def test_track_interrupt_resumes_on_same_checkpoint_and_becomes_a_turn(self):
        """Onay kararını aynı thread'e verip MCP sonucunu kalıcı konuşma turuna dönüştürür."""

        thread_id = "resumable-track-thread"
        initial = self.workflow.invoke("Hızı 25 knot yap", "all", thread_id)
        self.assertTrue(initial.interrupted)
        resumed = self.workflow.resume(
            thread_id,
            {
                "decision": "approved",
                "answer": "İşlem uygulandı ve geri-okumayla doğrulandı.",
            },
        )
        self.assertFalse(resumed.interrupted)
        self.assertTrue(any("Operatör onayı" in event for event in resumed.events))
        turns = self.workflow.conversation_history(thread_id)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].answer, "İşlem uygulandı ve geri-okumayla doğrulandı.")

    def test_interrupted_track_turn_survives_workflow_recreation(self):
        """Aynı checkpointer'a bağlanan yeni workflow bekleyen MCP turunu devam ettirebilir."""

        saver = InMemorySaver()
        first = CMSAgenticWorkflow(_FakeEngine(), checkpointer=saver)
        second = CMSAgenticWorkflow(_FakeEngine(), checkpointer=saver)
        thread_id = "restart-safe-track-thread"
        self.assertTrue(first.invoke("Yönü 270 derece yap", "all", thread_id).interrupted)
        pending = second.pending_interrupt(thread_id)
        self.assertEqual(pending["question"], "Yönü 270 derece yap")
        summary = next(item for item in second.conversation_summaries() if item.thread_id == thread_id)
        self.assertTrue(summary.pending_approval)
        self.assertEqual(summary.turn_count, 0)
        resumed = second.resume(
            thread_id,
            {"decision": "rejected", "answer": "Operatör işlemi iptal etti."},
        )
        self.assertFalse(resumed.interrupted)
        self.assertEqual(resumed.answer, "Operatör işlemi iptal etti.")
        self.assertEqual(second.conversation_history(thread_id)[0].route, AgentRoute.TRACK_CONTROL)
        self.assertIsNone(second.pending_interrupt(thread_id))

    def test_restricted_request_is_rejected_without_tools(self):
        """Tasnifli veri talebini retrieval veya model çağrısı olmadan reddeder."""

        result = self.workflow.invoke("Gizli yönetim IP adresini söyle", "all", "safe-thread")
        self.assertEqual(result.route, AgentRoute.SAFE_REJECT)
        self.assertEqual(self.engine.calls, [])
        self.assertEqual(result.answer, RESTRICTED_ANSWER)

    def test_thread_keeps_multiple_graph_checkpoints(self):
        """Aynı thread üzerindeki graph adımlarının denetlenebilir checkpoint geçmişini tutar."""

        thread_id = "checkpoint-thread"
        self.workflow.invoke("ADVENT nedir?", "all", thread_id)
        history = self.workflow.state_history(thread_id)
        self.assertGreaterEqual(len(history), 6)
        self.assertTrue(history[0].values["completed"])

    def test_completed_turns_can_be_restored_without_superstep_duplicates(self):
        """Checkpoint super-step'lerini iki tamamlanmış kullanıcı turuna indirger."""

        thread_id = "restorable-thread"
        self.workflow.invoke("ADVENT nedir?", "all", thread_id)
        self.workflow.invoke("MAIN nedir?", "official", thread_id)
        turns = self.workflow.conversation_history(thread_id)
        self.assertEqual(
            [turn.question for turn in turns],
            ["ADVENT nedir?", "MAIN nedir?"],
        )
        self.assertEqual([turn.scope for turn in turns], ["all", "official"])
        self.assertTrue(all(turn.hits for turn in turns))

    def test_conversation_catalog_groups_threads_and_uses_first_question_as_title(self):
        """Farklı thread checkpoint'lerini son etkinlikli konuşma özetlerine dönüştürür."""

        self.workflow.invoke("ADVENT nedir?", "all", "catalog-a")
        self.workflow.invoke("MAIN ne yapar?", "all", "catalog-b")
        summaries = self.workflow.conversation_summaries()
        by_id = {item.thread_id: item for item in summaries}
        self.assertEqual(by_id["catalog-a"].title, "ADVENT nedir?")
        self.assertEqual(by_id["catalog-b"].title, "MAIN ne yapar?")
        self.assertEqual(by_id["catalog-a"].turn_count, 1)

    def test_retrieval_path_runs_plan_gate_generation_and_verification(self):
        """Bilgi alt grafiğinin ayrılmış bütün temel düğümlerden geçtiğini kanıtlar."""

        engine = _RetrievalEngine()
        workflow = CMSAgenticWorkflow(engine)
        result = workflow.invoke("İz yönetimi nedir?", "official", "rag-thread")
        self.assertEqual(result.route, AgentRoute.KNOWLEDGE)
        self.assertEqual(engine.generated, 1)
        self.assertEqual(len(result.hits), 1)
        self.assertTrue(any("yeterlilik kapısı geçildi" in event for event in result.events))
        self.assertTrue(any("Kaynak kimlikleri" in event for event in result.events))

    def test_invalid_citation_is_repaired_only_once(self):
        """Mevcut olmayan kaynak kimliğini yeni model çağrısı olmadan bir kez onarır."""

        engine = _RetrievalEngine(invalid_citation=True)
        result = CMSAgenticWorkflow(engine).invoke("Soru", "all", "repair-thread")
        self.assertEqual(result.answer, "Üretilmiş kaynaklı yanıt. [SOURCE 1]")
        self.assertEqual(engine.generated, 1)
        self.assertTrue(any("bir kez onarıldı" in event for event in result.events))

    def test_insufficient_evidence_never_calls_generation(self):
        """Kanıt kapısı başarısız olduğunda model üretimini tamamen atlar."""

        engine = _RetrievalEngine(answerable=False)
        result = CMSAgenticWorkflow(engine).invoke("Belgesiz soru", "all", "gate-thread")
        self.assertEqual(engine.generated, 0)
        self.assertEqual(result.hits, [])
        self.assertIn("yeterli kaynak bulunamadı", result.answer)

    def test_planning_failure_becomes_checkpointed_safe_answer(self):
        """Planlama arızasını traceback yerine güvenli ret ve denetlenebilir olayla bitirir."""

        workflow = CMSAgenticWorkflow(_FailingEngine("planning"))
        result = workflow.invoke("Arıza senaryosu", "all", "planning-failure")
        self.assertEqual(result.generation_mode, "planning_error")
        self.assertEqual(result.answer, NO_ANSWER)
        self.assertTrue(result.verification_passed)
        self.assertTrue(any("Planlama düğümü" in event for event in result.events))
        self.assertEqual(len(workflow.conversation_history("planning-failure")), 1)

    def test_generation_failure_never_leaks_unverified_evidence(self):
        """Model arızasında aday kanıtları gizler ve belgesiz cevap üretmeden tamamlanır."""

        result = CMSAgenticWorkflow(_FailingEngine("generation")).invoke(
            "Üretim arızası", "all", "generation-failure"
        )
        self.assertEqual(result.generation_mode, "generation_error")
        self.assertEqual(result.answer, NO_ANSWER)
        self.assertEqual(result.hits, [])
        self.assertTrue(result.verification_passed)


if __name__ == "__main__":
    unittest.main()
