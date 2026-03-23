"""Tab 4 — COT: Commitment of Traders positioning."""
from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from db.queries import get_cot_series, get_cot_percentile, get_price_series
from config import COT_COMMODITIES

COT_OPTIONS = [
    {"label": slug.replace("_", " ").title(), "value": slug}
    for slug in COT_COMMODITIES.values()
]

PERIOD_OPTIONS = [
    {"label": "6M",  "value": 26},
    {"label": "1A",  "value": 52},
    {"label": "2A",  "value": 104},
    {"label": "3A",  "value": 156},
]

SLUG_TO_TICKER = {
    "gold":      "GC=F",
    "silver":    "SI=F",
    "platinum":  "PL=F",
    "palladium": "PA=F",
    "crude_oil": "CL=F",
    "nat_gas":   "NG=F",
    "copper":    "HG=F",
}

_INFO = """
**COT — Commitment of Traders (CFTC)**
Informe semanal del regulador de EEUU. Posicionamiento neto en contratos de futuros.

- 🔵 **Non-Commercials (especuladores)**: fondos y hedge funds — siguen tendencias.
  Posición extrema larga (índice >70%) → posible techo. Extrema corta (<30%) → señal contraria alcista.
- 🟠 **Commercials (hedgers)**: productores y consumidores reales — suelen ir a contracorriente.
"""

layout = html.Div([
    dbc.Row(dbc.Col(
        dbc.Alert(
            dcc.Markdown(_INFO, style={"fontSize": "12px", "marginBottom": "0"}),
            color="dark",
            style={"backgroundColor": "#16213e", "border": "1px solid #2a2a4a",
                   "padding": "10px 16px", "marginBottom": "12px"},
        )
    )),

    # Controls — responsive
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id="cot-commodity",
                options=COT_OPTIONS,
                value="gold",
                clearable=False,
                style={"backgroundColor": "#16213e", "color": "#000"},
            ),
            xs=12, md=4, style={"marginBottom": "8px"},
        ),
        dbc.Col(
            html.Div([
                html.Label("Período:",
                           style={"color": "#a0a0b0", "fontSize": "12px",
                                  "marginRight": "8px"}),
                dcc.RadioItems(
                    id="cot-period",
                    options=PERIOD_OPTIONS,
                    value=104,
                    inline=True,
                    labelStyle={"marginRight": "14px", "color": "#e0e0e0",
                                "fontSize": "13px"},
                ),
            ], style={"display": "flex", "alignItems": "center"}),
            xs=12, md=6, style={"marginBottom": "8px"},
        ),
        dbc.Col(
            html.Div(id="cot-percentile-badge"),
            xs=12, md=2,
            style={"display": "flex", "alignItems": "center"},
        ),
    ], style={"marginBottom": "8px"}),

    dbc.Row(dbc.Col(
        dcc.Graph(id="cot-chart",
                  style={"height": "520px"},
                  config={"displayModeBar": False}),
    )),
], style={"padding": "8px"})


def build_cot_chart(slug: str, weeks: int = 104):
    rows = get_cot_series(slug, weeks=weeks)

    if not rows:
        fig = go.Figure()
        fig.update_layout(title="Sin datos COT — ejecuta fetch_cot primero",
                          **_dark_layout())
        return fig

    dates       = [r["report_date"]  for r in rows]
    noncomm_net = [r["noncomm_net"] or 0 for r in rows]
    comm_net    = [r["comm_net"]    or 0 for r in rows]

    # Spot price — limit to same date range as COT
    ticker = SLUG_TO_TICKER.get(slug)
    price_dates, price_vals = [], []
    if ticker and dates:
        price_rows = get_price_series(ticker, days=weeks * 7)
        price_rows = [r for r in price_rows if r["date"] >= dates[0]]
        price_dates = [r["date"]  for r in price_rows]
        price_vals  = [r["close"] for r in price_rows]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.45],
        vertical_spacing=0.06,
        subplot_titles=["Posición neta (contratos)", "Precio spot"],
    )

    # Non-commercial — line, filled area to zero
    fig.add_trace(go.Scatter(
        x=dates, y=noncomm_net,
        mode="lines",
        name="No-Comerciales (especuladores)",
        line={"color": "#2ecc71", "width": 2},
        fill="tozeroy",
        fillcolor="rgba(46,204,113,0.12)",
        hovertemplate="%{x}<br>%{y:,.0f} contratos<extra>Especuladores</extra>",
    ), row=1, col=1)

    # Commercial — line
    fig.add_trace(go.Scatter(
        x=dates, y=comm_net,
        mode="lines",
        name="Comerciales (hedgers)",
        line={"color": "#e67e22", "width": 2},
        hovertemplate="%{x}<br>%{y:,.0f} contratos<extra>Hedgers</extra>",
    ), row=1, col=1)

    fig.add_hline(y=0, line_color="#555", line_width=1, row=1, col=1)

    if price_dates:
        fig.add_trace(go.Scatter(
            x=price_dates, y=price_vals,
            mode="lines",
            name="Precio spot",
            line={"color": "#3498db", "width": 2},
            hovertemplate="%{x}<br>$%{y:,.2f}<extra>Spot</extra>",
        ), row=2, col=1)

    name = slug.replace("_", " ").title()
    fig.update_layout(
        title=f"{name} — COT",
        **_dark_layout(),
    )
    fig.update_yaxes(gridcolor="#2a2a4a", zerolinecolor="#2a2a4a")
    # Force x-axis range to match the requested period
    if dates:
        fig.update_xaxes(range=[dates[0], dates[-1]])
    return fig


def build_percentile_badge(slug: str):
    pct = get_cot_percentile(slug)
    if pct is None:
        return html.Span("—", style={"color": "#888"})

    color = "#2ecc71" if pct >= 70 else "#e74c3c" if pct <= 30 else "#f39c12"
    label = "Largos ext." if pct >= 70 else "Cortos ext." if pct <= 30 else "Neutral"

    return html.Div([
        html.Div(f"{pct:.0f}%",
                 style={"color": color, "fontWeight": "700",
                        "fontSize": "22px", "lineHeight": "1"}),
        html.Div(label,
                 style={"color": color, "fontSize": "11px"}),
        html.Div("índice COT",
                 style={"color": "#666", "fontSize": "10px"}),
    ])


def _dark_layout():
    return dict(
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#0f3460",
        font={"color": "#e0e0e0"},
        xaxis={"gridcolor": "#2a2a4a"},
        margin={"t": 60, "b": 40, "l": 60, "r": 20},
        legend={"bgcolor": "#16213e", "bordercolor": "#2a2a4a",
                "orientation": "h", "y": -0.15},
    )


@callback(
    Output("cot-chart", "figure"),
    Output("cot-percentile-badge", "children"),
    Input("cot-commodity", "value"),
    Input("cot-period", "value"),
    Input("auto-refresh", "n_intervals"),
    Input("main-tabs", "active_tab"),
    Input("manual-refresh-ts", "data"),
)
def update_cot(slug, weeks, _, active_tab, refresh_ts):
    return build_cot_chart(slug, weeks or 104), build_percentile_badge(slug)
