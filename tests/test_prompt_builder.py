import unittest

from langchain_core.documents import Document

from src.generation.prompt_builder import CMSPromptBuilder
from src.generation.evidence_answers import CMSEvidenceAnswers
from src.memory.conversation_memory import CMSConversationMemory


class PromptAndMemoryTests(unittest.TestCase):
    def test_context_contains_provenance(self):
        prompt = CMSPromptBuilder.build(
            "What is ADVENT?",
            [Document(page_content="Evidence", metadata={"document": "brochure.pdf", "page": 2, "authority": "official"})],
        )
        self.assertIn("SOURCE 1: brochure.pdf, page 3, official", prompt)

    def test_memory_is_bounded(self):
        memory = CMSConversationMemory(max_turns=2)
        for number in range(3):
            memory.add(f"q{number}", f"a{number}")
        self.assertEqual([item["question"] for item in memory.get_history()], ["q1", "q2"])

    def test_track_management_definition_uses_grounded_turkish_answer(self):
        answer = CMSEvidenceAnswers.answer(
            "\u0130z y\u00f6netimi nedir?",
            [(0.9, Document(page_content="TRACK MANAGEMENT manages the lifecycle of tracks."))],
        )
        self.assertIn("ya\u015fam d\u00f6ng\u00fcs\u00fcn\u00fc", answer)
        self.assertIn("[SOURCE 1]", answer)

    def test_track_management_follow_up_provides_labelled_example(self):
        answer = CMSEvidenceAnswers.answer(
            "\u0130z y\u00f6netimi nedir? \u00d6rnek ver.",
            [(0.9, Document(page_content="TRACK MANAGEMENT manages the lifecycle of tracks."))],
        )
        self.assertIn("Temsili senaryo", answer)
        self.assertIn("[SOURCE 1]", answer)
