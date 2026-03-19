"""
fetch_prices.py
Fetches spot prices, FX rates, and futures curves via yfinance.
Run manually: python -m fetchers.fetch_prices
"""
import logging
import os
import sys
from datetime import datetime, date, timedelta

import yfinance as yf
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TICKERS, FUTURES_CURVE, MONTH_CODES, LOG_DIR
from db.schema import get_conn

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "fetch_prices.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def next_active_contracts(root: str, exchange: str, valid_months: list,
                          n: int = 6) -> list[str]:
    """
    Build the next N dated futures tickers in Yahoo Finance format.
    E.g. root='GC', exchange='CMX', valid_months=[2,4,6,8,10,12]
    → ['GCJ26.CMX', 'GCM26.CMX', ...]
    """
    tickers = []
    today = date.today()
    year, month = today.year, today.month

    checked = 0
    while len(tickers) < n and checked < 36:
        if month > 12:
            month = 1
            year += 1
        if month in valid_months:
            code = MONTH_CODES[month]
            yy = str(year)[-2:]
            tickers.append(f"{root}{code}{yy}.{exchange}")
        month += 1
        checked += 1

    return tickers


def upsert_spot(conn, ticker: str, meta: dict, df: pd.DataFrame):
    """Insert or replace spot price rows for a ticker."""
    fetched_at = datetime.utcnow().isoformat()
    rows = []
    for idx, row in df.iterrows():
        close = row.get("Close")
        if close is None or pd.isna(close):
            continue
        rows.append((
            ticker,
            meta["name"],
            meta["category"],
            str(idx.date()),
            row.get("Open"),
            row.get("High"),
            row.get("Low"),
            float(close),
            row.get("Volume"),
            "USD",
            "yfinance",
            fetched_at,
        ))
    if rows:
        conn.executemany("""
            INSERT OR REPLACE INTO spot_prices
                (ticker, name, category, date, open, high, low, close,
                 volume, currency, source, fetched_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
    return len(rows)


def upsert_fx(conn, pair: str, df: pd.DataFrame):
    """Insert or replace FX rate rows."""
    fetched_at = datetime.utcnow().isoformat()
    rows = []
    for idx, row in df.iterrows():
        rate = row.get("Close")
        if rate is None or pd.isna(rate):
            continue
        rows.append((str(idx.date()), pair, float(rate), fetched_at))
    if rows:
        conn.executemany("""
            INSERT OR REPLACE INTO fx_rates (date, pair, rate, fetched_at)
            VALUES (?,?,?,?)
        """, rows)
    return len(rows)


def upsert_curve(conn, commodity: str, contract_label: str,
                 ticker: str, price: float):
    """Insert or replace a single futures curve point for today."""
    today = str(date.today())
    fetched_at = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO futures_curve
            (commodity, date, contract, ticker, price, fetched_at)
        VALUES (?,?,?,?,?,?)
    """, (commodity, today, contract_label, ticker, price, fetched_at))


# ── Main fetch routines ───────────────────────────────────────────────────────

def fetch_spot_prices():
    log.info("=== fetch_spot_prices start ===")
    conn = get_conn()

    spot_tickers = [t for t, m in TICKERS.items() if m["category"] != "fx"]
    fx_tickers   = [t for t, m in TICKERS.items() if m["category"] in ("fx", "currency")]

    # Download last 5 trading days to fill gaps
    try:
        data = yf.download(
            spot_tickers, period="5d", interval="1d",
            group_by="ticker", auto_adjust=True, progress=False
        )
    except Exception as e:
        log.error(f"yfinance spot download failed: {e}")
        conn.close()
        return

    total = 0
    for ticker, meta in TICKERS.items():
        if meta["category"] in ("fx",):
            continue
        try:
            df = data[ticker] if len(spot_tickers) > 1 else data
            n = upsert_spot(conn, ticker, meta, df)
            total += n
            log.info(f"  {ticker} ({meta['name']}): {n} rows")
        except Exception as e:
            log.warning(f"  {ticker}: {e}")

    conn.commit()
    log.info(f"Spot prices: {total} rows upserted")

    # FX rates
    try:
        fx_data = yf.download(
            fx_tickers, period="5d", interval="1d",
            group_by="ticker", auto_adjust=True, progress=False
        )
    except Exception as e:
        log.error(f"yfinance FX download failed: {e}")
        conn.close()
        return

    fx_total = 0
    for pair in fx_tickers:
        try:
            df = fx_data[pair] if len(fx_tickers) > 1 else fx_data
            n = upsert_fx(conn, pair, df)
            fx_total += n
        except Exception as e:
            log.warning(f"  FX {pair}: {e}")

    conn.commit()
    log.info(f"FX rates: {fx_total} rows upserted")
    conn.close()


def fetch_futures_curves():
    log.info("=== fetch_futures_curves start ===")
    conn = get_conn()
    total = 0

    for commodity, cfg in FUTURES_CURVE.items():
        contracts = next_active_contracts(cfg["root"], cfg["exchange"], cfg["months"], n=6)
        log.info(f"  {commodity}: fetching {contracts}")

        try:
            data = yf.download(
                contracts, period="2d", interval="1d",
                group_by="ticker", auto_adjust=True, progress=False
            )
        except Exception as e:
            log.warning(f"  {commodity} download failed: {e}")
            continue

        for i, ticker in enumerate(contracts):
            label = f"M{i+1}"
            try:
                df = data[ticker] if len(contracts) > 1 else data
                close = df["Close"].dropna()
                if close.empty:
                    log.warning(f"    {ticker}: no data")
                    continue
                price = float(close.iloc[-1])
                upsert_curve(conn, commodity, label, ticker, price)
                total += 1
                log.info(f"    {label} {ticker}: {price:.2f}")
            except Exception as e:
                log.warning(f"    {ticker}: {e}")

    conn.commit()
    conn.close()
    log.info(f"Futures curve: {total} points upserted")


def fetch_history(days: int = 365):
    """One-time backfill of historical spot prices."""
    log.info(f"=== fetch_history ({days} days) start ===")
    conn = get_conn()

    all_tickers = list(TICKERS.keys())
    period = f"{days}d"

    try:
        data = yf.download(
            all_tickers, period=period, interval="1d",
            group_by="ticker", auto_adjust=True, progress=False
        )
    except Exception as e:
        log.error(f"History download failed: {e}")
        conn.close()
        return

    total = 0
    for ticker, meta in TICKERS.items():
        cat = meta["category"]
        try:
            df = data[ticker] if len(all_tickers) > 1 else data
            if cat in ("fx", "currency"):
                n = upsert_fx(conn, ticker, df)
            else:
                n = upsert_spot(conn, ticker, meta, df)
            total += n
            log.info(f"  {ticker}: {n} rows")
        except Exception as e:
            log.warning(f"  {ticker}: {e}")

    conn.commit()
    conn.close()
    log.info(f"History backfill: {total} rows upserted")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    fetch_spot_prices()
    fetch_futures_curves()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=int, default=0,
                        help="Backfill N days of history (e.g. 730)")
    args = parser.parse_args()

    if args.history:
        fetch_history(args.history)
    else:
        main()
