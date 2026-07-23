"""Manual Ollama connectivity smoke check; it is not part of the test suite."""

from src.generation.llm import CMSLLM


def main() -> None:
    answer = CMSLLM().generate("Explain what a Combat Management System is.")
    print(answer)


if __name__ == "__main__":
    main()
