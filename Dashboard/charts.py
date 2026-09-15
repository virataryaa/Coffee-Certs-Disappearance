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

# TDM-style crop-year palette: pastel rotation for older years, with the
# latest and prior crop year always picked out — matches
# TDM/files/app.py's cy_style()/_PAL so a multi-year overlay reads the same
# way here as it does there.
YEAR_PAL = ["#7bafd4", "#f4a460", "#82c982", "#c9a0dc", "#e8c96a", "#7ec8c0",
            "#e89090", "#a0aad4", "#c8a06e", "#90b8a0", "#d4c0a0", "#a8c0d8"]
YEAR_CURRENT = INK       # latest crop year — bold dark line
YEAR_PREVIOUS = "#c0392b"  # prior crop year — red
BAND_MAX = "#5a9e6f"
BAND_MIN = "#e07b39"
BAND_AVG = "#aaaaaa"


def _year_style(cy, current, previous, pal_state):
    """Returns (color, width) for one crop-year series — current year bold
    dark, previous year red, everything else a cycling pastel, thin."""
    if cy == current:
        return YEAR_CURRENT, 2.5
    if cy == previous:
        return YEAR_PREVIOUS, 2.0
    color = YEAR_PAL[pal_state["i"] % len(YEAR_PAL)]
    pal_state["i"] += 1
    return color, 1.4


# Compact by default — dense multi-chart pages read better with small,
# tightly-margined panels than a handful of oversized ones.
COMPACT_HEIGHT = 220


def _title_html(title, subtitle=""):
    """A brief-but-detailed header: bold title, one small muted context line
    (unit / basis / type) underneath — e.g. 'Robusta Disappearance' +
    'Crop Year · MT · same month'."""
    if not subtitle:
        return f"<b>{title}</b>"
    return f"<b>{title}</b><br><span style='font-size:9.5px;color:{MUTED}'>{subtitle}</span>"


def _base_layout(title, height=COMPACT_HEIGHT, y_suffix="", subtitle=""):
    top_margin = 40 if subtitle else 30
    return dict(
        title=dict(text=_title_html(title, subtitle), x=0, xanchor="left", y=0.97, yanchor="top",
                   font=dict(size=12.5, color=INK, family="system-ui, -apple-system, Segoe UI, sans-serif")),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=INK_SECONDARY, family="system-ui, -apple-system, Segoe UI, sans-serif", size=10),
        margin=dict(l=44, r=10, t=top_margin, b=26),
        height=height,
        showlegend=False,
        hovermode="x unified",
        xaxis=dict(gridcolor=GRID, linecolor=BASELINE, tickfont=dict(color=MUTED, size=9),
                   showgrid=False, zeroline=False),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED, size=9),
                   tickformat=",.0f", ticksuffix=y_suffix, zeroline=True, zerolinecolor=BASELINE,
                   zerolinewidth=1),
    )


def _legend(y=-0.24):
    return dict(orientation="h", yanchor="top", y=y, xanchor="left", x=0,
                bgcolor="rgba(0,0,0,0)", font=dict(size=9, color=INK_SECONDARY))


def recent_columns(columns, n=6):
    """Last n columns (crop years / years), oldest first — keeps a handful of
    stale outlier years from ever entering a chart's axis range."""
    cols = list(columns)
    return cols[-n:] if len(cols) > n else cols


