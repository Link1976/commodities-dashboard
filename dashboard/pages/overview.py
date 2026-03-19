"""Tab 1 — Overview: spot prices table + ratio cards con semáforos y explicaciones."""
from datetime import date
from dash import html, dash_table, Input, Output, callback
import dash_bootstrap_components as dbc
from dash import dcc

from db.queries import (
    get_latest_prices, get_pct_change, get_ytd_change,
    get_fx_rate, get_price_on_date,
)
from config import RATIOS

# ── Category display order ────────────────────────────────────────────────────
CATEGORY_ORDER  = ["precious", "pgm", "energy", "industrial", "currency"]
CATEGORY_LABELS = {
    "precious":   "Metales Preciosos",
    "pgm":        "PGMs",
    "energy":     "Energía",
    "industrial": "Metales Industriales",
    "currency":   "Divisas Productoras",
}

# ── Semaphore thresholds for % changes ───────────────────────────────────────
# (abs value of 1D change that triggers yellow/red alert in table)
ALERT_1D_YELLOW = 2.0   # ±2% in one day → yellow
ALERT_1D_RED    = 4.0   # ±4% in one day → red


def _fmt(val, suffix=""):
    return f"{val:+.2f}{suffix}" if val is not None else "—"


def _semaphore_color(val, yellow_threshold=ALERT_1D_YELLOW, red_threshold=ALERT_1D_RED):
    """Return color for a % change value."""
    if val is None:
        return "#888"
    if abs(val) >= red_threshold:
        return "#e74c3c"
    if abs(val) >= yellow_threshold:
        return "#f39c12"
    return "#2ecc71" if val > 0 else "#95a5a6"


def _ratio_semaphore(value, alert_high, alert_low):
    """
    🟢 normal  🟡 cerca del extremo  🔴 en extremo
    Returns (emoji, color)
    """
    if value is None:
        return "⚪", "#888"
    triggered_high = alert_high is not None and value >= alert_high
    triggered_low  = alert_low  is not None and value <= alert_low
    near_high = alert_high is not None and value >= alert_high * 0.9
    near_low  = alert_low  is not None and alert_low > 0 and value <= alert_low * 1.1

    if triggered_high or triggered_low:
        return "🔴", "#e74c3c"
    if near_high or near_low:
        return "🟡", "#f39c12"
    return "🟢", "#2ecc71"


# ── Layout ────────────────────────────────────────────────────────────────────
layout = html.Div([
    dbc.Row([
        dbc.Col(html.Div(id="prices-table"), width=8),
        dbc.Col(html.Div(id="ratio-cards"),  width=4),
    ]),
], style={"padding": "8px"})


# ── Prices table ──────────────────────────────────────────────────────────────

def build_prices_table():
    prices   = get_latest_prices()
    eur_rate = get_fx_rate("EURUSD=X") or 1
    gbp_rate = get_fx_rate("GBPUSD=X") or 1
    today    = str(date.today())

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
            "EUR":        f"{close / eur_rate:,.2f}",
            "GBP":        f"{close / gbp_rate:,.2f}",
            "_d1": d1, "_d7": d7, "_ytd": ytd,
        })

    rows.sort(key=lambda r: (
        CATEGORY_ORDER.index(
            next((k for k, v in CATEGORY_LABELS.items() if v == r["Categoría"]),
                 "industrial")
        ),
        r["Nombre"]
    ))

    visible = ["Categoría", "Nombre", "Precio USD",
               "1D %", "1W %", "1M %", "YTD %", "EUR", "GBP"]

    # Conditional formatting: color + weight by magnitude
    style_data_conditional = []
    for i, row in enumerate(rows):
        for field, col in [("_d1", "1D %"), ("_d7", "1W %"), ("_ytd", "YTD %")]:
            val = row.get(field)
            color = _semaphore_color(val)
            style_data_conditional.append({
                "if": {"row_index": i, "column_id": col},
                "color": color,
                "fontWeight": "bold" if val is not None and abs(val) >= ALERT_1D_YELLOW else "normal",
            })

    return dash_table.DataTable(
        data=[{k: v for k, v in r.items() if not k.startswith("_")} for r in rows],
        columns=[{"name": c, "id": c} for c in visible],
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#16213e", "color": "#a0a0b0",
            "fontWeight": "600", "border": "1px solid #2a2a4a", "fontSize": "12px",
        },
        style_cell={
            "backgroundColor": "#0f3460", "color": "#e0e0e0",
            "border": "1px solid #1a1a3e", "fontSize": "13px",
            "padding": "8px 12px", "textAlign": "right",
        },
        style_cell_conditional=[
            {"if": {"column_id": c}, "textAlign": "left"}
            for c in ["Categoría", "Nombre"]
        ],
        style_data_conditional=style_data_conditional,
        page_size=30,
        sort_action="native",
        tooltip_header={
            "1D %":  "Cambio porcentual en el último día",
            "1W %":  "Cambio porcentual en los últimos 7 días",
            "1M %":  "Cambio porcentual en los últimos 30 días",
            "YTD %": "Cambio porcentual desde el 1 de enero",
            "EUR":   "Precio convertido a EUR al tipo de cambio actual",
            "GBP":   "Precio convertido a GBP al tipo de cambio actual",
        },
        tooltip_delay=0,
        tooltip_duration=None,
    )


# ── Ratio cards ───────────────────────────────────────────────────────────────

def build_ratio_cards():
    today = str(date.today())
    cards = []

    for r in RATIOS:
        p_num = get_price_on_date(r["num"], today)
        p_den = get_price_on_date(r["den"], today)

        if p_num is None or p_den is None or p_den == 0:
            value   = None
            val_str = "—"
        elif r["type"] == "spread":
            value   = p_num - p_den
            val_str = f"{value:+.2f} $"
        else:
            value   = p_num / p_den
            val_str = f"{value:.3f}"

        emoji, sem_color = _ratio_semaphore(
            value,
            r.get("alert_high"),
            r.get("alert_low"),
        )

        description = r.get("description", "")

        cards.append(
            dbc.Card(
                dbc.CardBody([
                    # Header: semáforo + nombre
                    html.Div([
                        html.Span(emoji, style={"fontSize": "16px", "marginRight": "6px"}),
                        html.Span(r["name"], style={
                            "color": "#a0a0b0", "fontSize": "12px", "fontWeight": "600",
                        }),
                    ], style={"marginBottom": "4px"}),

                    # Valor
                    html.H4(val_str, style={
                        "color": sem_color, "fontWeight": "700", "marginBottom": "8px",
                    }),

                    # Explicación
                    html.P(description, style={
                        "color": "#7a7a9a", "fontSize": "11px",
                        "marginBottom": "0", "lineHeight": "1.4",
                    }),
                ]),
                style={
                    "backgroundColor": "#16213e",
                    "border": f"1px solid {sem_color if sem_color != '#2ecc71' else '#2a2a4a'}",
                    "marginBottom": "8px",
                },
            )
        )

    return html.Div(cards)


# ── Callback ──────────────────────────────────────────────────────────────────

@callback(
    Output("prices-table", "children"),
    Output("ratio-cards",  "children"),
    Input("auto-refresh",  "n_intervals"),
)
def update_overview(_):
    return build_prices_table(), build_ratio_cards()
