"""
Trading Signals App — Or · Brent · Nasdaq
Run: streamlit run trading_app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Trading Signals | Or · Brent · Nasdaq",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark theme override + hide Streamlit chrome
st.markdown("""
<style>
  .stApp { background-color: #0d1117; }
  .stSidebar { background-color: #0d1117; border-right: 1px solid #1a1a2e; }
  .stMetric { background: #161b22; border-radius: 10px; padding: 12px; border: 1px solid #1a1a2e; }
  #MainMenu { visibility: hidden; }
  footer    { visibility: hidden; }
  header    { visibility: hidden; }
  .stTabs [data-baseweb="tab-list"] { background: #0d1117; gap: 4px; }
  .stTabs [data-baseweb="tab"]      { background: #161b22; border-radius: 8px 8px 0 0; color: #aaa; }
  .stTabs [aria-selected="true"]    { background: #1f6feb; color: white; }
  .stNumberInput input, .stTextInput input, .stSelectbox div[data-baseweb="select"] {
    background: #161b22 !important; border-color: #30363d !important; color: white !important;
  }
  .streamlit-expanderHeader { background: #161b22 !important; border-radius: 10px; }
  div[data-testid="stCode"] > pre { background: #0d1117 !important; border: 1px solid #1a1a2e; }
  /* Hide auto-discovered page nav items from the ESSCA app */
  [data-testid="stSidebarNav"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── Import page renderers ────────────────────────────────────────────────────
from trading.pages.dashboard     import render as _dashboard
from trading.pages.signals_page  import render as _signals
from trading.pages.news_page     import render as _news
from trading.pages.calendar_page import render as _calendar
from trading.pages.positions_page import render as _positions

# ── Explicit navigation (suppresses auto-discovery of pages/ folder) ─────────
pg = st.navigation(
    {
        "📊 Analyse": [
            st.Page(_dashboard,  title="Dashboard",          icon="🏠", url_path="dashboard"),
            st.Page(_signals,    title="Signaux détaillés",  icon="📡", url_path="signals"),
        ],
        "🌍 Marché": [
            st.Page(_news,       title="Actualités",         icon="📰", url_path="news"),
            st.Page(_calendar,   title="Calendrier macro",   icon="📅", url_path="calendar"),
        ],
        "💼 Trading": [
            st.Page(_positions,  title="Mes positions",      icon="💼", url_path="positions"),
        ],
    },
    position="sidebar",
)

# ── Sidebar header ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:16px 0 12px">
      <div style="font-size:34px">🎯</div>
      <div style="font-size:18px;font-weight:800;color:#fff;margin-top:4px">Trading Signals</div>
      <div style="font-size:12px;color:#444;margin-top:2px">🥇 Or &nbsp;·&nbsp; 🛢️ Brent &nbsp;·&nbsp; 📈 Nasdaq</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

pg.run()

# ── Sidebar footer (shown on every page) ────────────────────────────────────
with st.sidebar:
    st.divider()
    st.markdown("""
    <div style="font-size:11px;color:#333;padding:6px 0;line-height:1.7">
      <b style="color:#444">Stratégie</b><br>
      ⚡ Intraday : levier 10–30×, SL 0.5 ATR<br>
      📊 Swing : levier 2–8×, SL 1.5 ATR<br><br>
      <b style="color:#444">Score combiné</b><br>
      Technique 60% · News 25% · Macro 15%<br><br>
      <b style="color:#444">1 position à la fois</b><br>
      Renforçable via entrées multiples.
    </div>
    """, unsafe_allow_html=True)
