"""
queries.py
Reusable read functions for the dashboard.
All functions return plain Python dicts/lists — no SQLite Row objects.
"""
import sqlite3
from datetime import date, timedelta
from db.schema import get_conn


def _rows(conn, sql, params=()):
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ── Spot prices ───────────────────────────────────────────────────────────────

def get_latest_prices() -> list[dict]:
    """Last close for every ticker in spot_prices."""
    conn = get_conn()
    rows = _rows(conn, """
        SELECT s.ticker, s.name, s.category, s.date, s.close, s.currency
        FROM spot_prices s
        INNER JOIN (
            SELECT ticker, MAX(date) AS max_date
            FROM spot_prices
            GROUP BY ticker
        ) t ON s.ticker = t.ticker AND s.date = t.max_date
        ORDER BY s.category, s.name
    """)
    conn.close()
    return rows


def get_price_series(ticker: str, days: int = 365) -> list[dict]:
    """OHLCV history for one ticker."""
    since = str(date.today() - timedelta(days=days))
    conn = get_conn()
    rows = _rows(conn, """
        SELECT date, open, high, low, close, volume
        FROM spot_prices
        WHERE ticker = ? AND date >= ?
        ORDER BY date ASC
    """, (ticker, since))
    conn.close()
    return rows


def get_price_on_date(ticker: str, target_date: str) -> float | None:
    """Return closing price for a ticker on or before target_date."""
    conn = get_conn()
    row = conn.execute("""
        SELECT close FROM spot_prices
        WHERE ticker = ? AND date <= ?
        ORDER BY date DESC LIMIT 1
    """, (ticker, target_date)).fetchone()
    conn.close()
    return float(row[0]) if row else None


def get_pct_change(ticker: str, days: int) -> float | None:
    """% change over last N calendar days."""
    today_str = str(date.today())
    past_str  = str(date.today() - timedelta(days=days))
    current = get_price_on_date(ticker, today_str)
    past    = get_price_on_date(ticker, past_str)
    if current and past and past != 0:
        return round((current - past) / past * 100, 2)
    return None


def get_ytd_change(ticker: str) -> float | None:
    """% change since 31-Dec of last year."""
    dec31 = str(date(date.today().year - 1, 12, 31))
    today_str = str(date.today())
    current = get_price_on_date(ticker, today_str)
    past    = get_price_on_date(ticker, dec31)
    if current and past and past != 0:
        return round((current - past) / past * 100, 2)
    return None


# ── Valuation indicators ──────────────────────────────────────────────────────

def get_52w_range(ticker: str) -> tuple:
    """(min, max) closing price over the last 365 days."""
    since = str(date.today() - timedelta(days=365))
    conn = get_conn()
    row = conn.execute("""
        SELECT MIN(close), MAX(close) FROM spot_prices
        WHERE ticker = ? AND date >= ?
    """, (ticker, since)).fetchone()
    conn.close()
    if row and row[0] is not None and row[1] is not None:
        return float(row[0]), float(row[1])
    return None, None


def get_ma(ticker: str, period: int = 200) -> float | None:
    """Simple moving average of the last N closing prices."""
    conn = get_conn()
    row = conn.execute("""
        SELECT AVG(close) FROM (
            SELECT close FROM spot_prices
            WHERE ticker = ?
            ORDER BY date DESC LIMIT ?
        )
    """, (ticker, period)).fetchone()
    conn.close()
    return float(row[0]) if row and row[0] is not None else None


# ── Futures curve ─────────────────────────────────────────────────────────────

def get_futures_curve(commodity: str, on_date: str = None) -> list[dict]:
    """M1-M6 curve for a commodity on a given date (default: latest)."""
    conn = get_conn()
    if on_date is None:
        row = conn.execute(
            "SELECT MAX(date) FROM futures_curve WHERE commodity = ?",
            (commodity,)
        ).fetchone()
        on_date = row[0] if row and row[0] else str(date.today())

    rows = _rows(conn, """
        SELECT contract, ticker, price, expiry
        FROM futures_curve
        WHERE commodity = ? AND date = ?
        ORDER BY contract ASC
    """, (commodity, on_date))
    conn.close()
    return rows


