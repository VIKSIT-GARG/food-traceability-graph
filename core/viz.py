"""Plotly figures: layered network graph + contamination timeline."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

LAYER_ORDER = ["Supplier", "Batch", "Facility", "CloudKitchen", "Dish", "Order", "Customer"]
LAYER_X = {name: i for i, name in enumerate(LAYER_ORDER)}
COLORS = {
    "Supplier": "#4338ca", "Batch": "#ea580c", "Facility": "#64748b",
    "CloudKitchen": "#0284c7", "Dish": "#d97706", "Order": "#0d9488", "Customer": "#e11d48",
}
STATUS_COLORS = {"CLEAR": "#15803d", "IN WINDOW": "#b91c1c",
                 "AUDIT": "#4338ca", "NO WINDOW": "#64748b"}


def _naive_ts(value):
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("Asia/Kolkata").tz_localize(None)
    return ts


def network_figure(graph):
    nodes, edges = graph["nodes"], graph["edges"]
    layers = {}
    for n in nodes:
        layers.setdefault(n["label"], []).append(n)
    pos = {}
    for label, ns in layers.items():
        x = LAYER_X.get(label, len(LAYER_ORDER))
        for i, n in enumerate(ns):
            pos[n["key"]] = (float(x), (len(ns) - 1) / 2 - i)

    fig = go.Figure()
    for e in edges:
        a, b = pos.get(e["from"]), pos.get(e["to"])
        if not a or not b:
            continue
        fig.add_trace(go.Scatter(x=[a[0], b[0]], y=[a[1], b[1]], mode="lines",
                                 line=dict(width=1.2, color="#cbd5e1"),
                                 hoverinfo="skip", showlegend=False))
    for label in LAYER_ORDER:
        ns = [n for n in nodes if n["label"] == label and n["key"] in pos]
        if not ns:
            continue
        fig.add_trace(go.Scatter(
            x=[pos[n["key"]][0] for n in ns], y=[pos[n["key"]][1] for n in ns],
            mode="markers+text", text=[n["text"] for n in ns], textposition="top center",
            textfont=dict(size=9.5, family="Plus Jakarta Sans, sans-serif", color="#334155"),
            marker=dict(size=26 if label == "Batch" else 15, color=COLORS[label],
                        line=dict(width=1.5, color="#ffffff")),
            name=label))
    fig.update_layout(height=560, margin=dict(l=15, r=15, t=35, b=15),
                      xaxis=dict(visible=False), yaxis=dict(visible=False),
                      plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                      font=dict(family="Plus Jakarta Sans, sans-serif"),
                      legend=dict(orientation="h", y=1.08, font=dict(size=10.5, color="#475569")))
    return fig


def timeline_figure(events, contamination_date=None):
    if not events:
        return None
    df = pd.DataFrame(events).sort_values("ts")
    df["ts"] = df["ts"].map(_naive_ts)
    df["end"] = df["ts"] + pd.Timedelta(minutes=45)
    cd_ts = _naive_ts(contamination_date) if contamination_date else None

    def _status(row):
        if row["kind"] == "AUDIT":
            return "AUDIT"
        if cd_ts is None:
            return "NO WINDOW"
        return "IN WINDOW" if row["ts"] >= cd_ts else "CLEAR"

    df["status"] = df.apply(_status, axis=1)

    fig = px.timeline(df, x_start="ts", x_end="end", y="label", color="status",
                      color_discrete_map=STATUS_COLORS)
    if cd_ts is not None:
        fig.add_vline(x=cd_ts, line_dash="dash", line_color="#b91c1c", line_width=1.8,
                      annotation_text="Contamination threshold (IST)", annotation_position="top",
                      annotation_font=dict(family="Plus Jakarta Sans, sans-serif", size=10, color="#b91c1c"))
    fig.update_layout(height=max(320, 38 * len(df) + 110),
                      margin=dict(l=15, r=15, t=35, b=15),
                      plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                      font=dict(family="Plus Jakarta Sans, sans-serif"),
                      yaxis=dict(automargin=True, title=None, tickfont=dict(size=10.5, color="#334155")),
                      xaxis=dict(title=dict(text="Time (IST)", font=dict(size=11, color="#475569")),
                                 gridcolor="#f1f5f9"),
                      legend=dict(orientation="h", y=1.08, font=dict(size=10.5, color="#475569")))
    return fig
