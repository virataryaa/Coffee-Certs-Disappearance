import numpy as np
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


COMPACT_HEIGHT = 340


# No title lives inside the Plotly figure — a Plotly title's position is a
# fraction of the *whole* figure (paper coordinates), so it's one font-metric
# surprise away from clipping against the canvas edge (exactly what kept
# happening here). The title/subtitle instead render as plain DOM text via
# table_html.chart_header_html(), placed directly above st.plotly_chart —
# same pattern already used for the HTML tables, and immune to the problem.
def _base_layout(height=COMPACT_HEIGHT, y_suffix=""):
    return dict(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=INK_SECONDARY, family="system-ui, -apple-system, Segoe UI, sans-serif", size=11),
        margin=dict(l=54, r=16, t=12, b=44),
        height=height,
        showlegend=False,
        hovermode="x unified",
        xaxis=dict(gridcolor=GRID, linecolor=BASELINE, tickfont=dict(color=MUTED, size=10),
                   showgrid=False, zeroline=False),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED, size=10),
                   tickformat=",.0f", ticksuffix=y_suffix, zeroline=True, zerolinecolor=BASELINE,
                   zerolinewidth=1),
    )


def _legend(y=-0.18):
    return dict(orientation="h", yanchor="top", y=y, xanchor="left", x=0,
                bgcolor="rgba(0,0,0,0)", font=dict(size=10.5, color=INK_SECONDARY))


def recent_columns(columns, n=6):
    """Last n columns (crop years / years), oldest first — keeps a handful of
    stale outlier years from ever entering a chart's axis range."""
    cols = list(columns)
    return cols[-n:] if len(cols) > n else cols


def seasonal_chart(wide, current=None, previous=None, height=COMPACT_HEIGHT):
    """One line per selected crop year (x = crop month) — latest year bold
    dark, previous year red, older years a cycling pastel palette, every
    year labeled in the legend. No Min/Max/Avg band here — that comparison
    already has its own chart (latest_vs_band_chart); dropping it is also
    what makes room for every year's legend entry to fit on one line."""
    cols = list(wide.columns)
    current = current if current is not None else (cols[-1] if cols else None)
    previous = previous if previous is not None else (cols[-2] if len(cols) > 1 else None)
    fig = go.Figure()

    pal_state = {"i": 0}
    for cy in cols:
        color, width = _year_style(cy, current, previous, pal_state)
        fig.add_trace(go.Scatter(x=wide.index, y=wide[cy], mode="lines+markers", name=str(cy),
                                  line=dict(color=color, width=width), marker=dict(size=4)))

    layout = _base_layout(height)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def latest_vs_band_chart(wide, current, ref_years, height=COMPACT_HEIGHT):
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
    layout = _base_layout(height)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def cumulative_chart(cum_wide, current=None, previous=None, show_avg=True, height=COMPACT_HEIGHT):
    """Cumulative sum per crop year (x = crop month), same current/previous/
    palette color scheme as seasonal_chart, plus an Avg line across all
    plotted years (show_avg) so the current year's build reads against a
    baseline, not just against a wall of peer lines."""
    cols = list(cum_wide.columns)
    current = current or cols[-1]
    previous = previous or (cols[-2] if len(cols) > 1 else None)
    fig = go.Figure()
    if show_avg and len(cols) > 1:
        avg = cum_wide.mean(axis=1, skipna=True)
        fig.add_trace(go.Scatter(x=cum_wide.index, y=avg, name=f"Avg ({len(cols)}y)",
                                  mode="lines", line=dict(color=BAND_AVG, width=1.4, dash="dot")))
    pal_state = {"i": 0}
    for cy in cols:
        color, width = _year_style(cy, current, previous, pal_state)
        # Same rule as seasonal_chart: only current/previous get a legend
        # entry, so a 6-year overlay never wraps into a crowded legend.
        fig.add_trace(go.Scatter(x=cum_wide.index, y=cum_wide[cy], mode="lines+markers", name=str(cy),
                                  line=dict(color=color, width=width), marker=dict(size=4),
                                  showlegend=cy in (current, previous)))
    layout = _base_layout(height)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def single_line_chart(x, y, color=BLUE, height=COMPACT_HEIGHT, y_suffix=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=2)))
    fig.update_layout(**_base_layout(height, y_suffix))
    return fig


def two_line_chart(x, y1, name1, y2, name2, height=COMPACT_HEIGHT):
    """Two series that share one meaningful axis — e.g. a level and its
    rolling average. Never use this to fake a dual-axis comparison."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y1, mode="lines", name=name1, line=dict(color=BLUE, width=2)))
    fig.add_trace(go.Scatter(x=x, y=y2, mode="lines", name=name2, line=dict(color=MUTED, width=1.5, dash="dot")))
    layout = _base_layout(height)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def scatter_with_r2(x, y, x_name, y_name, height=COMPACT_HEIGHT):
    """Scatter of two series with a fitted regression line and R² — returns
    (figure, r2) so the caller can put R² in the chart's own header text
    rather than duplicating it inside the plot."""
    pair = pd.DataFrame({"x": x, "y": y}).dropna()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pair["x"], y=pair["y"], mode="markers", name=f"{x_name} vs {y_name}",
                              marker=dict(color=BLUE, size=6, opacity=0.75,
                                          line=dict(color=SURFACE, width=1))))
    r2 = 0.0
    if len(pair) >= 2 and pair["x"].std() > 0:
        slope, intercept = np.polyfit(pair["x"], pair["y"], 1)
        x_line = np.linspace(pair["x"].min(), pair["x"].max(), 100)
        fig.add_trace(go.Scatter(x=x_line, y=slope * x_line + intercept, mode="lines", name="Fit",
                                  line=dict(color=CRITICAL, width=1.5, dash="dash")))
        r2 = float(pair["x"].corr(pair["y"]) ** 2)
    layout = _base_layout(height)
    layout["showlegend"] = False
    layout["xaxis"]["title"] = dict(text=x_name, font=dict(color=MUTED, size=10))
    layout["yaxis"]["title"] = dict(text=y_name, font=dict(color=MUTED, size=10))
    fig.update_layout(**layout)
    return fig, r2


def r2_heatmap_chart(z, x_labels, y_labels, x_title="", y_title="", height=COMPACT_HEIGHT + 60):
    """Blues heatmap of R² values over a (rolling avg x arb lag) grid."""
    fig = go.Figure(go.Heatmap(
        z=z, x=x_labels, y=y_labels, colorscale="Blues", zmin=0, zmax=1,
        colorbar=dict(title="R²", thickness=12, outlinewidth=0),
        text=[[f"{v:.2f}" for v in row] for row in z],
        texttemplate="%{text}", textfont=dict(size=9),
        hovertemplate=f"{x_title}: %{{x}}<br>{y_title}: %{{y}}<br>R²: %{{z:.2f}}<extra></extra>",
    ))
    layout = _base_layout(height)
    layout["xaxis"]["title"] = dict(text=x_title, font=dict(color=MUTED, size=10))
    layout["yaxis"]["title"] = dict(text=y_title, font=dict(color=MUTED, size=10))
    layout["xaxis"]["type"] = "category"
    layout["yaxis"]["type"] = "category"
    fig.update_layout(**layout)
    return fig


def multi_series_chart(df_x_date, series: dict, height=COMPACT_HEIGHT):
    """<=4 categorical series sharing one axis, direct-labeled at the line end
    (mandatory once you're at 4 series). `series` = {name: (y_values, color)}."""
    fig = go.Figure()
    for name, (y, color) in series.items():
        fig.add_trace(go.Scatter(x=df_x_date, y=y, mode="lines", name=name, line=dict(color=color, width=2)))
    layout = _base_layout(height)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig


def diverging_bar_chart(x, y, height=COMPACT_HEIGHT):
    """A single continuous time series of signed values (stock build/draw) —
    green above zero, red below. One bar per period, chronological — not
    grouped by year, which is what turns this into an unreadable wall."""
    colors = [GOOD if v >= 0 else CRITICAL for v in y]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=y, marker_color=colors, marker_line_width=0))
    fig.update_layout(**_base_layout(height))
    return fig


def bars_with_secondary_line_chart(x_bars, bar_series: dict, x_line, y_line, line_name,
                                    height=COMPACT_HEIGHT, line_color=INK):
    """Grouped monthly bars (e.g. Robusta/Arabica disappearance) on the
    primary axis, one line (e.g. the KC/RC spread) on a secondary axis.
    Deliberately a dual-axis chart, by explicit request — the disappearance
    volumes and the price spread are in unrelated units and orders of
    magnitude, so there's no honest single-axis way to show both together;
    the two axes are labeled so the reader isn't misled about scale."""
    fig = go.Figure()
    colors = {"Robusta": BLUE, "Arabica": ORANGE}
    for name, y in bar_series.items():
        fig.add_trace(go.Bar(x=x_bars, y=y, name=name, marker_color=colors.get(name, GREEN), marker_line_width=0))
    fig.add_trace(go.Scatter(x=x_line, y=y_line, name=line_name, mode="lines",
                              line=dict(color=line_color, width=2.2), yaxis="y2"))
    layout = _base_layout(height)
    layout["barmode"] = "group"
    layout["showlegend"] = True
    layout["legend"] = _legend()
    layout["yaxis2"] = dict(overlaying="y", side="right", gridcolor=GRID, showgrid=False,
                             tickfont=dict(color=MUTED, size=10), zeroline=False)
    fig.update_layout(**layout)
    return fig


def line_with_secondary_line_chart(x1, y1, name1, x2, y2, name2, height=COMPACT_HEIGHT,
                                    color1=BLUE, color2=INK):
    """One line on the primary axis (e.g. Robusta's % share of disappearance),
    one line on a secondary axis (e.g. the KC/RC spread) — same deliberate
    dual-axis exception as bars_with_secondary_line_chart, for the same
    reason: a % share and a $/MT or ¢/lb spread have no honest common axis."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x1, y=y1, name=name1, mode="lines", line=dict(color=color1, width=2.2)))
    fig.add_trace(go.Scatter(x=x2, y=y2, name=name2, mode="lines", line=dict(color=color2, width=2.2), yaxis="y2"))
    layout = _base_layout(height)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    layout["yaxis2"] = dict(overlaying="y", side="right", gridcolor=GRID, showgrid=False,
                             tickfont=dict(color=MUTED, size=10), zeroline=False)
    fig.update_layout(**layout)
    return fig


def rolling_multi_chart(df_by_type: dict, height=COMPACT_HEIGHT + 40):
    """Rolling N-month Disappearance for 2+ coffee types on one axis —
    e.g. {'Robusta': (dates, values), 'Arabica': (dates, values)}. Same unit,
    directly comparable, categorical color per type."""
    fig = go.Figure()
    colors = {"Robusta": BLUE, "Arabica": ORANGE}
    for name, (x, y) in df_by_type.items():
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=name,
                                  line=dict(color=colors.get(name, GREEN), width=2)))
    layout = _base_layout(height)
    layout["showlegend"] = True
    layout["legend"] = _legend()
    fig.update_layout(**layout)
    return fig
