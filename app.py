from html import escape
from pathlib import Path

import streamlit as st

from src.cms_rag.engine import CMSRAGEngine


ROOT = Path(__file__).parent
ENGINE_SOURCE_FILES = tuple((ROOT / "src" / "cms_rag").glob("*.py"))
ENGINE_CACHE_VERSION = max(path.stat().st_mtime_ns for path in ENGINE_SOURCE_FILES)
st.set_page_config(
    page_title="CMS-RAG | Knowledge Operations",
    page_icon="◆",
    layout="wide",
)

st.markdown(
    """
    <style>
      .stApp { background: #f5f7fb; }
      [data-testid="stSidebar"] { background: #0c1b33; }
      [data-testid="stSidebar"] * { color: #edf4ff; }
      .hero { padding: 1.2rem 0 1.4rem; border-bottom: 1px solid #d9e2f0; margin-bottom: 1.2rem; }
      .eyebrow { color: #4777b7; font-size: .78rem; font-weight: 700; letter-spacing: .12rem; }
      .hero h1 { color: #102a4c; margin: .15rem 0; font-size: 2.25rem; }
      .hero p { color: #61718b; margin: 0; }
      .metric-card { background: #ffffff; border: 1px solid #dbe4f0; border-radius: 12px; padding: .8rem 1rem; }
      .metric-label { color: #71809a; font-size: .75rem; text-transform: uppercase; letter-spacing: .06rem; }
      .metric-value { color: #112c51; font-size: 1.25rem; font-weight: 700; }
      .answer-label { color: #315f99; font-size: .75rem; font-weight: 700; letter-spacing: .08rem; }
      .evidence-card { background: #f7faff; border-left: 3px solid #4d87cd; border-radius: 5px; padding: .65rem .85rem; margin: .45rem 0; }
      .source-meta { color: #456789; font-size: .8rem; font-weight: 700; }
      .source-quote { color: #58677e; font-size: .86rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def cached_engine(source_version: int) -> CMSRAGEngine:
    """Cache heavy models, but invalidate when any engine source file changes."""
    del source_version
    return CMSRAGEngine(ROOT / "data")


def engine() -> CMSRAGEngine:
    return cached_engine(ENGINE_CACHE_VERSION)


def source_payload(hit) -> dict:
    excerpt = " ".join(hit.chunk.text.split())
    return {
        "document": hit.chunk.document,
        "page": hit.chunk.page,
        "excerpt": excerpt[:360] + ("..." if len(excerpt) > 360 else ""),
        "collection": hit.chunk.collection,
        "authority": hit.chunk.authority,
        "source_url": hit.chunk.source_url,
    }


def show_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"Kanıt paketi · {len(sources)} kaynak", expanded=False):
        for source in sources:
            url = source.get("source_url", "")
            link = (
                f" · <a href='{escape(url)}' target='_blank' rel='noopener noreferrer'>"
                "Kaynağı aç</a>"
                if url
                else ""
            )
            st.markdown(
                f"<div class='evidence-card'><div class='source-meta'>"
                f"{escape(source['document'])} · Sayfa {source['page']} · "
                f"{escape(source.get('authority', 'unknown'))}{link}</div>"
                f"<div class='source-quote'>"
                f"{escape(source.get('excerpt', 'Sayfa kanıt olarak kullanıldı.'))}"
                f"</div></div>",
                unsafe_allow_html=True,
            )


def render_message(message: dict) -> None:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.markdown(
                "<div class='answer-label'>KAYNAKLI YANIT</div>",
                unsafe_allow_html=True,
            )
        st.markdown(message["content"])
        if message["role"] == "assistant":
            show_sources(message.get("sources", []))


if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.markdown("### ◆ Knowledge Operations")
    st.caption("Yerel, kaynak kontrollü CMS bilgi katmanı")
    st.divider()
    scope = st.selectbox(
        "Sorgu kapsamı",
        ["all", "official", "open_source"],
        format_func=lambda value: {
            "all": "Birleşik · tüm güvenilir kaynaklar",
            "official": "Yalnızca resmî HAVELSAN",
            "open_source": "Yalnızca açık/kamu referansları",
        }[value],
    )
    uploaded = st.file_uploader(
        "Resmî PDF yükle",
        type=["pdf"],
        accept_multiple_files=True,
    )
    if uploaded and st.button(
        "Belgeyi doğrula ve indeksle",
        type="primary",
        use_container_width=True,
    ):
        result = engine().store.save_uploads(uploaded)
        if result.added:
            with st.spinner("Sayfalar ayrıştırılıyor ve hibrit indeks kuruluyor..."):
                chunk_count = engine().rebuild()
            st.success(
                f"{len(result.added)} belge doğrulandı · "
                f"{chunk_count} kanıt parçası hazır"
            )
        if result.duplicates:
            st.info(
                f"{len(result.duplicates)} belge zaten kayıtlı; "
                "yinelenen kopya eklenmedi."
            )
        if result.rejected:
            st.error(
                f"{len(result.rejected)} dosya geçerli PDF imzası taşımıyor "
                "veya boyut sınırını aşıyor; kabul edilmedi."
            )
    if st.button("İndeksi yenile", use_container_width=True):
        with st.spinner("Yerel indeks yenileniyor..."):
            st.success(f"{engine().rebuild()} kanıt parçası hazır")
    if st.button("Oturumu temizle", use_container_width=True):
        engine().clear_chat()
        st.session_state.messages = []
        st.rerun()
    st.divider()
    documents = engine().store.pdfs()
    st.caption("ÇALIŞMA DURUMU")
    st.caption(f"Model · {engine().model}")
    st.caption(f"Belge · {len(documents)}")
    st.caption(f"Koleksiyon · {scope}")
    st.caption("Arama · Semantic + BM25 + Reranking")
    for path in documents:
        st.caption(f"• {engine().store.display_name(path)}")
    with st.expander("Belge yönetimi"):
        records = engine().store.records()
        if not records:
            st.caption("Yüklenmiş yerel PDF yok.")
        for record in records:
            st.caption(
                f"{record['display_name']} · "
                f"{record['size_bytes'] / 1024 / 1024:.1f} MB"
            )
            if st.button(
                "Belgeyi kaldır",
                key=f"delete_{record['sha256']}",
                use_container_width=True,
            ):
                if engine().store.delete(record["sha256"]):
                    engine().rebuild()
                    st.session_state.messages = []
                    st.rerun()

if engine().retriever is None:
    with st.spinner("Yerel kanıt indeksi hazırlanıyor..."):
        engine().rebuild()

documents = engine().store.pdfs()
chunk_count = len(engine().retriever.chunks) if engine().retriever else 0
left, middle, right = st.columns([2.4, 1, 1])
with left:
    st.markdown(
        "<div class='hero'>"
        "<div class='eyebrow'>CMS-RAG / EVIDENCE-FIRST ASSISTANT</div>"
        "<h1>Komuta Bilgi Keşfi</h1>"
        "<p>Belge kanıtını, çoklu aramayı ve yerel üretimi "
        "tek operasyonda birleştirir.</p></div>",
        unsafe_allow_html=True,
    )
with middle:
    st.markdown(
        "<div class='metric-card'><div class='metric-label'>Yüklü belge</div>"
        f"<div class='metric-value'>{len(documents)}</div></div>",
        unsafe_allow_html=True,
    )
with right:
    st.markdown(
        "<div class='metric-card'><div class='metric-label'>Kanıt parçası</div>"
        f"<div class='metric-value'>{chunk_count}</div></div>",
        unsafe_allow_html=True,
    )

if not st.session_state.messages and not documents:
    st.info(
        "Seçilmiş resmî ve açık kaynaklar hazır. Kendi resmî PDF'inizi eklemek "
        "için sol paneldeki yükleme alanını kullanabilirsiniz."
    )
elif not st.session_state.messages:
    st.caption(
        "Önerilen başlangıç soruları: “ADVENT nedir?”, "
        "“Savaş gemisinde ADVENT ne yapar?”, "
        "“Taktik veri bağlantısı nedir?”"
    )

for message in st.session_state.messages:
    render_message(message)

question = st.chat_input(
    "CMS / ADVENT hakkında kanıta dayalı soru sorun...",
    disabled=engine().retriever is None,
)
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    render_message(st.session_state.messages[-1])
    with st.chat_message("assistant"):
        st.markdown(
            "<div class='answer-label'>YANIT ÜRETİMİ</div>",
            unsafe_allow_html=True,
        )
        status = st.status(
            "Sorgu bağlamı çözümleniyor ve kanıtlar yeniden sıralanıyor...",
            expanded=False,
        )
        stream, hits = engine().stream_ask(question, scope)
        sources = [source_payload(hit) for hit in hits]
        status.update(
            label=f"{len(sources)} kanıt seçildi · yanıt üretiliyor",
            state="running",
            expanded=False,
        )
        answer = st.write_stream(stream)
        answer = str(answer or "Yanıt üretilemedi; lütfen sorguyu yeniden deneyin.")
        unsupported_markers = (
            "yeterli kaynak bulunamadı",
            "ollama servisine ulaşılamadı",
        )
        if any(marker in answer.lower() for marker in unsupported_markers):
            sources = []
        final_status = (
            "Yanıt kaynaklarla birlikte tamamlandı"
            if sources
            else "Bu soru için belge desteği bulunamadı"
        )
        status.update(
            label=final_status,
            state="complete",
            expanded=False,
        )
        show_sources(sources)
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )
