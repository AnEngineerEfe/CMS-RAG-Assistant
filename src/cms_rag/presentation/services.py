"""Ağır RAG motorunun Streamlit yaşam döngüsünü yöneten servis erişimi."""

import streamlit as st

from ..application import CMSRAGEngine
from .config import DATA_DIR, PROJECT_ROOT


# Alt paketlerdeki değişiklikleri de izleyerek eski motorun önbellekte kalmasını engelleriz.
_ENGINE_SOURCE_FILES = tuple((PROJECT_ROOT / "src" / "cms_rag").rglob("*.py"))
_ENGINE_CACHE_VERSION = max(path.stat().st_mtime_ns for path in _ENGINE_SOURCE_FILES)


@st.cache_resource
def _cached_engine(source_version: int) -> CMSRAGEngine:
    """Embedding ve reranker modellerini Streamlit yeniden çalıştırmalarında korur."""

    # Parametre yalnızca önbellek anahtarıdır; motorun kurulumunda doğrudan kullanılmaz.
    del source_version
    return CMSRAGEngine(DATA_DIR)


def get_engine() -> CMSRAGEngine:
    """Geçerli kaynak sürümüyle eşleşen tek RAG motoru örneğini döndürür."""

    return _cached_engine(_ENGINE_CACHE_VERSION)
