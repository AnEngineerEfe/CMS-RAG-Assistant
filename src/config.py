# -----------------------------
# Paths
# -----------------------------

RAW_DATA_PATH = "data/raw/uploaded"

VECTOR_DB_PATH = "data/vectorstore/faiss_index"

METADATA_PATH = "data/vectorstore/metadata.json"

# -----------------------------
# Chunking
# -----------------------------

CHUNK_SIZE = 600

CHUNK_OVERLAP = 100


# -----------------------------
# Models
# -----------------------------

EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

RERANKER_MODEL = "BAAI/bge-reranker-base"

OLLAMA_MODEL = "llama3"


# -----------------------------
# Retrieval
# -----------------------------

TOP_K = 3

UPLOAD_FOLDER = "data/raw/uploaded"