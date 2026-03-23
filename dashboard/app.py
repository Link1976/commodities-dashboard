"""
app.py — Commodities Dashboard entry point
Run: conda activate cartera && python dashboard/app.py
Open: http://127.0.0.1:8050
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

from dashboard.layout import build_layout


def _needs_history():
    """True si la DB no tiene suficiente historia de precios (menos de 20 días de Gold)."""
    try:
        from db.queries import get_price_series
        rows = get_price_series("GC=F", days=30)
        return len(rows) < 20
    except Exception:
        return True


def _needs_cot_history():
    """True si la DB no tiene suficiente historia COT (menos de 50 semanas de Gold)."""
    try:
        from db.queries import get_cot_series
        rows = get_cot_series("gold", weeks=52)
        return len(rows) < 40
    except Exception:
        return True


def _background_fetch():
    """Fetchea datos en background: historia completa al inicio, luego cada 30 min."""
    time.sleep(15)  # espera a que la app arranque

    # Inicialización: historia de precios
    if _needs_history():
        try:
            print("[bg-fetch] DB sin historia de precios — fetcheando 365 días...")
            from fetchers.fetch_prices import fetch_history
            fetch_history(days=365)
            print("[bg-fetch] historia de precios completada")
        except Exception as e:
            print(f"[bg-fetch] error historia precios: {e}")

    # Inicialización: historia COT (3 años para que los percentiles sean útiles)
    if _needs_cot_history():
        try:
            print("[bg-fetch] DB sin historia COT — fetcheando 3 años...")
            from fetchers.fetch_cot import main as fetch_cot
            fetch_cot(history=True)
            print("[bg-fetch] historia COT completada")
        except Exception as e:
            print(f"[bg-fetch] error historia COT: {e}")

    while True:
        try:
            from fetchers.fetch_prices import main as fetch_main
            from fetchers.fetch_cot import main as fetch_cot
            print("[bg-fetch] fetch programado...")
            fetch_main()
            fetch_cot()
            print("[bg-fetch] fetch completado")
        except Exception as e:
            print(f"[bg-fetch] error: {e}")
        time.sleep(30 * 60)


# Lanza el hilo de fetch en background (una sola vez)
threading.Thread(target=_background_fetch, daemon=True, name="bg-fetch").start()


app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
    title="Commodity Pulse",
    meta_tags=[{"name": "viewport",
                "content": "width=device-width, initial-scale=1, shrink-to-fit=no"}],
)
app.layout = build_layout()

# Import pages so their callbacks are registered
from dashboard.pages import overview, term_structure, history, cot  # noqa: F401

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(debug=False, host="0.0.0.0", port=port)
