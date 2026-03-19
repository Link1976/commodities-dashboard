"""Tab 1 — Overview: spot prices table + ratio indicators."""
from dash import html, dash_table, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc

from db.queries import (
    get_latest_prices, get_pct_change, get_ytd_change,
    get_fx_rate, get_price_on_date,
)
from config import RATIOS

# ── Category display order and labels ────────────────────────────────────────
CATEGORY_ORDER = ["precious", "pgm", "energy", "industrial", "currency"]
CATEGORY_LABELS = {
    "precious":   "Precious Metals",
    "pgm":        "PGMs",
    "energy":     "Energy",
    "industrial": "Industrial Metals",
    "currency":   "Producer Currencies",
}

# ── Layout ────────────────────────────────────────────────────────────────────
layout = html.Div([
    dbc.Row([
        # Prices table
        dbc.Col(html.Div(id="prices-table"), width=8),
        # Ratio indicators
        dbc.Col(html.Div(id="ratio-cards"), width=4),
    ]),
], style={"padding": "8px"})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _arrow(val):
    if val is None:
        return ""
    return "▲" if val > 0 else "▼"


def _fmt(val, suffix=""):
    if val is None:
        return "—"
    return f"{val:+.2f}{suffix}"


def _color(val):
    if val is None:
        return "#888"
    return "#2ecc71" if val > 0 else "#e74c3c"


def build_prices_table():
    prices = get_latest_prices()
    eur_rate = get_fx_rate("EURUSD=X") or 1
    gbp_rate = get_fx_rate("GBPUSD=X") or 1

    rows = []
    for p in prices:
        if p["category"] in ("fx", "currency"):
            continue
        ticker = p["ticker"]
        close  = p["close"]
        d1  = get_pct_change(ticker, 1)
        d7  = get_pct_change(ticker, 7)
        d30 = get_pct_change(ticker, 30)
        ytd = get_ytd_change(ticker)
        rows.append({
            "Categoría":  CATEGORY_LABELS.get(p["category"], p["category"]),
            "Nombre":     p["name"],
            "Precio USD": f"{close:,.2f}",
            "1D %":       _fmt(d1, "%"),
            "1W %":       _fmt(d7, "%"),
            "1M %":       _fmt(d30, "%"),
            "YTD %":      _fmt(ytd, "%"),
            "EUR":        f"{close / eur_rate:,.2f}" if eur_rate else "—",
            "GBP":        f"{close / gbp_rate:,.2f}" if gbp_rate else "—",
            "_d1":        d1,   # hidden for conditional formatting
            "_d7":        d7,
            "_ytd":       ytd,
        })

    # Sort by category order
    rows.sort(key=lambda r: (
        CATEGORY_ORDER.index(
            next((k for k, v in CATEGORY_LABELS.items() if v == r["Categoría"]),
                 "industrial")
        ),
        r["Nombre"]
    ))

    visible_cols = ["Categoría", "Nombre", "Precio USD",
                    "1D %", "1W %", "1M %", "YTD %", "EUR", "GBP"]

    style_data_conditional = []
    for i, row in enumerate(rows):
        for field, col in [("_d1", "1D %"), ("_d7", "1W %"), ("_ytd", "YTD %")]:
            val = row.get(field)
            if val is not None:
                color = "#2ecc71" if val > 0 else "#e74c3c"
                style_data_conditional.append({
                    "if": {"row_index": i, "column_id": col},
                    "color": color,
                    "fontWeight": "bold",
                })

    return dash_table.DataTable(
        data=[{k: v for k, v in r.items() if not k.startswith("_")} for r in rows],
        columns=[{"name": c, "id": c} for c in visible_cols],
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#16213e",
            "color": "#a0a0b0",
            "fontWeight": "600",
            "border": "1px solid #2a2a4a",
            "fontSize": "12px",
        },
        style_cell={
            "backgroundColor": "#0f3460",
            "color": "#e0e0e0",
            "border": "1px solid #1a1a3e",
            "fontSize": "13px",
            "padding": "8px 12px",
            "textAlign": "right",
        },
        style_cell_conditional=[
            {"if": {"column_id": c}, "textAlign": "left"}
            for c in ["Categoría", "Nombre"]
        ],
        style_data_conditional=style_data_conditional,
        page_size=25,
        sort_action="native",
    )


def build_ratio_cards():
    cards = []
    for r in RATIOS:
        p_num = get_price_on_date(r["num"], str(__import__("datetime").date.today()))
        p_den = get_price_on_date(r["den"], str(__import__("datetime").date.today()))

        if p_num is None or p_den is None or p_den == 0:
            value_str = "—"
            color = "#888"
        elif r["type"] == "spread":
            val = p_num - p_den
            value_str = f"{val:+.2f}"
            color = "#2ecc71" if val > 0 else "#e74c3c"
        else:
            val = p_num / p_den
            value_str = f"{val:.3f}"
            color = "#e0e0e0"

        cards.append(
            dbc.Card(
                dbc.CardBody([
                    html.P(r["name"], style={
                        "color": "#a0a0b0", "fontSize": "12px",
                        "marginBottom": "4px", "fontWeight": "600",
                    }),
                    html.H4(value_str, style={
                        "color": color, "fontWeight": "700",
                        "marginBottom": "0",
                    }),
                ]),
                style={
                    "backgroundColor": "#16213e",
                    "border": "1px solid #2a2a4a",
                    "marginBottom": "8px",
                },
            )
        )
    return html.Div(cards)


# ── Callbacks ─────────────────────────────────────────────────────────────────

@callback(
    Output("prices-table", "children"),
    Output("ratio-cards", "children"),
    Input("auto-refresh", "n_intervals"),
)
def update_overview(_):
    return build_prices_table(), build_ratio_cards()
