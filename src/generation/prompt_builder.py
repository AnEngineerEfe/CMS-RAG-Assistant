class CMSPromptBuilder:

    @staticmethod
    def build(question, documents):

        context = "\n\n".join(
            [doc.page_content for doc in documents]
        )

        return f"""
You are a senior AI assistant specialized in Combat Management Systems (CMS).

Instructions:
- Answer ONLY using the provided context.
- Do NOT invent information.
- If the answer is not present in the context, reply exactly:
"I couldn't find this information in the available CMS documents."
- Answer in a clear, concise and technical manner.
- If possible, summarize instead of copying sentences verbatim.

======================
CONTEXT
======================

{context}

======================
QUESTION
======================

{question}

======================
ANSWER
======================
"""