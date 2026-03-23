"""layout.py — Top-level tab structure and refresh interval."""
from datetime import datetime
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc

from dashboard.pages.overview       import layout as overview_layout
from dashboard.pages.term_structure import layout as term_structure_layout
from dashboard.pages.history        import layout as history_layout
from dashboard.pages.cot            import layout as cot_layout


def build_layout():
    return dbc.Container(
        fluid=True,
        style={"backgroundColor": "#1a1a2e", "minHeight": "100vh"},
        children=[
            # ── Header ────────────────────────────────────────────────────────
            html.Div(style={
                "height": "3px",
                "background": "linear-gradient(90deg, #f1c40f, #e67e22, #3498db, #1abc9c)",
                "margin": "0 -12px 0 -12px",
            }),
            dbc.Row([
                dbc.Col(
                    html.Div([
                        html.Span("◈ ", style={"color": "#f1c40f", "fontSize": "20px"}),
                        html.Span("Commodities", style={
                            "color": "#ffffff", "fontWeight": "700",
                            "fontSize": "20px", "letterSpacing": "1px",
                        }),
                        html.Span(" Dashboard", style={
                            "color": "#8899aa", "fontWeight": "400",
                            "fontSize": "20px",
                        }),
                    ], style={"padding": "16px 0 10px 0"}),
                    xs=12, md=8,
                ),
                dbc.Col(
                    html.Div([
                        dcc.Loading(
                            type="dot",
                            color="#3498db",
                            children=html.Span(id="refresh-status",
                                               style={"color": "#556", "fontSize": "11px"}),
                        ),
                        dbc.Button(
                            "⟳ Actualizar",
                            id="refresh-btn",
                            color="secondary",
                            outline=True,
                            size="sm",
                            style={"marginLeft": "10px", "fontSize": "12px",
                                   "borderColor": "#2a3a4a", "color": "#8899aa"},
                        ),
                    ], style={"display": "flex", "alignItems": "center",
                              "justifyContent": "flex-end", "paddingTop": "14px"}),
                    xs=12, md=4,
                ),
            ]),

            # Store para propagar refresh manual a todos los callbacks
            dcc.Store(id="manual-refresh-ts", data=0),

            # ── Tabs ──────────────────────────────────────────────────────────
            dbc.Tabs(
                id="main-tabs",
                active_tab="tab-overview",
                children=[
                    dbc.Tab(label="Overview",       tab_id="tab-overview",
                            label_style={"color": "#8899aa", "fontSize": "13px"},
                            active_label_style={"color": "#ffffff", "fontWeight": "700"}),
                    dbc.Tab(label="Futuros",        tab_id="tab-term-structure",
                            label_style={"color": "#8899aa", "fontSize": "13px"},
                            active_label_style={"color": "#ffffff", "fontWeight": "700"}),
                    dbc.Tab(label="Histórico",      tab_id="tab-history",
                            label_style={"color": "#8899aa", "fontSize": "13px"},
                            active_label_style={"color": "#ffffff", "fontWeight": "700"}),
                    dbc.Tab(label="COT",            tab_id="tab-cot",
                            label_style={"color": "#8899aa", "fontSize": "13px"},
                            active_label_style={"color": "#ffffff", "fontWeight": "700"}),
                ],
                style={"marginBottom": "16px", "borderBottom": "1px solid #1e2d3d"},
            ),

            # ── Tab content ───────────────────────────────────────────────────
            html.Div(id="tab-content"),

            # ── Auto-refresh every 5 minutes ──────────────────────────────────
            dcc.Interval(
                id="auto-refresh",
                interval=5 * 60 * 1000,   # ms
                n_intervals=0,
            ),
        ],
    )


@callback(Output("tab-content", "children"), Input("main-tabs", "active_tab"))
def render_tab(tab):
    if tab == "tab-overview":
        return overview_layout
    if tab == "tab-term-structure":
        return term_structure_layout
    if tab == "tab-history":
        return history_layout
    if tab == "tab-cot":
        return cot_layout
    return html.P("Tab not found")


@callback(
    Output("manual-refresh-ts", "data"),
    Output("refresh-status", "children"),
    Input("refresh-btn", "n_clicks"),
    prevent_initial_call=True,
)
def manual_refresh(n_clicks):
    from fetchers.fetch_prices import main as fetch_main
    fetch_main()
    ts = datetime.now().strftime("%H:%M:%S")
    return n_clicks, f"Actualizado {ts}"
