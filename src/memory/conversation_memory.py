class CMSConversationMemory:
    """Bounded session memory used only to resolve short follow-up questions."""

    def __init__(self, max_turns: int = 3):
        self.max_turns = max_turns
        self.history = []

    def add(self, question, answer):
        self.history.append({"question": question, "answer": answer})
        self.history = self.history[-self.max_turns:]

    def get_history(self):
        return list(self.history)

    def clear(self):
        self.history.clear()
