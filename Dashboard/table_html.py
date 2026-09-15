import pandas as pd

from charts import GOOD, CRITICAL, GRID, INK, MUTED

LIGHT_GREEN = (234, 250, 240)
DARK_GREEN = (10, 110, 66)


def _green_shade(t):
    t = max(0.0, min(1.0, t))
    r = LIGHT_GREEN[0] + (DARK_GREEN[0] - LIGHT_GREEN[0]) * t
    g = LIGHT_GREEN[1] + (DARK_GREEN[1] - LIGHT_GREEN[1]) * t
    b = LIGHT_GREEN[2] + (DARK_GREEN[2] - LIGHT_GREEN[2]) * t
    return f"rgb({int(r)},{int(g)},{int(b)})", "#0b0b0b"


def _bar_cell(pct, scale=15, height=16, font_size=10):
    if pd.isna(pct):
        return ""
    color = CRITICAL if pct < 0 else GOOD
    width = max(4, min(abs(pct) / scale * 100, 100))
    return (
        f'<div style="position:relative;height:{height}px;background:#f2f1ee;'
        'border-radius:4px;overflow:hidden;">'
        f'<div style="position:absolute;top:0;left:0;height:100%;width:{width:.0f}%;'
        f'background:{color};opacity:0.28;"></div>'
        f'<div style="position:relative;z-index:1;text-align:center;font-size:{font_size}px;'
        f'line-height:{height}px;font-weight:700;color:{color};">{pct:+.0f}%</div>'
        '</div>'
    )


def _flatten(html):
    return "\n".join(line.strip() for line in html.strip().split("\n"))


_STYLE = f"""
<style>
.coffee-table-wrap {{ overflow-x: auto; margin: 8px 0; border: 1px solid {GRID}; border-radius: 6px; }}
.coffee-table {{ border-collapse: collapse; width: 100%; font-size: 11px;
                font-family: system-ui, -apple-system, Segoe UI, sans-serif; }}
.coffee-table caption {{ text-align: left; font-weight: 700; font-size: 13px;
                         padding: 6px 10px; color: {INK}; }}
.coffee-table th {{ background: #1e3a5f; color: white; padding: 4px 8px;
                    text-align: right; white-space: nowrap; }}
.coffee-table th.period-col, .coffee-table td.period-col {{ text-align: left; font-style: italic;
                    color: {MUTED}; white-space: nowrap; }}
.coffee-table td {{ padding: 3px 8px; line-height: 15px; text-align: right; white-space: nowrap; }}
.coffee-table td.bar-cell {{ min-width: 60px; padding: 2px 6px; }}
.coffee-table tr.total-row td {{ font-weight: 700; border-top: 2px solid {INK}; }}
</style>
"""


def _fmt(v, decimals=0):
    if pd.isna(v):
        return ""
    return f"{v:,.{decimals}f}"


def disappearance_table_html(pivot, month_cols, title, subtitle=""):
    """Crop-year rows x crop-month columns, plus Total / YoY%, with a
    heatmap on the month cells and Min/Max/Avg(5) reference rows appended."""
    vals = pivot[month_cols].values.flatten()
    vals = vals[~pd.isna(vals)]
    vmin, vmax = (vals.min(), vals.max()) if len(vals) else (0, 1)
    span = (vmax - vmin) or 1

    def month_cells(row):
        cells = []
        for m in month_cols:
            v = row[m]
            if pd.isna(v):
                cells.append("<td></td>")
                continue
            t = (v - vmin) / span
            bg, txt = _green_shade(t)
            cells.append(f'<td style="background:{bg};color:{txt};">{_fmt(v)}</td>')
        return "".join(cells)

    rows_html = []
    for _, row in pivot.iterrows():
        total_cell = f'<td style="font-weight:700;">{_fmt(row["Total"])}</td>'
        yoy_cell = f'<td class="bar-cell">{_bar_cell(row["YoY %"])}</td>'
        rows_html.append(
            f'<tr><td class="period-col">{row["CropYear"]}</td>{month_cells(row)}{total_cell}{yoy_cell}</tr>'
        )

    header_cells = "".join(f"<th>{m}</th>" for m in month_cols)
    sub = f'<caption style="font-weight:400;font-size:11px;color:{MUTED};">{subtitle}</caption>' if subtitle else ""

    html = f"""
    {_STYLE}
    <div class="coffee-table-wrap">
    <table class="coffee-table">
      <caption>{title}</caption>
      {sub}
      <thead><tr><th class="period-col">Crop Year</th>{header_cells}<th>Total</th><th>YoY</th></tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    </div>
    """
    return _flatten(html)


