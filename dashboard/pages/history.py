"""Tab 3 — Historical price charts (candlestick + MA overlays)."""
from dash import html, dcc, Input, Output, callback, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from db.queries import get_price_series, get_rhodium_series
from config import TICKERS

TICKER_OPTIONS = [
    {"label": f"{meta['name']} ({ticker})", "value": ticker}
    for ticker, meta in TICKERS.items()
    if meta["category"] not in ("fx", "currency")
] + [{"label": "Rhodium (scraped)", "value": "RHODIUM"}]

PERIOD_OPTIONS = [
    {"label": "1M",  "value": 30},
    {"label": "3M",  "value": 90},
    {"label": "6M",  "value": 180},
    {"label": "1Y",  "value": 365},
    {"label": "3Y",  "value": 1095},
]

layout = html.Div([
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id="hist-ticker",
                options=TICKER_OPTIONS,
                value="GC=F",
                clearable=False,
                style={"backgroundColor": "#16213e", "color": "#000"},
            ),
            width=4,
        ),
        dbc.Col(
            dcc.RadioItems(
                id="hist-period",
                options=PERIOD_OPTIONS,
                value=365,
                inline=True,
                labelStyle={"marginRight": "16px", "color": "#e0e0e0"},
            ),
            width=5,
        ),
        dbc.Col(
            dcc.Checklist(
                id="hist-ma",
                options=[
                    {"label": " MA20",  "value": 20},
                    {"label": " MA50",  "value": 50},
                    {"label": " MA200", "value": 200},
                ],
                value=[],
                inline=True,
                labelStyle={"marginRight": "12px", "color": "#e0e0e0", "fontSize": "13px"},
            ),
            width=3,
        ),
    ], style={"marginBottom": "16px"}),

    dbc.Row(dbc.Col(dcc.Graph(id="hist-chart", style={"height": "500px"}))),
], style={"padding": "8px"})


def build_history_chart(ticker: str, days: int, ma_periods: list):
    if ticker == "RHODIUM":
        rows = get_rhodium_series(days=days)
        dates  = [r["date"] for r in rows]
        closes = [r["mid"]  for r in rows]
        name   = "Rhodium"
        has_ohlc = False
    else:
        rows = get_price_series(ticker, days=days)
        name = TICKERS.get(ticker, {}).get("name", ticker)
        has_ohlc = any(r.get("open") for r in rows)
        dates  = [r["date"]  for r in rows]
        opens  = [r["open"]  for r in rows]
        highs  = [r["high"]  for r in rows]
        lows   = [r["low"]   for r in rows]
        closes = [r["close"] for r in rows]
        vols   = [r.get("volume") or 0 for r in rows]

    if not dates:
        fig = go.Figure()
        fig.update_layout(title="No data available", **_dark_layout())
        return fig

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.8, 0.2],
        vertical_spacing=0.03,
    )

    # Price trace
    if has_ohlc:
        fig.add_trace(go.Candlestick(
            x=dates, open=opens, high=highs, low=lows, close=closes,
            name=name,
            increasing_line_color="#2ecc71",
            decreasing_line_color="#e74c3c",
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=dates, y=closes, mode="lines",
            name=name,
            line={"color": "#3498db", "width": 1.8},
        ), row=1, col=1)

    # Moving averages
    if ma_periods and closes:
        s = pd.Series(closes, index=dates)
        ma_colors = {20: "#f39c12", 50: "#9b59b6", 200: "#1abc9c"}
        for period in ma_periods:
            ma = s.rolling(period).mean()
            fig.add_trace(go.Scatter(
                x=dates, y=ma.tolist(),
                mode="lines",
                name=f"MA{period}",
                line={"color": ma_colors.get(period, "#888"), "width": 1.2, "dash": "dot"},
            ), row=1, col=1)

    # Volume
    if has_ohlc and vols:
        vol_colors = [
            "#2ecc71" if c >= o else "#e74c3c"
            for c, o in zip(closes, opens)
        ]
        fig.add_trace(go.Bar(
            x=dates, y=vols,
            marker_color=vol_colors,
            name="Volume",
            opacity=0.6,
        ), row=2, col=1)

    fig.update_layout(
        title=f"{name} — Price History",
        xaxis_rangeslider_visible=False,
        **_dark_layout(),
    )
    fig.update_yaxes(gridcolor="#2a2a4a", zerolinecolor="#2a2a4a")
    return fig


def _dark_layout():
    return dict(
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#0f3460",
        font={"color": "#e0e0e0"},
        xaxis={"gridcolor": "#2a2a4a", "zerolinecolor": "#2a2a4a"},
        margin={"t": 50, "b": 40, "l": 60, "r": 20},
        legend={"bgcolor": "#16213e", "bordercolor": "#2a2a4a"},
    )


@callback(
    Output("hist-chart", "figure"),
    Input("hist-ticker", "value"),
    Input("hist-period", "value"),
    Input("hist-ma", "value"),
    Input("auto-refresh", "n_intervals"),
)
def update_history(ticker, days, ma_periods, _):
    return build_history_chart(ticker, days or 365, ma_periods or [])
