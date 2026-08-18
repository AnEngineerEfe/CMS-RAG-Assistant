"""LangGraph yönlendirme, güvenlik, parity ve checkpoint davranışı testleri."""

import unittest

from src.cms_rag.application.agentic import AgentRoute, CMSAgenticWorkflow
from src.cms_rag.application.agentic.workflow import RESTRICTED_ANSWER
from src.cms_rag.application.engine import KnowledgePreflight
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


if __name__ == "__main__":
    unittest.main()
