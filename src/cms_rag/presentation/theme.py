"""Kurumsal Streamlit görünümünün sayfa ve CSS yapılandırması."""

import streamlit as st


_STYLES = """
<style>
  :root {
    --navy: #10213b;
    --blue: #3267b1;
    --ink: #17263d;
    --muted: #66758d;
    --line: #dce5f0;
    --surface: rgba(255, 255, 255, .94);
  }
  .stApp {
    color: var(--ink);
    background:
      radial-gradient(circle at 82% 4%, rgba(68, 126, 203, .10), transparent 28rem),
      linear-gradient(180deg, #f8fafd 0%, #f2f6fb 100%);
  }
  [data-testid="stHeader"] { background: transparent; }
  [data-testid="stMainBlockContainer"] {
    max-width: 1180px;
    padding-top: 2.2rem;
    padding-bottom: 7rem;
  }
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b1b32 0%, #102846 100%);
    border-right: 1px solid rgba(255,255,255,.08);
  }
  [data-testid="stSidebar"] * { color: #edf4ff; }
  [data-testid="stSidebar"] [data-baseweb="select"] > div,
  [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    background: rgba(255,255,255,.08);
    border-color: rgba(255,255,255,.16);
    border-radius: 12px;
  }
  [data-testid="stSidebar"] button {
    border-radius: 10px;
    border-color: rgba(255,255,255,.20);
  }
  .sidebar-brand { padding: .4rem 0 .75rem; }
  .sidebar-brand strong {
    display: block;
    font-size: 1.03rem;
    letter-spacing: .02rem;
  }
  .sidebar-brand span { color: #aebed4 !important; font-size: .78rem; }
  .hero {
    padding: .5rem 0 1.45rem;
    border-bottom: 1px solid var(--line);
    margin-bottom: 1.15rem;
  }
  .eyebrow {
    color: var(--blue);
    font-size: .72rem;
    font-weight: 750;
    letter-spacing: .14rem;
  }
  .hero h1 {
    color: var(--navy);
    margin: .35rem 0 .28rem;
    font-size: clamp(2rem, 3vw, 2.65rem);
    letter-spacing: -.045em;
  }
  .hero p {
    color: var(--muted);
    margin: 0;
    max-width: 42rem;
    line-height: 1.6;
  }
  .metric-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    box-shadow: 0 8px 26px rgba(24, 48, 82, .06);
    margin-top: .45rem;
  }
  .metric-label {
    color: var(--muted);
    font-size: .68rem;
    text-transform: uppercase;
    letter-spacing: .09rem;
  }
  .metric-value {
    color: var(--navy);
    font-size: 1.45rem;
    font-weight: 750;
    margin-top: .15rem;
  }
  [data-testid="stChatMessage"] {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: .45rem .7rem;
    margin-bottom: .75rem;
    box-shadow: 0 5px 18px rgba(25, 48, 79, .035);
  }
  [data-testid="stChatMessage"] p { line-height: 1.7; }
  .answer-label {
    color: var(--blue);
    font-size: .68rem;
    font-weight: 750;
    letter-spacing: .1rem;
    margin-bottom: .28rem;
  }
  [data-testid="stStatusWidget"], [data-testid="stExpander"] {
    border-color: var(--line);
    border-radius: 12px;
    background: rgba(249, 251, 254, .88);
  }
  .evidence-card {
    background: #f7faff;
    border-left: 3px solid #4d87cd;
    border-radius: 8px;
    padding: .72rem .9rem;
    margin: .55rem 0;
  }
  .source-meta {
    color: #315b8d;
    font-size: .78rem;
    font-weight: 700;
    margin-bottom: .2rem;
  }
  .source-quote {
    color: #596b83;
    font-size: .84rem;
    line-height: 1.55;
  }
  [data-testid="stChatInput"] {
    border: 1px solid #cad7e8;
    border-radius: 16px;
    background: rgba(255,255,255,.97);
    box-shadow: 0 14px 36px rgba(19, 43, 76, .12);
  }
  .prompt-guide {
    color: var(--muted);
    font-size: .8rem;
    padding: .1rem 0 .8rem;
  }
  @media (max-width: 760px) {
    [data-testid="stMainBlockContainer"] { padding-top: 1rem; }
    .hero h1 { font-size: 2rem; }
    .metric-card { margin-top: 0; }
  }
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
