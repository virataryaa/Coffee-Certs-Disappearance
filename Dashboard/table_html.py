import pandas as pd

from charts import GOOD, CRITICAL, GRID, INK, INK_SECONDARY, MUTED, SURFACE

MONTH_ABBR = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
              7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}


def _flatten(html):
    # st.markdown treats 4+ space indented lines as a code block, not HTML —
    # strip leading whitespace per line so the tags actually render.
    return "\n".join(line.strip() for line in html.strip().split("\n"))


def _delta_cell(pct, scale=20):
    if pd.isna(pct):
        return "<td></td>"
    color = CRITICAL if pct < 0 else GOOD
    width = max(6, min(abs(pct) / scale * 100, 100))
    return (
        f'<td class="delta-cell"><div class="delta-track">'
        f'<div class="delta-fill" style="width:{width:.0f}%;background:{color};"></div>'
        f'<span style="color:{color};">{pct:+.0f}%</span></div></td>'
    )


_STYLE = f"""
<style>
.coffee-table-wrap {{ overflow-x: auto; margin: 4px 0 20px; }}
.coffee-table {{ border-collapse: collapse; width: 100%; font-size: 12px;
                font-variant-numeric: tabular-nums;
                font-family: system-ui, -apple-system, Segoe UI, sans-serif; }}
.coffee-table-title {{ font-size: 13px; font-weight: 600; color: {INK}; margin: 0 0 2px; }}
.coffee-table-subtitle {{ font-size: 11px; color: {MUTED}; margin: 0 0 10px; font-variant-numeric: normal; }}
.coffee-table th {{ text-align: right; padding: 6px 10px; font-size: 10.5px; font-weight: 600;
                    color: {MUTED}; text-transform: uppercase; letter-spacing: 0.03em;
                    border-bottom: 1px solid {GRID}; white-space: nowrap; }}
.coffee-table th.period-col {{ text-align: left; }}
.coffee-table td {{ padding: 5px 10px; text-align: right; white-space: nowrap;
                    color: {INK}; border-bottom: 1px solid {GRID}; }}
.coffee-table td.period-col {{ text-align: left; color: {INK_SECONDARY}; font-variant-numeric: normal; }}
.coffee-table tr:last-child td {{ border-bottom: none; }}
.coffee-table tr.total-row td {{ font-weight: 600; border-top: 1px solid {MUTED}; border-bottom: none; }}
.coffee-table td.total-col {{ font-weight: 600; }}
.coffee-table td.delta-cell {{ min-width: 90px; padding: 5px 10px; }}
.delta-track {{ position: relative; height: 14px; background: {GRID}; border-radius: 3px;
               overflow: hidden; display: flex; align-items: center; justify-content: center; }}
.delta-fill {{ position: absolute; top: 0; left: 0; height: 100%; opacity: 0.16; }}
.delta-track span {{ position: relative; z-index: 1; font-size: 10px; font-weight: 700; }}
</style>
"""


def _fmt(v, decimals=0):
    if pd.isna(v):
        return ""
    return f"{v:,.{decimals}f}"


def _compact(v):
    """Auto-compact big numbers for a stat-tile value: 1,284 / 12.9K / 4.2M."""
    if pd.isna(v):
        return "–"
    a = abs(v)
    if a >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if a >= 10_000:
        return f"{v / 1_000:.1f}K"
    return f"{v:,.0f}"


_TILE_STYLE = f"""
<style>
.coffee-tile-row {{ display: flex; gap: 12px; margin: 4px 0 20px; flex-wrap: wrap; }}
.coffee-tile {{ flex: 1 1 180px; border: 1px solid {GRID}; border-radius: 8px;
               padding: 14px 16px; background: {SURFACE}; }}
.coffee-tile .label {{ font-size: 11px; font-weight: 600; color: {MUTED};
               text-transform: uppercase; letter-spacing: 0.03em; }}
.coffee-tile .value {{ font-size: 24px; font-weight: 700; color: {INK}; margin: 4px 0 2px;
               font-variant-numeric: normal; }}
.coffee-tile .delta {{ font-size: 12px; font-weight: 600; }}
.coffee-tile .desc {{ font-size: 11px; color: {MUTED}; margin-top: 4px; }}
</style>
"""


