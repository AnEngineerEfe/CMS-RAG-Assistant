"""Prompt construction with strict evidence and language controls."""


class CMSPromptBuilder:
    @staticmethod
    def build(question, documents, history=""):
        language = "Turkish" if CMSPromptBuilder._is_turkish(question) else "English"
        context = "\n\n".join(
            CMSPromptBuilder._format_source(index + 1, document)
            for index, document in enumerate(documents)
        )
        no_answer = "Bu soruyu destekleyecek yeterli g\u00fcvenilir kaynak bulunamad\u0131."
        return f"""
You are a documentation-grounded Combat Management Systems assistant.

Use only the supplied CONTEXT as evidence. Answer the QUESTION directly in at
most two short factual paragraphs. Cite every factual paragraph as [SOURCE n].
Do not invent examples, scenarios, platforms, claims, or capabilities.
If the context is insufficient, return exactly: \"{no_answer}\".

Output language: {language}.
When output language is Turkish, write fluent Turkish only: do not use English
adjectives or filler words. Preserve only indispensable product names and
technical abbreviations (for example ADVENT, CMS, TDL). Translate "command and
control" as "komuta ve kontrol"; never use "komando". Do not mention AI,
autonomy, countries, or system capabilities unless they are explicitly stated
in the cited context. Conversation history may resolve a short follow-up, but
is not evidence.

CONVERSATION HISTORY
{history}

CONTEXT
{context}

QUESTION
{question}

ANSWER
"""

    @staticmethod
    def _format_source(index, document):
        source_url = document.metadata.get("source_url", "")
        url_line = f"\nURL: {source_url}" if source_url else ""
        return (
            f"[SOURCE {index}: {document.metadata.get('document', 'Unknown')}, "
            f"page {document.metadata.get('page', 0) + 1}, "
            f"{document.metadata.get('authority', 'unknown')}]"
            f"{url_line}\n{document.page_content}"
        )

    @staticmethod
    def _is_turkish(question):
        lowered = question.lower()
        markers = (
            " nedir", " nas\u0131l", " hangi", " \u00f6rnek", " m\u0131", " mi",
            " ve ", " i\u00e7in", " neden", " var m\u0131",
        )
        return any(marker in f" {lowered}" for marker in markers) or any(
            char in lowered for char in "\u00e7\u011f\u0131\u00f6\u015f\u00fc"
        )
