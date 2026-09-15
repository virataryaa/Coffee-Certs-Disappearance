import streamlit as st

from data_loader import (
    build_disappearance, build_disappearance_by_type, period_table, ytd_by_period,
    cumulative_by_period, rolling_12m, rolling_window, complete_periods, period_month_order,
    CALENDAR, CROP_YEAR, UNIT_MT, UNIT_BAGS, to_unit, unit_col,
    TDM_EU_PARQUET, ORIGIN_TYPE_SPLIT_PARQUET,
    stock_types, stocks_calendar_table, load_stocks,
    stocks_total_series, stocks_composition_series,
)
from charts import (
    seasonal_chart, cumulative_chart, latest_vs_band_chart, rolling_multi_chart,
    single_line_chart, bar_chart, latest_vs_avg_bar_chart,
    two_line_chart, multi_series_chart, diverging_bar_chart,
    BLUE, ORANGE, AQUA,
)
from table_html import (
    heatmap_table_html, stocks_level_table_html, stocks_change_table_html, chart_header_html,
)

st.set_page_config(page_title="Coffee Certs & Disappearance", layout="wide")

CSS = """
<style>
.stApp { background-color: #fcfcfb; }
.block-container { max-width: 1400px; padding-top: 4rem; }
h1.coffee-title { font-size: 18px; font-weight: 700; color: #0b0b0b; margin: 0; }
p.coffee-caption { font-size: 11px; color: #898781; margin: 1px 0 8px; }
[data-testid="stVerticalBlock"] { gap: 0.5rem; }

/* Segmented-button styling for st.radio, used as toggle controls */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    display: inline-flex; gap: 2px; background: #f2f1ee; padding: 3px;
    border-radius: 8px; width: fit-content; flex-wrap: wrap;
}
div[data-testid="stRadio"] label {
    background: transparent; border-radius: 6px; padding: 5px 12px !important;
    margin: 0 !important; font-size: 12px; color: #52514e; cursor: pointer;
    transition: background 0.15s, color 0.15s;
}
div[data-testid="stRadio"] label:has(input:checked) {
    background: #ffffff; color: #0b0b0b; font-weight: 600;
    box-shadow: 0 1px 3px rgba(11,11,11,0.12);
}
div[data-testid="stRadio"] label > div:first-child { display: none; }
div[data-testid="stRadio"] label div[data-testid="stMarkdownContainer"] p { margin: 0; }
section[data-testid="stSidebar"] .block-container { padding-top: 2.2rem; }
section[data-testid="stSidebar"] div[data-testid="stRadio"] > div[role="radiogroup"] { display: flex; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def show_chart(fig, title, subtitle=""):
    """Chart + its title/subtitle as real DOM text right above it (see
    table_html.chart_header_html) — never clips, unlike a Plotly-internal
    title anchored in paper coordinates."""
    st.markdown(chart_header_html(title, subtitle), unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)


# ── Global controls (sidebar) ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p style="font-size:12px;font-weight:700;color:#898781;'
                'text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px;">Settings</p>',
                unsafe_allow_html=True)
    basis_label = st.radio("Period basis", ["Crop Year", "Calendar Year"], key="global_basis")
    st.caption("Oct–Sep" if basis_label == "Crop Year" else "Jan–Dec")
    unit_label = st.radio("Unit", [UNIT_MT, UNIT_BAGS], key="global_unit")
    lag_label = st.radio("Lag", ["Same month", "1-month lag"], key="global_lag")
    start_month = CALENDAR if basis_label == "Calendar Year" else CROP_YEAR
    y_unit = "MT" if unit_label == UNIT_MT else "bags"
    lag = {"Same month": 0, "1-month lag": 1}[lag_label]

    _ref_df = build_disappearance(lag=lag, start_month=start_month)
    _ref_pivot = period_table(_ref_df, start_month=start_month) if not _ref_df.empty else None
    if _ref_pivot is not None and not _ref_pivot.empty:
        _all_periods_global = _ref_pivot["Period"].tolist()
        period_range = st.select_slider(
            "Period range (charts)", options=_all_periods_global,
            value=(_all_periods_global[0], _all_periods_global[-1]), key="global_period_range",
        )
    else:
        period_range = None


def render_disappearance(build_fn, title, caption, key_prefix, footnote=None):
    """Shared body for the Disappearance tab: the heatmap table + charts,
    all in the globally chosen period basis / unit / lag / period range.
    `build_fn(lag, start_month)` returns the merged Net-Imports/Stock-Change
    dataframe (still in MT)."""
    st.markdown(f'<h1 class="coffee-title">{title}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="coffee-caption">{caption}</p>', unsafe_allow_html=True)

    df = build_fn(lag, start_month)
    if df.empty:
        st.warning("No overlapping data available for this selection yet.")
        return
    df = df.copy()
    df["Disappearance"] = to_unit(df["Disappearance"], unit_label)

    month_order = period_month_order(start_month)
    pivot = period_table(df, start_month=start_month)
    all_periods = pivot["Period"].tolist()
    if not all_periods:
        st.warning("Not enough history to build a full period yet.")
        return
    current_period = all_periods[-1]
    n_months = int(df.loc[df["Period"] == current_period, "PeriodMonthNum"].max())

    ytd = ytd_by_period(df, n_months, start_month=start_month, valid_periods=all_periods)
    ref_periods = complete_periods(pivot, start_month=start_month)[-10:]
    roll = rolling_12m(df)

    rng = period_range if period_range else (all_periods[0], all_periods[-1])
    sel_periods = [p for p in all_periods if rng[0] <= p <= rng[1]]
    ctx = f"{basis_label} · {y_unit} · {lag_label.lower()}"

    st.markdown(
        heatmap_table_html(
            pivot, month_order,
            title=f"Monthly disappearance ({ctx})",
            subtitle="Disappearance = Net Imports (TDM) − Stock Change (ECF certified stocks).",
            ref_years=ref_periods, current_period=current_period, ytd_months=n_months,
        ),
        unsafe_allow_html=True,
    )
    if footnote:
        with st.expander("Assumptions & methodology", expanded=False):
            st.markdown(footnote)

    wide = pivot.set_index("Period")[month_order].T
    wide_sel = wide[sel_periods]
    cum = cumulative_by_period(df, start_month=start_month, valid_periods=all_periods)
    cum_sel = cum[[p for p in sel_periods if p in cum.columns]]

    show_chart(
        seasonal_chart(wide_sel, ref_years=ref_periods, current=current_period),
        "Seasonal pattern", ctx,
    )

    c1, c2 = st.columns(2)
    with c1:
        show_chart(bar_chart(ytd.index, ytd.values), "YTD trend", ctx)
    with c2:
        show_chart(
            latest_vs_band_chart(wide, current_period, ref_periods),
            f"{current_period} vs Min/Max/Avg", f"L{len(ref_periods)}Y · {ctx}",
        )

    c3, c4 = st.columns(2)
    with c3:
        show_chart(single_line_chart(roll["Date"], roll["Rolling12mKMT"]),
                    "Rolling 12-month", f"k {y_unit} · {basis_label}")
    with c4:
        show_chart(cumulative_chart(cum_sel, current=current_period), "Cumulative", ctx)


def render_type_bar_views(df_t, pivot_t, current_t, ref_t, all_periods_t, ctx, key_prefix):
    """Collapsed-by-default alternate views for one coffee type: Seasonal
    and Cumulative as line charts (with an average reference line), and
    Min-Max-Avg-vs-latest / YTD as bars."""
    month_order = period_month_order(start_month)
    with st.expander(f"{key_prefix} — Seasonal / Min-Max-Avg / YTD / Cumulative", expanded=False):
        wide_t = pivot_t.set_index("Period")[month_order].T
        rng = period_range if period_range else (all_periods_t[0], all_periods_t[-1])
        sel_t = [p for p in all_periods_t if rng[0] <= p <= rng[1]]
        wide_t_sel = wide_t[sel_t]
        cum_t = cumulative_by_period(df_t, start_month=start_month, valid_periods=all_periods_t)
        cum_t_sel = cum_t[[p for p in sel_t if p in cum_t.columns]]
        n_months_t = int(df_t.loc[df_t["Period"] == current_t, "PeriodMonthNum"].max())
        ytd_t = ytd_by_period(df_t, n_months_t, start_month=start_month, valid_periods=all_periods_t)

        b1, b2 = st.columns(2)
        with b1:
            show_chart(seasonal_chart(wide_t_sel, ref_years=ref_t, current=current_t), "Seasonal pattern", ctx)
        with b2:
            show_chart(latest_vs_avg_bar_chart(wide_t, current_t, ref_t),
                       f"{current_t} vs Avg (bars)", f"L{len(ref_t)}Y · {ctx}")
        b3, b4 = st.columns(2)
        with b3:
            show_chart(bar_chart(ytd_t.index, ytd_t.values), "YTD trend (bars)", ctx)
        with b4:
            show_chart(cumulative_chart(cum_t_sel, current=current_t), "Cumulative", ctx)


TYPE_FOOTNOTE = (
    "**Imports** are allocated by origin country (see `Automator/build_type_split.py`): "
    "Brazil uses a dynamic monthly ratio from Cecafe Monthly's Brazil→Europe Type split; "
    "India is locked at 60% Robusta / 40% Arabica; Uganda at 80% / 20%; ~19 other origins "
    "are treated as near-pure by geography (e.g. Vietnam = Robusta, Colombia = Arabica). "
    "~92% of import volume is classified this way — the remainder is assumed to share that "
    "month's classified mix.\n\n"
    "**Exports** aren't origin-attributable (the TDM partner field is the destination, not "
    "the origin), so the same month's import-side type mix is applied to Exports too, as an "
    "approximation — Europe is assumed to re-export roughly the type mix it's currently holding."
)

tab_disapp, tab_type, tab_stocks = st.tabs(["Disappearance", "Arabica / Robusta", "ECF Stocks"])

# ── Disappearance ─────────────────────────────────────────────────────────────
with tab_disapp:
    if not TDM_EU_PARQUET.exists():
        st.warning(
            f"No TDM EU trade-flow data found at `{TDM_EU_PARQUET}`. "
            "Run `Automator/tdm_eu_ingest.py --full` first to populate Net Imports."
        )
        st.stop()
    render_disappearance(
        build_disappearance,
        "Europe Coffee Disappearance",
        "Net Imports (TDM) minus ECF stock change",
        key_prefix="total",
    )

# ── Arabica / Robusta ─────────────────────────────────────────────────────────
with tab_type:
    if not ORIGIN_TYPE_SPLIT_PARQUET.exists():
        st.warning(
            f"No type-split data found at `{ORIGIN_TYPE_SPLIT_PARQUET}`. "
            "Run `Automator/build_type_split.py` first."
        )
        st.stop()

    st.markdown('<h1 class="coffee-title">Arabica / Robusta Disappearance</h1>', unsafe_allow_html=True)
    st.markdown('<p class="coffee-caption">Net Imports split by origin, minus ECF stock change by type</p>',
                unsafe_allow_html=True)

    ctx = f"{basis_label} · {y_unit} · {lag_label.lower()}"

    type_dfs = {}
    for t in ("Robusta", "Arabica"):
        d = build_disappearance_by_type(t, lag=lag, start_month=start_month)
        d = d.copy()
        d["Disappearance"] = to_unit(d["Disappearance"], unit_label)
        type_dfs[t] = d

    win_col, _ = st.columns([2, 4])
    with win_col:
        window_label = st.radio("Rolling window", ["1m", "3m", "6m", "12m"], horizontal=True,
                                 label_visibility="collapsed", key="roll_window")
    window = int(window_label.rstrip("m"))
    rolling_series = {t: (r["Date"], r["Rolling"]) for t, d in type_dfs.items()
                       for r in [rolling_window(d, window)]}

    show_chart(
        rolling_multi_chart(rolling_series),
        f"Rolling {window_label} disappearance", f"Robusta vs Arabica · {y_unit}",
    )

    for t in ("Robusta", "Arabica"):
        df_t = type_dfs[t]
        month_order = period_month_order(start_month)
        pivot_t = period_table(df_t, start_month=start_month)
        if pivot_t.empty:
            st.warning(f"Not enough {t} history yet.")
            continue
        current_t = pivot_t["Period"].iloc[-1]
        n_months_t = int(df_t.loc[df_t["Period"] == current_t, "PeriodMonthNum"].max())
        ref_t = complete_periods(pivot_t, start_month=start_month)[-10:]
        all_periods_t = pivot_t["Period"].tolist()
        st.markdown(
            heatmap_table_html(
                pivot_t, month_order,
                title=f"{t} monthly disappearance ({ctx})",
                ref_years=ref_t, current_period=current_t, ytd_months=n_months_t,
            ),
            unsafe_allow_html=True,
        )
        render_type_bar_views(df_t, pivot_t, current_t, ref_t, all_periods_t, ctx, f"{t} monthly disappearance")

    with st.expander("Assumptions & methodology", expanded=False):
        st.markdown(TYPE_FOOTNOTE)

# ── ECF Stocks ────────────────────────────────────────────────────────────────
with tab_stocks:
    st.markdown('<h1 class="coffee-title">ECF Stocks</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="coffee-caption">Monthly ECF certified stocks by coffee type, {y_unit} — data from Jan 2020</p>',
                unsafe_allow_html=True)

    type_ = st.radio("Type of Coffee", stock_types(), horizontal=True, key="stock_type")
    col = unit_col(unit_label)

    stocks = load_stocks(type_)
    level, change, avg_row = stocks_calendar_table(type_, unit=col)

    st.markdown(
        stocks_level_table_html(level, f"{type_} — monthly level ({y_unit})", n_years=8),
        unsafe_allow_html=True,
    )
    st.markdown(
        stocks_change_table_html(change, avg_row, f"{type_} — month-over-month change ({y_unit})", n_years=8),
        unsafe_allow_html=True,
    )

    change_col = "BagsChange" if col == "Bags" else "StockChange"
    s1, s2 = st.columns(2)
    with s1:
        show_chart(diverging_bar_chart(stocks["Date"], stocks[change_col]),
                   f"{type_} — month-over-month change", y_unit)
    with s2:
        total = stocks_total_series(unit=unit_label)
        show_chart(
            two_line_chart(total["Date"], total["Level"], "Total Europe", total["RollingAvg"], "12m average"),
            "Total Europe stocks & 12m average", y_unit,
        )

    comp = stocks_composition_series(unit=unit_label)
    show_chart(
        multi_series_chart(
            comp["Date"],
            {
                "Robusta": (comp["Robusta"], BLUE),
                "Natural Arabica": (comp["Natural Arabica"], ORANGE),
                "Washed Arabica": (comp["Washed Arabica"], AQUA),
            },
        ),
        "Stocks by coffee type", y_unit,
    )

    st.caption(
        "Data starts January 2020 — Aug–Dec 2019 was a one-off ECF certified-stock "
        "re-certification event, dropped rather than shown as real seasonality."
    )
