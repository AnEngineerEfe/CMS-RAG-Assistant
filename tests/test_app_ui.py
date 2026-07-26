"""Streamlit-level regression test for the real multi-turn user journey."""

import unittest

from streamlit.testing.v1 import AppTest


class StreamlitJourneyTests(unittest.TestCase):
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
