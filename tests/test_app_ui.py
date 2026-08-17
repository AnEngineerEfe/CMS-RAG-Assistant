"""Streamlit-level regression test for the real multi-turn user journey."""

import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.cms_rag.application import CMSRAGEngine
from src.cms_rag.application.track_control import TrackControlService
from src.cms_rag.domain import Chunk, SearchHit
from src.cms_rag.domain.track_control import TrackState


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
    def test_unknown_ship_type_rejects_the_whole_command_with_allowed_values(self):
        """Geçersiz gemi tipinde kısmi yazma yapmadan anlaşılır seçenekleri gösterir."""

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
        self.assertIn("MCP · KOMUT DOĞRULAMA", page)
        self.assertIn("sancar", page)
        self.assertIn("Fırkateyn", page)
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
