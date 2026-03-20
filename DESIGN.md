# Commodities Dashboard — Architecture Design

## Overview

Local Python dashboard to monitor commodity prices (energy, precious metals, PGMs, industrial metals) with spot vs futures comparison, historical evolution, COT positioning, and energy inventory tracking.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.11 (conda env `cartera`) |
| Data — prices/futures/FX | yfinance |
| Data — energy inventories | EIA API (free key) |
| Data — COT positioning | CFTC via `cot_reports` library |
| Data — rhodium spot | Web scraping (Kitco daily) |
| Data — LME warehouse stocks | Web scraping (LME daily) |
| Storage | SQLite (`data/commodities.db`) |
| Dashboard | Dash + Plotly |
| Scheduler | launchd (macOS) |

---

## Directory Structure

```
commodities-dashboard/
│
├── config.py                   # API keys, tickers, constants
├── run_fetcher.sh              # Shell wrapper for launchd (activates conda)
│
├── fetchers/
│   ├── fetch_prices.py         # yfinance: spot + futures M1-M6 + FX
│   ├── fetch_eia.py            # EIA API: weekly energy inventories
│   ├── fetch_cot.py            # CFTC COT via cot_reports
│   ├── fetch_rhodium.py        # Scraping: rhodium spot from Kitco
│   └── fetch_lme.py            # Scraping: LME warehouse stocks
│
├── db/
│   ├── schema.py               # CREATE TABLE + init_db()
│   └── queries.py              # Reusable read/write functions
│
├── dashboard/
│   ├── app.py                  # Dash entry point — python dashboard/app.py
│   ├── layout.py               # Tab structure
│   └── pages/
│       ├── overview.py         # Tab 1: Spot prices table + ratios
│       ├── term_structure.py   # Tab 2: Futures curves (contango/backwardation)
│       ├── history.py          # Tab 3: Historical candlestick charts
│       ├── cot.py              # Tab 4: COT positioning
│       ├── inventories.py      # Tab 5: EIA energy inventories vs 5y avg
│       ├── lme.py              # Tab 6: LME warehouse stocks
│       └── currencies.py       # Tab 7: Producer currency overlays
│
├── launchd/
│   ├── com.commodities.prices.plist
│   ├── com.commodities.eia.plist
│   ├── com.commodities.cot.plist
│   ├── com.commodities.rhodium.plist
│   └── com.commodities.lme.plist
│
├── logs/                       # One log file per fetcher
└── data/
    └── commodities.db          # SQLite database
```

---

## Data Sources

| Source | Data | Frequency | Notes |
|---|---|---|---|
| yfinance | Spot prices, futures M1-M6, FX rates | Weekdays 18:30 + 00:30 | No registration needed |
| EIA API | Crude/gasoline/nat gas inventories | Thursdays 16:30 | Free API key required |
| CFTC | COT report (commercials vs specs) | Fridays 22:00 | Free, `cot_reports` lib |
| Kitco (scraping) | Rhodium spot bid/ask | Weekdays 12:00 | No exchange contract for Rh |
| LME (scraping) | Warehouse stocks by metal | Weekdays 19:00 | Published ~17:00 London |

---

## Instruments Covered

### Precious Metals
| Instrument | yfinance ticker |
|---|---|
| Gold | `GC=F` |
| Silver | `SI=F` |

### PGMs (Platinum Group Metals)
| Instrument | yfinance ticker | Notes |
|---|---|---|
| Platinum | `PL=F` | NYMEX |
| Palladium | `PA=F` | NYMEX |
| Rhodium | — | OTC only, scraped from Kitco |
| Iridium | — | OTC, future scope |
| Ruthenium | — | OTC, future scope |

### Energy
| Instrument | yfinance ticker |
|---|---|
| WTI Crude Oil | `CL=F` |
| Brent Crude | `BZ=F` |
| Natural Gas | `NG=F` |
| Heating Oil | `HO=F` |
| RBOB Gasoline | `RB=F` |

### Industrial Metals
| Instrument | yfinance ticker |
|---|---|
| Copper | `HG=F` |
| Aluminum | `ALI=F` |
| Zinc | `ZNC=F` |
| Nickel | `NI=F` |

### Producer Currencies
| Currency | yfinance ticker | Linked to |
|---|---|---|
| South African Rand | `ZARUSD=X` | Platinum, Palladium |
| Australian Dollar | `AUDUSD=X` | Gold, Copper |
| Canadian Dollar | `CADUSD=X` | Oil |
| Chilean Peso | `CLPUSD=X` | Copper |

---

## Database Schema

### `spot_prices`
```sql
CREATE TABLE IF NOT EXISTS spot_prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,   -- 'precious', 'pgm', 'energy', 'industrial', 'currency'
    date        TEXT NOT NULL,   -- YYYY-MM-DD
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL NOT NULL,
    volume      REAL,
    currency    TEXT DEFAULT 'USD',
    source      TEXT DEFAULT 'yfinance',
    fetched_at  TEXT NOT NULL,
    UNIQUE(ticker, date)
);
```

### `futures_curve`
```sql
CREATE TABLE IF NOT EXISTS futures_curve (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    commodity   TEXT NOT NULL,
    date        TEXT NOT NULL,
    contract    TEXT NOT NULL,   -- 'M1', 'M2', ... 'M6'
    ticker      TEXT NOT NULL,
    expiry      TEXT,
    price       REAL NOT NULL,
    fetched_at  TEXT NOT NULL,
    UNIQUE(commodity, date, contract)
);
```

