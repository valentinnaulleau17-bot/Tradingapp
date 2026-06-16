"""Dashboard — live prices, best signal, active position P&L, mini chart."""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from trading.config import ASSETS, SIGNAL_CONFIG
from trading.engine.market_data import get_current_prices, get_ohlcv
from trading.engine.signals import compute_all_signals, get_best_signal
from trading.engine.positions import get_active, live_pnl
from trading.engine.technical import _ema  # reuse helper for chart overlay


def _price_card(asset: str, data: dict, cfg: dict):
    if "error" in data:
        st.error(f"{cfg['icon']} {asset}: {data['error']}")
        return
    pct   = data.get("change_pct", 0)
    chg   = data.get("change", 0)
    price = data.get("price", 0)
    color = "#00E676" if pct >= 0 else "#FF1744"
    arrow = "▲" if pct >= 0 else "▼"
    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#0d1117,#1c1c2e);
        border:1.5px solid {cfg['color']};
        border-radius:14px; padding:18px; text-align:center;
        box-shadow:0 0 18px {cfg['color']}33;">
      <div style="font-size:30px">{cfg['icon']}</div>
      <div style="font-size:15px;font-weight:700;color:{cfg['color']};margin:4px 0">{asset}</div>
      <div style="font-size:28px;font-weight:800;color:#fff">{price:,.2f}</div>
      <div style="font-size:15px;color:{color};font-weight:600">
        {arrow} {abs(pct):.2f}%&nbsp;&nbsp;({chg:+.2f})
      </div>
      <div style="font-size:11px;color:#555;margin-top:4px">{cfg['unit']}</div>
    </div>
    """, unsafe_allow_html=True)


def _active_position_banner(pos: dict, current_price: float):
    pnl = live_pnl(current_price)
    if pnl is None:
        return
    lev_pnl  = pnl["leveraged_pnl_pct"]
    gross_pct = pnl["pnl_pct"]
    border    = "#00E676" if lev_pnl >= 0 else "#FF1744"
    sig_label = SIGNAL_CONFIG[pos["signal_type"]]["label"]
    sig_color = SIGNAL_CONFIG[pos["signal_type"]]["color"]
    dir_emoji = "📈" if pos["direction"] == "long" else "📉"

    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#0d1117,#161b22);
        border:2px solid {border};border-radius:16px;padding:20px;margin-bottom:16px;">
      <div style="font-size:12px;color:#888;margin-bottom:6px;letter-spacing:1px">▶ POSITION ACTIVE</div>
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
        <div>
          <span style="font-size:22px;font-weight:800;color:#fff">
            {dir_emoji} {pos['asset']} — {pos['direction'].upper()}
          </span>
          <span style="background:{sig_color};color:#000;border-radius:8px;
                       padding:3px 10px;margin-left:10px;font-size:11px;font-weight:700">
            {sig_label}
          </span>
        </div>
        <div style="text-align:right">
          <div style="font-size:30px;font-weight:800;color:{border}">
            {lev_pnl:+.2f}% (x{pos['leverage']})
          </div>
          <div style="font-size:13px;color:#666">P&L brut : {gross_pct:+.2f}%</div>
        </div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:18px;margin-top:14px;font-size:13px">
        <span style="color:#aaa">Prix moy. : <b style="color:#fff">{pos['average_price']:,.2f}</b></span>
        <span style="color:#aaa">Cours actuel : <b style="color:#fff">{current_price:,.2f}</b></span>
        <span style="color:#aaa">Entrées : <b style="color:#fff">{len(pos['entries'])}</b></span>
        <span style="color:#FF6B6B">Stop Loss : <b>{pos['stop_loss']:,.2f}</b></span>
        <span style="color:#00E676">Take Profit : <b>{pos['take_profit']:,.2f}</b></span>
        <span style="color:#aaa">Levier : <b style="color:#fff">x{pos['leverage']}</b></span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _signal_card(sig, is_best=False):
    cfg  = SIGNAL_CONFIG[sig.signal_type]
    border = "2.5px solid #FFD700" if is_best else f"1.5px solid {cfg['color']}"
    best_badge = '<span style="background:#FFD700;color:#000;border-radius:6px;padding:2px 8px;font-size:11px;font-weight:800;margin-right:6px">★ MEILLEUR</span>' if is_best else ""

    st.markdown(f"""
    <div style="background:#0d1117;border:{border};border-radius:14px;padding:18px;margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <div>
          {best_badge}
          <span style="font-size:17px;font-weight:700;color:#fff">
            {ASSETS[sig.asset]['icon']} {sig.asset}
          </span>
          <span style="background:{cfg['color']};color:#000;border-radius:6px;
                       padding:2px 8px;margin-left:8px;font-size:11px;font-weight:700">
            {cfg['emoji']} {cfg['label']}
          </span>
          <span style="color:{sig.direction_color};margin-left:10px;font-weight:700;font-size:15px">
            {sig.direction_label}
          </span>
        </div>
        <div style="display:flex;gap:18px;flex-wrap:wrap;align-items:center">
          <div style="text-align:center">
            <div style="font-size:10px;color:#666">CONFIANCE</div>
            <div style="font-size:17px;font-weight:700;color:{cfg['color']}">{sig.confidence*100:.0f}%</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:10px;color:#666">LEVIER</div>
            <div style="font-size:17px;font-weight:700;color:#fff">x{sig.leverage_suggested}</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:10px;color:#666">R/R</div>
            <div style="font-size:17px;font-weight:700;color:#fff">{sig.rr_ratio:.1f}</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:10px;color:#FF6B6B">STOP LOSS</div>
            <div style="font-size:15px;font-weight:700;color:#FF6B6B">{sig.stop_loss:,.2f}</div>
            <div style="font-size:10px;color:#555">-{sig.sl_pct:.1f}%</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:10px;color:#00E676">TAKE PROFIT</div>
            <div style="font-size:15px;font-weight:700;color:#00E676">{sig.take_profit:,.2f}</div>
            <div style="font-size:10px;color:#555">+{sig.tp_pct:.1f}%</div>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _candlestick_chart(sig):
    cfg    = SIGNAL_CONFIG[sig.signal_type]
    ticker = ASSETS[sig.asset]["ticker"]
    df     = get_ohlcv(ticker, cfg["fetch_period"], cfg["fetch_interval"])
    if df is None or df.empty:
        st.warning("Données graphique indisponibles.")
        return

    # Keep last N candles for readability
    df = df.tail(80)

    fig = make_subplots(
        rows=2, cols=1, row_heights=[0.75, 0.25],
        shared_xaxes=True, vertical_spacing=0.02,
    )
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        name="Prix",
        increasing_line_color="#00E676",
        increasing_fillcolor="#00E676",
        decreasing_line_color="#FF1744",
        decreasing_fillcolor="#FF1744",
    ), row=1, col=1)

    # EMA overlays
    import pandas as pd
    for n, color in [(21, "#FFC107"), (50, "#2196F3")]:
        if len(df) >= n:
            e = _ema(df["Close"], n)
            fig.add_trace(go.Scatter(
                x=df.index, y=e, name=f"EMA{n}",
                line=dict(color=color, width=1.2), opacity=0.8,
            ), row=1, col=1)

    # SL / TP / current price lines
    for val, color, label in [
        (sig.stop_loss,    "#FF6B6B", f"SL {sig.stop_loss:,.1f}"),
        (sig.take_profit,  "#00E676", f"TP {sig.take_profit:,.1f}"),
        (sig.current_price,"#FFFFFF", f"Prix {sig.current_price:,.1f}"),
    ]:
        fig.add_hline(y=val, line_color=color, line_dash="dash",
                      line_width=1.2,
                      annotation_text=label,
                      annotation_font_color=color,
                      row=1, col=1)

    # Volume
    colors = ["rgba(0,230,118,0.4)" if c >= o else "rgba(255,23,68,0.4)"
              for o, c in zip(df["Open"], df["Close"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        name="Volume", marker_color=colors,
    ), row=2, col=1)

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0d1117",
        font_color="white",
        xaxis_rangeslider_visible=False,
        height=480,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font_size=11),
        margin=dict(t=30, b=40, l=60, r=60),
    )
    fig.update_xaxes(gridcolor="#1a1a1a", zeroline=False)
    fig.update_yaxes(gridcolor="#1a1a1a", zeroline=False)
    st.plotly_chart(fig, use_container_width=True)


def render():
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=60_000, key="dash_refresh")
    except ImportError:
        pass

    st.markdown("""
    <h1 style="font-size:28px;margin-bottom:0">
    🎯 Trading Signals — Or · Brent · Nasdaq
    </h1>
    <p style="color:#555;font-size:13px;margin-top:4px">
    Données actualisées automatiquement toutes les 60 secondes.
    </p>
    """, unsafe_allow_html=True)

    # ── Live prices ──────────────────────────────────────────────────────────
    prices = get_current_prices()
    cols   = st.columns(3)
    for i, (asset, cfg) in enumerate(ASSETS.items()):
        with cols[i]:
            _price_card(asset, prices.get(asset, {"error": "N/A"}), cfg)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Active position ──────────────────────────────────────────────────────
    active = get_active()
    if active:
        cur = prices.get(active["asset"], {}).get("price", active["average_price"])
        _active_position_banner(active, cur)

    # ── Best signal ──────────────────────────────────────────────────────────
    st.markdown("### 🏆 Meilleur signal du moment")

    with st.spinner("Analyse technique + macro en cours…"):
        all_sigs = compute_all_signals()

    if not all_sigs:
        st.info(
            "Aucun signal suffisamment fort détecté. "
            "Les marchés sont en phase de consolidation ou les données sont temporairement indisponibles."
        )
    else:
        best = all_sigs[0]

        # Main signal card
        _signal_card(best, is_best=True)

        # Detail columns: summary + score gauge
        col_sum, col_gauge = st.columns([3, 2])

        with col_sum:
            st.markdown("**Résumé du signal**")
            st.code(best.summary, language=None)

        with col_gauge:
            # Confidence gauge
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number",
                value=best.confidence * 100,
                title={"text": "Confiance globale", "font": {"size": 14, "color": "white"}},
                gauge={
                    "axis": {"range": [0, 100], "tickcolor": "white"},
                    "bar":  {"color": SIGNAL_CONFIG[best.signal_type]["color"]},
                    "steps": [
                        {"range": [0, 55],  "color": "#111"},
                        {"range": [55, 70], "color": "#1a2a1a"},
                        {"range": [70, 100],"color": "#0d2a0d"},
                    ],
                },
                number={"suffix": "%", "font": {"color": "white"}},
            ))
            fig_g.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                height=220,
                margin=dict(t=40, b=0, l=20, r=20),
            )
            st.plotly_chart(fig_g, use_container_width=True)

            # Score breakdown bar chart
            labels = ["Technique", "Actualités", "Calendrier"]
            vals   = [best.technical_score, best.news_score, best.calendar_score]
            bar_colors = ["#00E676" if v >= 0 else "#FF1744" for v in vals]
            fig_b = go.Figure(go.Bar(
                x=labels, y=vals,
                marker_color=bar_colors,
                text=[f"{v:+.2f}" for v in vals],
                textposition="outside",
                textfont_color="white",
            ))
            fig_b.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#0d1117",
                font_color="white",
                height=180,
                margin=dict(t=10, b=30, l=10, r=10),
                yaxis=dict(range=[-1.1, 1.1], gridcolor="#1a1a1a"),
                xaxis=dict(gridcolor="#1a1a1a"),
                showlegend=False,
            )
            st.plotly_chart(fig_b, use_container_width=True)

        # Chart
        st.markdown(f"**📊 Graphique {best.asset} — {SIGNAL_CONFIG[best.signal_type]['label']}**")
        _candlestick_chart(best)

        # Other signals
        if len(all_sigs) > 1:
            with st.expander(f"Voir tous les signaux détectés ({len(all_sigs)} au total)"):
                for sig in all_sigs[1:]:
                    _signal_card(sig)
