"""fetch_news.py — Fetches commodity news from public RSS feeds."""
import html as _html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

# ── RSS sources ───────────────────────────────────────────────────────────────
FEEDS = [
    {"url": "https://finance.yahoo.com/rss/headline?s=GC%3DF",  "source": "Yahoo Finance", "hint": "gold"},
    {"url": "https://finance.yahoo.com/rss/headline?s=SI%3DF",  "source": "Yahoo Finance", "hint": "silver"},
    {"url": "https://finance.yahoo.com/rss/headline?s=PL%3DF",  "source": "Yahoo Finance", "hint": "platinum"},
    {"url": "https://finance.yahoo.com/rss/headline?s=PA%3DF",  "source": "Yahoo Finance", "hint": "palladium"},
    {"url": "https://finance.yahoo.com/rss/headline?s=HG%3DF",  "source": "Yahoo Finance", "hint": "copper"},
    {"url": "https://finance.yahoo.com/rss/headline?s=CL%3DF",  "source": "Yahoo Finance", "hint": "crude_oil"},
    {"url": "https://finance.yahoo.com/rss/headline?s=BZ%3DF",  "source": "Yahoo Finance", "hint": "crude_oil"},
    {"url": "https://finance.yahoo.com/rss/headline?s=NG%3DF",  "source": "Yahoo Finance", "hint": "nat_gas"},
    {"url": "https://oilprice.com/rss/main",                    "source": "OilPrice",      "hint": "crude_oil"},
]

# ── Commodity keyword mapping ─────────────────────────────────────────────────
# slug → (label_es, keywords_to_match)
COMMODITY_TAGS: dict[str, tuple[str, list[str]]] = {
    "gold":      ("Oro",       ["gold", "oro", "bullion", "xau"]),
    "silver":    ("Plata",     ["silver", "plata", "xag"]),
    "platinum":  ("Platino",   ["platinum", "platino", "xpt"]),
    "palladium": ("Paladio",   ["palladium", "paladio", "xpd"]),
    "copper":    ("Cobre",     ["copper", "cobre"]),
    "crude_oil": ("Petróleo",  ["oil", "crude", "brent", "wti", "opec", "petróleo", "barrel", "barril"]),
    "nat_gas":   ("Gas",       ["natural gas", "gas natural", "lng", "ttf", "jkm", "henry hub"]),
    "aluminum":  ("Aluminio",  ["aluminum", "aluminium", "aluminio"]),
    "nickel":    ("Níquel",    ["nickel", "níquel"]),
    "uranium":   ("Uranio",    ["uranium", "uranio", "nuclear"]),
}

# General commodity keywords — article must match at least one to be included
_GENERAL_KEYWORDS = [kw for _, (_, kws) in COMMODITY_TAGS.items() for kw in kws] + [
    "commodity", "commodities", "metal", "metals", "mining", "mine",
    "inflation", "fed", "federal reserve", "dollar", "tariff",
    "supply", "demand", "inventory", "stockpile", "futures",
]


def _tag_article(title: str, summary: str, feed_hint: str) -> list[str]:
    """Return list of commodity slugs that match this article."""
    text = (title + " " + summary).lower()
    tags = []
    for slug, (_label, keywords) in COMMODITY_TAGS.items():
        if any(kw in text for kw in keywords):
            tags.append(slug)
    # If no keyword match but feed has a hint, use the hint as fallback tag
    if not tags and feed_hint in COMMODITY_TAGS:
        tags.append(feed_hint)
    return tags


def _is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in _GENERAL_KEYWORDS)


def _clean_html(text: str) -> str:
    """Strip HTML tags and unescape entities."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = _html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _truncate(text: str, max_chars: int = 220) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


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
        secs = int((datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
        if secs < 60:   return "ahora"
        if secs < 3600: return f"{secs // 60}m"
        if secs < 86400: return f"{secs // 3600}h"
        return f"{secs // 86400}d"
    except Exception:
        return ""


def fetch_news(max_per_feed: int = 15) -> list[dict]:
    """
    Returns a deduplicated list of articles sorted by date desc.
    Each item: {title, url, source, summary, tags, published_dt, age_str}
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
                title   = _clean_html(getattr(entry, "title",   "") or "")
                summary = _clean_html(getattr(entry, "summary", "") or "")
                link    = (getattr(entry, "link", "") or "").strip()
                if not title or not link or link in seen_urls:
                    continue
                if not _is_relevant(title, summary):
                    continue
                seen_urls.add(link)
                pub  = _parse_date(entry)
                tags = _tag_article(title, summary, feed_cfg["hint"])
                articles.append({
                    "title":        title,
                    "url":          link,
                    "source":       feed_cfg["source"],
                    "summary":      _truncate(summary),
                    "tags":         tags,
                    "published_dt": pub,
                    "age_str":      _age(pub),
                })
                count += 1
        except Exception:
            pass

    articles.sort(key=lambda x: x["published_dt"], reverse=True)
    return articles


# Expose label map for the UI
COMMODITY_LABELS: dict[str, str] = {slug: label for slug, (label, _) in COMMODITY_TAGS.items()}
