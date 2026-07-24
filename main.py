"""Optional terminal interface for the same guarded CMS-RAG workflow as the UI."""

from src.config import RAW_DATA_PATH
from src.services.knowledge_base import CMSKnowledgeBase


def main() -> None:
    knowledge_base = CMSKnowledgeBase(RAW_DATA_PATH)
    print(f"CMS-RAG hazır: {knowledge_base.build()} parça indekslendi.")
    print("Çıkmak için 'exit' yazın.")
    while True:
        query = input("\nSoru: ").strip()
        if query.lower() in {"exit", "quit"}:
            break
        answer, sources = knowledge_base.ask(query)
        print(f"\n{answer}")
        for score, document in sources:
            print(f"- {document.metadata['document']} | sayfa {document.metadata['page'] + 1} | alaka {score:.0%}")


if __name__ == "__main__":
    main()