### `cot_data`
```sql
CREATE TABLE IF NOT EXISTS cot_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date     TEXT NOT NULL,
    commodity_name  TEXT NOT NULL,
    commodity_slug  TEXT NOT NULL,
    comm_long       REAL,
    comm_short      REAL,
    comm_net        REAL,
    noncomm_long    REAL,
    noncomm_short   REAL,
    noncomm_net     REAL,
    open_interest   REAL,
    fetched_at      TEXT NOT NULL,
    UNIQUE(report_date, commodity_slug)
);
```

### `eia_inventories`
```sql
CREATE TABLE IF NOT EXISTS eia_inventories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL,
    series_id   TEXT NOT NULL,
    series_name TEXT NOT NULL,
    value       REAL NOT NULL,
    unit        TEXT NOT NULL,   -- 'MBBL' or 'BCF'
    fetched_at  TEXT NOT NULL,
    UNIQUE(report_date, series_id)
);
```

### `lme_stocks`
```sql
CREATE TABLE IF NOT EXISTS lme_stocks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    metal       TEXT NOT NULL,
    on_warrant  REAL,
    cancelled   REAL,
    total       REAL NOT NULL,
    fetched_at  TEXT NOT NULL,
    UNIQUE(date, metal)
);
```

### `rhodium_prices`
```sql
CREATE TABLE IF NOT EXISTS rhodium_prices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    bid         REAL,
    ask         REAL,
    mid         REAL NOT NULL,
    source      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    UNIQUE(date, source)
);
```

### `fx_rates`
```sql
CREATE TABLE IF NOT EXISTS fx_rates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    pair        TEXT NOT NULL,
    rate        REAL NOT NULL,
    fetched_at  TEXT NOT NULL,
    UNIQUE(date, pair)
);
```

---

## Dashboard Tabs

| Tab | Content |
|---|---|
| **Overview** | Spot prices table (USD/EUR/GBP, % changes 1D/1W/1M/YTD) + ratio indicators |
| **Term Structure** | Futures curve M1→M6 per commodity — contango/backwardation visualized |
| **History** | Candlestick chart + volume + MA overlays, multi-commodity overlay |
| **COT** | Commercials vs non-commercials net position + price overlay + COT percentile index |
| **Inventories** | EIA weekly stocks vs 5-year seasonal average (crude, gasoline, nat gas) |
| **LME Stocks** | Warehouse tonnes by metal + cancelled warrants trend |
| **Currencies** | Producer currency vs commodity price overlay (ZAR/Pt, AUD/Au, CLP/Cu, CAD/Oil) |

---

## Key Ratios (Overview Tab)

| Ratio | Formula | Significance |
|---|---|---|
| Gold / Silver | Au price / Ag price | >80 historically = silver cheap |
| Platinum / Palladium | Pt price / Pd price | Historically Pt > Pd; inverted since 2017 |
| Platinum / Gold | Pt price / Au price | Pt discount to Au = historically anomalous |
| Copper / Gold | Cu price / Au price | Rising = economic growth signal |
| Brent / WTI spread | Brent − WTI (USD) | Quality/location premium |

---

## Scheduler (launchd)

| Job | Runs | When |
|---|---|---|
| `fetch_prices` | Weekdays | 18:30 + 00:30 |
| `fetch_eia` | Thursdays | 16:30 |
| `fetch_cot` | Fridays | 22:00 |
| `fetch_rhodium` | Weekdays | 12:00 |
| `fetch_lme` | Weekdays | 19:00 |

All jobs: `~/Library/LaunchAgents/` (user-level, no root needed).

---

## Dependencies

```bash
conda activate cartera
pip install dash plotly cot_reports lxml
# Register free EIA API key at: https://www.eia.gov/opendata/register.php
```

Already installed in `cartera`: `yfinance`, `pandas`, `requests`, `beautifulsoup4`, `numpy`, `openpyxl`.

---

## Deployment

| Target | URL |
|---|---|
| HuggingFace Space | `https://huggingface.co/spaces/Occam1976/commodities-dashboard` |
| URL directa (sin barra HF) | `https://occam1976-commodities-dashboard.hf.space` |
| GitHub | `https://github.com/Link1976/commodities-dashboard` |

**Deploy:** `git push origin main && git push hf main`

**Secrets en HF Spaces:** `EIA_API_KEY`, `NASDAQ_API_KEY`

**Nota:** La DB SQLite es efímera en HF (se repuebla en cada restart vía `startup.sh`). Los fetchers schedulados (launchd) solo aplican en local.

---

## Implementation Status

| Componente | Estado |
|---|---|
| `db/schema.py` + `db/queries.py` | ✅ |
| `config.py` | ✅ |
| `fetchers/fetch_prices.py` | ✅ |
| `fetchers/fetch_rhodium.py` | ✅ |
| `fetchers/fetch_eia.py` | ✅ |
| `fetchers/fetch_cot.py` | ✅ |
| `fetchers/fetch_lme.py` | ✅ |
| `dashboard/app.py` + `layout.py` | ✅ |
| Tab 1: Overview | ✅ |
| Tab 2: Term Structure | ✅ |
| Tab 3: History | ✅ |
| Tab 4: COT | ✅ |
| Tab 5: Inventories (EIA) | ⏳ pendiente |
| Tab 6: LME Stocks | ⏳ pendiente |
| Tab 7: Currencies | ⏳ pendiente |
| `Dockerfile` + `startup.sh` | ✅ |
| launchd plists (local) | ⏳ pendiente |
