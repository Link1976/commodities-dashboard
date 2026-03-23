"""Tab 5 — Noticias: commodity news, estilo editorial."""
from dash import html, Input, Output, callback, dcc, ctx
import dash_bootstrap_components as dbc

from fetchers.fetch_news import COMMODITY_LABELS

# ── Filter config ─────────────────────────────────────────────────────────────
# "all" + one button per commodity slug
FILTER_SLUGS = ["all"] + list(COMMODITY_LABELS.keys())
FILTER_LABELS = {"all": "Todo"} | COMMODITY_LABELS

SOURCE_COLORS = {
    "Yahoo Finance": "#3498db",
    "OilPrice":      "#e67e22",
    "Reuters":       "#f1c40f",
    "Kitco":         "#bdc3c7",
    "MarketWatch":   "#1abc9c",
}

# ── Static layout ─────────────────────────────────────────────────────────────
layout = html.Div([
    dcc.Store(id="news-active-filter", data="all"),

    # ── Filter bar ────────────────────────────────────────────────────────────
    html.Div(
        id="news-filter-bar",
        style={
            "display": "flex",
            "flexWrap": "wrap",
            "gap": "6px",
            "marginBottom": "20px",
        },
        children=[
            html.Button(
                FILTER_LABELS[slug],
                id={"type": "news-filter", "index": slug},
                n_clicks=0,
                style={
                    "background": "#1f2937" if slug != "all" else "#2d3748",
                    "color": "#f1f5f9" if slug == "all" else "#94a3b8",
                    "border": "1px solid #374151",
                    "borderRadius": "20px",
                    "padding": "4px 14px",
                    "fontSize": "12px",
                    "cursor": "pointer",
                    "fontWeight": "600" if slug == "all" else "400",
                    "transition": "all 0.15s",
                },
            )
            for slug in FILTER_SLUGS
        ],
    ),

    # ── News feed ─────────────────────────────────────────────────────────────
    dcc.Loading(
        type="dot",
        color="#3498db",
        children=html.Div(id="news-list"),
    ),
], style={"padding": "4px 0"})


# ── Helpers ───────────────────────────────────────────────────────────────────
def _badge(text: str, color: str) -> html.Span:
    return html.Span(
        text,
        style={
            "backgroundColor": color + "22",
            "color": color,
            "border": f"1px solid {color}44",
            "borderRadius": "4px",
            "padding": "2px 8px",
            "fontSize": "10px",
            "fontWeight": "700",
            "letterSpacing": "0.5px",
            "whiteSpace": "nowrap",
        },
    )


def _commodity_pills(tags: list[str]) -> list:
    pills = []
    for slug in tags[:3]:
        label = COMMODITY_LABELS.get(slug, slug)
        pills.append(html.Span(
            label,
            style={
                "backgroundColor": "#374151",
                "color": "#94a3b8",
                "borderRadius": "4px",
                "padding": "1px 7px",
                "fontSize": "10px",
                "marginLeft": "6px",
                "whiteSpace": "nowrap",
            },
        ))
    return pills


def _news_card(article: dict) -> html.Div:
    source_color = SOURCE_COLORS.get(article["source"], "#4b5563")
    has_summary  = bool(article.get("summary"))

    return html.Div(
        style={
            "borderBottom": "1px solid #1f2937",
            "padding": "18px 4px 18px 0",
        },
        children=[
            # ── Meta row: source badge + commodity pills + age ────────────────
            html.Div(
                style={"display": "flex", "alignItems": "center",
                       "flexWrap": "wrap", "gap": "4px", "marginBottom": "8px"},
                children=[
                    _badge(article["source"], source_color),
                    *_commodity_pills(article.get("tags", [])),
                    html.Span(
                        article["age_str"],
                        style={"color": "#4b5563", "fontSize": "11px", "marginLeft": "auto"},
                    ),
                ],
            ),
            # ── Headline ──────────────────────────────────────────────────────
            html.A(
                href=article["url"],
                target="_blank",
                rel="noopener noreferrer",
                style={"textDecoration": "none"},
                children=html.P(
                    article["title"],
                    style={
                        "margin": "0 0 8px 0",
                        "fontSize": "15px",
                        "fontWeight": "700",
                        "color": "#f1f5f9",
                        "lineHeight": "1.4",
                    },
                ),
            ),
            # ── Summary paragraph ─────────────────────────────────────────────
            *(
                [html.P(
                    article["summary"],
                    style={
                        "margin": "0 0 10px 0",
                        "fontSize": "13px",
                        "color": "#94a3b8",
                        "lineHeight": "1.6",
                    },
                )]
                if has_summary else []
            ),
            # ── "Seguir leyendo" link ─────────────────────────────────────────
            html.A(
                "Seguir leyendo →",
                href=article["url"],
                target="_blank",
                rel="noopener noreferrer",
                style={
                    "fontSize": "12px",
                    "color": source_color,
                    "textDecoration": "none",
                    "fontWeight": "600",
                    "letterSpacing": "0.3px",
                },
            ),
        ],
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────
@callback(
    Output("news-active-filter", "data"),
    [Input({"type": "news-filter", "index": slug}, "n_clicks") for slug in FILTER_SLUGS],
    prevent_initial_call=True,
)
def _set_filter(*_):
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
        articles = [a for a in articles if active_filter in a.get("tags", [])]

    articles.sort(key=lambda x: x["published_dt"], reverse=True)

    if not articles:
        return html.P("No hay noticias disponibles.",
                      style={"color": "#64748b", "fontSize": "13px"})

    return html.Div(
        [_news_card(a) for a in articles],
        style={"maxWidth": "780px"},
    )
