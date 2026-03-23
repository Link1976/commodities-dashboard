import os

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "data", "commodities.db")
LOG_DIR  = os.path.join(BASE_DIR, "logs")

# ── API Keys ──────────────────────────────────────────────────────────────────
EIA_API_KEY    = os.environ.get("EIA_API_KEY", "V8AsbpxexkPQA1K06unOlMoyuNoRlJAYkx1N6g59")
NASDAQ_API_KEY = os.environ.get("NASDAQ_API_KEY", "Q3qg2RtJp_F6Pfz5dcpH")

# ── Spot + FX tickers (yfinance) ──────────────────────────────────────────────
TICKERS = {
    # Precious metals
    "GC=F":  {"name": "Gold",        "category": "precious",   "unit": "USD/oz"},
    "SI=F":  {"name": "Silver",      "category": "precious",   "unit": "USD/oz"},

    # PGMs
    "PL=F":  {"name": "Platinum",    "category": "pgm",        "unit": "USD/oz"},
    "PA=F":  {"name": "Palladium",   "category": "pgm",        "unit": "USD/oz"},
    # Rhodium: no yfinance ticker — fetched separately via fetch_rhodium.py

    # Energy
    "CL=F":  {"name": "WTI Crude",      "category": "energy",     "unit": "USD/bbl"},
    "BZ=F":  {"name": "Brent Crude",    "category": "energy",     "unit": "USD/bbl"},
    "NG=F":  {"name": "Nat Gas (USA)",   "category": "energy",     "unit": "USD/MMBtu"},
    "TTF=F": {"name": "Nat Gas Europa (TTF)", "category": "energy", "unit": "EUR/MWh"},
    "JKM=F": {"name": "Nat Gas Asia (JKM)",   "category": "energy", "unit": "USD/MMBtu"},
    "HO=F":  {"name": "Heating Oil",    "category": "energy",     "unit": "USD/gal"},
    "RB=F":  {"name": "Gasoline",       "category": "energy",     "unit": "USD/gal"},
    # Carbon — no direct futures on Yahoo Finance; liquid US producer stocks as proxies
    "BTU":   {"name": "Carbón Térmico",    "category": "carbon", "unit": "USD (proxy BTU)"},
    "HCC":   {"name": "Carbón Metalúrgico","category": "carbon", "unit": "USD (proxy HCC)"},

    # Industrial metals
    "HG=F":  {"name": "Copper",      "category": "industrial", "unit": "USD/lb"},
    "ALI=F": {"name": "Aluminum",    "category": "industrial", "unit": "USD/lb"},
    "ZNC=F": {"name": "Zinc",        "category": "industrial", "unit": "USD/t"},
    "NI=F":  {"name": "Nickel",      "category": "industrial", "unit": "USD/t"},
    # Estaño: no hay proxy líquido en Yahoo Finance — pendiente fuente alternativa (LME directo)

    # Nuclear / Uranium (no futures on Yahoo — Cameco as proxy)
    "CCJ":   {"name": "Uranium ⚠️ proxy", "category": "nuclear",    "unit": "USD"},

    # Producer currencies (vs USD)
    "ZARUSD=X": {"name": "ZAR/USD",  "category": "currency",   "unit": "rate"},
    "AUDUSD=X": {"name": "AUD/USD",  "category": "currency",   "unit": "rate"},
    "CADUSD=X": {"name": "CAD/USD",  "category": "currency",   "unit": "rate"},
    "CLPUSD=X": {"name": "CLP/USD",  "category": "currency",   "unit": "rate"},

    # Cross currencies for multi-currency pricing
    "EURUSD=X": {"name": "EUR/USD",  "category": "fx",         "unit": "rate"},
    "GBPUSD=X": {"name": "GBP/USD",  "category": "fx",         "unit": "rate"},
}

# ── Futures curve config ───────────────────────────────────────────────────────
# exchange: Yahoo Finance exchange suffix for dated contracts (e.g. CLK26.NYM)
FUTURES_CURVE = {
    "crude_oil":   {"root": "CL", "exchange": "NYM", "months": list(range(1, 13)),    "name": "WTI Crude"},
    "nat_gas":     {"root": "NG", "exchange": "NYM", "months": list(range(1, 13)),    "name": "Nat Gas"},
    "gold":        {"root": "GC", "exchange": "CMX", "months": [2, 4, 6, 8, 10, 12], "name": "Gold"},
    "silver":      {"root": "SI", "exchange": "CMX", "months": [3, 5, 7, 9, 12],     "name": "Silver"},
    "platinum":    {"root": "PL", "exchange": "NYM", "months": [1, 4, 7, 10],        "name": "Platinum"},
    "palladium":   {"root": "PA", "exchange": "NYM", "months": [3, 6, 9, 12],        "name": "Palladium"},
    "copper":      {"root": "HG", "exchange": "CMX", "months": [3, 5, 7, 9, 12],     "name": "Copper"},
    "heating_oil": {"root": "HO", "exchange": "NYM", "months": list(range(1, 13)),    "name": "Heating Oil"},
    "gasoline":    {"root": "RB", "exchange": "NYM", "months": list(range(1, 13)),    "name": "Gasoline"},
}

