"""News page — RSS feed per asset with sentiment scores."""
import plotly.graph_objects as go
import streamlit as st

from trading.config import ASSETS
from trading.engine.news import fetch_all_news, filter_for_asset, aggregate_sentiment


def _sentiment_gauge(score: float, asset: str, color: str):
    pct   = (score + 1) / 2 * 100   # remap -1…+1 to 0…100
    label = "Très haussier" if score > 0.4 else \
            "Haussier"      if score > 0.1 else \
            "Neutre"        if score > -0.1 else \
            "Baissier"      if score > -0.4 else "Très baissier"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        title={"text": f"Sentiment {asset}", "font": {"size": 13, "color": "white"}},
        delta={"reference": 50, "valueformat": ".0f"},
        gauge={
            "axis": {"range": [0, 100], "tickvals": [0, 25, 50, 75, 100],
                     "ticktext": ["Très baissier", "Baissier", "Neutre", "Haussier", "Très haussier"],
                     "tickcolor": "white"},
            "bar":  {"color": color},
            "steps": [
                {"range": [0, 30],  "color": "#2a0d0d"},
                {"range": [30, 45], "color": "#1a1a0d"},
                {"range": [45, 55], "color": "#111"},
                {"range": [55, 70], "color": "#0d1a0d"},
                {"range": [70, 100],"color": "#0d2a0d"},
            ],
            "threshold": {"line": {"color": "white", "width": 2}, "value": pct},
        },
        number={"suffix": f" — {label}", "font": {"color": "white", "size": 12}},
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        height=200,
        margin=dict(t=40, b=10, l=30, r=30),
    )
    return fig


def _news_card(art: dict):
    score   = art.get("sentiment", 0.0)
    color   = "#00E676" if score > 0.1 else ("#FF1744" if score < -0.1 else "#aaa")
    label   = "📈 Haussier" if score > 0.1 else ("📉 Baissier" if score < -0.1 else "➖ Neutre")
    source  = art.get("source", "")
    pubdate = art.get("published", "")[:22]
    link    = art.get("link", "#")

    st.markdown(f"""
    <div style="background:#0d1117;border:1px solid #1a1a2e;border-radius:10px;
                padding:14px;margin-bottom:8px">
      <div style="display:flex;justify-content:space-between;align-items:start;gap:8px">
        <a href="{link}" target="_blank"
           style="font-size:14px;font-weight:600;color:#58a6ff;
                  text-decoration:none;flex:1;line-height:1.4">
          {art['title']}
        </a>
        <span style="color:{color};font-size:12px;white-space:nowrap;font-weight:600">
          {label}
        </span>
      </div>
      <div style="font-size:11px;color:#555;margin-top:6px">{source} · {pubdate}</div>
      <div style="font-size:12px;color:#888;margin-top:6px;line-height:1.5">
        {art.get('summary','')[:200]}…
      </div>
    </div>
    """, unsafe_allow_html=True)


def render():
    st.markdown("## 📰 Actualités & Sentiment de marché")

    with st.spinner("Chargement des flux d'actualités…"):
        all_articles = fetch_all_news()

    if not all_articles:
        st.error("Impossible de récupérer les actualités. Vérifiez votre connexion.")
        return

    # Overall sentiment summary
    st.markdown("### Sentiment global par actif")
    gauge_cols = st.columns(3)
    for i, (asset, cfg) in enumerate(ASSETS.items()):
        arts   = filter_for_asset(all_articles, asset)
        score  = aggregate_sentiment(arts)
        with gauge_cols[i]:
            st.plotly_chart(_sentiment_gauge(score, asset, cfg["color"]),
                            use_container_width=True)

    st.divider()

    # Per-asset news tabs
    tabs = st.tabs([f"{cfg['icon']} {asset}" for asset, cfg in ASSETS.items()])
    for tab, (asset, cfg) in zip(tabs, ASSETS.items()):
        with tab:
            arts = filter_for_asset(all_articles, asset)
            if not arts:
                st.info(f"Aucune actualité récente pour {asset}.")
                continue

            score = aggregate_sentiment(arts)
            # Sentiment banner
            s_color = "#00E676" if score > 0.1 else ("#FF1744" if score < -0.1 else "#aaa")
            s_label = "HAUSSIER" if score > 0.1 else ("BAISSIER" if score < -0.1 else "NEUTRE")
            st.markdown(f"""
            <div style="background:#0d1117;border:1px solid {s_color};
                        border-radius:10px;padding:12px;margin-bottom:16px;
                        display:flex;justify-content:space-between;align-items:center">
              <span style="color:#aaa;font-size:13px">
                Sentiment agrégé ({len(arts)} articles)
              </span>
              <span style="color:{s_color};font-weight:800;font-size:18px">
                {s_label} ({score:+.2f})
              </span>
            </div>
            """, unsafe_allow_html=True)

            # Sort by sentiment extremity
            arts_sorted = sorted(arts, key=lambda a: abs(a.get("sentiment", 0)), reverse=True)
            for art in arts_sorted:
                _news_card(art)
