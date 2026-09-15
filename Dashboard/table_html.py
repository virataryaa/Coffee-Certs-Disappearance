import pandas as pd

from charts import GOOD, CRITICAL, GRID, INK, INK_SECONDARY, MUTED

MONTH_ABBR = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
              7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

# TDM/files/app.py's heatmap conditional-formatting palette: sequential Blues
# for magnitude cells, diverging RdYlGn for the vs-Avg% delta row.
_BLUES = ["#f7fbff", "#deebf7", "#c6dbef", "#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#08519c", "#08306b"]
_RDYLGN = ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850"]
_NAVY = "#0a2463"
_NAVY_TEXT = "#dde4f0"
_IDX_BG = "#f5f5f7"
_IDX_BORDER = "#d8d8e0"
_REF_BG = "#eef3fb"
_REF_TEXT = "#2c3e6e"


def _lerp_hex(pal, t):
    t = max(0.0, min(1.0, t))
    n = len(pal) - 1
    i = int(t * n)
    f = t * n - i
    if i >= n:
        return pal[-1]

    def _h(x):
        return [int(x.lstrip("#")[j:j + 2], 16) for j in (0, 2, 4)]

    r1, g1, b1 = _h(pal[i])
    r2, g2, b2 = _h(pal[i + 1])
    return f"#{int(r1 + f * (r2 - r1)):02x}{int(g1 + f * (g2 - g1)):02x}{int(b1 + f * (b2 - b1)):02x}"


