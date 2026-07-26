from langchain_ollama import ChatOllama
from src.config import OLLAMA_MODEL


class CMSLLM:

    def __init__(self):

        self.llm = ChatOllama(
            model=OLLAMA_MODEL,
            temperature=0
        )

    @property
    def model_name(self):
        return OLLAMA_MODEL

    def generate(self, prompt):

        response = self.llm.invoke(prompt)

        return response.content

    def stream(self, prompt):

        for chunk in self.llm.stream(prompt):

            yield chunk.content
