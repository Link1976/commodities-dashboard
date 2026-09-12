---
title: Commodity Pulse
emoji: 📈
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Commodity Pulse

A self-hosted dashboard for tracking physical commodity markets — energy, precious
metals, PGMs, industrial metals, coal and uranium — in one place, with the context
needed to read them rather than just the prices.

**Live:** https://occam1976-commodities-dashboard.hf.space

![Overview — prices, session and period moves, 52-week position and distance from the 200-day average](https://github.com/Link1976/commodities-dashboard/releases/download/v1.0/overview.png)

![Futures — the WTI term structure, labelled backwardation, with each expiry's spread against the front contract](https://github.com/Link1976/commodities-dashboard/releases/download/v1.0/futures.png)

---

## Why

Commodity data is scattered. Spot prices live on one site, futures curves on another,
CFTC positioning in a weekly text file, LME warehouse stocks behind a daily PDF, and
rhodium does not trade on an exchange at all. Pulling those together by hand, every
day, to answer a simple question — *is this market tight or loose right now?* — is the
kind of work that should be automated once.

This dashboard does that: a set of collectors write into a local SQLite database, and a
Dash front end reads from it. No subscriptions, no vendor terminal.

## What it shows

### Overview
Every instrument in one sortable table: price, and the move over the last session, week,
month and year to date. Two columns add the context that a raw price lacks — where the
price sits inside its 52-week range (0% = the year's low, 100% = the high), and how far
it has drifted from its 200-day moving average. Cards at the top call out the session's
biggest mover in each direction and the best and worst performers of the year.

Below the table, cross-commodity ratios — gold/silver, platinum/palladium,
platinum/gold, copper/gold, and the Brent–WTI spread — each with its historical range
and a note on what a reading outside that range usually means.

### Futures
The term structure for a given commodity, plotted across its real listed contracts, with
the shape labelled automatically: **contango** (futures above spot — ample supply, storage
being paid for) or **backwardation** (futures below spot — physical scarcity, a premium for
immediate delivery). A table lists each expiry and its spread against the front contract,
and a date picker replays how the curve looked on any earlier day the collector ran.

### History
Candlestick charts for any instrument over the stored history.

### COT
Weekly CFTC Commitments of Traders positioning — commercials against speculators — with
each week's reading expressed as a percentile of the last three years, so an extreme is
visible as an extreme.

### News
A filtered feed of commodity headlines.

## Coverage

| Group | Instruments |
|---|---|
| Precious | Gold, Silver |
| PGMs | Platinum, Palladium, Rhodium |
| Energy | WTI, Brent, Henry Hub, TTF (Europe), JKM (Asia), Heating Oil, Gasoline |
| Coal | Thermal, Metallurgical (equity proxies) |
| Industrial | Copper, Aluminium, Zinc, Nickel |
| Nuclear | Uranium (equity proxy) |
| Producer FX | ZAR, AUD, CAD, CLP against USD |

Three of these have no tradable futures contract on the data source, and are marked in
the interface as proxies rather than presented as the thing itself. Rhodium trades OTC
only and is scraped from a daily dealer quote.

## How it works

```
fetchers/          collectors, one per source, each independently runnable
  fetch_prices.py    spot, futures curves and FX          (yfinance)
  fetch_cot.py       CFTC positioning                     (cot_reports)
  fetch_eia.py       US energy inventories                (EIA API)
  fetch_lme.py       LME warehouse stocks                 (Nasdaq Data Link)
  fetch_rhodium.py   rhodium spot                         (scraped)
  fetch_news.py      headlines                            (RSS)

db/                SQLite schema and every read query in one place
dashboard/         Dash app; one module per tab under pages/
config.py          instruments, tickers, ratio thresholds
```

Collectors and interface are deliberately separate: each collector can be run, retried or
scheduled on its own, and a source going down degrades one panel instead of the app.
Scheduling is left to the host — `launchd` on macOS.

**Stack:** Python 3.11 · Dash 4 · Plotly · pandas · SQLite · Docker

## Running it

```bash
git clone https://github.com/Link1976/commodities-dashboard.git
cd commodities-dashboard
pip install -r requirements.txt

python fetchers/fetch_prices.py --history 1095   # first run: backfill 3 years
python dashboard/app.py                      # http://localhost:7860
```

Or with Docker:

```bash
docker build -t commodity-pulse .
docker run -p 7860:7860 commodity-pulse
```

### Configuration

Two collectors need a free API key, supplied through the environment:

| Variable | Used by | Register |
|---|---|---|
| `EIA_API_KEY` | US energy inventories | https://www.eia.gov/opendata/ |
| `NASDAQ_API_KEY` | LME warehouse stocks | https://data.nasdaq.com/sign-up |

Neither is required to start. If unset, those two collectors skip and log why; prices,
futures, COT and news are unaffected. Never commit these values — set them in your shell,
or as Space secrets when deploying.

## Known limitations

- **Storage is not persistent in the hosted deployment.** The container's database is
  rebuilt on every restart, which refetches three years of price history and drops the
  scraped rhodium and LME series, since those have no downloadable archive.
- **The EIA and LME collectors are scheduled by the host**, so they run locally but not
  inside the container.
- Illiquid contracts can repeat a stale close for several sessions; the figures are shown
  as reported rather than smoothed.

## Notes

Built for my own use. The interface is in Spanish; the code and this document are in
English. Not investment advice — it reports public data and nothing more.
