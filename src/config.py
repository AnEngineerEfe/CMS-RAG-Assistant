# -----------------------------
# Paths
# -----------------------------

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# Collections are deliberately isolated.  Official HAVELSAN material must never
# be silently mixed with general public/reference material during retrieval.
RAW_DATA_PATH = DATA_DIR / "raw"
HAVELSAN_DATA_PATH = RAW_DATA_PATH / "havelsan"
OPEN_SOURCE_DATA_PATH = RAW_DATA_PATH / "open_source"
VECTOR_DB_PATH = DATA_DIR / "vectorstore"
METADATA_PATH = VECTOR_DB_PATH / "manifest.json"

# -----------------------------
# Chunking
# -----------------------------

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150


# -----------------------------
# Models
# -----------------------------

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

RERANKER_MODEL = "BAAI/bge-reranker-base"

OLLAMA_MODEL = "qwen2.5:3b"


# -----------------------------
# Retrieval
# -----------------------------

RETRIEVAL_K = 8
TOP_K = 4
UPLOAD_FOLDER = HAVELSAN_DATA_PATH
