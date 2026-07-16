from src.generation.llm import CMSLLM

llm = CMSLLM()

answer = llm.generate(
    "Explain what a Combat Management System is."
)

print(answer)