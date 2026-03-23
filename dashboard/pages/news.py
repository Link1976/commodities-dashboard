"""Tab 5 — Noticias: commodity news from RSS feeds."""
from dash import html, Input, Output, callback, dcc
import dash_bootstrap_components as dbc

# ── Category filter config ────────────────────────────────────────────────────
FILTERS = [
    {"label": "Todo",    "value": "all"},
    {"label": "Metales", "value": "metals"},
    {"label": "Energía", "value": "energy"},
    {"label": "Macro",   "value": "macro"},
]

SOURCE_COLORS = {
    "Reuters":     "#f1c40f",
    "Kitco":       "#bdc3c7",
    "OilPrice":    "#e67e22",
    "MarketWatch": "#3498db",
}

# ── Static layout ─────────────────────────────────────────────────────────────
layout = html.Div([
    # Filter bar
    html.Div(
        [
            dbc.Button(
                f["label"],
                id={"type": "news-filter", "index": f["value"]},
                color="secondary",
                outline=True,
                size="sm",
                style={
                    "marginRight": "6px",
                    "fontSize": "12px",
                    "borderColor": "#2d3748",
                    "color": "#94a3b8",
                },
            )
            for f in FILTERS
        ],
        style={"marginBottom": "16px", "display": "flex", "alignItems": "center"},
    ),

    # Hidden store for active filter
    dcc.Store(id="news-active-filter", data="all"),

    # News list
    dcc.Loading(
        type="dot",
        color="#3498db",
        children=html.Div(id="news-list"),
    ),
], style={"padding": "4px 0"})


# ── Helpers ───────────────────────────────────────────────────────────────────
def _source_badge(source: str) -> html.Span:
    color = SOURCE_COLORS.get(source, "#4b5563")
    return html.Span(
        source,
        style={
            "backgroundColor": color + "22",
            "color": color,
            "border": f"1px solid {color}55",
            "borderRadius": "4px",
            "padding": "1px 7px",
            "fontSize": "10px",
            "fontWeight": "600",
            "marginRight": "8px",
            "letterSpacing": "0.4px",
            "whiteSpace": "nowrap",
        },
    )


def _news_card(article: dict) -> html.A:
    return html.A(
        href=article["url"],
        target="_blank",
        rel="noopener noreferrer",
        style={"textDecoration": "none", "color": "inherit"},
        children=html.Div(
            style={
                "backgroundColor": "#1f2937",
                "border": "1px solid #2d3748",
                "borderLeft": f"3px solid {SOURCE_COLORS.get(article['source'], '#4b5563')}",
                "borderRadius": "6px",
                "padding": "10px 14px",
                "marginBottom": "8px",
                "cursor": "pointer",
                "transition": "background 0.15s",
            },
            children=[
                # Header row: badge + age
                html.Div([
                    _source_badge(article["source"]),
                    html.Span(
                        article["age_str"],
                        style={"color": "#4b5563", "fontSize": "11px"},
                    ),
                ], style={"marginBottom": "5px", "display": "flex", "alignItems": "center"}),
                # Headline
                html.P(
                    article["title"],
                    style={
                        "margin": "0",
                        "fontSize": "13px",
                        "color": "#e2e8f0",
                        "lineHeight": "1.45",
                        "fontWeight": "500",
                    },
                ),
            ],
        ),
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────
@callback(
    Output("news-active-filter", "data"),
    Input({"type": "news-filter", "index": "all"},    "n_clicks"),
    Input({"type": "news-filter", "index": "metals"}, "n_clicks"),
    Input({"type": "news-filter", "index": "energy"}, "n_clicks"),
    Input({"type": "news-filter", "index": "macro"},  "n_clicks"),
    prevent_initial_call=True,
)
def _set_filter(all_, metals, energy, macro):
    from dash import ctx
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        return triggered["index"]
    return "all"


@callback(
    Output("news-list", "children"),
    Input("main-tabs", "active_tab"),
    Input("news-active-filter", "data"),
    Input("auto-refresh", "n_intervals"),
    Input("manual-refresh-ts", "data"),
)
def _render_news(active_tab, active_filter, _n, _ts):
    if active_tab != "tab-news":
        return []

    try:
        from fetchers.fetch_news import fetch_news
        articles = fetch_news(max_per_feed=20)
    except Exception as e:
        return html.P(f"Error cargando noticias: {e}",
                      style={"color": "#ef4444", "fontSize": "13px"})

    if active_filter and active_filter != "all":
        articles = [a for a in articles if a["category"] == active_filter]

    if not articles:
        return html.P("No hay noticias disponibles.",
                      style={"color": "#64748b", "fontSize": "13px"})

    return html.Div([_news_card(a) for a in articles])
