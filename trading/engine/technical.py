"""
Technical analysis engine — pure pandas/numpy, no TA-Lib dependency.
Returns structured signals with direction, score, barriers and indicator breakdown.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd


# ── helpers ──────────────────────────────────────────────────────────────────

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    gain = d.clip(lower=0).rolling(n).mean()
    loss = (-d).clip(lower=0).rolling(n).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _macd(s: pd.Series, fast=12, slow=26, sig=9):
    m = _ema(s, fast) - _ema(s, slow)
    sl = _ema(m, sig)
    return m, sl, m - sl


def _bbands(s: pd.Series, n=20, k=2.0):
    mid = s.rolling(n).mean()
    std = s.rolling(n).std()
    return mid + k * std, mid, mid - k * std


def _atr(h: pd.Series, l: pd.Series, c: pd.Series, n=14) -> pd.Series:
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _stoch(h: pd.Series, l: pd.Series, c: pd.Series, k=14, d=3):
    ll = l.rolling(k).min()
    hh = h.rolling(k).max()
    pct_k = 100 * (c - ll) / (hh - ll).replace(0, np.nan)
    return pct_k, pct_k.rolling(d).mean()


# ── signal dataclass ─────────────────────────────────────────────────────────

@dataclass
class TechResult:
    direction: Literal["long", "short", "neutral"]
    score: float            # −1 … +1
    confidence: float       # 0 … 1
    current_price: float
    atr: float
    stop_loss: float
    take_profit: float
    rr_ratio: float
    indicators: dict = field(default_factory=dict)


# ── main analysis function ────────────────────────────────────────────────────

def analyze(df: pd.DataFrame, atr_sl_mult: float, atr_tp_mult: float) -> TechResult | None:
    """
    Compute all technical indicators on *df* (OHLCV DataFrame).
    Returns None if not enough data.
    """
    if df is None or len(df) < 30:
        return None

    close = df["Close"].astype(float)
    high  = df["High"].astype(float)
    low   = df["Low"].astype(float)

    # ── compute indicators ──
    ema9  = _ema(close, 9)
    ema21 = _ema(close, 21)
    ema50 = _ema(close, 50) if len(close) >= 50 else None
    ema200= _ema(close, 200) if len(close) >= 200 else None

    rsi             = _rsi(close)
    macd, macd_sig, macd_hist = _macd(close)
    bb_up, bb_mid, bb_lo      = _bbands(close)
    atr_series                = _atr(high, low, close)
    stoch_k, stoch_d          = _stoch(high, low, close)

    # latest values
    def f(s): return float(s.iloc[-1]) if s is not None and not pd.isna(s.iloc[-1]) else None
    def fp(s): return float(s.iloc[-2]) if s is not None and len(s) > 1 and not pd.isna(s.iloc[-2]) else None

    cur   = f(close)
    e9    = f(ema9)
    e21   = f(ema21)
    e50   = f(ema50) if ema50 is not None else None
    e200  = f(ema200) if ema200 is not None else None
    r     = f(rsi)
    mh    = f(macd_hist)
    mh_p  = fp(macd_hist)
    bbu   = f(bb_up)
    bbl   = f(bb_lo)
    bbm   = f(bb_mid)
    atr   = f(atr_series)
    sk    = f(stoch_k)
    sd    = f(stoch_d)

    if atr is None or atr == 0 or cur is None:
        return None

    # ── signal scoring ──
    signals: dict[str, tuple[str, str, float]] = {}  # name → (direction, description, raw_score)

    # 1. EMA alignment
    if e9 and e21:
        if e9 > e21 and (e50 is None or e21 > e50):
            signals["ema_align"] = ("long", f"EMA9({e9:,.1f}) > EMA21({e21:,.1f}) — tendance haussière", 1.0)
        elif e9 < e21 and (e50 is None or e21 < e50):
            signals["ema_align"] = ("short", f"EMA9({e9:,.1f}) < EMA21({e21:,.1f}) — tendance baissière", -1.0)
        else:
            signals["ema_align"] = ("neutral", "EMAs mixtes — consolidation", 0.0)

    # 2. EMA 200 (long-term trend bias)
    if e200:
        if cur > e200:
            signals["ema200"] = ("long", f"Prix({cur:,.1f}) > EMA200({e200:,.1f}) — bull market LT", 0.5)
        else:
            signals["ema200"] = ("short", f"Prix({cur:,.1f}) < EMA200({e200:,.1f}) — bear market LT", -0.5)

    # 3. RSI
    if r is not None:
        if r < 25:
            signals["rsi"] = ("long", f"RSI {r:.1f} — survente extrême (rebond attendu)", 1.0)
        elif r > 75:
            signals["rsi"] = ("short", f"RSI {r:.1f} — surachat extrême (correction attendue)", -1.0)
        elif r < 40:
            signals["rsi"] = ("short", f"RSI {r:.1f} — momentum baissier", -0.4)
        elif r > 60:
            signals["rsi"] = ("long", f"RSI {r:.1f} — momentum haussier", 0.4)
        else:
            signals["rsi"] = ("neutral", f"RSI {r:.1f} — zone neutre", 0.0)

    # 4. MACD histogram crossover
    if mh is not None and mh_p is not None:
        if mh > 0 and mh_p <= 0:
            signals["macd"] = ("long", "Croisement MACD ↑ (signal fort)", 1.0)
        elif mh < 0 and mh_p >= 0:
            signals["macd"] = ("short", "Croisement MACD ↓ (signal fort)", -1.0)
        elif mh > 0:
            signals["macd"] = ("long", f"Histogramme MACD positif (+{mh:.2f})", 0.5)
        elif mh < 0:
            signals["macd"] = ("short", f"Histogramme MACD négatif ({mh:.2f})", -0.5)
        else:
            signals["macd"] = ("neutral", "MACD neutre", 0.0)

    # 5. Bollinger Bands
    if bbu and bbl and bbm:
        bb_range = bbu - bbl
        bb_pos = (cur - bbl) / bb_range if bb_range > 0 else 0.5
        if cur <= bbl:
            signals["bbands"] = ("long", f"Prix sous BB inf ({bbl:,.1f}) — compression baissière", 1.0)
        elif cur >= bbu:
            signals["bbands"] = ("short", f"Prix sur BB sup ({bbu:,.1f}) — extension haussière", -1.0)
        elif bb_pos < 0.30:
            signals["bbands"] = ("long", "Prix dans bas des Bollinger", 0.4)
        elif bb_pos > 0.70:
            signals["bbands"] = ("short", "Prix dans haut des Bollinger", -0.4)
        else:
            signals["bbands"] = ("neutral", f"Prix au milieu des BB ({bbm:,.1f})", 0.0)

    # 6. Stochastic
    if sk is not None and sd is not None:
        if sk < 20 and sk > sd:
            signals["stoch"] = ("long", f"Stoch {sk:.0f} — survente + croisement haussier", 1.0)
        elif sk > 80 and sk < sd:
            signals["stoch"] = ("short", f"Stoch {sk:.0f} — surachat + croisement baissier", -1.0)
        elif sk < 20:
            signals["stoch"] = ("long", f"Stoch {sk:.0f} — zone de survente", 0.5)
        elif sk > 80:
            signals["stoch"] = ("short", f"Stoch {sk:.0f} — zone de surachat", -0.5)
        else:
            signals["stoch"] = ("neutral", f"Stoch {sk:.0f}", 0.0)

    # ── aggregate ──
    raw_scores = [v[2] for v in signals.values()]
    if not raw_scores:
        return None

    combined = float(np.mean(raw_scores))
    confidence = min(abs(combined), 1.0)

    if combined > 0.10:
        direction = "long"
    elif combined < -0.10:
        direction = "short"
    else:
        direction = "neutral"

    # ── barriers ──
    if direction == "long":
        sl = cur - atr_sl_mult * atr
        tp = cur + atr_tp_mult * atr
    else:
        sl = cur + atr_sl_mult * atr
        tp = cur - atr_tp_mult * atr

    sl_dist = abs(sl - cur)
    tp_dist = abs(tp - cur)
    rr = tp_dist / sl_dist if sl_dist > 0 else 1.0

    return TechResult(
        direction=direction,
        score=combined,
        confidence=confidence,
        current_price=cur,
        atr=atr,
        stop_loss=sl,
        take_profit=tp,
        rr_ratio=rr,
        indicators=signals,
    )
