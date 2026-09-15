import pandas as pd

from charts import GOOD, CRITICAL, GRID, INK, MUTED

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


_STYLE = f"""
<style>
.coffee-table-title {{ font-size: 12px; font-weight: 600; color: {INK}; margin: 0 0 1px; }}
.coffee-table-subtitle {{ font-size: 10px; color: {MUTED}; margin: 0 0 6px; font-variant-numeric: normal; }}
</style>
"""


def _fmt(v, decimals=0):
    if pd.isna(v):
        return ""
    return f"{v:,.{decimals}f}"


_HEATMAP_STYLE = f"""
<style>
.coffee-hm-wrap {{ overflow-x: auto; border-radius: 6px; border: 1px solid {GRID}; margin: 2px 0 12px; }}
.coffee-hm {{ border-collapse: collapse; width: 100%; font-family: system-ui, -apple-system, Segoe UI, sans-serif; }}
.coffee-hm th, .coffee-hm td {{ padding: 2px 6px; white-space: nowrap; font-size: 10px; text-align: center; }}
.coffee-hm th {{ background: {_NAVY}; color: {_NAVY_TEXT}; font-weight: 600; border-bottom: 1px solid #2a4a83; }}
.coffee-hm th.idx {{ text-align: left; }}
.coffee-hm td.idx {{ text-align: left; font-weight: 600; background: {_IDX_BG}; border-right: 1px solid {_IDX_BORDER}; }}
.coffee-hm td.blank {{ background: {GRID}; }}
.coffee-hm td.total {{ background: {_IDX_BG}; border-left: 2px solid {_IDX_BORDER}; font-weight: 700; }}
.coffee-hm td.ref {{ background: {_REF_BG}; color: {_REF_TEXT}; font-style: italic; font-weight: 600; }}
.coffee-hm td.sep {{ height: 2px; padding: 0; background: {_IDX_BORDER}; }}
.coffee-hm td.chg {{ min-width: 64px; padding: 2px 4px; }}
.coffee-chg-track {{ position: relative; height: 13px; background: {GRID}; border-radius: 3px;
                     overflow: hidden; display: flex; align-items: center; justify-content: center; }}
.coffee-chg-fill {{ position: absolute; top: 0; left: 0; height: 100%; opacity: 0.20; }}
.coffee-chg-track span {{ position: relative; z-index: 1; font-size: 9px; font-weight: 700; }}
</style>
"""


