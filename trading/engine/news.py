"""
News fetcher: pulls RSS feeds, filters by asset keywords, scores sentiment.
No external API key required — uses public RSS.
"""
from __future__ import annotations
import re
import streamlit as st
import feedparser

from trading.config import ASSETS, RSS_FEEDS

BULLISH_WORDS = {
    "surge", "rally", "gain", "rise", "jump", "soar", "climb", "strong",
    "bull", "beat", "better", "exceed", "record", "high", "positive",
    "growth", "recovery", "boost", "upside", "hawkish" , "optimist",
}
BEARISH_WORDS = {
    "fall", "drop", "decline", "plunge", "crash", "weak", "miss", "worse",
    "bear", "low", "negative", "concern", "fear", "risk", "sell-off",
    "correction", "worry", "slump", "downside", "recession", "contraction",
}


def _clean(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


@st.cache_data(ttl=900)   # 15 min
def fetch_all_news(max_per_feed: int = 25) -> list[dict]:
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                articles.append({
                    "title":   _clean(entry.get("title", "")),
                    "summary": _clean(entry.get("summary", "")),
                    "link":    entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source":  feed.feed.get("title", url),
                })
        except Exception:
            continue
    return articles


def filter_for_asset(articles: list[dict], asset: str) -> list[dict]:
    keywords = ASSETS[asset]["keywords"]
    out = []
    for art in articles:
        text = (art["title"] + " " + art["summary"]).lower()
        if any(kw in text for kw in keywords):
            art = dict(art)
            art["sentiment"] = _score_article(text)
            out.append(art)
    # Deduplicate by title prefix
    seen: set[str] = set()
    unique = []
    for a in out:
        key = a["title"][:60]
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique[:12]


def _score_article(text: str) -> float:
    words = set(re.findall(r"\b\w+\b", text.lower()))
    bull = len(words & BULLISH_WORDS)
    bear = len(words & BEARISH_WORDS)
    total = bull + bear
    return (bull - bear) / total if total else 0.0


def aggregate_sentiment(articles: list[dict]) -> float:
    """Return mean sentiment score across articles (−1 … +1)."""
    if not articles:
        return 0.0
    scores = [a.get("sentiment", 0.0) for a in articles]
    return float(sum(scores) / len(scores))