def stat_tile_row_html(tiles):
    """tiles: list of (label, value, unit, delta_pct_or_None, description)."""
    cards = []
    for label, value, unit, delta, desc in tiles:
        delta_html = ""
        if delta is not None and pd.notna(delta):
            color = CRITICAL if delta < 0 else GOOD
            delta_html = f'<div class="delta" style="color:{color};">{delta:+.1f}% YoY</div>'
        desc_html = f'<div class="desc">{desc}</div>' if desc else ""
        cards.append(f"""
        <div class="coffee-tile">
          <div class="label">{label}</div>
          <div class="value">{_compact(value)} <span style="font-size:13px;color:{MUTED};">{unit}</span></div>
          {delta_html}
          {desc_html}
        </div>
        """)
    return _flatten(f"""
    {_TILE_STYLE}
    <div class="coffee-tile-row">{''.join(cards)}</div>
    """)


def disappearance_table_html(pivot, month_cols, title, subtitle=""):
    """Crop-year rows x crop-month columns, plain numeric cells (no per-cell
    heatmap — a decade of history spans regimes a global color scale can't
    represent honestly), Total + a YoY delta bar."""
    rows_html = []
    for _, row in pivot.iterrows():
        cells = "".join(f"<td>{_fmt(row[m])}</td>" for m in month_cols)
        total_cell = f'<td class="total-col">{_fmt(row["Total"])}</td>'
        rows_html.append(
            f'<tr><td class="period-col">{row["CropYear"]}</td>{cells}{total_cell}{_delta_cell(row["YoY %"])}</tr>'
        )

    header_cells = "".join(f"<th>{m}</th>" for m in month_cols)
    sub = f'<div class="coffee-table-subtitle">{subtitle}</div>' if subtitle else ""

    html = f"""
    {_STYLE}
    <div class="coffee-table-title">{title}</div>
    {sub}
    <div class="coffee-table-wrap">
    <table class="coffee-table">
      <thead><tr><th class="period-col">Crop Year</th>{header_cells}<th>Total</th><th>YoY</th></tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    </div>
    """
    return _flatten(html)


def ytd_summary_table_html(ytd_series, title, unit=""):
    yoy = ytd_series.pct_change() * 100
    rows_html = []
    for cy in ytd_series.index:
        v = ytd_series[cy]
        val_cell = f"<td>{_fmt(v)}</td>" if pd.notna(v) else "<td></td>"
        rows_html.append(f'<tr><td class="period-col">{cy}</td>{val_cell}{_delta_cell(yoy.get(cy))}</tr>')

    return _flatten(f"""
    {_STYLE}
    <div class="coffee-table-title">{title}</div>
    <div class="coffee-table-wrap">
    <table class="coffee-table">
      <thead><tr><th class="period-col">Crop Year</th><th>Total {unit}</th><th>YoY</th></tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    </div>
    """)


def stocks_level_table_html(level, title, subtitle="", n_years=8):
    """Calendar-year rows x calendar-month columns, plain numeric levels —
    last n_years only, since older regimes (a different stock-reporting
    universe a decade ago) aren't a useful comparison anyway."""
    years = list(level.index)[-n_years:]
    level = level.loc[years]
    rows_html = []
    for year in level.index:
        cells = "".join(
            f"<td>{_fmt(level.loc[year, m])}</td>" if pd.notna(level.loc[year, m]) else "<td></td>"
            for m in level.columns
        )
        rows_html.append(f'<tr><td class="period-col">{year}</td>{cells}</tr>')

    header_cells = "".join(f"<th>{MONTH_ABBR[m]}</th>" for m in level.columns)
    sub = f'<div class="coffee-table-subtitle">{subtitle}</div>' if subtitle else ""
    html = f"""
    {_STYLE}
    <div class="coffee-table-title">{title}</div>
    {sub}
    <div class="coffee-table-wrap">
    <table class="coffee-table">
      <thead><tr><th class="period-col">Year</th>{header_cells}</tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    </div>
    """
    return _flatten(html)
