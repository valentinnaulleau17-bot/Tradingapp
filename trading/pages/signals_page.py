"""Signals page — deep breakdown of every detected signal."""
import plotly.graph_objects as go
import streamlit as st

from trading.config import ASSETS, SIGNAL_CONFIG
from trading.engine.signals import compute_all_signals


def _indicator_table(indicators: dict, direction: str):
    rows = []
    for name, (dir_, desc, score) in indicators.items():
        aligned = "✅" if dir_ == direction else ("⚪" if dir_ == "neutral" else "❌")
        color   = "#00E676" if score > 0 else ("#FF1744" if score < 0 else "#aaa")
        rows.append(f"""
        <tr>
          <td style="padding:6px 10px;color:#aaa;font-size:12px">{name}</td>
          <td style="padding:6px 10px;font-size:12px;color:#fff">{desc}</td>
          <td style="padding:6px 10px;text-align:center">{aligned}</td>
          <td style="padding:6px 10px;text-align:center;color:{color};font-weight:700">{score:+.2f}</td>
        </tr>
        """)
    table = "".join(rows)
    st.markdown(f"""
    <table style="width:100%;border-collapse:collapse;background:#0d1117;border-radius:10px;overflow:hidden">
      <thead>
        <tr style="background:#161b22">
          <th style="padding:8px 10px;color:#888;font-size:11px;text-align:left">Indicateur</th>
          <th style="padding:8px 10px;color:#888;font-size:11px;text-align:left">Description</th>
          <th style="padding:8px 10px;color:#888;font-size:11px;text-align:center">Aligné</th>
          <th style="padding:8px 10px;color:#888;font-size:11px;text-align:center">Score</th>
        </tr>
      </thead>
      <tbody>{table}</tbody>
    </table>
    """, unsafe_allow_html=True)


def render():
    st.markdown("## 📡 Analyse détaillée des signaux")

    with st.spinner("Calcul des signaux en cours…"):
        all_sigs = compute_all_signals()

    if not all_sigs:
        st.info("Aucun signal détecté. Marché en consolidation.")
        return

    # Asset / signal type filter
    col_a, col_b = st.columns(2)
    with col_a:
        asset_filter = st.multiselect(
            "Filtrer par actif",
            list(ASSETS.keys()),
            default=list(ASSETS.keys()),
        )
    with col_b:
        type_filter = st.multiselect(
            "Filtrer par type",
            ["intraday", "swing"],
            default=["intraday", "swing"],
            format_func=lambda x: SIGNAL_CONFIG[x]["label"],
        )

    sigs = [s for s in all_sigs if s.asset in asset_filter and s.signal_type in type_filter]

    if not sigs:
        st.warning("Aucun signal correspond aux filtres sélectionnés.")
        return

    for i, sig in enumerate(sigs):
        cfg        = SIGNAL_CONFIG[sig.signal_type]
        asset_cfg  = ASSETS[sig.asset]
        badge      = "🥇 Meilleur signal" if i == 0 else f"#{i+1}"

        with st.expander(
            f"{badge} — {asset_cfg['icon']} {sig.asset} | "
            f"{cfg['emoji']} {cfg['label']} | "
            f"{'LONG ▲' if sig.direction=='long' else 'SHORT ▼'} | "
            f"Confiance {sig.confidence*100:.0f}%",
            expanded=(i == 0),
        ):
            # ── Key metrics ──────────────────────────────────────────────
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Cours", f"{sig.current_price:,.2f}")
            m2.metric("Stop Loss", f"{sig.stop_loss:,.2f}", f"-{sig.sl_pct:.1f}%", delta_color="inverse")
            m3.metric("Take Profit", f"{sig.take_profit:,.2f}", f"+{sig.tp_pct:.1f}%")
            m4.metric("R/R", f"{sig.rr_ratio:.1f}x")
            m5.metric("Levier suggéré", f"x{sig.leverage_suggested}")
            m6.metric("ATR", f"{sig.atr:,.2f}")

            st.markdown("<br>", unsafe_allow_html=True)

            col_l, col_r = st.columns([3, 2])

            with col_l:
                # ── Score breakdown ─────────────────────────────────────
                st.markdown("**Décomposition du score combiné**")
                labels = ["Technique (60%)", "Actualités (25%)", "Calendrier (15%)", "Combiné"]
                vals   = [
                    sig.technical_score * 0.60,
                    sig.news_score      * 0.25,
                    sig.calendar_score  * 0.15,
                    sig.combined_score,
                ]
                raw_vals  = [sig.technical_score, sig.news_score, sig.calendar_score, sig.combined_score]
                bar_cols  = ["#00E676" if v >= 0 else "#FF1744" for v in vals]
                fig = go.Figure(go.Bar(
                    y=labels, x=vals,
                    orientation="h",
                    marker_color=bar_cols,
                    text=[f"{v:+.3f}" for v in raw_vals],
                    textposition="outside",
                    textfont_color="white",
                ))
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="#0d1117",
                    font_color="white",
                    height=200,
                    margin=dict(t=10, b=10, l=10, r=60),
                    xaxis=dict(range=[-0.7, 0.7], gridcolor="#1a1a1a", zeroline=True,
                               zerolinecolor="#333"),
                    yaxis=dict(gridcolor="#1a1a1a"),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

                # ── Technical indicators ────────────────────────────────
                st.markdown("**Indicateurs techniques**")
                _indicator_table(sig.tech_indicators, sig.direction)

            with col_r:
                # ── Radar chart of component scores ─────────────────────
                cats   = ["RSI", "MACD", "EMA", "Bollinger", "Stoch"]
                # Extract per-indicator scores if present
                def _get(key, default=0.0):
                    v = sig.tech_indicators.get(key)
                    return v[2] if v else default

                radar_vals = [
                    _get("rsi"),
                    _get("macd"),
                    _get("ema_align"),
                    _get("bbands"),
                    _get("stoch"),
                ]
                radar_vals_closed = radar_vals + [radar_vals[0]]
                cats_closed       = cats + [cats[0]]

                fig_r = go.Figure(go.Scatterpolar(
                    r=[abs(v) for v in radar_vals_closed],
                    theta=cats_closed,
                    fill="toself",
                    fillcolor=f"{cfg['color']}44",
                    line_color=cfg["color"],
                ))
                fig_r.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    polar=dict(
                        bgcolor="#0d1117",
                        angularaxis=dict(color="white"),
                        radialaxis=dict(range=[0, 1], color="white", gridcolor="#222"),
                    ),
                    font_color="white",
                    height=250,
                    margin=dict(t=20, b=20, l=20, r=20),
                    showlegend=False,
                )
                st.plotly_chart(fig_r, use_container_width=True)

                # ── Summary ─────────────────────────────────────────────
                st.markdown("**Résumé narratif**")
                st.code(sig.summary, language=None)
