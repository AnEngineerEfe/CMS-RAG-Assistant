"""Kurumsal Streamlit görünümünün sayfa ve CSS yapılandırması."""

import streamlit as st


_STYLES = """
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
"""


def apply_theme() -> None:
    """Sayfa meta verisini ve ortak CSS kurallarını yalnızca bir kez uygular."""

    st.set_page_config(
        page_title="CMS-RAG | Knowledge Operations",
        page_icon="◆",
        layout="wide",
    )
    st.markdown(_STYLES, unsafe_allow_html=True)