def get_curve_dates(commodity: str) -> list[str]:
    """All dates we have curve data for a commodity."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT date FROM futures_curve WHERE commodity = ? ORDER BY date DESC",
        (commodity,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ── COT data ──────────────────────────────────────────────────────────────────

def get_cot_series(commodity_slug: str, weeks: int = 104) -> list[dict]:
    """COT history for a commodity (default 2 years)."""
    since = str(date.today() - timedelta(weeks=weeks))
    conn = get_conn()
    rows = _rows(conn, """
        SELECT report_date, comm_long, comm_short, comm_net,
               noncomm_long, noncomm_short, noncomm_net, open_interest
        FROM cot_data
        WHERE commodity_slug = ? AND report_date >= ?
        ORDER BY report_date ASC
    """, (commodity_slug, since))
    conn.close()
    return rows


def get_cot_percentile(commodity_slug: str, lookback_weeks: int = 156) -> float | None:
    """
    Current non-commercial net position as percentile of last N weeks.
    0 = historically max short, 100 = historically max long.
    """
    rows = get_cot_series(commodity_slug, weeks=lookback_weeks)
    if len(rows) < 2:
        return None
    net_values = [r["noncomm_net"] for r in rows if r["noncomm_net"] is not None]
    if not net_values:
        return None
    current = net_values[-1]
    min_val, max_val = min(net_values), max(net_values)
    if max_val == min_val:
        return 50.0
    return round((current - min_val) / (max_val - min_val) * 100, 1)


# ── EIA inventories ───────────────────────────────────────────────────────────

def get_eia_series(series_id: str, weeks: int = 260) -> list[dict]:
    """EIA inventory history for one series."""
    since = str(date.today() - timedelta(weeks=weeks))
    conn = get_conn()
    rows = _rows(conn, """
        SELECT report_date, value, unit, series_name
        FROM eia_inventories
        WHERE series_id = ? AND report_date >= ?
        ORDER BY report_date ASC
    """, (series_id, since))
    conn.close()
    return rows


def get_eia_seasonal_avg(series_id: str, week_of_year: int,
                          years: int = 5) -> float | None:
    """Average inventory value for a given week-of-year over last N years."""
    conn = get_conn()
    # SQLite: strftime('%W', date) gives week number
    row = conn.execute("""
        SELECT AVG(value)
        FROM eia_inventories
        WHERE series_id = ?
          AND CAST(strftime('%W', report_date) AS INTEGER) = ?
          AND CAST(strftime('%Y', report_date) AS INTEGER) >= ?
    """, (series_id, week_of_year, date.today().year - years)).fetchone()
    conn.close()
    return float(row[0]) if row and row[0] else None


# ── LME warehouse stocks ──────────────────────────────────────────────────────

def get_lme_latest() -> list[dict]:
    """Latest stock for each metal."""
    conn = get_conn()
    rows = _rows(conn, """
        SELECT l.metal, l.date, l.on_warrant, l.cancelled, l.total
        FROM lme_stocks l
        INNER JOIN (
            SELECT metal, MAX(date) AS max_date
            FROM lme_stocks GROUP BY metal
        ) t ON l.metal = t.metal AND l.date = t.max_date
        ORDER BY l.metal
    """)
    conn.close()
    return rows


def get_lme_series(metal: str, days: int = 365) -> list[dict]:
    """Historical warehouse stocks for one metal."""
    since = str(date.today() - timedelta(days=days))
    conn = get_conn()
    rows = _rows(conn, """
        SELECT date, on_warrant, cancelled, total
        FROM lme_stocks
        WHERE metal = ? AND date >= ?
        ORDER BY date ASC
    """, (metal, since))
    conn.close()
    return rows


# ── Rhodium ───────────────────────────────────────────────────────────────────

def get_rhodium_series(days: int = 365) -> list[dict]:
    """Rhodium spot price history."""
    since = str(date.today() - timedelta(days=days))
    conn = get_conn()
    rows = _rows(conn, """
        SELECT date, bid, ask, mid, source
        FROM rhodium_prices
        WHERE date >= ?
        ORDER BY date ASC
    """, (since,))
    conn.close()
    return rows


# ── FX rates ──────────────────────────────────────────────────────────────────

def get_fx_rate(pair: str, on_date: str = None) -> float | None:
    """Latest FX rate for a pair."""
    if on_date is None:
        on_date = str(date.today())
    conn = get_conn()
    row = conn.execute("""
        SELECT rate FROM fx_rates
        WHERE pair = ? AND date <= ?
        ORDER BY date DESC LIMIT 1
    """, (pair, on_date)).fetchone()
    conn.close()
    return float(row[0]) if row else None


def get_fx_series(pair: str, days: int = 365) -> list[dict]:
    """FX rate history for a currency pair."""
    since = str(date.today() - timedelta(days=days))
    conn = get_conn()
    rows = _rows(conn, """
        SELECT date, rate FROM fx_rates
        WHERE pair = ? AND date >= ?
        ORDER BY date ASC
    """, (pair, since))
    conn.close()
    return rows
