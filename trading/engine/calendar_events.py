"""
Economic calendar engine.
Source: ForexFactory free JSON endpoint (no auth required).
Interprets event surprises (actual vs forecast) into directional impact on
Gold, Brent and Nasdaq.
"""
from __future__ import annotations
import re
import requests
import streamlit as st

from trading.config import CALENDAR_API_URL

# Which currencies matter for each asset
ASSET_CURRENCIES = {
    "Gold":   ["USD", "EUR"],
    "Brent":  ["USD", "EUR"],
    "Nasdaq": ["USD"],
}

# Impact matrix: event keyword → surprise direction → asset → (direction, explanation_FR)
IMPACT_MATRIX: dict[str, dict[str, dict[str, tuple[str, str]]]] = {
    "CPI": {
        "above": {
            "Gold":   ("long",  "Inflation > prévisions → demande d'or comme protection"),
            "Nasdaq": ("short", "Inflation > prévisions → Fed hawkish → taux plus hauts → valorisations comprimées"),
            "Brent":  ("long",  "Inflation → coûts en hausse, pression sur les matières premières"),
        },
        "below": {
            "Gold":   ("short", "Inflation < prévisions → moins besoin de valeur refuge"),
            "Nasdaq": ("long",  "Inflation maîtrisée → Fed dovish → taux en baisse → boost valorisations tech"),
            "Brent":  ("short", "Inflation basse → activité ralentie → demande pétrole modérée"),
        },
    },
    "PPI": {
        "above": {
            "Gold":   ("long",  "Pression inflationniste amont → or soutenu"),
            "Nasdaq": ("short", "Marges comprimées par coûts producteurs"),
        },
        "below": {
            "Gold":   ("short", "Pression producteurs faible → moins d'inflation anticipée"),
            "Nasdaq": ("long",  "Coûts producteurs maîtrisés → marges préservées"),
        },
    },
    "Non-Farm": {
        "above": {
            "Gold":   ("short", "Emploi solide → dollar fort → pression sur l'or"),
            "Nasdaq": ("long",  "Économie robuste → revenus et consommation en hausse"),
            "Brent":  ("long",  "Activité forte → demande énergie en hausse"),
        },
        "below": {
            "Gold":   ("long",  "Emploi décevant → dollar faible → or soutenu"),
            "Nasdaq": ("short", "Signaux de ralentissement économique"),
            "Brent":  ("short", "Ralentissement potentiel → demande pétrole réduite"),
        },
    },
    "NFP": {
        "above": {
            "Gold":   ("short", "NFP solide → dollar fort → pression sur l'or"),
            "Nasdaq": ("long",  "Marché du travail robuste"),
            "Brent":  ("long",  "Activité forte → demande énergie"),
        },
        "below": {
            "Gold":   ("long",  "NFP décevant → dollar faible → or haussier"),
            "Nasdaq": ("short", "Ralentissement du marché du travail"),
            "Brent":  ("short", "Ralentissement économique → demande pétrolière modérée"),
        },
    },
    "FOMC": {
        "above": {   # "above" = hawkish surprise (higher rate)
            "Gold":   ("short", "Taux plus élevés → dollar fort → pression sur l'or"),
            "Nasdaq": ("short", "Taux directeurs montés → valorisations discount"),
            "Brent":  ("short", "Resserrement monétaire → récession potentielle → pétrole baissier"),
        },
        "below": {   # "below" = dovish surprise (lower/unchanged rate)
            "Gold":   ("long",  "Fed dovish → dollar faible → or haussier"),
            "Nasdaq": ("long",  "Taux en baisse → taux d'actualisation réduit → valorisations tech"),
            "Brent":  ("long",  "Stimulus monétaire → activité économique soutenue"),
        },
    },
    "GDP": {
        "above": {
            "Nasdaq": ("long",  "Croissance > attentes → profit corporate en hausse"),
            "Brent":  ("long",  "PIB fort → demande énergie soutenue"),
            "Gold":   ("short", "Économie forte → moins de besoin de valeur refuge"),
        },
        "below": {
            "Nasdaq": ("short", "Croissance décevante → révision des profits à la baisse"),
            "Brent":  ("short", "PIB faible → demande pétrole réduite"),
            "Gold":   ("long",  "Craintes de récession → fuite vers l'or"),
        },
    },
    "EIA": {
        "above": {   # above = stocks > forecast (bearish crude)
            "Brent":  ("short", "Stocks pétrole supérieurs aux attentes → offre excédentaire"),
        },
        "below": {
            "Brent":  ("long",  "Stocks pétrole inférieurs aux attentes → tension sur l'offre"),
        },
    },
    "Crude": {
        "above": {
            "Brent":  ("short", "Hausse des inventaires bruts → excès d'offre"),
        },
        "below": {
            "Brent":  ("long",  "Baisse des inventaires bruts → demande soutenue"),
        },
    },
    "PMI": {
        "above": {
            "Nasdaq": ("long",  "PMI > 50 en hausse → expansion économique → bonnes nouvelles pour les actions"),
            "Brent":  ("long",  "Activité manufacturière forte → demande énergie"),
        },
        "below": {
            "Nasdaq": ("short", "PMI en baisse → activité contractée"),
            "Brent":  ("short", "Contraction industrielle → demande pétrole faible"),
        },
    },
    "ISM": {
        "above": {
            "Nasdaq": ("long",  "ISM > 50 → expansion services/manufacturing"),
            "Brent":  ("long",  "Activité soutenue → énergie demandée"),
        },
        "below": {
            "Nasdaq": ("short", "ISM en baisse → signaux de contraction"),
            "Brent":  ("short", "Activité réduite → moindre consommation d'énergie"),
        },
    },
    "OPEC": {
        "above": {   # above = production cut (bullish)
            "Brent":  ("long",  "Réduction de production OPEC → offre restreinte → pétrole haussier"),
        },
        "below": {   # below = production increase (bearish)
            "Brent":  ("short", "Augmentation production OPEC → surplus d'offre → pétrole baissier"),
        },
    },
}


