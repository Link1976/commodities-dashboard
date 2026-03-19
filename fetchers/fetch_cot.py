"""
fetch_cot.py
Downloads CFTC Commitment of Traders (Legacy Futures) data.
No API key needed — downloads official CFTC CSV files.
Run manually: python -m fetchers.fetch_cot
             python -m fetchers.fetch_cot --history  (backfill 3 years)
"""
import logging
import os
import sys
from datetime import datetime

import pandas as pd
import cot_reports as cot

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR
from db.schema import get_conn

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "fetch_cot.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ── Commodity filter ──────────────────────────────────────────────────────────
# Exact CFTC market names → our slug (use the most liquid/representative contract)
COT_FILTER = {
    "GOLD - COMMODITY EXCHANGE INC.":           "gold",
    "SILVER - COMMODITY EXCHANGE INC.":         "silver",
    "PLATINUM - NEW YORK MERCANTILE EXCHANGE":  "platinum",
    "PALLADIUM - NEW YORK MERCANTILE EXCHANGE": "palladium",
    "WTI FINANCIAL CRUDE OIL - NEW YORK MERCANTILE EXCHANGE": "crude_oil",
    "HENRY HUB - NEW YORK MERCANTILE EXCHANGE": "nat_gas",
    "COPPER- #1 - COMMODITY EXCHANGE INC.":     "copper",
}

# ── Column mapping ────────────────────────────────────────────────────────────
COL = {
    "date":         "As of Date in Form YYYY-MM-DD",
    "name":         "Market and Exchange Names",
    "comm_long":    "Commercial Positions-Long (All)",
    "comm_short":   "Commercial Positions-Short (All)",
    "noncomm_long": "Noncommercial Positions-Long (All)",
    "noncomm_short":"Noncommercial Positions-Short (All)",
    "oi":           "Open Interest (All)",
}


# ── Process ───────────────────────────────────────────────────────────────────

def process_year(year: int) -> pd.DataFrame:
    """Download and filter one year of COT data."""
    log.info(f"Downloading COT {year}...")
    try:
        df = cot.cot_year(year=year, cot_report_type="legacy_fut")
    except Exception as e:
        log.error(f"COT download failed for {year}: {e}")
        return pd.DataFrame()

    # Filter to our commodities
    mask = df[COL["name"]].isin(COT_FILTER.keys())
    filtered = df[mask].copy()
    log.info(f"  {year}: {len(filtered)} rows after filter (from {len(df)} total)")
    return filtered


def upsert_cot(conn, df: pd.DataFrame):
    """Write filtered COT rows to cot_data table."""
    if df.empty:
        return 0

    fetched_at = datetime.utcnow().isoformat()
    rows = []

    for _, row in df.iterrows():
        name = row[COL["name"]]
        slug = COT_FILTER.get(name)
        if not slug:
            continue

        try:
            comm_long    = float(row[COL["comm_long"]])
            comm_short   = float(row[COL["comm_short"]])
            noncomm_long = float(row[COL["noncomm_long"]])
            noncomm_short= float(row[COL["noncomm_short"]])
            oi           = float(row[COL["oi"]])
            report_date  = str(row[COL["date"]])[:10]  # YYYY-MM-DD
        except (ValueError, KeyError) as e:
            log.warning(f"  Parse error for {name}: {e}")
            continue

        rows.append((
            report_date,
            name,
            slug,
            comm_long,
            comm_short,
            round(comm_long - comm_short, 0),
            noncomm_long,
            noncomm_short,
            round(noncomm_long - noncomm_short, 0),
            oi,
            fetched_at,
        ))

    if rows:
        conn.executemany("""
            INSERT OR REPLACE INTO cot_data (
                report_date, commodity_name, commodity_slug,
                comm_long, comm_short, comm_net,
                noncomm_long, noncomm_short, noncomm_net,
                open_interest, fetched_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, rows)

    return len(rows)


# ── Entry point ───────────────────────────────────────────────────────────────

def main(history: bool = False):
    log.info(f"=== fetch_cot start (history={history}) ===")

    current_year = datetime.now().year
    years = list(range(current_year - 3, current_year + 1)) if history else [current_year]

    conn = get_conn()
    total = 0

    for year in years:
        df = process_year(year)
        n = upsert_cot(conn, df)
        total += n
        log.info(f"  {year}: {n} rows upserted")

    conn.commit()
    conn.close()
    log.info(f"=== fetch_cot done — {total} total rows ===")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true",
                        help="Backfill last 3 years")
    args = parser.parse_args()
    main(history=args.history)
