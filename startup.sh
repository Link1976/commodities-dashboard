#!/bin/bash
# startup.sh — inicializa DB y arranca el dashboard
# El fetch de datos históricos lo gestiona el hilo de fondo en app.py

set -e

echo "[startup] Inicializando base de datos..."
python -c "from db.schema import init_db; init_db()"

echo "[startup] Arrancando dashboard..."
exec python dashboard/app.py
