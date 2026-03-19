import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH


def get_conn():
    """Return a WAL-mode connection to the database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
    -- ── Spot prices (all instruments) ──────────────────────────────────────
    CREATE TABLE IF NOT EXISTS spot_prices (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker      TEXT    NOT NULL,
        name        TEXT    NOT NULL,
        category    TEXT    NOT NULL,
        date        TEXT    NOT NULL,
        open        REAL,
        high        REAL,
        low         REAL,
        close       REAL    NOT NULL,
        volume      REAL,
        currency    TEXT    DEFAULT 'USD',
        source      TEXT    DEFAULT 'yfinance',
        fetched_at  TEXT    NOT NULL,
        UNIQUE(ticker, date)
    );

    -- ── Futures term structure ───────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS futures_curve (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        commodity   TEXT    NOT NULL,
        date        TEXT    NOT NULL,
        contract    TEXT    NOT NULL,
        ticker      TEXT    NOT NULL,
        expiry      TEXT,
        price       REAL    NOT NULL,
        fetched_at  TEXT    NOT NULL,
        UNIQUE(commodity, date, contract)
    );

    -- ── CFTC Commitment of Traders ──────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS cot_data (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date     TEXT    NOT NULL,
        commodity_name  TEXT    NOT NULL,
        commodity_slug  TEXT    NOT NULL,
        comm_long       REAL,
        comm_short      REAL,
        comm_net        REAL,
        noncomm_long    REAL,
        noncomm_short   REAL,
        noncomm_net     REAL,
        open_interest   REAL,
        fetched_at      TEXT    NOT NULL,
        UNIQUE(report_date, commodity_slug)
    );

    -- ── EIA energy inventories ──────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS eia_inventories (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT    NOT NULL,
        series_id   TEXT    NOT NULL,
        series_name TEXT    NOT NULL,
        value       REAL    NOT NULL,
        unit        TEXT    NOT NULL,
        fetched_at  TEXT    NOT NULL,
        UNIQUE(report_date, series_id)
    );

    -- ── LME warehouse stocks ────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS lme_stocks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL,
        metal       TEXT    NOT NULL,
        on_warrant  REAL,
        cancelled   REAL,
        total       REAL    NOT NULL,
        fetched_at  TEXT    NOT NULL,
        UNIQUE(date, metal)
    );

    -- ── Rhodium spot (scraped, no exchange contract) ────────────────────────
    CREATE TABLE IF NOT EXISTS rhodium_prices (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL,
        bid         REAL,
        ask         REAL,
        mid         REAL    NOT NULL,
        source      TEXT    NOT NULL,
        fetched_at  TEXT    NOT NULL,
        UNIQUE(date, source)
    );

    -- ── FX rates ────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS fx_rates (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL,
        pair        TEXT    NOT NULL,
        rate        REAL    NOT NULL,
        fetched_at  TEXT    NOT NULL,
        UNIQUE(date, pair)
    );

    -- ── Indexes ─────────────────────────────────────────────────────────────
    CREATE INDEX IF NOT EXISTS idx_spot_ticker_date
        ON spot_prices(ticker, date);
    CREATE INDEX IF NOT EXISTS idx_spot_category
        ON spot_prices(category, date);
    CREATE INDEX IF NOT EXISTS idx_futures_commodity_date
        ON futures_curve(commodity, date);
    CREATE INDEX IF NOT EXISTS idx_cot_slug_date
        ON cot_data(commodity_slug, report_date);
    CREATE INDEX IF NOT EXISTS idx_eia_series_date
        ON eia_inventories(series_id, report_date);
    CREATE INDEX IF NOT EXISTS idx_lme_metal_date
        ON lme_stocks(metal, date);
    CREATE INDEX IF NOT EXISTS idx_fx_pair_date
        ON fx_rates(pair, date);
    """)

    conn.commit()
    conn.close()
    print(f"DB initialised at: {DB_PATH}")


if __name__ == "__main__":
    init_db()