def _parse_num(value: str | None) -> float | None:
    """Parse a value string like '2.3%', '-150K', '0.5M' to float."""
    if not value or str(value).strip() in ("", "-", "—", "N/A"):
        return None
    s = str(value).strip()
    mult = 1.0
    if s.endswith("K"):
        mult = 1_000
        s = s[:-1]
    elif s.endswith("M"):
        mult = 1_000_000
        s = s[:-1]
    elif s.endswith("B"):
        mult = 1_000_000_000
        s = s[:-1]
    s = s.replace("%", "").replace(",", "").strip()
    try:
        return float(s) * mult
    except ValueError:
        return None


@st.cache_data(ttl=1800)   # 30 min
def fetch_calendar() -> list[dict]:
    """Fetch this week's economic events from ForexFactory free endpoint."""
    try:
        resp = requests.get(CALENDAR_API_URL, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        events = []
        for ev in raw:
            events.append({
                "date":     ev.get("date", ""),
                "time":     ev.get("time", ""),
                "currency": ev.get("country", ""),
                "event":    ev.get("title", ""),
                "impact":   ev.get("impact", ""),
                "forecast": ev.get("forecast", ""),
                "previous": ev.get("previous", ""),
                "actual":   ev.get("actual", ""),
            })
        return events
    except Exception:
        return []


def get_asset_calendar(events: list[dict], asset: str) -> list[dict]:
    """Filter events that matter for *asset*."""
    currencies = ASSET_CURRENCIES.get(asset, ["USD"])
    relevant = []
    for ev in events:
        if ev.get("currency", "") not in currencies:
            continue
        if ev.get("impact", "") not in ("High", "3", "high", "Medium", "2", "medium"):
            continue
        # Match against IMPACT_MATRIX keys
        matched_key = None
        for key in IMPACT_MATRIX:
            if key.lower() in ev["event"].lower():
                matched_key = key
                break
        ev = dict(ev)
        ev["impact_key"] = matched_key
        relevant.append(ev)
    return relevant


def compute_calendar_score(events: list[dict], asset: str) -> tuple[float, list[dict]]:
    """
    Return (score, impact_list) for a given asset.
    score ∈ [-1, +1]: positive = bullish, negative = bearish.
    impact_list: list of dicts with direction + explanation.
    """
    relevant = get_asset_calendar(events, asset)
    impacts = []
    scores: list[float] = []

    for ev in relevant:
        key = ev.get("impact_key")
        actual_v   = _parse_num(ev.get("actual"))
        forecast_v = _parse_num(ev.get("forecast"))

        if actual_v is not None and forecast_v is not None and key:
            surprise = "above" if actual_v > forecast_v else "below"
            interp = IMPACT_MATRIX.get(key, {}).get(surprise, {}).get(asset)
            if interp:
                direction, explanation = interp
                score = 0.7 if direction == "long" else -0.7
                impacts.append({
                    "event":       ev["event"],
                    "actual":      ev["actual"],
                    "forecast":    ev["forecast"],
                    "surprise":    surprise,
                    "direction":   direction,
                    "explanation": explanation,
                    "status":      "published",
                    "time":        ev.get("time", ""),
                    "currency":    ev.get("currency", ""),
                    "score":       score,
                })
                scores.append(score)
        else:
            # Upcoming event — flag it
            impacts.append({
                "event":       ev["event"],
                "actual":      ev.get("actual", ""),
                "forecast":    ev.get("forecast", ""),
                "direction":   "pending",
                "explanation": "Résultat non encore publié — surveiller",
                "status":      "upcoming",
                "time":        ev.get("time", ""),
                "currency":    ev.get("currency", ""),
                "score":       0.0,
            })

    avg = sum(scores) / len(scores) if scores else 0.0
    return avg, impacts
