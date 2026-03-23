"""fetch_news.py — Fetches commodity news from public RSS feeds."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

# ── RSS sources ───────────────────────────────────────────────────────────────
FEEDS = [
    # Yahoo Finance — per ticker (most reliable, 20 entries each)
    {"url": "https://finance.yahoo.com/rss/headline?s=GC%3DF",  "source": "Yahoo Finance", "category": "metals"},
    {"url": "https://finance.yahoo.com/rss/headline?s=SI%3DF",  "source": "Yahoo Finance", "category": "metals"},
    {"url": "https://finance.yahoo.com/rss/headline?s=PL%3DF",  "source": "Yahoo Finance", "category": "metals"},
    {"url": "https://finance.yahoo.com/rss/headline?s=HG%3DF",  "source": "Yahoo Finance", "category": "metals"},
    {"url": "https://finance.yahoo.com/rss/headline?s=CL%3DF",  "source": "Yahoo Finance", "category": "energy"},
    {"url": "https://finance.yahoo.com/rss/headline?s=NG%3DF",  "source": "Yahoo Finance", "category": "energy"},
    {"url": "https://finance.yahoo.com/rss/headline?s=BZ%3DF",  "source": "Yahoo Finance", "category": "energy"},
    # OilPrice — energy specialist
    {"url": "https://oilprice.com/rss/main",                    "source": "OilPrice",      "category": "energy"},
]

# Keywords to filter-in (keep only commodity-relevant articles)
_KEYWORDS = [
    "gold", "silver", "platinum", "palladium", "copper", "aluminum", "aluminium",
    "zinc", "nickel", "uranium", "rhodium", "tin",
    "oil", "crude", "brent", "wti", "gas", "lng", "ttf", "energy", "opec",
    "coal", "carbon",
    "commodity", "commodities", "metal", "metals", "mining",
    "inflation", "fed", "federal reserve", "dollar", "treasury",
    "tariff", "sanctions", "supply", "demand", "inventory", "stockpile",
    "oro", "plata", "petróleo", "cobre",
]


def _is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in _KEYWORDS)


def _parse_date(entry) -> datetime:
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return parsedate_to_datetime(val)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _age(dt: datetime) -> str:
    try:
        now = datetime.now(timezone.utc)
        secs = int((now - dt.astimezone(timezone.utc)).total_seconds())
        if secs < 60:
            return "ahora"
        if secs < 3600:
            return f"{secs // 60}m"
        if secs < 86400:
            return f"{secs // 3600}h"
        return f"{secs // 86400}d"
    except Exception:
        return ""


def fetch_news(max_per_feed: int = 15) -> list[dict]:
    """
    Returns a deduplicated list of articles sorted by date desc.
    Each item: {title, url, source, category, published_dt, age_str}
    """
    seen_urls: set[str] = set()
    articles: list[dict] = []

    for feed_cfg in FEEDS:
        try:
            d = feedparser.parse(feed_cfg["url"])
            count = 0
            for entry in d.entries:
                if count >= max_per_feed:
                    break
                title   = (getattr(entry, "title",   "") or "").strip()
                summary = getattr(entry, "summary", "") or ""
                link    = (getattr(entry, "link",    "") or "").strip()
                if not title or not link or link in seen_urls:
                    continue
                if not _is_relevant(title, summary):
                    continue
                seen_urls.add(link)
                pub = _parse_date(entry)
                articles.append({
                    "title":        title,
                    "url":          link,
                    "source":       feed_cfg["source"],
                    "category":     feed_cfg["category"],
                    "published_dt": pub,
                    "age_str":      _age(pub),
                })
                count += 1
        except Exception:
            pass

    articles.sort(key=lambda x: x["published_dt"], reverse=True)
    return articles
