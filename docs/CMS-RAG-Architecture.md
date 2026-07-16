# CMS-RAG Assistant

## Project Goal

Develop an AI assistant capable of answering questions about Combat Management Systems (CMS), especially HAVELSAN ADVENT CMS, using Retrieval-Augmented Generation (RAG).

The assistant should answer only based on trusted documentation instead of relying solely on the language model's internal knowledge.

---

# Objectives

- Build a LangChain-based RAG system.
- Create a structured knowledge base.
- Combine official HAVELSAN documents with open-source CMS resources.
- Support Hybrid Search.
- Support Re-ranking.
- Provide source citations.
- Be modular and extensible.

---

# Data Sources

## Official Sources

- HAVELSAN ADVENT CMS PDF
- HAVELSAN official website

## Open Source Sources

- NATO publications
- Naval Warfare documents
- Academic papers
- Defense terminology
- Technical reports

---

# High-Level Architecture

User

↓

Query

↓

Hybrid Retriever

↓

Relevant Documents

↓

Re-ranker

↓

LLM

↓

Answer + Sources

---

# Technologies

- Python
- LangChain
- FAISS
- HuggingFace Embeddings
- BM25
- Cross Encoder
- PyPDF
- Markdown
