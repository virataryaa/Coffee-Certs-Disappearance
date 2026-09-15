import pandas as pd
import plotly.graph_objects as go

# Validated palette (dataviz skill reference instance, light mode).
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
GOOD = "#0ca30c"
CRITICAL = "#d03b3b"

# Categorical, fixed order — never cycle past what's assigned.
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
MAGENTA = "#e87ba4"
GREEN = "#008300"
VIOLET = "#4a3aa7"
RED = "#e34948"
CATEGORICAL = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]

SERIES = {"blue": BLUE, "orange": ORANGE, "aqua": AQUA, "yellow": YELLOW,
          "magenta": MAGENTA, "green": GREEN, "violet": VIOLET, "red": RED}


def _base_layout(title, height=320, y_suffix=""):
    return dict(
        title=dict(text=title, x=0, xanchor="left", y=0.98, yanchor="top",
                   font=dict(size=13, color=INK, family="system-ui, -apple-system, Segoe UI, sans-serif")),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=INK_SECONDARY, family="system-ui, -apple-system, Segoe UI, sans-serif", size=11),
        margin=dict(l=48, r=16, t=40, b=36),
        height=height,
        showlegend=False,
        hovermode="x unified",
        xaxis=dict(gridcolor=GRID, linecolor=BASELINE, tickfont=dict(color=MUTED, size=10),
                   showgrid=False, zeroline=False),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED, size=10),
                   tickformat=",.0f", ticksuffix=y_suffix, zeroline=True, zerolinecolor=BASELINE,
                   zerolinewidth=1),
    )


def _legend(y=-0.22):
    return dict(orientation="h", yanchor="top", y=y, xanchor="left", x=0,
                bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=INK_SECONDARY))


def recent_columns(columns, n=6):
    """Last n columns (crop years / years), oldest first — keeps a handful of
    stale outlier years from ever entering a chart's axis range."""
    cols = list(columns)
    return cols[-n:] if len(cols) > n else cols


def emphasis_line_chart(wide, title, n_recent=6, y_suffix="", height=330):
    """One highlighted (current) series in blue, the rest in de-emphasis gray —
    the 'one series is the point, rest are context' form. Only the last
    n_recent columns are ever plotted, so a stale outlier year can't stretch
    the axis for the years that matter."""
    cols = recent_columns(wide.columns, n_recent)
    current = cols[-1]
    fig = go.Figure()
    for c in cols[:-1]:
        fig.add_trace(go.Scatter(
            x=wide.index, y=wide[c], mode="lines", name=str(c),
            line=dict(color=BASELINE, width=1.5),
        ))
    fig.add_trace(go.Scatter(
        x=wide.index, y=wide[current], mode="lines+markers", name=str(current),
        line=dict(color=BLUE, width=2.5), marker=dict(size=6, color=BLUE,
                  line=dict(width=2, color=SURFACE)),
    ))
    layout = _base_layout(title, height, y_suffix)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def band_chart(wide, current_col, title, n_years=5, height=330):
    """Min / Max / Avg band of prior years behind the current year — a single
    'is this normal' read, not a wall of lines."""
    prior = [c for c in wide.columns if c != current_col]
    prior = recent_columns(prior, n_years)
    hist = wide[prior]
    lo, hi, avg = hist.min(axis=1, skipna=True), hist.max(axis=1, skipna=True), hist.mean(axis=1, skipna=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=wide.index, y=hi, mode="lines", line=dict(width=0), showlegend=False,
                              hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=wide.index, y=lo, mode="lines", line=dict(width=0), fill="tonexty",
                              fillcolor="rgba(42,120,214,0.08)", name=f"Min–Max ({len(prior)}y)",
                              hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=wide.index, y=avg, mode="lines", name=f"Avg ({len(prior)}y)",
                              line=dict(color=MUTED, width=1.5, dash="dot")))
    if current_col in wide.columns:
        fig.add_trace(go.Scatter(x=wide.index, y=wide[current_col], mode="lines+markers", name=str(current_col),
                                  line=dict(color=BLUE, width=2.5),
                                  marker=dict(size=6, color=BLUE, line=dict(width=2, color=SURFACE))))
    layout = _base_layout(title, height)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def single_line_chart(x, y, title, color=BLUE, height=300, y_suffix=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=2)))
    fig.update_layout(**_base_layout(title, height, y_suffix))
    return fig


def two_line_chart(x, y1, name1, y2, name2, title, height=300):
    """Two series that share one meaningful axis — e.g. a level and its
    rolling average. Never use this to fake a dual-axis comparison."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y1, mode="lines", name=name1, line=dict(color=BLUE, width=2)))
    fig.add_trace(go.Scatter(x=x, y=y2, mode="lines", name=name2, line=dict(color=MUTED, width=1.5, dash="dot")))
    layout = _base_layout(title, height)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def multi_series_chart(df_x_date, series: dict, title, height=320):
    """<=4 categorical series sharing one axis, direct-labeled at the line end
    (mandatory once you're at 4 series). `series` = {name: (y_values, color)}."""
    fig = go.Figure()
    for name, (y, color) in series.items():
        fig.add_trace(go.Scatter(x=df_x_date, y=y, mode="lines", name=name, line=dict(color=color, width=2)))
    layout = _base_layout(title, height)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def diverging_bar_chart(x, y, title, height=300):
    """A single continuous time series of signed values (stock build/draw) —
    green above zero, red below. One bar per period, chronological — not
    grouped by year, which is what turns this into an unreadable wall."""
    colors = [GOOD if v >= 0 else CRITICAL for v in y]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=y, marker_color=colors, marker_line_width=0))
    fig.update_layout(**_base_layout(title, height))
    return fig
