import pandas as pd
import streamlit as st

from data_loader import (
    build_disappearance, crop_year_table, ytd_table, cumulative_by_crop_year,
    rolling_12m, CROP_MONTH_ORDER, TDM_EU_PARQUET, STOCKS_PATH,
    stock_types, stocks_calendar_table, load_stocks,
    stocks_total_series, stocks_composition_series,
)
from charts import (
    emphasis_line_chart, band_chart, single_line_chart, two_line_chart,
    multi_series_chart, diverging_bar_chart, BLUE, ORANGE, AQUA,
)
from table_html import (
    disappearance_table_html, ytd_summary_table_html, stocks_level_table_html,
    stat_tile_row_html,
)

st.set_page_config(page_title="Coffee Certs & Disappearance", layout="wide")

CSS = """
<style>
.stApp { background-color: #fcfcfb; }
.block-container { max-width: 1400px; padding-top: 2rem; }
h1.coffee-title { font-size: 20px; font-weight: 700; color: #0b0b0b; margin: 0; }
p.coffee-caption { font-size: 12px; color: #898781; margin: 2px 0 18px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

tab_disapp, tab_stocks = st.tabs(["Disappearance", "ECF Stocks"])

# ── Disappearance ─────────────────────────────────────────────────────────────
with tab_disapp:
    head_col, toggle_col = st.columns([5, 1.3])
    with head_col:
        st.markdown('<h1 class="coffee-title">Europe Coffee Disappearance</h1>', unsafe_allow_html=True)
        st.markdown('<p class="coffee-caption">Net Imports (TDM) minus ICE-certified stock change</p>',
                    unsafe_allow_html=True)
    with toggle_col:
        lag_label = st.radio("Timing", ["Same month", "1-month lag"], horizontal=True,
                              label_visibility="collapsed", key="lag_radio")
    lag = lag_label == "1-month lag"

    if not TDM_EU_PARQUET.exists():
        st.warning(
            f"No TDM EU trade-flow data found at `{TDM_EU_PARQUET}`. "
            "Run `Automator/tdm_eu_ingest.py --full` first to populate Net Imports."
        )
        st.stop()

    df = build_disappearance(lag=lag)
    if df.empty:
        st.warning("No overlapping months between TDM Net Imports and the Coffee Stocks file yet.")
        st.stop()

    pivot = crop_year_table(df)
    n_months = int(df.sort_values("Date")["CropMonthNum"].iloc[-1])
    current_crop_year = pivot["CropYear"].iloc[-1]

    ytd = ytd_table(df, n_months)
    cum = cumulative_by_crop_year(df)
    roll = rolling_12m(df)

    latest = df.sort_values("Date").iloc[-1]
    ytd_now, ytd_prev = ytd.iloc[-1], (ytd.iloc[-2] if len(ytd) > 1 else float("nan"))
    ytd_yoy = (ytd_now / ytd_prev - 1) * 100 if ytd_prev and ytd_prev == ytd_prev else None
    full_year_idx = -2 if n_months < 12 else -1
    total_now = pivot["Total"].iloc[full_year_idx]
    total_yoy = pivot["YoY %"].iloc[full_year_idx]
    total_year_label = pivot["CropYear"].iloc[full_year_idx]

    st.markdown(
        stat_tile_row_html([
            ("Latest month", latest["Disappearance"], "MT", None,
             latest["Date"].strftime("%b %Y")),
            (f"Crop YTD ({current_crop_year})", ytd_now, "MT", ytd_yoy,
             f"Oct–{df.sort_values('Date').iloc[-1]['CropMonth']}, vs same window last year"),
            (f"Full crop year ({total_year_label})", total_now, "MT", total_yoy, "Oct–Sep total"),
        ]),
        unsafe_allow_html=True,
    )

    st.markdown(
        disappearance_table_html(
            pivot, CROP_MONTH_ORDER,
            title=f"Monthly disappearance by crop year ({lag_label.lower()})",
            subtitle="Disappearance = Net Imports (TDM) − Stock Change (ICE Europe certs). Units: MT.",
        ),
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns([1, 2.4])
    with col_a:
        st.markdown(ytd_summary_table_html(ytd, title="YTD by crop year", unit="(MT)"), unsafe_allow_html=True)
    with col_b:
        st.plotly_chart(
            emphasis_line_chart(pivot.set_index("CropYear")[CROP_MONTH_ORDER].T,
                                 "Seasonal pattern — last 6 crop years"),
            use_container_width=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(single_line_chart(ytd.index, ytd.values, "YTD trend by crop year"),
                         use_container_width=True)
    with c2:
        st.plotly_chart(
            band_chart(pivot.set_index("CropYear")[CROP_MONTH_ORDER].T, current_crop_year,
                       f"{current_crop_year} vs 5-year min–max band"),
            use_container_width=True,
        )

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(single_line_chart(roll["Date"], roll["Rolling12mKMT"],
                                           "Rolling 12-month disappearance (k MT)"),
                         use_container_width=True)
    with c4:
        st.plotly_chart(
            emphasis_line_chart(cum, "Cumulative by crop year — last 6", y_suffix=""),
            use_container_width=True,
        )

    with st.expander("Data sources & methodology"):
        st.markdown(
            f"""
            - **Net Imports** = TDM Imports − TDM Exports for "EU 28 External Trade" (E28,
              the pre-aggregated extra-EU bloc reporter) + UK + Norway + Switzerland
              (all coffee HS codes: green, roast & ground, instant), from `{TDM_EU_PARQUET.name}`.
            - **Stock Change** = month-over-month change in ICE Europe certified stocks,
              "Total Europe" row, from `{STOCKS_PATH.name}` (sheet: ECF).
            - **Disappearance** = Net Imports − Stock Change.
            - **1-month lag**: pairs the prior month's Net Imports with the current month's
              Stock Change (customs data vs. certification timing).
            - Charts show the last 6 crop years by design — a one-off ICE stock
              re-certification in 2019 produces an extreme outlier month that would
              otherwise dominate the axis on every chart. The full history is still in
              the table above.
            """
        )

# ── ECF Stocks ────────────────────────────────────────────────────────────────
with tab_stocks:
    st.markdown('<h1 class="coffee-title">ICE Europe Certified Stocks</h1>', unsafe_allow_html=True)
    st.markdown('<p class="coffee-caption">Monthly certified stocks by coffee type, 60kg bags</p>',
                unsafe_allow_html=True)

    type_ = st.radio("Type of Coffee", stock_types(), horizontal=True, key="stock_type")

    stocks = load_stocks(type_)
    level, _, _ = stocks_calendar_table(type_, unit="Bags")
    latest_s = stocks.sort_values("Date").iloc[-1]
    yoy_s = None
    same_month_prior = stocks[(stocks["MonthNum"] == latest_s["MonthNum"]) & (stocks["Year"] == latest_s["Year"] - 1)]
    if not same_month_prior.empty and same_month_prior["Bags"].iloc[0]:
        yoy_s = (latest_s["Bags"] / same_month_prior["Bags"].iloc[0] - 1) * 100

    st.markdown(
        stat_tile_row_html([
            (f"{type_} stocks", latest_s["Bags"], "bags", yoy_s, latest_s["Date"].strftime("%b %Y")),
            ("Month change", latest_s["BagsChange"], "bags", None, "vs prior month"),
        ]),
        unsafe_allow_html=True,
    )

    st.markdown(
        stocks_level_table_html(level, f"{type_} — monthly level (60kg bags)", n_years=8),
        unsafe_allow_html=True,
    )

    recent_cutoff = stocks["Date"].max() - pd.DateOffset(years=6)
    recent_stocks = stocks[stocks["Date"] > recent_cutoff]

    s1, s2 = st.columns(2)
    with s1:
        st.plotly_chart(
            diverging_bar_chart(recent_stocks["Date"], recent_stocks["BagsChange"],
                                 f"{type_} — month-over-month change (last 6 years)"),
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
        "Aug 2019–Jan 2020 shows a sharp, temporary drop across all types — a known "
        "ICE Europe certified-stock re-certification event, not a data error."
    )
