"""Positions page — open/add/close positions, P&L history."""
import plotly.graph_objects as go
import streamlit as st

from trading.config import ASSETS, SIGNAL_CONFIG
from trading.engine.positions import (
    get_active, get_history, open_position,
    add_entry, close_position, update_barriers, live_pnl,
)
from trading.engine.market_data import get_current_prices


# ── helpers ───────────────────────────────────────────────────────────────────

def _pnl_color(val: float) -> str:
    return "#00E676" if val >= 0 else "#FF1744"


def _format_pct(val: float) -> str:
    return f"{val:+.2f}%"


def _entry_table(entries: list[dict]):
    rows = "".join(
        f"""<tr>
          <td style="padding:6px 10px;color:#aaa;font-size:12px">#{i+1}</td>
          <td style="padding:6px 10px;color:#fff;font-size:13px">{e['price']:,.2f}</td>
          <td style="padding:6px 10px;color:#aaa;font-size:12px">{e['quantity']}</td>
          <td style="padding:6px 10px;color:#aaa;font-size:12px">{str(e['date'])[:16]}</td>
        </tr>"""
        for i, e in enumerate(entries)
    )
    st.markdown(f"""
    <table style="width:100%;border-collapse:collapse;background:#0d1117;
                  border-radius:8px;overflow:hidden;margin-bottom:14px">
      <thead>
        <tr style="background:#161b22">
          <th style="padding:7px 10px;color:#888;font-size:11px;text-align:left">#</th>
          <th style="padding:7px 10px;color:#888;font-size:11px;text-align:left">Prix d'entrée</th>
          <th style="padding:7px 10px;color:#888;font-size:11px;text-align:left">Qté</th>
          <th style="padding:7px 10px;color:#888;font-size:11px;text-align:left">Date</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """, unsafe_allow_html=True)


# ── Active position panel ─────────────────────────────────────────────────────

