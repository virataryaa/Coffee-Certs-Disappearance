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
    single_line_chart, two_line_chart, multi_series_chart, diverging_bar_chart,
    BLUE, ORANGE, AQUA,
)
from table_html import heatmap_table_html, stocks_level_table_html, stocks_change_table_html

st.set_page_config(page_title="Coffee Certs & Disappearance", layout="wide")

CSS = """
<style>
.stApp { background-color: #fcfcfb; }
.block-container { max-width: 1400px; padding-top: 1.4rem; }
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
section[data-testid="stSidebar"] .block-container { padding-top: 1.4rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ── Global controls (sidebar) ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p style="font-size:12px;font-weight:700;color:#898781;'
                'text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px;">Settings</p>',
                unsafe_allow_html=True)
    basis_label = st.radio("Period basis", ["Crop Year", "Calendar Year"], key="global_basis")
    st.caption("Oct–Sep" if basis_label == "Crop Year" else "Jan–Dec")
    unit_label = st.radio("Unit", [UNIT_MT, UNIT_BAGS], key="global_unit")
    start_month = CALENDAR if basis_label == "Calendar Year" else CROP_YEAR
    y_unit = "MT" if unit_label == UNIT_MT else "bags"


def render_disappearance(build_fn, title, caption, key_prefix, footnote=None):
    """Shared body for the Disappearance and Arabica/Robusta tabs: lag
    toggle, the heatmap table, and the six charts, all in the globally
    chosen period basis + unit. `build_fn(lag, start_month)` returns the
    merged Net-Imports/Stock-Change dataframe (still in MT)."""
    head_col, toggle_col = st.columns([5, 1.6])
    with head_col:
        st.markdown(f'<h1 class="coffee-title">{title}</h1>', unsafe_allow_html=True)
        st.markdown(f'<p class="coffee-caption">{caption}</p>', unsafe_allow_html=True)
    with toggle_col:
        lag_label = st.radio("Timing", ["Same month", "1-month lag"], horizontal=True,
                              label_visibility="collapsed", key=f"{key_prefix}_lag")
    lag = lag_label == "1-month lag"

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

    period_range = st.select_slider(
        "Period range (charts below)", options=all_periods,
        value=(all_periods[0], all_periods[-1]), key=f"{key_prefix}_range",
    )
    sel_periods = [p for p in all_periods if period_range[0] <= p <= period_range[1]]
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
    st.caption(
        f"Blue shade = magnitude (table-wide). vs Avg% = current period vs the "
        f"average of the last {len(ref_periods)} complete periods."
    )
    if footnote:
        with st.expander("Assumptions & methodology", expanded=False):
            st.markdown(footnote)

    wide = pivot.set_index("Period")[month_order].T
    wide_sel = wide[sel_periods]
    cum = cumulative_by_period(df, start_month=start_month, valid_periods=all_periods)
    cum_sel = cum[[p for p in sel_periods if p in cum.columns]]

    st.plotly_chart(
        seasonal_chart(wide_sel, "Seasonal pattern", ref_years=ref_periods,
                       current=current_period, subtitle=ctx),
        use_container_width=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(single_line_chart(ytd.index, ytd.values, "YTD trend", subtitle=ctx),
                         use_container_width=True)
    with c2:
        st.plotly_chart(
            latest_vs_band_chart(wide, current_period, ref_periods,
                                  f"{current_period} vs Min/Max/Avg", subtitle=f"L{len(ref_periods)}Y · {ctx}"),
            use_container_width=True,
        )

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(single_line_chart(roll["Date"], roll["Rolling12mKMT"],
                                           "Rolling 12-month", subtitle=f"k {y_unit} · {basis_label}"),
                         use_container_width=True)
    with c4:
        st.plotly_chart(
            cumulative_chart(cum_sel, "Cumulative", current=current_period, subtitle=ctx),
            use_container_width=True,
        )


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

    win_col, _ = st.columns([2, 4])
    with win_col:
        window_label = st.radio("Rolling window", ["1m", "3m", "6m", "12m"], horizontal=True,
                                 label_visibility="collapsed", key="roll_window")
    window = int(window_label.rstrip("m"))

    type_dfs = {}
    rolling_series = {}
    for t in ("Robusta", "Arabica"):
        d = build_disappearance_by_type(t, lag=False, start_month=start_month)
        d = d.copy()
        d["Disappearance"] = to_unit(d["Disappearance"], unit_label)
        type_dfs[t] = d
        r = rolling_window(d, window)
        rolling_series[t] = (r["Date"], r["Rolling"])

    st.plotly_chart(
        rolling_multi_chart(
            rolling_series, window,
            f"Rolling {window_label} disappearance",
            subtitle=f"Robusta vs Arabica · {y_unit}",
        ),
        use_container_width=True,
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
        st.markdown(
            heatmap_table_html(
                pivot_t, month_order,
                title=f"{t} monthly disappearance ({basis_label} · {y_unit})",
                ref_years=ref_t, current_period=current_t, ytd_months=n_months_t,
            ),
            unsafe_allow_html=True,
        )

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
        st.plotly_chart(
            diverging_bar_chart(stocks["Date"], stocks[change_col],
                                 f"{type_} — month-over-month change", subtitle=y_unit),
            use_container_width=True,
        )
    with s2:
        total = stocks_total_series(unit=unit_label)
        st.plotly_chart(
            two_line_chart(total["Date"], total["Level"], "Total Europe",
                           total["RollingAvg"], "12m average",
                           "Total Europe stocks & 12m average", subtitle=y_unit),
            use_container_width=True,
        )

    comp = stocks_composition_series(unit=unit_label)
    st.plotly_chart(
        multi_series_chart(
            comp["Date"],
            {
                "Robusta": (comp["Robusta"], BLUE),
                "Natural Arabica": (comp["Natural Arabica"], ORANGE),
                "Washed Arabica": (comp["Washed Arabica"], AQUA),
            },
            "Stocks by coffee type", subtitle=y_unit,
            height=260,
        ),
        use_container_width=True,
    )

    st.caption(
        "Data starts January 2020 — Aug–Dec 2019 was a one-off ECF certified-stock "
        "re-certification event, dropped rather than shown as real seasonality."
    )
