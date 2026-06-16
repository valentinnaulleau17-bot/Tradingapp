import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import datetime
from trading.config import ASSETS


@st.cache_data(ttl=60)
def get_current_prices() -> dict:
    """Return current quote for all 3 assets (cached 60 s)."""
    result = {}
    for asset, cfg in ASSETS.items():
        try:
            tk = yf.Ticker(cfg["ticker"])
            info = tk.fast_info
            price = float(info.last_price)
            prev = float(info.previous_close)
            change = price - prev
            result[asset] = {
                "price": price,
                "prev_close": prev,
                "change": change,
                "change_pct": change / prev * 100 if prev else 0,
                "day_high": float(info.day_high),
                "day_low": float(info.day_low),
                "timestamp": datetime.now(),
            }
        except Exception as exc:
            result[asset] = {"error": str(exc), "price": 0}
    return result


@st.cache_data(ttl=300)
def get_ohlcv(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """Download OHLCV data (cached 5 min for intraday, 1 h for daily)."""
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        # Flatten MultiIndex columns produced by yfinance >= 0.2.x
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        return df
    except Exception:
        return pd.DataFrame()