# Month code mapping (futures contract letters)
MONTH_CODES = {
    1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
    7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z",
}

# ── EIA series ────────────────────────────────────────────────────────────────
EIA_SERIES = {
    "PET.WCRSTUS1.W":          {"name": "US Crude Oil Stocks",    "unit": "MBBL"},
    "PET.WGTSTUS1.W":          {"name": "US Gasoline Stocks",     "unit": "MBBL"},
    "NG.NW2_EPG0_SWO_R48_BCF.W": {"name": "US Nat Gas Storage",  "unit": "BCF"},
}

# ── COT commodity slugs ───────────────────────────────────────────────────────
# Maps CFTC market name (substring match) → our slug
COT_COMMODITIES = {
    "GOLD":          "gold",
    "SILVER":        "silver",
    "PLATINUM":      "platinum",
    "PALLADIUM":     "palladium",
    "CRUDE OIL":     "crude_oil",
    "NATURAL GAS":   "nat_gas",
    "COPPER":        "copper",
}

# ── LME metals ────────────────────────────────────────────────────────────────
LME_METALS = ["aluminium", "copper", "zinc", "nickel", "lead", "tin"]

# ── Producer currency pairs ───────────────────────────────────────────────────
CURRENCY_COMMODITY_PAIRS = {
    "gold":      ["ZARUSD=X", "AUDUSD=X"],
    "platinum":  ["ZARUSD=X"],
    "palladium": ["ZARUSD=X"],
    "copper":    ["AUDUSD=X", "CLPUSD=X"],
    "crude_oil": ["CADUSD=X"],
}

# ── Ratios ────────────────────────────────────────────────────────────────────
# alert_high / alert_low: semáforo rojo si supera/baja de esos niveles
# description: explicación para el tooltip
RATIOS = [
    {
        "name": "Gold / Silver", "num": "GC=F", "den": "SI=F", "type": "ratio",
        "alert_high": 90, "alert_low": 50,
        "description": (
            "Mide cuántas onzas de plata equivalen a una de oro. "
            "Históricamente oscila entre 40-80. "
            "Por encima de 80 la plata está barata relativa al oro (señal de compra plata). "
            "Por encima de 90 indica extremo histórico — reversion esperada."
        ),
    },
    {
        "name": "Platinum / Palladium", "num": "PL=F", "den": "PA=F", "type": "ratio",
        "alert_high": 1.5, "alert_low": 0.5,
        "description": (
            "Históricamente el platino cotizaba más caro que el paladio (ratio > 1). "
            "Desde 2017 el ratio se invirtió por demanda de catalizadores diésel vs gasolina. "
            "Un ratio < 0.6 indica paladio excepcionalmente caro frente al platino."
        ),
    },
    {
        "name": "Platinum / Gold", "num": "PL=F", "den": "GC=F", "type": "ratio",
        "alert_high": 1.2, "alert_low": 0.6,
        "description": (
            "El platino históricamente cotizaba por encima del oro (ratio > 1). "
            "Actualmente está muy por debajo (ratio ~0.7), anomalía histórica. "
            "Un ratio < 0.65 indica platino extremadamente barato vs oro."
        ),
    },
    {
        "name": "Copper / Gold", "num": "HG=F", "den": "GC=F", "type": "ratio",
        "alert_high": None, "alert_low": None,
        "description": (
            "Indicador macroeconómico: el cobre sube con el ciclo industrial, "
            "el oro sube con el miedo. Ratio al alza = economía fuerte. "
            "Ratio a la baja = señal de ralentización o recesión."
        ),
    },
    {
        "name": "Brent − WTI spread", "num": "BZ=F", "den": "CL=F", "type": "spread",
        "alert_high": 10, "alert_low": -2,
        "description": (
            "Diferencia de precio entre Brent (referencia europea/global) "
            "y WTI (referencia EEUU). Normalmente Brent > WTI (prima de calidad y logística). "
            "Un spread > $10 indica tensión en el mercado global o problemas logísticos en EEUU."
        ),
    },
]