def _render_active(pos: dict, prices: dict):
    cur   = prices.get(pos["asset"], {}).get("price", pos["average_price"])
    pnl   = live_pnl(cur) or {}
    lev_p = pnl.get("leveraged_pnl_pct", 0)
    raw_p = pnl.get("pnl_pct", 0)
    border = _pnl_color(lev_p)

    dir_emoji = "📈" if pos["direction"] == "long" else "📉"
    sig_label = SIGNAL_CONFIG[pos["signal_type"]]["label"]
    sig_color = SIGNAL_CONFIG[pos["signal_type"]]["color"]

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d1117,#161b22);
                border:2px solid {border};border-radius:16px;padding:20px;margin-bottom:20px">
      <div style="font-size:11px;color:#555;letter-spacing:1px;margin-bottom:8px">
        POSITION ACTIVE
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
        <div>
          <span style="font-size:24px;font-weight:800;color:#fff">
            {dir_emoji} {pos['asset']} — {pos['direction'].upper()}
          </span>
          <span style="background:{sig_color};color:#000;border-radius:8px;
                       padding:3px 10px;margin-left:10px;font-size:11px;font-weight:700">
            {sig_label}
          </span>
        </div>
        <div style="text-align:right">
          <div style="font-size:32px;font-weight:800;color:{border}">
            {_format_pct(lev_p)} (x{pos['leverage']})
          </div>
          <div style="font-size:13px;color:#666">P&L brut : {_format_pct(raw_p)}</div>
        </div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:18px;margin-top:14px;font-size:13px">
        <span style="color:#aaa">Prix moyen :
          <b style="color:#fff">{pos['average_price']:,.2f}</b>
        </span>
        <span style="color:#aaa">Cours actuel :
          <b style="color:#fff">{cur:,.2f}</b>
        </span>
        <span style="color:#FF6B6B">Stop Loss :
          <b>{pos['stop_loss']:,.2f}</b>
        </span>
        <span style="color:#00E676">Take Profit :
          <b>{pos['take_profit']:,.2f}</b>
        </span>
        <span style="color:#aaa">Levier :
          <b style="color:#fff">x{pos['leverage']}</b>
        </span>
        <span style="color:#aaa">Entrées :
          <b style="color:#fff">{len(pos['entries'])}</b>
        </span>
      </div>
      {('<div style="font-size:12px;color:#666;margin-top:8px">Note : ' + pos['note'] + '</div>') if pos.get('note') else ''}
    </div>
    """, unsafe_allow_html=True)

    # Entry table
    st.markdown("**Détail des entrées**")
    _entry_table(pos["entries"])

    # ── Actions ──
    st.markdown("**Actions sur la position**")
    tab_add, tab_close, tab_barriers = st.tabs(["➕ Ajouter une entrée", "✅ Fermer la position", "🔧 Modifier barrières"])

    with tab_add:
        with st.form("form_add_entry"):
            c1, c2 = st.columns(2)
            price = c1.number_input("Prix d'entrée", min_value=0.0, value=float(cur), format="%.2f")
            qty   = c2.number_input("Quantité", min_value=0.01, value=1.0, step=0.01)
            if st.form_submit_button("Ajouter l'entrée", type="primary"):
                try:
                    add_entry(price, qty)
                    st.success(f"Entrée ajoutée à {price:,.2f}. Nouveau prix moyen calculé.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab_close:
        with st.form("form_close"):
            exit_price = st.number_input(
                "Prix de sortie (sous-jacent)", min_value=0.0,
                value=float(cur), format="%.2f",
            )
            if st.form_submit_button("🔴 Fermer la position", type="primary"):
                try:
                    closed = close_position(exit_price)
                    lp = closed.get("leveraged_pnl_pct", 0)
                    if lp >= 0:
                        st.success(f"Position fermée ✅ | P&L x{pos['leverage']} : {_format_pct(lp)} | Brut : {_format_pct(closed.get('pnl_pct',0))}")
                    else:
                        st.warning(f"Position fermée | P&L x{pos['leverage']} : {_format_pct(lp)} | Brut : {_format_pct(closed.get('pnl_pct',0))}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab_barriers:
        with st.form("form_barriers"):
            c1, c2 = st.columns(2)
            new_sl = c1.number_input("Nouveau Stop Loss", min_value=0.0,
                                     value=float(pos["stop_loss"]), format="%.2f")
            new_tp = c2.number_input("Nouveau Take Profit", min_value=0.0,
                                     value=float(pos["take_profit"]), format="%.2f")
            if st.form_submit_button("Mettre à jour les barrières"):
                try:
                    update_barriers(new_sl, new_tp)
                    st.success("Barrières mises à jour.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


# ── Open new position panel ───────────────────────────────────────────────────

def _render_open_form(prices: dict):
    st.markdown("### ➕ Ouvrir une nouvelle position")
    with st.form("form_open"):
        c1, c2, c3 = st.columns(3)
        asset     = c1.selectbox("Actif", list(ASSETS.keys()))
        direction = c2.selectbox("Direction", ["long", "short"],
                                 format_func=lambda x: "LONG (achat)" if x == "long" else "SHORT (vente)")
        sig_type  = c3.selectbox("Type de signal", ["intraday", "swing"],
                                  format_func=lambda x: SIGNAL_CONFIG[x]["label"])

        cur = prices.get(asset, {}).get("price", 0.0)
        c4, c5 = st.columns(2)
        entry_price = c4.number_input("Prix d'entrée", min_value=0.0,
                                      value=float(cur), format="%.2f")
        quantity    = c5.number_input("Quantité", min_value=0.01, value=1.0, step=0.01)

        c6, c7, c8 = st.columns(3)
        leverage = c6.number_input("Levier (x)", min_value=1, max_value=100,
                                   value=10 if sig_type == "intraday" else 5)
        stop_loss   = c7.number_input("Stop Loss", min_value=0.0,
                                      value=float(cur * 0.99), format="%.2f")
        take_profit = c8.number_input("Take Profit", min_value=0.0,
                                      value=float(cur * 1.02), format="%.2f")
        note = st.text_input("Note (optionnel)", placeholder="ex: signal MACD + NFP haussier")

        if st.form_submit_button("🚀 Ouvrir la position", type="primary"):
            try:
                open_position(
                    asset=asset,
                    direction=direction,
                    signal_type=sig_type,
                    entry_price=entry_price,
                    quantity=quantity,
                    leverage=leverage,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    note=note,
                )
                st.success(f"Position {direction.upper()} {asset} ouverte à {entry_price:,.2f} (x{leverage}).")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


# ── History panel ─────────────────────────────────────────────────────────────

def _render_history(history: list[dict]):
    if not history:
        return
    st.markdown("### 📜 Historique des positions")

    # Summary stats
    total_lev_pnl = sum(h.get("leveraged_pnl_pct", 0) for h in history)
    wins  = sum(1 for h in history if h.get("leveraged_pnl_pct", 0) >= 0)
    loses = len(history) - wins
    wr    = wins / len(history) * 100 if history else 0

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Trades", len(history))
    s2.metric("Taux de réussite", f"{wr:.0f}%")
    s3.metric("P&L total (leviérisé)", f"{total_lev_pnl:+.2f}%", delta_color="normal")
    s4.metric("Gain / Perte", f"{wins}W / {loses}L")

    # Equity curve (cumulative leveraged PnL)
    if len(history) > 1:
        closed_sorted = sorted(history, key=lambda h: str(h.get("opened_at", "")))
        cum_pnl = []
        cum = 0
        for h in closed_sorted:
            cum += h.get("leveraged_pnl_pct", 0)
            cum_pnl.append(cum)

        fig = go.Figure(go.Scatter(
            y=cum_pnl,
            mode="lines+markers",
            line=dict(color="#4ECDC4", width=2),
            fill="tozeroy",
            fillcolor="#4ECDC422",
            name="P&L cumulé (leviérisé)",
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0d1117",
            font_color="white",
            height=200,
            margin=dict(t=10, b=40, l=60, r=10),
            yaxis=dict(gridcolor="#1a1a1a", title="P&L %"),
            xaxis=dict(gridcolor="#1a1a1a", title="N° trade"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    for h in history:
        lp = h.get("leveraged_pnl_pct", 0)
        rp = h.get("pnl_pct", 0)
        color  = _pnl_color(lp)
        status = "✅ Gain" if lp >= 0 else "❌ Perte"
        dir_emoji = "📈" if h.get("direction") == "long" else "📉"

        st.markdown(f"""
        <div style="background:#0d1117;border:1px solid {'#1a2a1a' if lp>=0 else '#2a1a1a'};
                    border-radius:10px;padding:14px;margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
            <div>
              <span style="font-size:14px;font-weight:700;color:#fff">
                {dir_emoji} {h.get('asset','')} — {h.get('direction','').upper()}
              </span>
              <span style="color:#555;font-size:12px;margin-left:8px">
                {SIGNAL_CONFIG.get(h.get('signal_type','swing'),{}).get('label','')}
              </span>
            </div>
            <div style="display:flex;gap:16px;font-size:13px;align-items:center;flex-wrap:wrap">
              <span style="color:#aaa">
                Entrée moy. : <b style="color:#fff">{h.get('average_price',0):,.2f}</b>
              </span>
              <span style="color:#aaa">
                Sortie : <b style="color:#fff">{h.get('exit_price',0):,.2f}</b>
              </span>
              <span style="color:#aaa">
                Levier : <b style="color:#fff">x{h.get('leverage',1)}</b>
              </span>
              <span style="font-weight:700;font-size:16px;color:{color}">
                {status} {_format_pct(lp)}
                <span style="font-size:11px;color:#555"> (brut {_format_pct(rp)})</span>
              </span>
            </div>
          </div>
          <div style="font-size:11px;color:#444;margin-top:6px">
            Ouverture : {str(h.get('opened_at',''))[:16]} ·
            Fermeture : {str(h.get('closed_at',''))[:16]} ·
            {len(h.get('entries',[]))} entrée(s)
            {(' · Note : ' + h['note']) if h.get('note') else ''}
          </div>
        </div>
        """, unsafe_allow_html=True)


# ── Main render ───────────────────────────────────────────────────────────────

def render():
    st.markdown("## 💼 Gestion de position")

    prices  = get_current_prices()
    active  = get_active()
    history = get_history()

    if active:
        _render_active(active, prices)
        st.divider()
    else:
        st.info("Aucune position ouverte actuellement.")
        _render_open_form(prices)
        st.divider()

    _render_history(history)