MONTH_ABBR = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
              7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}


def stocks_level_table_html(level, title, subtitle=""):
    """Calendar-year rows x calendar-month columns, red(low)->green(high)
    heatmap of stock levels — mirrors 'ECF EU Stocks Split'."""
    vals = level.values.flatten()
    vals = vals[~pd.isna(vals)]
    vmin, vmax = (vals.min(), vals.max()) if len(vals) else (0, 1)
    span = (vmax - vmin) or 1

    rows_html = []
    for year in level.index:
        cells = []
        for m in level.columns:
            v = level.loc[year, m]
            if pd.isna(v):
                cells.append("<td></td>")
                continue
            t = (v - vmin) / span
            bg, txt = _green_shade(t)
            cells.append(f'<td style="background:{bg};color:{txt};">{_fmt(v)}</td>')
        rows_html.append(f'<tr><td class="period-col">{year}</td>{"".join(cells)}</tr>')

    header_cells = "".join(f"<th>{MONTH_ABBR[m]}</th>" for m in level.columns)
    sub = f'<caption style="font-weight:400;font-size:11px;color:{MUTED};">{subtitle}</caption>' if subtitle else ""
    html = f"""
    {_STYLE}
    <div class="coffee-table-wrap">
    <table class="coffee-table">
      <caption>{title}</caption>
      {sub}
      <thead><tr><th class="period-col">Year</th>{header_cells}</tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    </div>
    """
    return _flatten(html)


def stocks_change_table_html(change, avg_row, title, subtitle=""):
    """Calendar-year rows x calendar-month columns, red(-ve)/green(+ve)
    bar-shaded change table, with an 'Avg' summary row appended."""
    def cell(v):
        if pd.isna(v):
            return "<td></td>"
        color = CRITICAL if v < 0 else GOOD
        return f'<td style="color:{color};font-weight:600;">{v:+,.0f}</td>'

    rows_html = []
    for year in change.index:
        cells = "".join(cell(change.loc[year, m]) for m in change.columns)
        rows_html.append(f'<tr><td class="period-col">{year}</td>{cells}</tr>')
    avg_cells = "".join(cell(avg_row.get(m)) for m in change.columns)
    rows_html.append(f'<tr class="total-row"><td class="period-col">Avg</td>{avg_cells}</tr>')

    header_cells = "".join(f"<th>{MONTH_ABBR[m]}</th>" for m in change.columns)
    sub = f'<caption style="font-weight:400;font-size:11px;color:{MUTED};">{subtitle}</caption>' if subtitle else ""
    html = f"""
    {_STYLE}
    <div class="coffee-table-wrap">
    <table class="coffee-table">
      <caption>{title}</caption>
      {sub}
      <thead><tr><th class="period-col">Year</th>{header_cells}</tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    </div>
    """
    return _flatten(html)


def ytd_summary_table_html(ytd_series, title, unit=""):
    values = ytd_series.dropna()
    if values.empty:
        vmin = vmax = 0
    else:
        vmin, vmax = values.min(), values.max()
    span = (vmax - vmin) or 1
    yoy = ytd_series.pct_change() * 100

    rows_html = []
    for cy in ytd_series.index:
        v = ytd_series[cy]
        if pd.isna(v):
            val_cell = "<td></td>"
        else:
            t = (v - vmin) / span
            bg, txt = _green_shade(t)
            val_cell = f'<td style="background:{bg};color:{txt};">{_fmt(v)}</td>'
        bar = _bar_cell(yoy.get(cy), height=14, font_size=9)
        rows_html.append(f'<tr><td class="period-col">{cy}</td>{val_cell}<td class="bar-cell">{bar}</td></tr>')

    return _flatten(f"""
    {_STYLE}
    <div class="coffee-table-wrap">
    <table class="coffee-table">
      <thead><tr><th class="period-col">Crop Year</th><th>Total {unit}</th><th>%</th></tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    </div>
    """)
