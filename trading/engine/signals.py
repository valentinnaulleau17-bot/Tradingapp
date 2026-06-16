"""
Signal aggregation engine.
Combines technical, news sentiment and calendar scores into ranked TradingSignals.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

import streamlit as st

from trading.config import ASSETS, SIGNAL_CONFIG, MIN_CONFIDENCE, WEIGHTS
from trading.engine.market_data import get_ohlcv, get_current_prices
from trading.engine.technical import analyze
from trading.engine.news import fetch_all_news, filter_for_asset, aggregate_sentiment
from trading.engine.calendar_events import fetch_calendar, compute_calendar_score


@dataclass
class TradingSignal:
    asset: str
    signal_type: str                        # "intraday" | "swing"
    direction: Literal["long", "short"]
    confidence: float                       # 0…1
    current_price: float
    stop_loss: float
    take_profit: float
    rr_ratio: float
    leverage_suggested: int
    atr: float
    sl_pct: float                           # SL distance as % of price
    tp_pct: float
    technical_score: float
    news_score: float
    calendar_score: float
    combined_score: float
    tech_indicators: dict = field(default_factory=dict)
    news_items: list = field(default_factory=list)
    calendar_impacts: list = field(default_factory=list)
    summary: str = ""

    @property
    def direction_label(self):
        return "LONG ▲" if self.direction == "long" else "SHORT ▼"

    @property
    def direction_color(self):
        return "#00E676" if self.direction == "long" else "#FF1744"


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _suggest_leverage(sl_pct: float, lev_min: int, lev_max: int) -> int:
    # Target 1 % account risk per trade → leverage = 1% / SL%
    if sl_pct <= 0:
        return lev_min
    raw = int(1.0 / sl_pct * 100)
    return _clamp(raw, lev_min, lev_max)


def _build_summary(asset: str, direction: str, sig_type: str,
                   indicators: dict, news: list, cal: list,
                   confidence: float) -> str:
    dir_fr = "LONG (achat)" if direction == "long" else "SHORT (vente)"
    type_fr = "Intraday" if sig_type == "intraday" else "Swing multi-jours"
    lines = [
        f"Signal {dir_fr} — {asset} ({type_fr}) | Confiance : {confidence*100:.0f}%",
        "",
    ]

    aligned_tech = [(k, v) for k, v in indicators.items() if v[0] == direction]
    if aligned_tech:
        lines.append("Signaux techniques :")
        for _, (_, desc, _) in aligned_tech[:4]:
            lines.append(f"  • {desc}")

    pub_cal = [c for c in cal if c.get("status") == "published" and c.get("direction") == direction]
    if pub_cal:
        lines.append("")
        lines.append("Catalyseurs macro récents :")
        for c in pub_cal[:3]:
            lines.append(f"  • {c['explanation']}")

    upcom = [c for c in cal if c.get("status") == "upcoming"]
    if upcom:
        lines.append("")
        lines.append("Évènements à surveiller cette semaine :")
        for c in upcom[:2]:
            time_str = f" ({c['time']})" if c.get("time") else ""
            lines.append(f"  ⏰ {c['event']}{time_str} — {c['explanation']}")

    if news:
        lines.append("")
        lines.append("Actualités récentes :")
        for n in news[:3]:
            lines.append(f"  • {n['title'][:110]}")

    return "\n".join(lines)


@st.cache_data(ttl=300)   # recompute every 5 min
def compute_all_signals() -> list[TradingSignal]:
    articles  = fetch_all_news()
    calendar  = fetch_calendar()

    all_sigs: list[TradingSignal] = []

    for asset, cfg in ASSETS.items():
        ticker = cfg["ticker"]
        asset_news = filter_for_asset(articles, asset)
        news_score = aggregate_sentiment(asset_news)
        cal_score, cal_impacts = compute_calendar_score(calendar, asset)

        for sig_type, sig_cfg in SIGNAL_CONFIG.items():
            df = get_ohlcv(ticker, sig_cfg["fetch_period"], sig_cfg["fetch_interval"])
            if df is None or len(df) < 20:
                continue

            tech = analyze(df, sig_cfg["atr_sl_mult"], sig_cfg["atr_tp_mult"])
            if tech is None or tech.direction == "neutral":
                continue

            combined = (
                WEIGHTS["technical"] * tech.score
                + WEIGHTS["news"]     * news_score
                + WEIGHTS["calendar"] * cal_score
            )
            confidence = min(abs(combined), 1.0)

            if confidence < MIN_CONFIDENCE:
                continue

            direction = "long" if combined > 0 else "short"
            cur = tech.current_price
            atr = tech.atr

            if direction == "long":
                sl = cur - sig_cfg["atr_sl_mult"] * atr
                tp = cur + sig_cfg["atr_tp_mult"] * atr
            else:
                sl = cur + sig_cfg["atr_sl_mult"] * atr
                tp = cur - sig_cfg["atr_tp_mult"] * atr

            sl_pct = abs(sl - cur) / cur * 100
            tp_pct = abs(tp - cur) / cur * 100
            rr     = tp_pct / sl_pct if sl_pct > 0 else 1.0
            lev    = _suggest_leverage(sl_pct, sig_cfg["leverage_min"], sig_cfg["leverage_max"])

            summary = _build_summary(asset, direction, sig_type,
                                     tech.indicators, asset_news, cal_impacts, confidence)

            all_sigs.append(TradingSignal(
                asset=asset,
                signal_type=sig_type,
                direction=direction,
                confidence=confidence,
                current_price=cur,
                stop_loss=sl,
                take_profit=tp,
                rr_ratio=rr,
                leverage_suggested=lev,
                atr=atr,
                sl_pct=sl_pct,
                tp_pct=tp_pct,
                technical_score=tech.score,
                news_score=news_score,
                calendar_score=cal_score,
                combined_score=combined,
                tech_indicators=tech.indicators,
                news_items=asset_news[:5],
                calendar_impacts=cal_impacts,
                summary=summary,
            ))

    all_sigs.sort(key=lambda s: s.confidence, reverse=True)
    return all_sigs


def get_best_signal() -> TradingSignal | None:
    sigs = compute_all_signals()
    return sigs[0] if sigs else None
