"""
app.py — Commodities Dashboard entry point
Run: conda activate cartera && python dashboard/app.py
Open: http://127.0.0.1:8050
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

from dashboard.layout import build_layout

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
    title="Commodities Dashboard",
)
app.layout = build_layout()

# Import pages so their callbacks are registered
from dashboard.pages import overview, term_structure, history, cot  # noqa: F401

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
