"""
fetch_lme.py
Fetches LME warehouse stock data via NASDAQ Data Link (ex-Quandl).
Requires free API key: https://data.nasdaq.com/sign-up
LME dataset codes: LME/ST_AL, LME/ST_CU, LME/ST_ZN, LME/ST_NI, LME/ST_PB, LME/ST_TN
Run manually: python -m fetchers.fetch_lme
             python -m fetchers.fetch_lme --history
"""
import logging
import os
import sys
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR, NASDAQ_API_KEY
from db.schema import get_conn

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "fetch_lme.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

NASDAQ_BASE = "https://data.nasdaq.com/api/v3/datasets/{dataset}.json"

# NASDAQ Data Link dataset codes for LME warehouse stocks
# Column layout: Date, On Warrant, Cancelled Warrants, Total
LME_DATASETS = {
    "aluminium": "LME/ST_AL",
    "copper":    "LME/ST_CU",
    "zinc":      "LME/ST_ZN",
    "nickel":    "LME/ST_NI",
    "lead":      "LME/ST_PB",
    "tin":       "LME/ST_TN",
}


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_metal(metal: str, dataset: str, rows: int = 30) -> list[dict]:
    """Fetch LME warehouse stock for one metal from NASDAQ Data Link."""
    if not NASDAQ_API_KEY:
        log.error("NASDAQ_API_KEY not set in fetchers/fetch_lme.py")
        return []

    url = NASDAQ_BASE.format(dataset=dataset)
    params = {
        "api_key": NASDAQ_API_KEY,
        "rows": rows,
        "order": "desc",
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.error(f"{metal} ({dataset}): request failed: {e}")
        return []

    payload = r.json()
    dataset_data = payload.get("dataset", {})
    columns = dataset_data.get("column_names", [])
    data    = dataset_data.get("data", [])

    log.info(f"{metal}: columns={columns}, {len(data)} rows")

    results = []
    for row in data:
        if len(row) < 2:
            continue
        record = dict(zip(columns, row))
        results.append({
            "date":       record.get("Date", ""),
            "on_warrant": record.get("On Warrant"),
            "cancelled":  record.get("Cancelled Warrants"),
            "total":      record.get("Total Stocks") or record.get("On Warrant"),
        })

    return results


def upsert_metal(conn, metal: str, data: list[dict]):
    """Write LME stock rows to lme_stocks table."""
    fetched_at = datetime.utcnow().isoformat()
    rows = []
    for item in data:
        if not item.get("date") or item.get("total") is None:
            continue
        rows.append((
            item["date"],
            metal,
            item.get("on_warrant"),
            item.get("cancelled"),
            float(item["total"]),
            fetched_at,
        ))
    if rows:
        conn.executemany("""
            INSERT OR REPLACE INTO lme_stocks
                (date, metal, on_warrant, cancelled, total, fetched_at)
            VALUES (?,?,?,?,?,?)
        """, rows)
    return len(rows)


# ── Entry point ───────────────────────────────────────────────────────────────

def main(history: bool = False):
    log.info(f"=== fetch_lme start (history={history}) ===")

    if not NASDAQ_API_KEY:
        log.error("NASDAQ_API_KEY is empty. Register at https://data.nasdaq.com/sign-up")
        print("ERROR: Set NASDAQ_API_KEY in fetchers/fetch_lme.py first.")
        return

    rows_per_metal = 365 if history else 30

    conn = get_conn()
    total = 0

    for metal, dataset in LME_DATASETS.items():
        data = fetch_metal(metal, dataset, rows=rows_per_metal)
        n = upsert_metal(conn, metal, data)
        total += n
        log.info(f"  {metal}: {n} rows upserted")

    conn.commit()
    conn.close()
    log.info(f"=== fetch_lme done — {total} total rows ===")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true",
                        help="Backfill 1 year of history")
    args = parser.parse_args()
    main(history=args.history)