def _txt_on(bg):
    r, g, b = [int(bg.lstrip("#")[j:j + 2], 16) for j in (0, 2, 4)]
    return "#1d1d1f" if (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.55 else "#ffffff"


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


_HEATMAP_STYLE = f"""
<style>
.coffee-hm-wrap {{ overflow-x: auto; border-radius: 6px; border: 1px solid {GRID}; margin: 4px 0 20px; }}
.coffee-hm {{ border-collapse: collapse; width: 100%; font-family: system-ui, -apple-system, Segoe UI, sans-serif; }}
.coffee-hm th, .coffee-hm td {{ padding: 3px 8px; white-space: nowrap; font-size: 11px; text-align: center; }}
.coffee-hm th {{ background: {_NAVY}; color: {_NAVY_TEXT}; font-weight: 600; border-bottom: 1px solid #2a4a83; }}
.coffee-hm th.idx {{ text-align: left; }}
.coffee-hm td.idx {{ text-align: left; font-weight: 600; background: {_IDX_BG}; border-right: 1px solid {_IDX_BORDER}; }}
.coffee-hm td.blank {{ background: {GRID}; }}
.coffee-hm td.total {{ background: {_IDX_BG}; border-left: 2px solid {_IDX_BORDER}; font-weight: 700; }}
.coffee-hm td.ref {{ background: {_REF_BG}; color: {_REF_TEXT}; font-style: italic; font-weight: 600; }}
.coffee-hm td.sep {{ height: 2px; padding: 0; background: {_IDX_BORDER}; }}
</style>
"""


def heatmap_table_html(pivot, month_cols, title, subtitle="", total_col="Total", yoy_col="YoY %",
                        ref_years=None, current_year=None, ytd_months=None):
    """Crop-year x month table with the TDM-style conditional formatting:
    a sequential Blues heatmap on the magnitude cells (normalized across the
    whole table), highlighted Total + YTD columns, a red/green YoY% text
    column, a diverging RdYlGn 'vs Avg%' row under the current year, and
    italic Min/Max/Avg(L{n}Y) reference rows from `ref_years` (complete
    years only). `ytd_months` = how many of the current crop year's months
    have been reported — the same window is summed for every row so YTD
    stays apples-to-apples across years."""
    pivot = pivot.set_index("CropYear") if "CropYear" in pivot.columns else pivot
    rows = list(pivot.index)
    current_year = current_year or rows[-1]
    ytd_cols = month_cols[:ytd_months] if ytd_months else []
    ytd_label = f"YTD ({ytd_cols[0]}–{ytd_cols[-1]})" if len(ytd_cols) > 1 else (f"YTD ({ytd_cols[0]})" if ytd_cols else None)
    n_extra = 2 + (1 if ytd_label else 0)

    nums = [float(pivot.loc[r, m]) for r in rows for m in month_cols if pd.notna(pivot.loc[r, m])]
    vmin, vmax = (min(nums), max(nums)) if nums else (0.0, 1.0)

    def _blue_bg(v):
        if pd.isna(v) or vmax == vmin:
            return GRID
        return _lerp_hex(_BLUES, (float(v) - vmin) / (vmax - vmin))

    extra_headers = f"<th>{total_col}</th>" + (f"<th>{ytd_label}</th>" if ytd_label else "") + f"<th>{yoy_col}</th>"
    header = f'<tr><th class="idx"></th>' + "".join(f"<th>{m}</th>" for m in month_cols) + extra_headers + "</tr>"

    body = []
    for r in rows:
        cells = [f'<td class="idx">{r}</td>']
        for m in month_cols:
            v = pivot.loc[r, m]
            if pd.isna(v):
                cells.append('<td class="blank"></td>')
            else:
                bg = _blue_bg(v)
                cells.append(f'<td style="background:{bg};color:{_txt_on(bg)}">{_fmt(v)}</td>')
        tv = pivot.loc[r, total_col]
        cells.append(f'<td class="total">{_fmt(tv)}</td>' if pd.notna(tv) else '<td class="total"></td>')
        if ytd_label:
            ytdv = pivot.loc[r, ytd_cols].sum(min_count=1)
            cells.append(f'<td class="total">{_fmt(ytdv)}</td>' if pd.notna(ytdv) else '<td class="total"></td>')
        yv = pivot.loc[r, yoy_col]
        if pd.isna(yv):
            cells.append("<td></td>")
        else:
            color = GOOD if yv >= 0 else CRITICAL
            cells.append(f'<td style="color:{color};font-weight:700">{yv:+.1f}%</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")

        # vs-Avg% diverging row, directly under the current (latest) crop year
        if r == current_year and ref_years:
            ref = pivot.loc[[y for y in ref_years if y in pivot.index], month_cols].astype(float)
            avg = ref.mean()
            vs_avg = {m: (float(pivot.loc[r, m]) / avg[m] - 1) * 100
                      if pd.notna(pivot.loc[r, m]) and avg[m] else float("nan") for m in month_cols}
            vals = [v for v in vs_avg.values() if pd.notna(v)]
            vabs = max(abs(min(vals)), abs(max(vals))) if vals else 20.0
            ncols = len(month_cols) + n_extra
            body.append(f'<tr><td class="sep" colspan="{ncols}"></td></tr>')
            cells = [f'<td class="idx" style="font-style:italic">vs Avg (L{len(ref_years)}Y)%</td>']
            for m in month_cols:
                v = vs_avg[m]
                if pd.isna(v):
                    cells.append('<td class="blank"></td>')
                else:
                    t = (v + vabs) / (2 * vabs) if vabs else 0.5
                    bg = _lerp_hex(_RDYLGN, t)
                    cells.append(f'<td style="background:{bg};color:{_txt_on(bg)};font-style:italic;font-weight:600">{v:+.1f}%</td>')
            cells.append('<td class="blank"></td>' * n_extra)
            body.append("<tr>" + "".join(cells) + "</tr>")

    if ref_years:
        complete = pivot.loc[[y for y in ref_years if y in pivot.index], month_cols + [total_col]].astype(float)
        if ytd_label:
            complete[ytd_label] = pivot.loc[complete.index, ytd_cols].sum(axis=1, min_count=1)
        ncols = len(month_cols) + n_extra
        body.append(f'<tr><td class="sep" colspan="{ncols}"></td></tr>')
        for label, agg in [(f"Min (L{len(ref_years)}Y)", complete.min()),
                            (f"Max (L{len(ref_years)}Y)", complete.max()),
                            (f"Avg (L{len(ref_years)}Y)", complete.mean())]:
            cells = [f'<td class="idx ref">{label}</td>']
            for m in month_cols:
                cells.append(f'<td class="ref">{_fmt(agg[m])}</td>')
            cells.append(f'<td class="ref total">{_fmt(agg[total_col])}</td>')
            if ytd_label:
                cells.append(f'<td class="ref total">{_fmt(agg[ytd_label])}</td>')
            cells.append('<td class="ref"></td>')
            body.append("<tr>" + "".join(cells) + "</tr>")

    sub = f'<div class="coffee-table-subtitle">{subtitle}</div>' if subtitle else ""
    html = f"""
    {_STYLE}
    {_HEATMAP_STYLE}
    <div class="coffee-table-title">{title}</div>
    {sub}
    <div class="coffee-hm-wrap">
    <table class="coffee-hm">{header}{''.join(body)}</table>
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
    """Calendar-year x calendar-month Blues heatmap, same conditional
    formatting as heatmap_table_html — last n_years only."""
    years = list(level.index)[-n_years:]
    level = level.loc[years]
    month_cols = list(level.columns)

    nums = [float(level.loc[y, m]) for y in years for m in month_cols if pd.notna(level.loc[y, m])]
    vmin, vmax = (min(nums), max(nums)) if nums else (0.0, 1.0)

    def _blue_bg(v):
        if pd.isna(v) or vmax == vmin:
            return GRID
        return _lerp_hex(_BLUES, (float(v) - vmin) / (vmax - vmin))

    header = '<tr><th class="idx"></th>' + "".join(f"<th>{MONTH_ABBR[m]}</th>" for m in month_cols) + "</tr>"
    body = []
    for y in years:
        cells = [f'<td class="idx">{y}</td>']
        for m in month_cols:
            v = level.loc[y, m]
            if pd.isna(v):
                cells.append('<td class="blank"></td>')
            else:
                bg = _blue_bg(v)
                cells.append(f'<td style="background:{bg};color:{_txt_on(bg)}">{_fmt(v)}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")

    sub = f'<div class="coffee-table-subtitle">{subtitle}</div>' if subtitle else ""
    html = f"""
    {_STYLE}
    {_HEATMAP_STYLE}
    <div class="coffee-table-title">{title}</div>
    {sub}
    <div class="coffee-hm-wrap">
    <table class="coffee-hm">{header}{''.join(body)}</table>
    </div>
    """
    return _flatten(html)
