"""
fetch_rhodium.py
Scrapes rhodium spot price from Kitco (primary) or JM Bullion (fallback).
Rhodium has no exchange-traded futures — prices are OTC reference quotes.
Run manually: python -m fetchers.fetch_rhodium
"""
import logging
import os
import re
import sys
from datetime import datetime, date

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR
from db.schema import get_conn

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "fetch_rhodium.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ── Scrapers ──────────────────────────────────────────────────────────────────

def scrape_kitco() -> dict | None:
    """
    Scrape rhodium bid/ask from Kitco's metals page.
    Returns dict with keys: bid, ask, mid, source.
    """
    url = "https://www.kitco.com/market/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"Kitco request failed: {e}")
        return None

    soup = BeautifulSoup(r.text, "lxml")

    # Find any tag containing "Rhodium" text and extract sibling/child prices
    for tag in soup.find_all(string=lambda s: s and "Rhodium" in s):
        container = tag.find_parent()
        if container is None:
            continue
        # Walk up one level to get the full price block
        block = container.find_parent() or container
        text = block.get_text(" ", strip=True)
        numbers = re.findall(r"[\d,]+\.?\d*", text)
        prices = [float(n.replace(",", "")) for n in numbers
                  if 300 < float(n.replace(",", "")) < 30000]
        if len(prices) >= 2:
            bid, ask = prices[0], prices[1]
            mid = round((bid + ask) / 2, 2)
            log.info(f"Kitco: bid={bid} ask={ask} mid={mid}")
            return {"bid": bid, "ask": ask, "mid": mid, "source": "kitco"}
        elif len(prices) == 1:
            mid = prices[0]
            log.info(f"Kitco: mid={mid} (single price)")
            return {"bid": None, "ask": None, "mid": mid, "source": "kitco"}

    log.warning("Kitco: rhodium price not found in page")
    return None


def scrape_jm_bullion() -> dict | None:
    """
    Fallback: scrape rhodium price from Johnson Matthey price table.
    """
    url = "http://www.platinum.matthey.com/prices/price-tables"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"JM Bullion request failed: {e}")
        return None

    soup = BeautifulSoup(r.text, "lxml")

    for row in soup.find_all("tr"):
        text = row.get_text(" ", strip=True)
        if "Rhodium" in text or "rhodium" in text:
            numbers = re.findall(r"[\d,]+\.?\d*", text)
            prices = [float(n.replace(",", "")) for n in numbers
                      if 300 < float(n.replace(",", "")) < 30000]
            if prices:
                mid = prices[0]
                log.info(f"JM: mid={mid}")
                return {"bid": None, "ask": None, "mid": mid, "source": "jm_bullion"}

    log.warning("JM Bullion: rhodium row not found")
    return None


# ── DB write ──────────────────────────────────────────────────────────────────

def save_rhodium(data: dict):
    today = str(date.today())
    fetched_at = datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO rhodium_prices
            (date, bid, ask, mid, source, fetched_at)
        VALUES (?,?,?,?,?,?)
    """, (today, data.get("bid"), data.get("ask"), data["mid"],
          data["source"], fetched_at))

    # Also write to spot_prices for unified dashboard table
    conn.execute("""
        INSERT OR REPLACE INTO spot_prices
            (ticker, name, category, date, close, currency, source, fetched_at)
        VALUES ('RHODIUM', 'Rhodium', 'pgm', ?, ?, 'USD', ?, ?)
    """, (today, data["mid"], data["source"], fetched_at))

    conn.commit()
    conn.close()
    log.info(f"Saved: mid={data['mid']} source={data['source']}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    log.info("=== fetch_rhodium start ===")

    result = scrape_kitco()
    if result is None:
        log.info("Trying JM Bullion fallback...")
        result = scrape_jm_bullion()

    if result is None:
        log.error("Both sources failed — no rhodium price saved")
        return

    save_rhodium(result)
    log.info("=== fetch_rhodium done ===")


if __name__ == "__main__":
    main()
