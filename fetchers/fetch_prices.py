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
# Also echo to stdout so fetch results show up in the Space's container logs
# (the log file lives inside the ephemeral container and is never seen).
_stdout = logging.StreamHandler(sys.stdout)
_stdout.setFormatter(logging.Formatter("[fetch_prices] %(levelname)s %(message)s"))
log.addHandler(_stdout)
log.setLevel(logging.INFO)


def _yf_errors() -> dict:
    """Per-ticker errors yfinance swallowed during the last download."""
    import yfinance.shared as shared
    return dict(getattr(shared, "_ERRORS", {}) or {})


def _rows_saved_since(started_at: str) -> int:
    """Read back, on a fresh connection, how many spot rows this run wrote."""
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM spot_prices WHERE fetched_at >= ?", (started_at,)
    ).fetchone()[0]
    conn.close()
    return n


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

def fetch_spot_prices() -> dict:
    """
    Download the last days of spot prices and FX. Returns a summary:
    ok / failed tickers, rows written, rows read back from the DB, and errors.
    """
    log.info("=== fetch_spot_prices start ===")
    started_at = datetime.utcnow().isoformat()
    summary = {"ok": [], "failed": [], "rows": 0, "saved": 0, "errors": {}}
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
        summary["errors"]["download"] = str(e)
        return summary

    yf_errors = _yf_errors()
    total = 0
    for ticker, meta in TICKERS.items():
        if meta["category"] in ("fx",):
            continue
        try:
            df = data[ticker] if len(spot_tickers) > 1 else data
            n = upsert_spot(conn, ticker, meta, df)
        except Exception as e:
            n = 0
            yf_errors.setdefault(ticker, str(e))
        total += n
        if n:
            summary["ok"].append(ticker)
        else:
            summary["failed"].append(ticker)
            log.warning(f"  {ticker}: no data ({yf_errors.get(ticker, 'empty response')})")

    conn.commit()
    summary["rows"] = total
    summary["errors"].update(yf_errors)
    log.info(f"Spot prices: {total} rows upserted, "
             f"{len(summary['ok'])} ok, {len(summary['failed'])} failed")

    # FX rates
    try:
        fx_data = yf.download(
            fx_tickers, period="5d", interval="1d",
            group_by="ticker", auto_adjust=True, progress=False
        )
    except Exception as e:
        log.error(f"yfinance FX download failed: {e}")
        conn.close()
        summary["saved"] = _rows_saved_since(started_at)
        return summary

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

    # Confirm the writes actually landed in the database file
    summary["saved"] = _rows_saved_since(started_at)
    if summary["saved"] < summary["rows"]:
        log.error(f"DB write check: wrote {summary['rows']} rows, "
                  f"read back only {summary['saved']}")
    else:
        log.info(f"DB write check: {summary['saved']} rows read back OK")
    return summary


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
    """One-time backfill of historical spot prices (one ticker at a time)."""
    log.info(f"=== fetch_history ({days} days) start ===")
    conn = get_conn()
    period = f"{days}d"
    total = 0

    for ticker, meta in TICKERS.items():
        cat = meta["category"]
        try:
            data = yf.download(
                ticker, period=period, interval="1d",
                auto_adjust=True, progress=False
            )
            if data.empty:
                log.warning(f"  {ticker}: no data returned")
                print(f"[history] {ticker}: sin datos")
                continue
            # yfinance 1.x returns MultiIndex columns for single ticker — flatten
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            if cat in ("fx", "currency"):
                n = upsert_fx(conn, ticker, data)
            else:
                n = upsert_spot(conn, ticker, meta, data)
            total += n
            print(f"[history] {ticker}: {n} rows")
            log.info(f"  {ticker}: {n} rows")
        except Exception as e:
            log.warning(f"  {ticker}: {e}")
            print(f"[history] {ticker}: ERROR {e}")

    conn.commit()
    conn.close()
    print(f"[history] Total: {total} rows guardados")
    log.info(f"History backfill: {total} rows upserted")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> dict:
    summary = fetch_spot_prices()
    try:
        fetch_futures_curves()
    except Exception as e:
        log.error(f"futures curves failed: {e}")
    return summary


def describe(summary: dict) -> str:
    """One-line, human-readable outcome of a fetch for the dashboard."""
    ok, failed = len(summary["ok"]), len(summary["failed"])
    if not ok:
        errs = " ".join(summary["errors"].values()).lower()
        if "rate" in errs or "too many" in errs or "429" in errs:
            return "Yahoo no devolvió datos (límite de peticiones)"
        return "Yahoo no devolvió datos"
    if summary["saved"] < summary["rows"]:
        return "Descargado pero no guardado en la base de datos"
    msg = f"{ok} precios actualizados"
    if failed:
        msg += f" · {failed} sin datos"
    return msg


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
