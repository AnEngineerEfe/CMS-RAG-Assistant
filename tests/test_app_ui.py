"""Streamlit-level regression test for the real multi-turn user journey."""

import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from src.cms_rag.application import CMSRAGEngine
from src.cms_rag.application.track_control import TrackControlService
from src.cms_rag.domain import Chunk, SearchHit
from src.cms_rag.domain.track_control import TrackState
from src.cms_rag.presentation.services import get_agentic_workflow


class _UiTrackGateway:
    """Streamlit testinde gerçek pencere açmadan onay davranışını izleyen kapı."""

    def __init__(self):
        """Sabit başlangıç durumu ve yazma sayacı oluşturur."""

        self.state = TrackState(10.0, 90, "KORVET", "Korvet")
        self.write_count = 0

    def get_state(self):
        """Canlı durumu taklit eder."""

        return self.state

    def get_write_policy(self):
        """Test operatörünün yazmaya izin verdiğini bildirir."""

        return True

    def set_state(self, state):
        """Onaylı yazmayı kaydedip yeni durumu döndürür."""

        self.write_count += 1
        self.state = state
        return state


class StreamlitJourneyTests(unittest.TestCase):
    def test_agentic_mode_routes_restricted_request_without_retrieval(self):
        """Arayüzde agentic modu açınca hassas talebi graph güvenlik yolunda sonlandırır."""

        app = AppTest.from_file("app.py", default_timeout=180).run()
        agentic_toggle = next(
            toggle for toggle in app.toggle if toggle.label == "Agentic LangGraph modu"
        )
        agentic_toggle.set_value(True).run()
        app.chat_input[0].set_value("Gizli yönetim IP adresini söyle").run()
        page = "\n".join(item.value for item in app.markdown)
        self.assertIn("AGENTIC · GÜVENLİ YANIT", page)
        self.assertIn("kamuya açık", page)
        self.assertFalse(app.exception)

    def test_agentic_mode_hands_track_write_to_existing_approval_flow(self):
        """Graph yönlendirmesinden geçen MCP yazmasının yine operatör onayı istediğini kanıtlar."""

        gateway = _UiTrackGateway()
        service = TrackControlService(gateway)
        with patch(
            "src.cms_rag.presentation.track_chat.get_track_control_service",
            return_value=service,
        ):
            app = AppTest.from_file("app.py", default_timeout=180).run()
            next(
                toggle for toggle in app.toggle if toggle.label == "Agentic LangGraph modu"
            ).set_value(True).run()
            app.chat_input[0].set_value("Hızı 35 knot yap").run()
            self.assertEqual(gateway.write_count, 0)
            approve = next(
                button for button in app.button if button.label == "Onayla ve uygula"
            )
            approve.click().run()

        self.assertEqual(gateway.write_count, 1)
        self.assertEqual(gateway.state.speed_knots, 35)
        self.assertFalse(app.exception)

    def test_agentic_signed_heading_correction_stays_in_mcp_flow(self):
        """Ondalıklı yön uyarısından sonraki negatif dereceyi RAG'a kaçırmadan uygular."""

        gateway = _UiTrackGateway()
        service = TrackControlService(gateway)
        with patch(
            "src.cms_rag.presentation.track_chat.get_track_control_service",
            return_value=service,
        ):
            app = AppTest.from_file("app.py", default_timeout=180).run()
            next(
                toggle for toggle in app.toggle if toggle.label == "Agentic LangGraph modu"
            ).set_value(True).run()
            app.chat_input[0].set_value("Dereceyi -75.8 derece yap").run()
            page = "\n".join(item.value for item in app.markdown)
            self.assertIn("Swing/MCP yön alanı tam sayı", page)
            self.assertNotIn("AGENTIC · KAYNAKLI YANIT", page)

            app.chat_input[0].set_value("-92 derece").run()
            approve = next(
                button for button in app.button if button.label == "Onayla ve uygula"
            )
            self.assertEqual(gateway.write_count, 0)
            approve.click().run()

        page = "\n".join(item.value for item in app.markdown)
        self.assertEqual(gateway.write_count, 1)
        self.assertEqual(gateway.state.heading_degrees, 268)
        self.assertIn("esas açıya dönüştürüldü", page)
        self.assertNotIn("Kaynakta soruyla ilgili", page)
        self.assertFalse(app.exception)

    def test_agentic_checkpoint_retry_never_repeats_the_mcp_write(self):
        """MCP sonrası checkpoint arızasını yalnız resume ederek kurtarır; set aracını yinelemez."""

        gateway = _UiTrackGateway()
        service = TrackControlService(gateway)
        workflow = Mock()
        workflow.resume.side_effect = [RuntimeError("database unavailable"), Mock()]
        with (
            patch(
                "src.cms_rag.presentation.track_chat.get_track_control_service",
                return_value=service,
            ),
            patch(
                "src.cms_rag.presentation.track_chat.get_agentic_workflow",
                return_value=workflow,
            ),
        ):
            app = AppTest.from_file("app.py", default_timeout=180).run()
            next(
                toggle for toggle in app.toggle if toggle.label == "Agentic LangGraph modu"
            ).set_value(True).run()
            app.chat_input[0].set_value("Hızı 36 knot yap").run()
            next(button for button in app.button if button.label == "Onayla ve uygula").click().run()
            self.assertEqual(gateway.write_count, 1)
            retry = next(
                button
                for button in app.button
                if button.label == "Checkpoint devamını yeniden dene"
            )
            retry.click().run()

        self.assertEqual(gateway.write_count, 1)
        self.assertEqual(workflow.resume.call_count, 2)
        self.assertFalse(app.exception)

    def test_agentic_mode_returns_grounded_knowledge_with_visible_graph_steps(self):
        """Gerçek bilgi tabanında agentic alt grafiğin kaynaklı yanıt ve adımlar üretmesini sınar."""

        app = AppTest.from_file("app.py", default_timeout=180).run()
        next(
            toggle for toggle in app.toggle if toggle.label == "Agentic LangGraph modu"
        ).set_value(True).run()
        app.chat_input[0].set_value("ADVENT nedir?").run()
        page = "\n".join(item.value for item in app.markdown)
        self.assertIn("AGENTIC · KAYNAKLI YANIT", page)
        self.assertIn("ADVENT", page)
        self.assertIn("SOURCE 1", page)
        self.assertGreaterEqual(len(app.status), 1)
        self.assertFalse(app.exception)

    def test_fresh_browser_session_restores_latest_agentic_conversation(self):
        """Sayfa yenilemesini taklit eden yeni Streamlit oturumunda son thread'i otomatik açar."""

        workflow = get_agentic_workflow()
        with (
            patch.dict("os.environ", {"CMS_RAG_AGENTIC_MODE": "1"}, clear=False),
            patch.object(workflow, "checkpoint_persistent", True),
        ):
            first = AppTest.from_file("app.py", default_timeout=180).run()
            first.chat_input[0].set_value("ADVENT hangi amaca hizmet etmektedir?").run()
            first_page = "\n".join(item.value for item in first.markdown)
            self.assertIn("ADVENT", first_page)

            refreshed = AppTest.from_file("app.py", default_timeout=180).run()

        refreshed_page = "\n".join(item.value for item in refreshed.markdown)
        self.assertIn("ADVENT hangi amaca hizmet etmektedir?", refreshed_page)
        self.assertIn("Savaş Yönetim Sistemi", refreshed_page)
        self.assertFalse(refreshed.exception)

    def test_refresh_restores_mcp_read_and_validation_messages(self):
        """Graph dışında üretilen MCP okuma ve hata açıklamalarını da yeni oturumda korur."""

        gateway = _UiTrackGateway()
        service = TrackControlService(gateway)
        workflow = get_agentic_workflow()
        with (
            patch.dict("os.environ", {"CMS_RAG_AGENTIC_MODE": "1"}, clear=False),
            patch.object(workflow, "checkpoint_persistent", True),
            patch(
                "src.cms_rag.presentation.track_chat.get_track_control_service",
                return_value=service,
            ),
        ):
            first = AppTest.from_file("app.py", default_timeout=180).run()
            first.chat_input[0].set_value("İz durumunu göster").run()
            first.chat_input[0].set_value("Dereceyi 75.8 derece yap").run()
            refreshed = AppTest.from_file("app.py", default_timeout=180).run()

        page = "\n".join(item.value for item in refreshed.markdown)
        self.assertIn("İz durumunu göster", page)
        self.assertIn("10 knot", page)
        self.assertIn("Dereceyi 75.8 derece yap", page)
        self.assertIn("Swing/MCP yön alanı tam sayı", page)
        self.assertNotIn("Kaynakta soruyla ilgili", page)
        self.assertFalse(refreshed.exception)

    def test_refresh_restores_pending_mcp_approval_and_completed_result(self):
        """Yenilemede bekleyen yazmayı yeniden onaya açar ve tamamlanmış sonucu da korur."""

        gateway = _UiTrackGateway()
        service = TrackControlService(gateway)
        workflow = get_agentic_workflow()
        with (
            patch.dict("os.environ", {"CMS_RAG_AGENTIC_MODE": "1"}, clear=False),
            patch.object(workflow, "checkpoint_persistent", True),
            patch(
                "src.cms_rag.presentation.track_chat.get_track_control_service",
                return_value=service,
            ),
        ):
            first = AppTest.from_file("app.py", default_timeout=180).run()
            first.chat_input[0].set_value("Hızı 43 knot yap").run()
            self.assertEqual(gateway.write_count, 0)

            pending_refresh = AppTest.from_file("app.py", default_timeout=180).run()
            approve = next(
                button
                for button in pending_refresh.button
                if button.label == "Onayla ve uygula"
            )
            self.assertEqual(gateway.write_count, 0)
            approve.click().run()
            self.assertEqual(gateway.write_count, 1)

            completed_refresh = AppTest.from_file("app.py", default_timeout=180).run()

        page = "\n".join(item.value for item in completed_refresh.markdown)
        self.assertEqual(gateway.state.speed_knots, 43)
        self.assertIn("Hızı 43 knot yap", page)
        self.assertIn("43 knot", page)
        self.assertIn("MCP · KAYITLI İŞLEM", page)
        self.assertFalse(completed_refresh.exception)

    def test_unspecified_track_value_is_clarified_and_revalidated_across_turns(self):
        """Belirsiz alanı, saklanan değeri ve yeni değeri ortak çok turlu akışta çözer."""

        gateway = _UiTrackGateway()
        service = TrackControlService(gateway)
        with patch(
            "src.cms_rag.presentation.track_chat.get_track_control_service",
            return_value=service,
        ):
            app = AppTest.from_file("app.py", default_timeout=180).run()
            app.chat_input[0].set_value("bu sefer izi 101 yap").run()
            page = "\n".join(item.value for item in app.markdown)
            self.assertIn("Hızı mı, yönü mü", page)
            self.assertNotIn("Bu soruyu destekleyecek yeterli kaynak bulunamadı", page)

            app.chat_input[0].set_value("hız").run()
            page = "\n".join(item.value for item in app.markdown)
            self.assertIn("101 knot", page)
            self.assertIn("0–100", page)

            app.chat_input[0].set_value("tamam 100 olsun").run()
            approve = next(
                button for button in app.button if button.label == "Onayla ve uygula"
            )
            self.assertEqual(gateway.write_count, 0)
            approve.click().run()

        self.assertEqual(gateway.state.speed_knots, 100)
        self.assertEqual(gateway.write_count, 1)
        self.assertNotIn("pending_track_correction", app.session_state)
        self.assertFalse(app.exception)

    def test_invalid_speed_accepts_a_short_contextual_correction(self):
        """Aralık dışı hızdan sonra yalnız `100` yazılınca RAG yerine onay planı açar."""

        gateway = _UiTrackGateway()
        service = TrackControlService(gateway)
        with patch(
            "src.cms_rag.presentation.track_chat.get_track_control_service",
            return_value=service,
        ):
            app = AppTest.from_file("app.py", default_timeout=180).run()
            app.chat_input[0].set_value("hızı pardon 101 yap").run()
            page = "\n".join(item.value for item in app.markdown)
            self.assertIn("101 knot", page)
            self.assertIn("0–100", page)
            self.assertEqual(gateway.write_count, 0)

            app.chat_input[0].set_value("100").run()
            page = "\n".join(item.value for item in app.markdown)
            self.assertIn("MCP · İŞLEM ONAYI", page)
            self.assertNotIn("Bu soruyu destekleyecek yeterli kaynak bulunamadı", page)
            approve = next(
                button for button in app.button if button.label == "Onayla ve uygula"
            )
            approve.click().run()

        self.assertEqual(gateway.write_count, 1)
        self.assertEqual(gateway.state.speed_knots, 100)
        self.assertNotIn("pending_track_correction", app.session_state)
        self.assertFalse(app.exception)

    def test_ship_typo_confirmation_creates_a_plan_instead_of_falling_back_to_rag(self):
        """`evet` cevabını bekleyen tip önerisine bağlayıp yine son işlem onayını ister."""

        gateway = _UiTrackGateway()
        service = TrackControlService(gateway)
        with patch(
            "src.cms_rag.presentation.track_chat.get_track_control_service",
            return_value=service,
        ):
            app = AppTest.from_file("app.py", default_timeout=180).run()
            app.chat_input[0].set_value("gemi tipi muhrap yap").run()
            page = "\n".join(item.value for item in app.markdown)
            self.assertIn("Muhrip", page)
            self.assertIn("**Evet doğru**", page)
            self.assertEqual(gateway.write_count, 0)

            app.chat_input[0].set_value("şey işte o").run()
            page = "\n".join(item.value for item in app.markdown)
            self.assertIn("MCP · ÖNERİ NETLEŞTİRME", page)
            self.assertEqual(gateway.write_count, 0)

            app.chat_input[0].set_value("Evet doğru, onu demek istedim").run()
            approve = next(
                button for button in app.button if button.label == "Onayla ve uygula"
            )
            self.assertEqual(gateway.write_count, 0)
            approve.click().run()

        page = "\n".join(item.value for item in app.markdown)
        self.assertEqual(gateway.write_count, 1)
        self.assertEqual(gateway.state.ship_type, "MUHRIP")
        self.assertIn("MCP · DOĞRULANMIŞ İŞLEM", page)
        self.assertNotIn("Bu soruyu destekleyecek yeterli kaynak bulunamadı", page)
        self.assertFalse(app.exception)

    def test_agentic_ship_typo_confirmation_remains_in_mcp_context(self):
        """Agentic modda doğal onay cümlesini bilgi sorusu sanmadan MCP planına dönüştürür."""

        gateway = _UiTrackGateway()
        service = TrackControlService(gateway)
        with patch(
            "src.cms_rag.presentation.track_chat.get_track_control_service",
            return_value=service,
        ):
            app = AppTest.from_file("app.py", default_timeout=180).run()
            next(
                toggle for toggle in app.toggle if toggle.label == "Agentic LangGraph modu"
            ).set_value(True).run()
            app.chat_input[0].set_value("gemi tipini firakteyn yap").run()
            page = "\n".join(item.value for item in app.markdown)
            self.assertIn("Fırkateyn", page)
            self.assertEqual(gateway.write_count, 0)

            app.chat_input[0].set_value("Evet doğru, onu demek istedim").run()
            page = "\n".join(item.value for item in app.markdown)
            self.assertIn("MCP · İŞLEM ONAYI", page)
            self.assertNotIn("AGENTIC · KAYNAKLI YANIT", page)
            self.assertEqual(gateway.write_count, 0)
            next(
                button for button in app.button if button.label == "Onayla ve uygula"
            ).click().run()

        page = "\n".join(item.value for item in app.markdown)
        self.assertEqual(gateway.write_count, 1)
        self.assertEqual(gateway.state.ship_type, "FIRKATEYN")
        self.assertIn("MCP · DOĞRULANMIŞ İŞLEM", page)
        self.assertNotIn("Bu soruyu destekleyecek yeterli kaynak bulunamadı", page)
        self.assertFalse(app.exception)

    def test_unknown_ship_type_requires_confirmation_for_valid_subset(self):
        """Geçerli alanları onaya sunar, tanınmayan gemi tipini değiştirmeden korur."""

        gateway = _UiTrackGateway()
        service = TrackControlService(gateway)
        with patch(
            "src.cms_rag.presentation.track_chat.get_track_control_service",
            return_value=service,
        ):
            app = AppTest.from_file("app.py", default_timeout=180).run()
            app.chat_input[0].set_value(
                "İzin hızını 100 knot, yönünü 270 derece ve tipini sancar yap"
            ).run()
            page = "\n".join(item.value for item in app.markdown)
            self.assertEqual(gateway.write_count, 0)
            self.assertEqual(gateway.state, TrackState(10.0, 90, "KORVET", "Korvet"))
            self.assertIn("MCP · İŞLEM ONAYI", page)
            self.assertIn("sancar", page)
            apply_valid = next(
                button
                for button in app.button
                if button.label == "Geçerli değişiklikleri uygula"
            )
            apply_valid.click().run()

        page = "\n".join(item.value for item in app.markdown)
        self.assertEqual(gateway.write_count, 1)
        self.assertEqual(gateway.state, TrackState(100.0, 270, "KORVET", "Korvet"))
        self.assertIn("Gemi tipi değiştirilmeyecek", page)
        self.assertFalse(app.exception)

    def test_mcp_write_requires_confirmation_and_verifies_result(self):
        """Serbest metin komutunun onaysız yazmadığını ve onayla bir kez uygulandığını sınar."""

        gateway = _UiTrackGateway()
        service = TrackControlService(gateway)
        with patch(
            "src.cms_rag.presentation.track_chat.get_track_control_service",
            return_value=service,
        ):
            app = AppTest.from_file("app.py", default_timeout=180).run()
            app.chat_input[0].set_value("İzin hızını 24,5 knot yap").run()
            self.assertEqual(gateway.write_count, 0)
            approve = next(button for button in app.button if button.label == "Onayla ve uygula")
            approve.click().run()

        page = "\n".join(item.value for item in app.markdown)
        self.assertEqual(gateway.write_count, 1)
        self.assertIn("MCP · DOĞRULANMIŞ İŞLEM", page)
        self.assertIn("24.5 knot", page)
        self.assertFalse(app.exception)

    def test_scope_control_defaults_to_combined_collection(self):
        app = AppTest.from_file("app.py", default_timeout=180).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "all")
        captions = "\n".join(item.value for item in app.caption)
        self.assertIn("Agent checkpoint", captions)
        self.assertIn("Bellek içi", captions)

    def test_evaluation_workspace_starts_with_live_test_counters(self):
        app = AppTest.from_file("app.py", default_timeout=180).run()
        self.assertFalse(app.exception)
        app.radio[0].set_value("evaluation").run()
        page = "\n".join(item.value for item in app.markdown)
        self.assertIn("Değerlendirme Merkezi", page)
        self.assertIn("Canlı test", page)
        self.assertIn("Doğru chunk", page)
        self.assertGreaterEqual(len(app.tabs), 4)
        tab_labels = [tab.label for tab in app.tabs]
        self.assertIn("FAISS · 40 vaka", tab_labels)
        self.assertIn("pgvector · 40 vaka", tab_labels)
        self.assertIn("Backend karşılaştırması", tab_labels)
        self.assertGreaterEqual(len(app.dataframe), 5)
        self.assertFalse(app.exception)

    def test_source_button_opens_the_exact_pdf_evidence_page(self):
        app = AppTest.from_file("app.py", default_timeout=180).run()
        app.chat_input[0].set_value("Savaş Gemisi ADVENT'te ne yapar?").run()
        preview = next(
            button for button in app.button
            if button.label == "Sayfa 18 · PDF önizle"
        )
        preview.click().run()
        page = "\n".join(item.value for item in app.markdown)
        self.assertIn("advent_cms.pdf", page)
        self.assertIn("Sayfa 18", page)
        self.assertFalse(app.exception)

    def test_open_source_scope_reaches_the_nato_collection(self):
        app = AppTest.from_file("app.py", default_timeout=180).run()
        self.assertFalse(app.exception)
        app.selectbox[0].set_value("open_source").run()
        app.chat_input[0].set_value(
            "NATO veri merkezli birlikte \u00e7al\u0131\u015fabilirlik ne sa\u011flar?"
        ).run()
        page = "\n".join(item.value for item in app.markdown)
        self.assertIn("NATO'nun dijital birlikte", page)
        self.assertIn("deniz_c2_veri_ai_yonetisim_arastirma.pdf", page)
        self.assertNotIn("ADVENT gibi", page)
        self.assertFalse(app.exception)

    def test_ollama_failure_does_not_display_unrelated_evidence(self):
        hit = SearchHit(
            Chunk(
                "Evidence that must not be shown for a failed answer.",
                "official.pdf",
                1,
                "official.pdf",
            ),
            1.0,
        )
        error = (
            "Yerel Ollama servisine ula\u015f\u0131lamad\u0131. "
            "`ollama serve` komutunu \u00e7al\u0131\u015ft\u0131r\u0131n."
        )
        with patch.object(
            CMSRAGEngine,
            "stream_ask",
            return_value=(iter([error]), [hit]),
        ):
            app = AppTest.from_file("app.py", default_timeout=180).run()
            initial_expanders = len(app.expander)
            app.chat_input[0].set_value("Belgeye dayal\u0131 teknik soru").run()
        page = "\n".join(item.value for item in app.markdown)
        self.assertIn("Ollama servisine ula\u015f\u0131lamad\u0131", page)
        self.assertEqual(len(app.expander), initial_expanders)
        self.assertFalse(app.exception)

    def test_grounded_follow_up_and_unsupported_question(self):
        app = AppTest.from_file("app.py", default_timeout=180).run()
        self.assertFalse(app.exception)

        app.chat_input[0].set_value("Sava\u015f Gemisi ADVENT'te ne yapar?").run()
        page = "\n".join(item.value for item in app.markdown)
        self.assertIn("y\u00fczey platformlar\u0131ndaki", page)
        self.assertIn("Sayfa 18", page)

        app.chat_input[0].set_value("Ba\u015fka hangi platformlarda kullan\u0131l\u0131r?").run()
        page = "\n".join(item.value for item in app.markdown)
        self.assertIn("ADVENT ROTA", page)
        self.assertIn("Sayfa 4", page)

        prior_evidence_count = len(app.expander)
        app.chat_input[0].set_value("Ben kimim?").run()
        page = "\n".join(item.value for item in app.markdown)
        self.assertIn("yeterli kaynak bulunamad\u0131", page)
        self.assertIn("G\u00dcVENL\u0130 YANIT", page)
        self.assertEqual(len(app.expander), prior_evidence_count)
        self.assertFalse(app.exception)
