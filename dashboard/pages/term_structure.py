"""Tab 2 — Futures term structure (contango / backwardation)."""
from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from db.queries import get_futures_curve, get_curve_dates
from config import FUTURES_CURVE

COMMODITY_OPTIONS = [
    {"label": cfg["name"], "value": key}
    for key, cfg in FUTURES_CURVE.items()
]

layout = html.Div([
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id="curve-commodity",
                options=COMMODITY_OPTIONS,
                value="crude_oil",
                clearable=False,
                style={"backgroundColor": "#16213e", "color": "#000"},
            ),
            width=4,
        ),
        dbc.Col(
            dcc.DatePickerSingle(
                id="curve-date",
                display_format="YYYY-MM-DD",
                style={"color": "#000"},
            ),
            width=3,
        ),
    ], style={"marginBottom": "16px"}),

    dbc.Row([
        dbc.Col(dcc.Graph(id="curve-chart"), width=8),
        dbc.Col(html.Div(id="curve-table"), width=4),
    ]),
], style={"padding": "8px"})


def build_curve_chart(commodity: str, on_date: str = None):
    data = get_futures_curve(commodity, on_date)

    if not data:
        fig = go.Figure()
        fig.update_layout(
            title="No futures curve data available",
            **_dark_layout(),
        )
        return fig

    contracts = [d["contract"] for d in data]
    prices    = [d["price"] for d in data]
    tickers   = [d["ticker"] for d in data]

    # Determine contango / backwardation
    slope_color = "#e74c3c" if prices[-1] > prices[0] else "#2ecc71"
    label = "Contango ▲" if prices[-1] > prices[0] else "Backwardation ▼"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=contracts,
        y=prices,
        mode="lines+markers+text",
        text=[f"${p:,.1f}" for p in prices],
        textposition="top center",
        line={"color": slope_color, "width": 2.5},
        marker={"size": 9, "color": slope_color},
        customdata=tickers,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Price: $%{y:,.2f}<br>"
            "Ticker: %{customdata}<extra></extra>"
        ),
    ))

    name = FUTURES_CURVE.get(commodity, {}).get("name", commodity)
    fig.update_layout(
        title=f"{name} — Term Structure  ({label})",
        xaxis_title="Contract",
        yaxis_title="Price (USD)",
        **_dark_layout(),
    )
    return fig


def build_curve_table(commodity: str, on_date: str = None):
    data = get_futures_curve(commodity, on_date)
    if not data:
        return html.P("No data", style={"color": "#888"})

    m1_price = data[0]["price"] if data else 1

    header = html.Tr([
        html.Th(c, style={"color": "#a0a0b0", "fontSize": "12px", "padding": "6px"})
        for c in ["Contract", "Ticker", "Price", "vs M1"]
    ])
    body_rows = []
    for d in data:
        diff = d["price"] - m1_price
        diff_str = f"{diff:+.2f}" if diff != 0 else "—"
        diff_color = "#e74c3c" if diff > 0 else "#2ecc71" if diff < 0 else "#888"
        body_rows.append(html.Tr([
            html.Td(d["contract"], style={"color": "#e0e0e0", "padding": "6px"}),
            html.Td(d["ticker"],   style={"color": "#a0a0b0", "padding": "6px", "fontSize": "11px"}),
            html.Td(f"${d['price']:,.2f}", style={"color": "#e0e0e0", "padding": "6px"}),
            html.Td(diff_str,      style={"color": diff_color, "padding": "6px", "fontWeight": "600"}),
        ]))

    return html.Table(
        [html.Thead(header), html.Tbody(body_rows)],
        style={"width": "100%", "borderCollapse": "collapse"},
    )


def _dark_layout():
    return dict(
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#0f3460",
        font={"color": "#e0e0e0"},
        xaxis={"gridcolor": "#2a2a4a", "zerolinecolor": "#2a2a4a"},
        yaxis={"gridcolor": "#2a2a4a", "zerolinecolor": "#2a2a4a"},
        margin={"t": 50, "b": 40, "l": 60, "r": 20},
    )


@callback(
    Output("curve-chart", "figure"),
    Output("curve-table", "children"),
    Input("curve-commodity", "value"),
    Input("curve-date", "date"),
    Input("auto-refresh", "n_intervals"),
)
def update_curve(commodity, on_date, _):
    return build_curve_chart(commodity, on_date), build_curve_table(commodity, on_date)
