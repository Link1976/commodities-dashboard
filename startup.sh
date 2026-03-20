#!/bin/bash
# startup.sh — inicializa DB y fetcha datos antes de arrancar el dashboard

set -e

echo "[startup] Inicializando base de datos..."
python -c "from db.schema import init_db; init_db()"

echo "[startup] Fetchando historial de precios (2 años)..."
python fetchers/fetch_prices.py --history 730 || echo "[startup] WARN: fetch_prices falló"
python -c "
from db.schema import get_conn
conn = get_conn()
n = conn.execute('SELECT COUNT(*) FROM spot_prices').fetchone()[0]
print(f'[startup] spot_prices rows en DB: {n}')
conn.close()
"

echo "[startup] Fetchando rhodio..."
python fetchers/fetch_rhodium.py || echo "[startup] WARN: fetch_rhodium falló"

echo "[startup] Fetchando inventarios EIA..."
python fetchers/fetch_eia.py || echo "[startup] WARN: fetch_eia falló"

echo "[startup] Fetchando COT..."
python fetchers/fetch_cot.py || echo "[startup] WARN: fetch_cot falló"

echo "[startup] Fetchando stocks LME..."
python fetchers/fetch_lme.py || echo "[startup] WARN: fetch_lme falló"

echo "[startup] Arrancando dashboard..."
exec python dashboard/app.py
