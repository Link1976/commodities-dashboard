"""
fetch_eia.py
Fetches weekly energy inventory data from the EIA Open Data API.
Register free at: https://www.eia.gov/opendata/register.php
Run manually: python -m fetchers.fetch_eia
             python -m fetchers.fetch_eia --history  (backfill 5 years)
"""
import logging
import os
import sys
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import EIA_API_KEY, EIA_SERIES, LOG_DIR
from db.schema import get_conn

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "fetch_eia.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

EIA_BASE = "https://api.eia.gov/v2/seriesid/{series_id}"


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_series(series_id: str, meta: dict, rows: int = 52) -> list[dict]:
    """
    Fetch the last `rows` weekly data points for a given EIA series.
    Returns list of {report_date, value} dicts.
    """
    if not EIA_API_KEY:
        log.error("EIA_API_KEY not set in config.py — skipping")
        return []

    url = EIA_BASE.format(series_id=series_id)
    params = {
        "api_key": EIA_API_KEY,
        "frequency": "weekly",
        "data[0]": "value",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": rows,
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.error(f"{series_id}: request failed: {e}")
        return []

    payload = r.json()
    data = payload.get("response", {}).get("data", [])
    log.info(f"{series_id}: {len(data)} rows fetched")
    return data


def upsert_series(conn, series_id: str, meta: dict, data: list[dict]):
    """Write fetched rows into eia_inventories table."""
    fetched_at = datetime.utcnow().isoformat()
    rows = []
    for item in data:
        period = item.get("period")         # format: "2024-03-08"
        value  = item.get("value")
        if period is None or value is None:
            continue
        rows.append((
            period,
            series_id,
            meta["name"],
            float(value),
            meta["unit"],
            fetched_at,
        ))

    if rows:
        conn.executemany("""
            INSERT OR REPLACE INTO eia_inventories
                (report_date, series_id, series_name, value, unit, fetched_at)
            VALUES (?,?,?,?,?,?)
        """, rows)
    return len(rows)


# ── Entry point ───────────────────────────────────────────────────────────────

def main(history: bool = False):
    log.info(f"=== fetch_eia start (history={history}) ===")

    if not EIA_API_KEY:
        log.error("EIA_API_KEY is empty. Register at https://www.eia.gov/opendata/register.php")
        print("ERROR: Set EIA_API_KEY in config.py first.")
        return

    rows_per_series = 260 if history else 52   # 5 years vs 1 year

    conn = get_conn()
    total = 0

    for series_id, meta in EIA_SERIES.items():
        data = fetch_series(series_id, meta, rows=rows_per_series)
        n = upsert_series(conn, series_id, meta, data)
        total += n
        log.info(f"  {meta['name']}: {n} rows upserted")

    conn.commit()
    conn.close()
    log.info(f"=== fetch_eia done — {total} total rows ===")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true",
                        help="Backfill 5 years of history")
    args = parser.parse_args()
    main(history=args.history)
