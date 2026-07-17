from langchain_ollama import ChatOllama


class CMSLLM:

    def __init__(self):

        self.llm = ChatOllama(
            model="qwen2.5:3b",
            temperature=0
        )

    # -----------------------------------------
    # Normal Response
    # -----------------------------------------

    def generate(self, prompt):

        response = self.llm.invoke(prompt)

        return response.content

    # -----------------------------------------
    # Streaming Response
    # -----------------------------------------

    def stream(self, prompt):

        for chunk in self.llm.stream(prompt):

            if chunk.content:

                yield chunk.content