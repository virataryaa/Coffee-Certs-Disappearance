import streamlit as st

from data_loader import (
    build_disappearance, period_table, ytd_by_period, cumulative_by_period,
    rolling_12m, complete_periods, period_month_order, CALENDAR, CROP_YEAR,
    TDM_EU_PARQUET, stock_types, stocks_calendar_table, load_stocks,
    stocks_total_series, stocks_composition_series,
)
from charts import (
    seasonal_chart, cumulative_chart, latest_vs_band_chart,
    single_line_chart, two_line_chart, multi_series_chart, diverging_bar_chart,
    BLUE, ORANGE, AQUA,
)
from table_html import heatmap_table_html, stocks_level_table_html

st.set_page_config(page_title="Coffee Certs & Disappearance", layout="wide")

CSS = """
<style>
.stApp { background-color: #fcfcfb; }
.block-container { max-width: 1400px; padding-top: 2rem; }
h1.coffee-title { font-size: 20px; font-weight: 700; color: #0b0b0b; margin: 0; }
p.coffee-caption { font-size: 12px; color: #898781; margin: 2px 0 18px; }

/* Segmented-button styling for st.radio, used as toggle controls */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    display: inline-flex; gap: 2px; background: #f2f1ee; padding: 3px;
    border-radius: 8px; width: fit-content;
}
div[data-testid="stRadio"] label {
    background: transparent; border-radius: 6px; padding: 6px 14px !important;
    margin: 0 !important; font-size: 13px; color: #52514e; cursor: pointer;
    transition: background 0.15s, color 0.15s;
}
div[data-testid="stRadio"] label:has(input:checked) {
    background: #ffffff; color: #0b0b0b; font-weight: 600;
    box-shadow: 0 1px 3px rgba(11,11,11,0.12);
}
div[data-testid="stRadio"] label > div:first-child { display: none; }
div[data-testid="stRadio"] label div[data-testid="stMarkdownContainer"] p { margin: 0; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

tab_disapp, tab_stocks = st.tabs(["Disappearance", "ECF Stocks"])

# ── Disappearance ─────────────────────────────────────────────────────────────
with tab_disapp:
    head_col, basis_col, toggle_col = st.columns([4, 2, 1.6])
    with head_col:
        st.markdown('<h1 class="coffee-title">Europe Coffee Disappearance</h1>', unsafe_allow_html=True)
        st.markdown('<p class="coffee-caption">Net Imports (TDM) minus ECF stock change</p>',
                    unsafe_allow_html=True)
    with basis_col:
        basis_label = st.radio("Basis", ["Crop Year", "Calendar Year"], horizontal=True,
                                label_visibility="collapsed", key="basis_radio")
        st.caption("Crop year = Oct-Sep" if basis_label == "Crop Year" else "")
    with toggle_col:
        lag_label = st.radio("Timing", ["Same month", "1-month lag"], horizontal=True,
                              label_visibility="collapsed", key="lag_radio")
    lag = lag_label == "1-month lag"
    start_month = CALENDAR if basis_label == "Calendar Year" else CROP_YEAR

    if not TDM_EU_PARQUET.exists():
        st.warning(
            f"No TDM EU trade-flow data found at `{TDM_EU_PARQUET}`. "
            "Run `Automator/tdm_eu_ingest.py --full` first to populate Net Imports."
        )
        st.stop()

    df = build_disappearance(lag=lag, start_month=start_month)
    if df.empty:
        st.warning("No overlapping months between TDM Net Imports and the ECF Stocks file yet.")
        st.stop()

    month_order = period_month_order(start_month)
    pivot = period_table(df, start_month=start_month)
    all_periods = pivot["Period"].tolist()
    current_period = all_periods[-1]
    n_months = int(df.loc[df["Period"] == current_period, "PeriodMonthNum"].max())

    ytd = ytd_by_period(df, n_months, start_month=start_month, valid_periods=all_periods)
    ref_periods = complete_periods(pivot, start_month=start_month)[-10:]
    roll = rolling_12m(df)

    period_range = st.select_slider(
        "Period range (charts below)", options=all_periods,
        value=(all_periods[0], all_periods[-1]),
    )
    sel_periods = [p for p in all_periods if period_range[0] <= p <= period_range[1]]

    st.markdown(
        heatmap_table_html(
            pivot, month_order,
            title=f"Monthly disappearance by {basis_label.split(' (')[0].lower()} ({lag_label.lower()})",
            subtitle="Disappearance = Net Imports (TDM) − Stock Change (ECF certified stocks). Units: MT.",
            ref_years=ref_periods, current_period=current_period, ytd_months=n_months,
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        f"Blue shade = magnitude (table-wide). vs Avg% = current period vs the "
        f"average of the last {len(ref_periods)} complete periods."
    )

    wide = pivot.set_index("Period")[month_order].T
    wide_sel = wide[sel_periods]
    cum = cumulative_by_period(df, start_month=start_month, valid_periods=all_periods)
    cum_sel = cum[[p for p in sel_periods if p in cum.columns]]

    st.plotly_chart(
        seasonal_chart(wide_sel, "Seasonal pattern by period", ref_years=ref_periods,
                       current=current_period),
        use_container_width=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(single_line_chart(ytd.index, ytd.values, "YTD trend by period"),
                         use_container_width=True)
    with c2:
        st.plotly_chart(
            latest_vs_band_chart(wide, current_period, ref_periods,
                                  f"{current_period} vs Min/Max/Avg (L{len(ref_periods)}Y)"),
            use_container_width=True,
        )

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(single_line_chart(roll["Date"], roll["Rolling12mKMT"],
                                           "Rolling 12-month disappearance (k MT)"),
                         use_container_width=True)
    with c4:
        st.plotly_chart(
            cumulative_chart(cum_sel, "Cumulative by period", current=current_period),
            use_container_width=True,
        )

# ── ECF Stocks ────────────────────────────────────────────────────────────────
with tab_stocks:
    st.markdown('<h1 class="coffee-title">ECF Stocks</h1>', unsafe_allow_html=True)
    st.markdown('<p class="coffee-caption">Monthly ECF certified stocks by coffee type, 60kg bags — data from Jan 2020</p>',
                unsafe_allow_html=True)

    type_ = st.radio("Type of Coffee", stock_types(), horizontal=True, key="stock_type")

    stocks = load_stocks(type_)
    level, _, _ = stocks_calendar_table(type_, unit="Bags")

    st.markdown(
        stocks_level_table_html(level, f"{type_} — monthly level (60kg bags)", n_years=8),
        unsafe_allow_html=True,
    )

    s1, s2 = st.columns(2)
    with s1:
        st.plotly_chart(
            diverging_bar_chart(stocks["Date"], stocks["BagsChange"], f"{type_} — month-over-month change"),
            use_container_width=True,
        )
    with s2:
        total = stocks_total_series()
        st.plotly_chart(
            two_line_chart(total["Date"], total["Bags"], "Total Europe",
                           total["RollingAvg"], "12m average",
                           "Total Europe stocks & 12-month average"),
            use_container_width=True,
        )

    comp = stocks_composition_series()
    st.plotly_chart(
        multi_series_chart(
            comp["Date"],
            {
                "Robusta": (comp["Robusta"], BLUE),
                "Natural Arabica": (comp["Natural Arabica"], ORANGE),
                "Washed Arabica": (comp["Washed Arabica"], AQUA),
            },
            "Stocks by coffee type",
            height=340,
        ),
        use_container_width=True,
    )

    st.caption(
        "Data starts January 2020 — Aug–Dec 2019 was a one-off ECF certified-stock "
        "re-certification event, dropped rather than shown as real seasonality."
    )
