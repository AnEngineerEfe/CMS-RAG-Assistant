"""Central configuration for the local CMS-RAG application."""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_PATH = DATA_DIR / "raw"
HAVELSAN_DATA_PATH = RAW_DATA_PATH / "havelsan"
OPEN_SOURCE_DATA_PATH = RAW_DATA_PATH / "open_source"
PROCESSED_MARKDOWN_PATH = DATA_DIR / "processed" / "markdown"
VECTOR_DB_PATH = DATA_DIR / "vectorstore"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

# Kept local and CPU-friendly. Turkish CMS terminology is expanded to its
# English counterpart before retrieval in CMSKnowledgeBase.
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL = "BAAI/bge-reranker-base"
OLLAMA_MODEL = os.getenv("CMS_RAG_OLLAMA_MODEL", "qwen2.5:7b")

RETRIEVAL_K = 20
TOP_K = 4
# Scores are sigmoid-normalised reranker logits. Below this threshold, the
# assistant abstains instead of asking the LLM to improvise an answer.
MIN_RERANK_RELEVANCE = 0.35

UPLOAD_FOLDER = HAVELSAN_DATA_PATH
