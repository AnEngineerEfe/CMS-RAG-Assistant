"""Streamlit-level regression test for the real multi-turn user journey."""

import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.cms_rag.application import CMSRAGEngine
from src.cms_rag.domain import Chunk, SearchHit


class StreamlitJourneyTests(unittest.TestCase):
    def test_scope_control_defaults_to_combined_collection(self):
        app = AppTest.from_file("app.py", default_timeout=180).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox[0].value, "all")

    def test_open_source_scope_reaches_the_nato_collection(self):
        app = AppTest.from_file("app.py", default_timeout=180).run()
        self.assertFalse(app.exception)
        app.selectbox[0].set_value("open_source").run()
        app.chat_input[0].set_value(
            "NATO veri merkezli birlikte \u00e7al\u0131\u015fabilirlik ne sa\u011flar?"
        ).run()
        page = "\n".join(item.value for item in app.markdown)
        self.assertIn("NATO'nun dijital birlikte", page)
        self.assertIn("nato-interoperability.md", page)
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
        self.assertEqual(len(app.expander), prior_evidence_count)
        self.assertFalse(app.exception)
