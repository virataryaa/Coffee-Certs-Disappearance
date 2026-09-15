import pandas as pd
import plotly.graph_objects as go

GOOD = "#006300"
CRITICAL = "#d03b3b"
MUTED = "#898781"
GRID = "#e1e0d9"
INK = "#0b0b0b"
SURFACE = "#fcfcfb"

SERIES = {
    "blue": "#3987e5",
    "green": "#008300",
    "magenta": "#d55181",
    "yellow": "#c98500",
    "aqua": "#199e70",
    "orange": "#d95926",
    "violet": "#9085e9",
    "red": "#e66767",
}
PALETTE = list(SERIES.values())


def _layout(title, height=340):
    margin = dict(l=50, r=20, t=45, b=70)
    domain_h = max(height - margin["t"] - margin["b"], 50)
    legend_y = -40.0 / domain_h
    return dict(
        title=dict(text=title, x=0.01, xanchor="left", y=0.97, yanchor="top", font=dict(size=14)),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=INK, family="system-ui, -apple-system, Segoe UI, sans-serif"),
        margin=margin,
        height=height,
        legend=dict(orientation="h", yanchor="top", y=legend_y, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        xaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED)),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED), tickformat=",.0f"),
    )


def monthly_lines(cum_or_flat, title, n_recent=5, height=340):
    """One line per crop year, x = crop month (Oct..Sep). Highlights the last
    n_recent crop years in color, greys out the rest."""
    cols = list(cum_or_flat.columns)
    recent = cols[-n_recent:]
    fig = go.Figure()
    for c in cols:
        if c in recent:
            idx = recent.index(c)
            fig.add_trace(go.Scatter(
                x=cum_or_flat.index, y=cum_or_flat[c], mode="lines+markers", name=c,
                line=dict(color=PALETTE[idx % len(PALETTE)], width=2), marker=dict(size=4),
            ))
        else:
            fig.add_trace(go.Scatter(
                x=cum_or_flat.index, y=cum_or_flat[c], mode="lines", name=c,
                line=dict(color=GRID, width=1), showlegend=False, hoverinfo="skip",
            ))
    fig.update_layout(**_layout(title, height))
    return fig


def cumulative_chart(cum, title, height=420):
    fig = go.Figure()
    for i, c in enumerate(cum.columns):
        fig.add_trace(go.Scatter(
            x=cum.index, y=cum[c], mode="lines+markers", name=c,
            line=dict(color=PALETTE[i % len(PALETTE)], width=2), marker=dict(size=4),
        ))
    fig.update_layout(**_layout(title, height))
    return fig


def ytd_trend_chart(ytd_series, title, height=340):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ytd_series.index, y=ytd_series.values, mode="lines+markers",
        line=dict(color=SERIES["blue"], width=2), marker=dict(size=5),
    ))
    fig.update_layout(**_layout(title, height))
    fig.update_layout(showlegend=False)
    return fig


def min_max_avg_chart(pivot, current_col, title, height=340, n_years=5):
    cols = [c for c in pivot.columns if c != current_col][-n_years:]
    hist = pivot[cols]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pivot.index, y=hist.min(axis=1, skipna=True), name="Min",
                              line=dict(color="#f0c419", width=1.5)))
    fig.add_trace(go.Scatter(x=pivot.index, y=hist.max(axis=1, skipna=True), name="Max",
                              line=dict(color=SERIES["green"], width=1.5)))
    fig.add_trace(go.Scatter(x=pivot.index, y=hist.mean(axis=1, skipna=True), name=f"Avg({len(cols)})",
                              line=dict(color=MUTED, width=1, dash="dot")))
    if current_col in pivot.columns:
        fig.add_trace(go.Scatter(x=pivot.index, y=pivot[current_col], name=current_col,
                                  line=dict(color=INK, width=2.5)))
    fig.update_layout(**_layout(title, height))
    return fig


def rolling_12m_chart(df, title, height=340):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Date"], y=df["Rolling12mKMT"], mode="lines",
                              line=dict(color=INK, width=1.5)))
    fig.update_layout(**_layout(title, height))
    fig.update_layout(showlegend=False)
    return fig


def stocks_change_bar_chart(change_table, title, height=380):
    """Grouped bars: one color per calendar year, x = month (Jan..Dec) —
    mirrors the 'Total Europe ECF EU Stocks Change' chart."""
    fig = go.Figure()
    months = list(change_table.columns)
    for i, year in enumerate(change_table.index):
        fig.add_trace(go.Bar(
            x=[f"{m:02d}" for m in months], y=change_table.loc[year].values,
            name=str(year), marker_color=PALETTE[i % len(PALETTE)],
        ))
    layout = _layout(title, height)
    layout["barmode"] = "group"
    fig.update_layout(**layout)
    fig.add_hline(y=0, line_color=GRID, line_width=1)
    return fig


def stocks_dual_axis_chart(df, title, height=460):
    """Total ECF stocks as bars (right axis) + Robusta / Natural Arabica /
    Washed Arabica as lines (left axis) + rolling 12m avg of Total (dotted,
    right axis) — mirrors the 'ECF Projection' panel."""
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Date"], y=df["Total"], name="Total ECF [Right]",
                          marker_color=GRID, yaxis="y2", opacity=0.7))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["RollingAvg"], name="Rolling 12m Avg [Right]",
                              line=dict(color=MUTED, width=1.5, dash="dot"), yaxis="y2"))
    line_colors = {"Robusta": INK, "Natural Arabica": "#7a2d1f", "Washed Arabica": "#e8b96b"}
    for col, color in line_colors.items():
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df["Date"], y=df[col], name=f"{col} [Left]",
                                      line=dict(color=color, width=2)))
    layout = _layout(title, height)
    layout["yaxis2"] = dict(overlaying="y", side="right", gridcolor=GRID, tickfont=dict(color=MUTED),
                             tickformat=",.0f")
    fig.update_layout(**layout)
    return fig
