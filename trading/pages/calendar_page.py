"""Economic calendar page — this week's events with predicted impact on our 3 assets."""
import streamlit as st

from trading.config import ASSETS
from trading.engine.calendar_events import fetch_calendar, get_asset_calendar, compute_calendar_score


_IMPACT_EMOJI = {
    "High": "🔴",
    "3":    "🔴",
    "Medium": "🟡",
    "2":    "🟡",
    "Low":  "🟢",
    "1":    "🟢",
}


def _event_impact_badge(direction: str) -> str:
    if direction == "long":
        return '<span style="background:#00E676;color:#000;border-radius:5px;padding:1px 7px;font-size:11px;font-weight:700">▲ Haussier</span>'
    if direction == "short":
        return '<span style="background:#FF1744;color:#fff;border-radius:5px;padding:1px 7px;font-size:11px;font-weight:700">▼ Baissier</span>'
    return '<span style="background:#333;color:#aaa;border-radius:5px;padding:1px 7px;font-size:11px">⏳ En attente</span>'


def render():
    st.markdown("## 📅 Calendrier économique & Impact prévu")
    st.markdown(
        "Source : ForexFactory (semaine en cours). "
        "Les impacts sont estimés selon la direction de la surprise "
        "(résultat vs consensus)."
    )

    with st.spinner("Chargement du calendrier…"):
        events = fetch_calendar()

    if not events:
        st.warning(
            "Impossible de charger le calendrier ForexFactory. "
            "Vérifiez votre connexion internet."
        )
        return

    # Filter high + medium impact USD/EUR events
    relevant = [e for e in events
                if e.get("impact") in ("High", "3", "Medium", "2")
                and e.get("currency") in ("USD", "EUR", "GBP")]

    if not relevant:
        st.info("Aucun événement à fort impact cette semaine.")
        return

    # ── Summary scores ───────────────────────────────────────────────────────
    st.markdown("### Bilan macro de la semaine par actif")
    score_cols = st.columns(3)
    for col, (asset, cfg) in zip(score_cols, ASSETS.items()):
        score, _ = compute_calendar_score(events, asset)
        direction = "Haussier" if score > 0.1 else ("Baissier" if score < -0.1 else "Neutre")
        color     = "#00E676" if score > 0.1 else ("#FF1744" if score < -0.1 else "#aaa")
        col.markdown(f"""
        <div style="background:#0d1117;border:1.5px solid {cfg['color']};
                    border-radius:12px;padding:16px;text-align:center">
          <div style="font-size:26px">{cfg['icon']}</div>
          <div style="font-size:15px;font-weight:700;color:{cfg['color']}">{asset}</div>
          <div style="font-size:22px;font-weight:800;color:{color}">{direction}</div>
          <div style="font-size:13px;color:#555">Score macro : {score:+.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ── Event table ──────────────────────────────────────────────────────────
    st.markdown("### Évènements détaillés")

    for ev in relevant:
        impact_emoji = _IMPACT_EMOJI.get(ev.get("impact", ""), "⚪")
        actual_str   = ev.get("actual", "") or ""
        fc_str       = ev.get("forecast", "") or ""
        prev_str     = ev.get("previous", "") or ""
        published    = bool(actual_str and actual_str not in ("", "-", "—"))

        # Determine asset impacts for this event
        asset_badges = []
        for asset, _ in ASSETS.items():
            _, impacts = compute_calendar_score([ev], asset)
            pub = [i for i in impacts if i["status"] == "published"]
            if pub:
                asset_badges.append(
                    f"{ASSETS[asset]['icon']} {_event_impact_badge(pub[0]['direction'])}"
                    f" <span style='font-size:11px;color:#aaa'>{pub[0]['explanation'][:80]}</span>"
                )

        badges_html = "<br>".join(asset_badges) if asset_badges else \
                      "<span style='color:#555;font-size:11px'>Impact non encore déterminé</span>"

        status_html = (
            f'<span style="background:#1a2a1a;color:#00E676;border-radius:5px;'
            f'padding:2px 7px;font-size:10px">✅ Publié</span>'
            if published else
            f'<span style="background:#2a2a1a;color:#FFC107;border-radius:5px;'
            f'padding:2px 7px;font-size:10px">⏳ À venir</span>'
        )

        st.markdown(f"""
        <div style="background:#0d1117;border:1px solid #1a1a2e;
                    border-radius:10px;padding:16px;margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:start;flex-wrap:wrap;gap:8px">
            <div>
              <span style="font-size:15px;font-weight:700;color:#fff">
                {impact_emoji} {ev.get('event', '')}
              </span>
              <span style="color:#555;font-size:12px;margin-left:8px">
                {ev.get('currency', '')} · {ev.get('date', '')} {ev.get('time', '')}
              </span>
              &nbsp;{status_html}
            </div>
            <div style="display:flex;gap:16px;font-size:13px">
              <span style="color:#aaa">Précédent : <b style="color:#fff">{prev_str or '—'}</b></span>
              <span style="color:#aaa">Prévision : <b style="color:#FFC107">{fc_str or '—'}</b></span>
              <span style="color:#aaa">Réel : <b style="color:{'#00E676' if published else '#555'}">
                {actual_str or '—'}
              </b></span>
            </div>
          </div>
          <div style="margin-top:10px;border-top:1px solid #1a1a1a;padding-top:10px">
            {badges_html}
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Upcoming high-impact events ──────────────────────────────────────────
    upcoming = [e for e in relevant
                if not (e.get("actual", "") and e["actual"] not in ("", "-", "—"))]
    if upcoming:
        st.markdown("### ⏰ Prochains évènements à surveiller")
        for ev in upcoming[:5]:
            impact_emoji = _IMPACT_EMOJI.get(ev.get("impact", ""), "⚪")
            # Show which assets will be affected
            affected = []
            for asset, cfg in ASSETS.items():
                rel = get_asset_calendar([ev], asset)
                if rel:
                    affected.append(f"{cfg['icon']} {asset}")
            affected_str = " · ".join(affected) if affected else "—"

            st.markdown(f"""
            <div style="background:#161b22;border-left:3px solid #FFC107;
                        border-radius:0 10px 10px 0;padding:12px;margin-bottom:8px">
              <b style="color:#fff">{impact_emoji} {ev.get('event', '')}</b>
              <span style="color:#555;font-size:12px;margin-left:8px">
                {ev.get('currency', '')} · {ev.get('date', '')} {ev.get('time', '')}
              </span>
              <br>
              <span style="font-size:12px;color:#aaa">Prévision :
                <b style="color:#FFC107">{ev.get('forecast', '—') or '—'}</b>
              </span>
              <span style="font-size:12px;color:#aaa;margin-left:12px">
                Actifs concernés : {affected_str}
              </span>
            </div>
            """, unsafe_allow_html=True)
