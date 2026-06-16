ASSETS = {
    "Gold": {
        "ticker": "GC=F",
        "name": "Or (Gold Futures)",
        "color": "#FFD700",
        "icon": "🥇",
        "unit": "$/oz",
        "keywords": [
            "gold", "xau", "precious metal", "bullion", "safe haven",
            "inflation", "dollar", "dxy", "fed", "real rate", "treasury",
            "rate hike", "monetary", "stagflation", "recession",
        ],
    },
    "Brent": {
        "ticker": "BZ=F",
        "name": "Brent Crude Oil",
        "color": "#2196F3",
        "icon": "🛢️",
        "unit": "$/bbl",
        "keywords": [
            "oil", "crude", "opec", "brent", "wti", "energy", "barrel",
            "petroleum", "inventory", "eia", "refinery", "gasoline",
            "supply", "demand", "production cut", "shale",
        ],
    },
    "Nasdaq": {
        "ticker": "NQ=F",
        "name": "Nasdaq 100 Futures",
        "color": "#00E676",
        "icon": "📈",
        "unit": "pts",
        "keywords": [
            "nasdaq", "tech", "technology", "growth", "earnings", "fed",
            "interest rate", "ai", "semiconductor", "qqq", "stock",
            "equity", "s&p", "apple", "microsoft", "nvidia", "alphabet",
            "rate cut", "valuation",
        ],
    },
}

SIGNAL_CONFIG = {
    "intraday": {
        "label": "Intraday",
        "fetch_period": "5d",
        "fetch_interval": "60m",
        "atr_sl_mult": 0.5,
        "atr_tp_mult": 1.2,
        "leverage_min": 10,
        "leverage_max": 30,
        "color": "#FF6B6B",
        "emoji": "⚡",
        "description": "Signal court terme (quelques heures)",
    },
    "swing": {
        "label": "Swing (Multi-jours)",
        "fetch_period": "6mo",
        "fetch_interval": "1d",
        "atr_sl_mult": 1.5,
        "atr_tp_mult": 3.5,
        "leverage_min": 2,
        "leverage_max": 8,
        "color": "#4ECDC4",
        "emoji": "📊",
        "description": "Signal moyen terme (1–5 jours)",
    },
}

RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://finance.yahoo.com/news/rssindex",
    "https://feeds.marketwatch.com/marketwatch/marketpulse/",
]

CALENDAR_API_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Minimum combined score (0–1) to emit a trading signal.
# Combined = 0.60*tech + 0.25*news + 0.15*cal
# 0.15 = tech-direction guard already filters pure-neutral; this catches
# any directional signal (even 2 indicators aligned without news/cal support).
MIN_CONFIDENCE = 0.15

# Weights for combined signal score
WEIGHTS = {
    "technical": 0.60,
    "news": 0.25,
    "calendar": 0.15,
}
