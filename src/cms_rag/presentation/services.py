"""Ağır RAG motorunun Streamlit yaşam döngüsünü yöneten servis erişimi."""

import atexit

import streamlit as st

from ..application import CMSRAGEngine
from ..application.track_control import TrackControlService
from ..infrastructure.mcp_audit import McpAuditStore
from ..infrastructure.mcp_track_client import StdioMcpTrackClient
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


@st.cache_resource
def get_track_control_service() -> TrackControlService:
    """Tek Swing/MCP sürecini Streamlit yeniden çalıştırmaları arasında korur."""

    client = StdioMcpTrackClient(PROJECT_ROOT)
    atexit.register(client.close)
    return TrackControlService(client, McpAuditStore(DATA_DIR / "audit"))