def heatmap_table_html(pivot, month_cols, title, subtitle="", total_col="Total",
                        ref_years=None, current_period=None, ytd_months=None):
    """Period x month table with the TDM-style conditional formatting: a
    sequential Blues heatmap on the magnitude cells (normalized across the
    whole table), a highlighted Total column with its own YoY%, a
    highlighted YTD column with its own YoY%, a diverging RdYlGn 'vs Avg%'
    row under the current period, and italic Min/Max/Avg(L{n}Y) reference
    rows from `ref_years` (complete periods only). `ytd_months` = how many
    of the current period's months have been reported — the same window is
    summed for every row so YTD stays apples-to-apples across periods."""
    pivot = pivot.set_index("Period") if "Period" in pivot.columns else pivot
    rows = list(pivot.index)
    current_period = current_period or rows[-1]
    ytd_cols = month_cols[:ytd_months] if ytd_months else []
    ytd_label = f"YTD ({ytd_cols[0]}–{ytd_cols[-1]})" if len(ytd_cols) > 1 else (f"YTD ({ytd_cols[0]})" if ytd_cols else None)
    n_extra = 2 + (2 if ytd_label else 0)  # Total, Total YoY%, [YTD, YTD YoY%]

    nums = [float(pivot.loc[r, m]) for r in rows for m in month_cols if pd.notna(pivot.loc[r, m])]
    vmin, vmax = (min(nums), max(nums)) if nums else (0.0, 1.0)

    def _blue_bg(v):
        if pd.isna(v) or vmax == vmin:
            return GRID
        return _lerp_hex(_BLUES, (float(v) - vmin) / (vmax - vmin))

    def _yoy_cell(v):
        if pd.isna(v):
            return "<td></td>"
        color = GOOD if v >= 0 else CRITICAL
        return f'<td style="color:{color};font-weight:700">{v:+.1f}%</td>'

    extra_headers = (f"<th>{total_col}</th><th>YoY %</th>"
                      + (f"<th>{ytd_label}</th><th>YoY %</th>" if ytd_label else ""))
    header = '<tr><th class="idx"></th>' + "".join(f"<th>{m}</th>" for m in month_cols) + extra_headers + "</tr>"

    ytd_series = pivot[ytd_cols].sum(axis=1, min_count=1) if ytd_label else None
    ytd_yoy = ytd_series.pct_change() * 100 if ytd_label else None
    total_yoy = pivot[total_col].pct_change() * 100

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
        cells.append(_yoy_cell(total_yoy.get(r)))
        if ytd_label:
            ytdv = ytd_series.get(r)
            cells.append(f'<td class="total">{_fmt(ytdv)}</td>' if pd.notna(ytdv) else '<td class="total"></td>')
            cells.append(_yoy_cell(ytd_yoy.get(r)))
        body.append("<tr>" + "".join(cells) + "</tr>")

        # vs-Avg% diverging row, directly under the current (latest) period
        if r == current_period and ref_years:
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
            complete[ytd_label] = ytd_series.reindex(complete.index)
        ncols = len(month_cols) + n_extra
        body.append(f'<tr><td class="sep" colspan="{ncols}"></td></tr>')
        for label, agg in [(f"Min (L{len(ref_years)}Y)", complete.min()),
                            (f"Max (L{len(ref_years)}Y)", complete.max()),
                            (f"Avg (L{len(ref_years)}Y)", complete.mean())]:
            cells = [f'<td class="idx ref">{label}</td>']
            for m in month_cols:
                cells.append(f'<td class="ref">{_fmt(agg[m])}</td>')
            cells.append(f'<td class="ref total">{_fmt(agg[total_col])}</td><td class="ref"></td>')
            if ytd_label:
                cells.append(f'<td class="ref total">{_fmt(agg[ytd_label])}</td><td class="ref"></td>')
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


def _chg_cell(v, vmax_abs, decimals=0):
    if pd.isna(v):
        return '<td class="chg blank"></td>'
    color = GOOD if v >= 0 else CRITICAL
    width = max(6, min(abs(v) / vmax_abs * 100, 100)) if vmax_abs else 6
    return (
        f'<td class="chg"><div class="coffee-chg-track">'
        f'<div class="coffee-chg-fill" style="width:{width:.0f}%;background:{color};"></div>'
        f'<span style="color:{color};">{v:+,.{decimals}f}</span></div></td>'
    )


def stocks_change_table_html(change, avg_row, title, subtitle="", n_years=8):
    """Calendar-year x calendar-month month-over-month stock change, with an
    inline green(build)/red(draw) bar per cell sized to that cell's own
    magnitude relative to the table-wide max — same idea as a delta column,
    applied to a full grid."""
    years = list(change.index)[-n_years:]
    change = change.loc[years]
    month_cols = list(change.columns)

    nums = [abs(float(change.loc[y, m])) for y in years for m in month_cols if pd.notna(change.loc[y, m])]
    vmax_abs = max(nums) if nums else 1.0

    header = '<tr><th class="idx"></th>' + "".join(f"<th>{MONTH_ABBR[m]}</th>" for m in month_cols) + "</tr>"
    body = []
    for y in years:
        cells = [f'<td class="idx">{y}</td>']
        for m in month_cols:
            cells.append(_chg_cell(change.loc[y, m], vmax_abs))
        body.append("<tr>" + "".join(cells) + "</tr>")
    avg_cells = [f'<td class="idx ref">Avg</td>']
    for m in month_cols:
        avg_cells.append(_chg_cell(avg_row.get(m), vmax_abs))
    body.append(f'<tr><td class="sep" colspan="{len(month_cols) + 1}"></td></tr>')
    body.append("<tr>" + "".join(avg_cells) + "</tr>")

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
