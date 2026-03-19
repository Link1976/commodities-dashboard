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

# Map slug → spot ticker for price overlay
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

Informe semanal del regulador de futuros de EEUU. Muestra el posicionamiento neto de:

- 🔵 **Non-Commercials (especuladores)**: fondos, hedge funds. Siguen tendencias.
  Posición neta alta = mercado muy largo → posible techo. Baja = posible suelo.
- 🟠 **Commercials (hedgers)**: productores y consumidores reales. Suelen ir a contracorriente.
- **Índice COT**: percentil de la posición especuladora vs los últimos 3 años.
  Por encima de 70% → especuladores muy largos (señal de cautela).
  Por debajo de 30% → especuladores muy cortos (señal contraria alcista).
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
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id="cot-commodity",
                options=COT_OPTIONS,
                value="gold",
                clearable=False,
                style={"backgroundColor": "#16213e", "color": "#000"},
            ),
            width=4,
        ),
        dbc.Col(
            html.Div(id="cot-percentile-badge"),
            width=4,
            style={"display": "flex", "alignItems": "center"},
        ),
    ], style={"marginBottom": "16px"}),

    dbc.Row(dbc.Col(dcc.Graph(id="cot-chart", style={"height": "520px"}))),
], style={"padding": "8px"})


def build_cot_chart(slug: str):
    rows = get_cot_series(slug, weeks=156)

    if not rows:
        fig = go.Figure()
        fig.update_layout(title="No COT data available", **_dark_layout())
        return fig

    dates      = [r["report_date"] for r in rows]
    noncomm_net = [r["noncomm_net"] or 0  for r in rows]
    comm_net    = [r["comm_net"]    or 0  for r in rows]

    # Spot price overlay
    ticker = SLUG_TO_TICKER.get(slug)
    price_dates, price_vals = [], []
    if ticker:
        price_rows = get_price_series(ticker, days=365 * 3)
        price_dates = [r["date"]  for r in price_rows]
        price_vals  = [r["close"] for r in price_rows]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.45],
        vertical_spacing=0.04,
        subplot_titles=["Net Positioning (contracts)", "Spot Price"],
    )

    # Non-commercial net (speculators)
    nc_colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in noncomm_net]
    fig.add_trace(go.Bar(
        x=dates, y=noncomm_net,
        marker_color=nc_colors,
        name="Non-Commercial (spec) net",
        opacity=0.85,
    ), row=1, col=1)

    # Commercial net (hedgers) — faint line
    fig.add_trace(go.Scatter(
        x=dates, y=comm_net,
        mode="lines",
        name="Commercial (hedger) net",
        line={"color": "#e67e22", "width": 1.2, "dash": "dot"},
        opacity=0.7,
    ), row=1, col=1)

    # Zero line
    fig.add_hline(y=0, line_color="#555", line_width=1, row=1, col=1)

    # Spot price
    if price_dates:
        fig.add_trace(go.Scatter(
            x=price_dates, y=price_vals,
            mode="lines",
            name="Spot price",
            line={"color": "#3498db", "width": 1.8},
        ), row=2, col=1)

    name = slug.replace("_", " ").title()
    fig.update_layout(
        title=f"{name} — COT Positioning (3 years)",
        barmode="relative",
        **_dark_layout(),
    )
    fig.update_yaxes(gridcolor="#2a2a4a", zerolinecolor="#2a2a4a")
    return fig


def build_percentile_badge(slug: str):
    pct = get_cot_percentile(slug)
    if pct is None:
        return html.Span("COT index: —", style={"color": "#888"})

    if pct >= 70:
        color, label = "#2ecc71", "LONGS extremos"
    elif pct <= 30:
        color, label = "#e74c3c", "SHORTS extremos"
    else:
        color, label = "#f39c12", "Neutral"

    return html.Div([
        html.Span("COT index: ", style={"color": "#a0a0b0", "fontSize": "13px"}),
        html.Span(f"{pct:.0f}%  ", style={"color": color, "fontWeight": "700", "fontSize": "18px"}),
        html.Span(label, style={"color": color, "fontSize": "13px"}),
    ])


def _dark_layout():
    return dict(
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#0f3460",
        font={"color": "#e0e0e0"},
        xaxis={"gridcolor": "#2a2a4a"},
        margin={"t": 60, "b": 40, "l": 60, "r": 20},
        legend={"bgcolor": "#16213e", "bordercolor": "#2a2a4a"},
    )


@callback(
    Output("cot-chart", "figure"),
    Output("cot-percentile-badge", "children"),
    Input("cot-commodity", "value"),
    Input("auto-refresh", "n_intervals"),
)
def update_cot(slug, _):
    return build_cot_chart(slug), build_percentile_badge(slug)
