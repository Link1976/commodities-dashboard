"""Tab 1 — Overview: movers strip + spot prices table + ratio cards."""
from datetime import date
from dash import html, dash_table, Input, Output, callback
import dash_bootstrap_components as dbc
from dash import dcc

from db.queries import (
    get_latest_prices, get_pct_change, get_ytd_change,
    get_fx_rate, get_price_on_date, get_52w_range, get_ma,
)
from config import RATIOS

# ── Category order & labels ───────────────────────────────────────────────────
CATEGORY_ORDER = ["precious", "pgm", "energy", "carbon", "industrial", "nuclear", "currency"]
CATEGORY_LABELS = {
    "precious":   "Metales Preciosos",
    "pgm":        "PGMs",
    "energy":     "Energía",
    "carbon":     "Carbón ⚠️ proxy",
    "industrial": "Metales Industriales",
    "nuclear":    "Nuclear / Uranium ⚠️ proxy",
    "currency":   "Divisas Productoras",
}

# Left-border accent color per category (for visual grouping in table)
CATEGORY_COLORS = {
    "Metales Preciosos":          "#f1c40f",
    "PGMs":                       "#bdc3c7",
    "Energía":                    "#e67e22",
    "Carbón ⚠️ proxy":            "#7f8c8d",
    "Metales Industriales":       "#3498db",
    "Nuclear / Uranium ⚠️ proxy": "#1abc9c",
}

ALERT_1D_YELLOW = 2.0
ALERT_1D_RED    = 4.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(val, suffix=""):
    return f"{val:+.2f}{suffix}" if val is not None else "—"


def _semaphore_color(val, yellow=ALERT_1D_YELLOW, red=ALERT_1D_RED):
    if val is None:
        return "#555"
    if abs(val) >= red:
        return "#e74c3c"
    if abs(val) >= yellow:
        return "#f39c12"
    return "#2ecc71" if val > 0 else "#95a5a6"


def _change_bg(_val):
    """No background tint on % cells — text color is enough."""
    return "transparent"


def _ratio_semaphore(value, alert_high, alert_low):
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
    html.Div(id="movers-strip", style={"marginBottom": "12px"}),
    dbc.Row(
        dbc.Col(html.Div(id="prices-table"), xs=12),
        style={"marginBottom": "16px"},
    ),
    dbc.Row(
        dbc.Col(html.Div(id="ratio-cards"), xs=12),
    ),
], style={"padding": "8px"})


# ── Data layer ────────────────────────────────────────────────────────────────

def _52w_color(pos):
    """Color for 52W position: green = near low (cheap), red = near high (expensive)."""
    if pos is None:
        return "#555"
    if pos <= 20:
        return "#2ecc71"   # near annual low → potentially cheap
    if pos >= 80:
        return "#e74c3c"   # near annual high → potentially expensive
    if pos <= 35:
        return "#27ae60"
    if pos >= 65:
        return "#c0392b"
    return "#94a3b8"       # mid-range → neutral


def _ma200_color(pct):
    """Color for vs MA200: green = well below (cheap), red = extended above."""
    if pct is None:
        return "#555"
    if pct <= -15:
        return "#2ecc71"   # significantly below MA200 → potentially undervalued
    if pct >= 20:
        return "#e74c3c"   # significantly above MA200 → extended / overvalued
    if pct <= -5:
        return "#27ae60"
    if pct >= 10:
        return "#c0392b"
    return "#94a3b8"       # near MA200 → neutral


def _get_rows():
    """Query DB and return enriched row list (includes hidden _fields)."""
    prices = get_latest_prices()

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

        # Valuation indicators
        low52, high52 = get_52w_range(ticker)
        if low52 is not None and high52 is not None and high52 > low52:
            pos52 = round((close - low52) / (high52 - low52) * 100, 1)
        else:
            pos52 = None

        ma200 = get_ma(ticker, 200)
        vs_ma200 = round((close - ma200) / ma200 * 100, 1) if ma200 else None

        rows.append({
            "Categoría":  CATEGORY_LABELS.get(p["category"], p["category"]),
            "Nombre":     p["name"],
            "Precio USD": f"{close:,.2f}",
            "1D %":       _fmt(d1,  "%"),
            "1W %":       _fmt(d7,  "%"),
            "1M %":       _fmt(d30, "%"),
            "YTD %":      _fmt(ytd, "%"),
            "52S %":      f"{pos52:.0f}%" if pos52 is not None else "—",
            "vs MA200":   _fmt(vs_ma200, "%"),
            "_d1": d1, "_d7": d7, "_d30": d30, "_ytd": ytd,
            "_pos52": pos52, "_vs_ma200": vs_ma200,
            "_cat": p["category"],
        })

    rows.sort(key=lambda r: (
        CATEGORY_ORDER.index(
            next((k for k, v in CATEGORY_LABELS.items() if v == r["Categoría"]), "industrial")
        ),
        r["Nombre"]
    ))
    return rows


# ── Movers strip ──────────────────────────────────────────────────────────────

def build_movers_strip(rows):
    valid_d1  = [(r["Nombre"], r["_d1"])  for r in rows if r["_d1"]  is not None]
    valid_ytd = [(r["Nombre"], r["_ytd"]) for r in rows if r["_ytd"] is not None]

    best_d1   = max(valid_d1,  key=lambda x: x[1])  if valid_d1  else None
    worst_d1  = min(valid_d1,  key=lambda x: x[1])  if valid_d1  else None
    best_ytd  = max(valid_ytd, key=lambda x: x[1])  if valid_ytd else None
    worst_ytd = min(valid_ytd, key=lambda x: x[1])  if valid_ytd else None

    def card(icon, label, name, val, color):
        return html.Div([
            html.Div(f"{icon} {label}", style={
                "color": "#4b5563", "fontSize": "10px",
                "textTransform": "uppercase", "letterSpacing": "0.8px",
                "marginBottom": "4px",
            }),
            html.Div(name or "—", style={
                "color": "#94a3b8", "fontSize": "13px", "fontWeight": "600",
                "marginBottom": "2px", "whiteSpace": "nowrap",
                "overflow": "hidden", "textOverflow": "ellipsis",
            }),
            html.Div(f"{val:+.2f}%" if val is not None else "—", style={
                "color": color, "fontSize": "18px", "fontWeight": "700",
            }),
        ], style={
            "backgroundColor": "#1f2937",
            "border": "1px solid #2d3748",
            "borderTop": f"3px solid {color}",
            "borderRadius": "6px",
            "padding": "10px 14px",
            "flex": "1 1 130px",
            "minWidth": "120px",
        })

    return html.Div([
        card("▲", "Mayor subida hoy",
             best_d1[0]  if best_d1  else None,
             best_d1[1]  if best_d1  else None, "#2ecc71"),
        card("▼", "Mayor caída hoy",
             worst_d1[0] if worst_d1 else None,
             worst_d1[1] if worst_d1 else None, "#e74c3c"),
        card("▲", "Mejor YTD",
             best_ytd[0]  if best_ytd  else None,
             best_ytd[1]  if best_ytd  else None, "#3498db"),
        card("▼", "Peor YTD",
             worst_ytd[0] if worst_ytd else None,
             worst_ytd[1] if worst_ytd else None, "#e67e22"),
    ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap"})


# ── Prices table ──────────────────────────────────────────────────────────────

def build_prices_table(rows):
    visible = ["Nombre", "Precio USD", "1D %", "1W %", "1M %", "YTD %", "52S %", "vs MA200"]

    style_data_conditional = []

    for i, row in enumerate(rows):
        # Left border accent by category
        cat_color = CATEGORY_COLORS.get(row["Categoría"], "#2a2a4a")
        style_data_conditional.append({
            "if": {"row_index": i},
            "borderLeft": f"3px solid {cat_color}",
        })

        # % change: color only
        for field, col in [("_d1", "1D %"), ("_d7", "1W %"), ("_d30", "1M %"), ("_ytd", "YTD %")]:
            val = row.get(field)
            style_data_conditional.append({
                "if": {"row_index": i, "column_id": col},
                "color": _semaphore_color(val),
                "fontWeight": "700" if val is not None and abs(val) >= ALERT_1D_YELLOW else "normal",
            })

        # Valuation indicators
        style_data_conditional.append({
            "if": {"row_index": i, "column_id": "52S %"},
            "color": _52w_color(row.get("_pos52")),
            "fontWeight": "700",
        })
        style_data_conditional.append({
            "if": {"row_index": i, "column_id": "vs MA200"},
            "color": _ma200_color(row.get("_vs_ma200")),
            "fontWeight": "700",
        })

        # Alternate row background for readability
        if i % 2 == 0:
            style_data_conditional.append({
                "if": {"row_index": i},
                "backgroundColor": "#1a2535",
            })

    return dash_table.DataTable(
        data=[{k: v for k, v in r.items() if not k.startswith("_")} for r in rows],
        columns=[{"name": c, "id": c} for c in visible],
        fixed_rows={"headers": True},
        fixed_columns={"headers": True, "data": 1},
        style_table={
            "overflowX": "auto",
            "overflowY": "auto",
            "maxHeight": "calc(100vh - 260px)",
            "minWidth": "100%",
            "borderRadius": "6px",
            "border": "1px solid #2d3748",
        },
        style_header={
            "backgroundColor": "#1a2535",
            "color": "#64748b",
            "fontWeight": "700",
            "border": "1px solid #2d3748",
            "fontSize": "11px",
            "textTransform": "uppercase",
            "letterSpacing": "0.6px",
            "padding": "10px 12px",
        },
        style_cell={
            "backgroundColor": "#111827",
            "color": "#cbd5e1",
            "border": "1px solid #1e293b",
            "fontSize": "13px",
            "padding": "9px 12px",
            "textAlign": "right",
            "minWidth": "72px",
        },
        style_cell_conditional=[
            {"if": {"column_id": "Nombre"},
             "textAlign": "left", "fontWeight": "600",
             "minWidth": "110px", "width": "110px", "maxWidth": "140px",
             "color": "#f1f5f9"},
            {"if": {"column_id": "Precio USD"},
             "fontFamily": "monospace", "color": "#e2e8f0"},
        ],
        style_data_conditional=style_data_conditional,
        page_size=50,
        sort_action="native",
        tooltip_header={
            "1D %":    "Cambio porcentual en el último día",
            "1W %":    "Cambio porcentual en los últimos 7 días",
            "1M %":    "Cambio porcentual en los últimos 30 días",
            "YTD %":   "Cambio porcentual desde el 1 de enero",
            "52S %":   "Posición en el rango anual (0% = mínimo del año, 100% = máximo). Verde < 25% (cerca de mínimos, potencialmente barato). Rojo > 75% (cerca de máximos, potencialmente caro).",
            "vs MA200":"Desviación respecto a la media móvil de 200 días. Muy negativo = precio por debajo de tendencia de largo plazo (potencialmente infravaluado). Muy positivo = extendido sobre tendencia.",
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

        emoji, sem_color = _ratio_semaphore(value, r.get("alert_high"), r.get("alert_low"))
        description = r.get("description", "")

        cards.append(html.Div([
            # Top accent bar
            html.Div(style={
                "height": "3px",
                "backgroundColor": sem_color,
                "borderRadius": "4px 4px 0 0",
                "margin": "-12px -12px 10px -12px",
            }),
            html.Div([
                html.Span(emoji, style={"fontSize": "14px", "marginRight": "5px"}),
                html.Span(r["name"], style={
                    "color": "#64748b", "fontSize": "11px", "fontWeight": "700",
                    "textTransform": "uppercase", "letterSpacing": "0.5px",
                }),
            ], style={"marginBottom": "6px"}),
            html.Div(val_str, style={
                "color": sem_color, "fontWeight": "700",
                "fontSize": "22px", "marginBottom": "8px",
                "fontFamily": "monospace",
            }),
            html.P(description, style={
                "color": "#475569", "fontSize": "11px",
                "marginBottom": "0", "lineHeight": "1.45",
            }),
        ], style={
            "backgroundColor": "#1f2937",
            "border": "1px solid #2d3748",
            "borderRadius": "6px",
            "padding": "12px",
            "flex": "1 1 200px",
            "minWidth": "180px",
            "maxWidth": "300px",
        }))

    return html.Div(cards, style={
        "display": "flex", "flexWrap": "wrap", "gap": "8px",
    })


# ── Callback ──────────────────────────────────────────────────────────────────

@callback(
    Output("movers-strip",  "children"),
    Output("prices-table",  "children"),
    Output("ratio-cards",   "children"),
    Input("auto-refresh",   "n_intervals"),
    Input("main-tabs",      "active_tab"),
    Input("manual-refresh-ts", "data"),
)
def update_overview(_, active_tab, refresh_ts):
    try:
        rows   = _get_rows()
        movers = build_movers_strip(rows)
        table  = build_prices_table(rows)
        print(f"[overview] OK: {len(rows)} filas")
    except Exception as e:
        import traceback
        traceback.print_exc()
        movers = html.Div()
        table  = html.P(f"Error cargando tabla: {e}", style={"color": "red"})
    try:
        ratios = build_ratio_cards()
    except Exception as e:
        print(f"[overview] ERROR ratios: {e}")
        ratios = html.P(f"Error ratios: {e}", style={"color": "red"})
    return movers, table, ratios