def seasonal_chart(wide, title, ref_years=None, current=None, previous=None, height=COMPACT_HEIGHT, subtitle=""):
    """One line per selected crop year (x = crop month), plus a Min/Max/Avg
    band from `ref_years` (last N *complete* crop years) behind them —
    mirrors TDM/files/app.py's Seasonal chart: latest year bold dark,
    previous year red, older years a cycling pastel palette."""
    cols = list(wide.columns)
    current = current or cols[-1]
    previous = previous or (cols[-2] if len(cols) > 1 else None)
    fig = go.Figure()

    if ref_years:
        ref = wide[[c for c in ref_years if c in wide.columns]]
        lo, hi, avg = ref.min(axis=1, skipna=True), ref.max(axis=1, skipna=True), ref.mean(axis=1, skipna=True)
        fig.add_trace(go.Scatter(x=wide.index, y=hi, mode="lines", name=f"Max (L{len(ref_years)}Y)",
                                  line=dict(color=BAND_MAX, width=1.2)))
        fig.add_trace(go.Scatter(x=wide.index, y=lo, mode="lines", name=f"Min (L{len(ref_years)}Y)",
                                  line=dict(color=BAND_MIN, width=1.2), fill="tonexty",
                                  fillcolor="rgba(180,180,180,0.10)"))
        fig.add_trace(go.Scatter(x=wide.index, y=avg, mode="lines", name=f"Avg (L{len(ref_years)}Y)",
                                  line=dict(color=BAND_AVG, width=1.2, dash="dot")))

    pal_state = {"i": 0}
    for cy in cols:
        color, width = _year_style(cy, current, previous, pal_state)
        fig.add_trace(go.Scatter(x=wide.index, y=wide[cy], mode="lines+markers", name=str(cy),
                                  line=dict(color=color, width=width), marker=dict(size=4)))

    layout = _base_layout(title, height, subtitle=subtitle)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def latest_vs_band_chart(wide, current, ref_years, title, height=COMPACT_HEIGHT, subtitle=""):
    """Min/Max/Avg band from ref_years, with ONLY the current (latest) year's
    line drawn on top — mirrors TDM's separate 'Min/Max/Avg vs Latest' panel,
    a cleaner 'is this year normal' read than the full multi-year overlay."""
    ref = wide[[c for c in ref_years if c in wide.columns]]
    lo, hi, avg = ref.min(axis=1, skipna=True), ref.max(axis=1, skipna=True), ref.mean(axis=1, skipna=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=wide.index, y=hi, mode="lines", name=f"Max (L{len(ref_years)}Y)",
                              line=dict(color=BAND_MAX, width=1.4)))
    fig.add_trace(go.Scatter(x=wide.index, y=lo, mode="lines", name=f"Min (L{len(ref_years)}Y)",
                              line=dict(color=BAND_MIN, width=1.4), fill="tonexty",
                              fillcolor="rgba(180,180,180,0.10)"))
    fig.add_trace(go.Scatter(x=wide.index, y=avg, mode="lines", name=f"Avg (L{len(ref_years)}Y)",
                              line=dict(color=BAND_AVG, width=1.4, dash="dot")))
    if current in wide.columns:
        fig.add_trace(go.Scatter(x=wide.index, y=wide[current], mode="lines+markers", name=str(current),
                                  line=dict(color=YEAR_CURRENT, width=2.5), marker=dict(size=6)))
    layout = _base_layout(title, height, subtitle=subtitle)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def cumulative_chart(cum_wide, title, current=None, previous=None, height=COMPACT_HEIGHT, subtitle=""):
    """Cumulative sum per crop year (x = crop month) — same current/previous/
    palette color scheme as seasonal_chart, no band (matches TDM's Cumulative
    panel, which is per-year lines only)."""
    cols = list(cum_wide.columns)
    current = current or cols[-1]
    previous = previous or (cols[-2] if len(cols) > 1 else None)
    fig = go.Figure()
    pal_state = {"i": 0}
    for cy in cols:
        color, width = _year_style(cy, current, previous, pal_state)
        fig.add_trace(go.Scatter(x=cum_wide.index, y=cum_wide[cy], mode="lines+markers", name=str(cy),
                                  line=dict(color=color, width=width), marker=dict(size=4)))
    layout = _base_layout(title, height, subtitle=subtitle)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def single_line_chart(x, y, title, color=BLUE, height=COMPACT_HEIGHT, y_suffix="", subtitle=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=2)))
    fig.update_layout(**_base_layout(title, height, y_suffix, subtitle=subtitle))
    return fig


def two_line_chart(x, y1, name1, y2, name2, title, height=COMPACT_HEIGHT, subtitle=""):
    """Two series that share one meaningful axis — e.g. a level and its
    rolling average. Never use this to fake a dual-axis comparison."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y1, mode="lines", name=name1, line=dict(color=BLUE, width=2)))
    fig.add_trace(go.Scatter(x=x, y=y2, mode="lines", name=name2, line=dict(color=MUTED, width=1.5, dash="dot")))
    layout = _base_layout(title, height, subtitle=subtitle)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def multi_series_chart(df_x_date, series: dict, title, height=COMPACT_HEIGHT, subtitle=""):
    """<=4 categorical series sharing one axis, direct-labeled at the line end
    (mandatory once you're at 4 series). `series` = {name: (y_values, color)}."""
    fig = go.Figure()
    for name, (y, color) in series.items():
        fig.add_trace(go.Scatter(x=df_x_date, y=y, mode="lines", name=name, line=dict(color=color, width=2)))
    layout = _base_layout(title, height, subtitle=subtitle)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def diverging_bar_chart(x, y, title, height=COMPACT_HEIGHT, subtitle=""):
    """A single continuous time series of signed values (stock build/draw) —
    green above zero, red below. One bar per period, chronological — not
    grouped by year, which is what turns this into an unreadable wall."""
    colors = [GOOD if v >= 0 else CRITICAL for v in y]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=y, marker_color=colors, marker_line_width=0))
    fig.update_layout(**_base_layout(title, height, subtitle=subtitle))
    return fig


def rolling_multi_chart(df_by_type: dict, window: int, title, height=COMPACT_HEIGHT + 40, subtitle=""):
    """Rolling `window`-month Disappearance for 2+ coffee types on one axis —
    e.g. {'Robusta': (dates, values), 'Arabica': (dates, values)}. Same unit,
    directly comparable, categorical color per type."""
    fig = go.Figure()
    colors = {"Robusta": BLUE, "Arabica": ORANGE}
    for name, (x, y) in df_by_type.items():
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=name,
                                  line=dict(color=colors.get(name, GREEN), width=2)))
    layout = _base_layout(title, height, subtitle=subtitle)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig
