"""Tab 2 — Futures term structure (contango / backwardation)."""
import re
from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from db.queries import get_futures_curve, get_curve_dates
from config import FUTURES_CURVE, MONTH_CODES

COMMODITY_OPTIONS = [
    {"label": cfg["name"], "value": key}
    for key, cfg in FUTURES_CURVE.items()
]

# Reverse month code lookup: letter → month name
_CODE_TO_MONTH = {v: k for k, v in MONTH_CODES.items()}
_MONTH_NAMES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

_INFO = """
**Curva de futuros (Term Structure)**
Cada punto es un contrato con vencimiento distinto. Pasa el cursor para ver el precio exacto.

- 📈 **Contango** (curva ascendente): futuro > spot → oferta abundante, coste de almacenamiento.
- 📉 **Backwardation** (curva descendente): futuro < spot → escasez física, prima por entrega inmediata.
"""


def ticker_to_label(ticker: str) -> str:
    """CLK26.NYM → 'May 26'"""
    m = re.match(r"[A-Z]+([A-Z])(\d{2})", ticker)
    if not m:
        return ticker
    code, yy = m.group(1), m.group(2)
    month_num = _CODE_TO_MONTH.get(code)
    if month_num is None:
        return ticker
    return f"{_MONTH_NAMES[month_num]} {yy}"


layout = html.Div([
    # Info panel
    dbc.Row(dbc.Col(
        dbc.Alert(
            dcc.Markdown(_INFO, style={"fontSize": "12px", "marginBottom": "0"}),
            color="dark",
            style={"backgroundColor": "#1f2937", "border": "1px solid #2d3748",
                   "padding": "10px 16px", "marginBottom": "12px"},
        )
    )),

    # Controls — responsive
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id="curve-commodity",
                options=COMMODITY_OPTIONS,
                value="crude_oil",
                clearable=False,
                style={"backgroundColor": "#1f2937", "color": "#000"},
            ),
            xs=12, md=4, style={"marginBottom": "8px"},
        ),
        dbc.Col(
            html.Div([
                html.Label("Snapshot histórico:",
                           style={"color": "#94a3b8", "fontSize": "12px",
                                  "marginBottom": "4px", "display": "block"}),
                dcc.Dropdown(
                    id="curve-date-dropdown",
                    placeholder="Hoy (último disponible)",
                    clearable=True,
                    style={"backgroundColor": "#1f2937", "color": "#000"},
                ),
            ]),
            xs=12, md=4, style={"marginBottom": "8px"},
        ),
    ], style={"marginBottom": "8px"}),

    # Chart + table — stack on mobile
    dbc.Row([
        dbc.Col(dcc.Graph(id="curve-chart",
                          style={"height": "420px"},
                          config={"displayModeBar": False}),
                xs=12, md=8),
        dbc.Col(html.Div(id="curve-table",
                         style={"overflowX": "auto"}),
                xs=12, md=4),
    ]),
], style={"padding": "8px"})


def build_curve_chart(commodity: str, on_date: str = None):
    data = get_futures_curve(commodity, on_date)

    if not data:
        fig = go.Figure()
        fig.update_layout(
            title="Sin datos de curva — ejecuta fetch_prices primero",
            **_dark_layout(),
        )
        return fig

    labels = [ticker_to_label(d["ticker"]) for d in data]
    prices = [d["price"] for d in data]
    tickers = [d["ticker"] for d in data]

    is_backwardation = prices[-1] < prices[0]
    slope_color = "#2ecc71" if is_backwardation else "#e74c3c"
    label = "Backwardation ▼ (escasez)" if is_backwardation else "Contango ▲ (oferta abundante)"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels,
        y=prices,
        mode="lines+markers",
        line={"color": slope_color, "width": 3},
        marker={"size": 10, "color": slope_color,
                "line": {"color": "#fff", "width": 1}},
        customdata=[[t, p] for t, p in zip(tickers, prices)],
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Precio: $%{y:,.2f}<br>"
            "Ticker: %{customdata[0]}<extra></extra>"
        ),
    ))

    # Horizontal reference line at M1 price
    fig.add_hline(
        y=prices[0], line_dash="dot",
        line_color="#888", line_width=1,
        annotation_text=f"M1 ${prices[0]:,.1f}",
        annotation_font_color="#888",
    )

    snap = f" | Snapshot: {on_date}" if on_date else " | Último disponible"
    name = FUTURES_CURVE.get(commodity, {}).get("name", commodity)
    fig.update_layout(
        title=f"{name} — {label}{snap}",
        xaxis_title="Vencimiento",
        yaxis_title="Precio (USD)",
        **_dark_layout(),
    )
    return fig


def build_curve_table(commodity: str, on_date: str = None):
    data = get_futures_curve(commodity, on_date)
    if not data:
        return html.P("Sin datos", style={"color": "#888", "fontSize": "13px"})

    base_price = data[0]["price"]

    header = html.Tr([
        html.Th(c, style={"color": "#94a3b8", "fontSize": "11px",
                           "padding": "6px 8px", "whiteSpace": "nowrap"})
        for c in ["Venc.", "Precio", "vs 1er contrato"]
    ])
    rows = []
    for d in data:
        label = ticker_to_label(d["ticker"])
        diff = d["price"] - base_price
        diff_str = f"{diff:+.2f}" if diff != 0 else "—"
        diff_color = "#e74c3c" if diff > 0 else "#2ecc71" if diff < 0 else "#888"
        rows.append(html.Tr([
            html.Td(label,
                    style={"color": "#cbd5e1", "padding": "6px 8px",
                           "fontWeight": "600", "fontSize": "13px"}),
            html.Td(f"${d['price']:,.2f}",
                    style={"color": "#cbd5e1", "padding": "6px 8px", "fontSize": "13px"}),
            html.Td(diff_str,
                    style={"color": diff_color, "padding": "6px 8px",
                           "fontWeight": "700", "fontSize": "13px"}),
        ]))

    return html.Table(
        [html.Thead(header), html.Tbody(rows)],
        style={"width": "100%", "borderCollapse": "collapse",
               "backgroundColor": "#1f2937", "borderRadius": "6px"},
    )


def _dark_layout():
    return dict(
        paper_bgcolor="#111827",
        plot_bgcolor="#1f2937",
        font={"color": "#cbd5e1"},
        xaxis={"gridcolor": "#2d3748", "zerolinecolor": "#374151"},
        yaxis={"gridcolor": "#2d3748", "zerolinecolor": "#374151"},
        margin={"t": 60, "b": 40, "l": 60, "r": 20},
    )


@callback(
    Output("curve-date-dropdown", "options"),
    Output("curve-date-dropdown", "value"),
    Input("curve-commodity", "value"),
    Input("auto-refresh", "n_intervals"),
    Input("main-tabs", "active_tab"),
    Input("manual-refresh-ts", "data"),
)
def update_date_options(commodity, _, active_tab, refresh_ts):
    dates = get_curve_dates(commodity)
    options = [{"label": d, "value": d} for d in dates]
    return options, None   # None = latest


@callback(
    Output("curve-chart", "figure"),
    Output("curve-table", "children"),
    Input("curve-commodity", "value"),
    Input("curve-date-dropdown", "value"),
    Input("auto-refresh", "n_intervals"),
    Input("main-tabs", "active_tab"),
    Input("manual-refresh-ts", "data"),
)
def update_curve(commodity, on_date, _, active_tab, refresh_ts):
    return build_curve_chart(commodity, on_date), build_curve_table(commodity, on_date)
