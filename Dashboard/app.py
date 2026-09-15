import streamlit as st

from data_loader import (
    build_disappearance, crop_year_table, ytd_table, cumulative_by_crop_year,
    rolling_12m, complete_crop_years, CROP_MONTH_ORDER, TDM_EU_PARQUET, STOCKS_PATH,
    stock_types, stocks_calendar_table, load_stocks,
    stocks_total_series, stocks_composition_series,
)
from charts import (
    seasonal_chart, cumulative_chart, latest_vs_band_chart,
    single_line_chart, two_line_chart, multi_series_chart, diverging_bar_chart,
    BLUE, ORANGE, AQUA,
)
from table_html import heatmap_table_html, ytd_summary_table_html, stocks_level_table_html

st.set_page_config(page_title="Coffee Certs & Disappearance", layout="wide")

CSS = """
<style>
.stApp { background-color: #fcfcfb; }
.block-container { max-width: 1400px; padding-top: 2rem; }
h1.coffee-title { font-size: 20px; font-weight: 700; color: #0b0b0b; margin: 0; }
p.coffee-caption { font-size: 12px; color: #898781; margin: 2px 0 18px; }

/* Segmented-button styling for st.radio, used as a lag/type toggle */
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

    all_years = pivot["CropYear"].tolist()
    ref_years = complete_crop_years(pivot)[-10:]

    default_start = all_years[max(0, len(all_years) - 6)]
    year_range = st.select_slider(
        "Crop year range (charts below)", options=all_years,
        value=(default_start, all_years[-1]),
    )
    sel_years = [y for y in all_years if year_range[0] <= y <= year_range[1]]

    st.markdown(
        heatmap_table_html(
            pivot, CROP_MONTH_ORDER,
            title=f"Monthly disappearance by crop year ({lag_label.lower()})",
            subtitle="Disappearance = Net Imports (TDM) − Stock Change (ICE Europe certs). Units: MT.",
            ref_years=ref_years, current_year=current_crop_year, ytd_months=n_months,
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        f"Blue shade = magnitude (table-wide). vs Avg% = current crop year vs the "
        f"average of the last {len(ref_years)} complete crop years."
    )

    wide = pivot.set_index("CropYear")[CROP_MONTH_ORDER].T
    wide_sel = wide[sel_years]
    cum_sel = cum[[y for y in sel_years if y in cum.columns]]

    col_a, col_b = st.columns([1, 2.4])
    with col_a:
        st.markdown(ytd_summary_table_html(ytd, title="YTD by crop year", unit="(MT)"), unsafe_allow_html=True)
    with col_b:
        st.plotly_chart(
            seasonal_chart(wide_sel, "Seasonal pattern by crop year", ref_years=ref_years,
                           current=current_crop_year),
            use_container_width=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(single_line_chart(ytd.index, ytd.values, "YTD trend by crop year"),
                         use_container_width=True)
    with c2:
        st.plotly_chart(
            latest_vs_band_chart(wide, current_crop_year, ref_years,
                                  f"{current_crop_year} vs Min/Max/Avg (L{len(ref_years)}Y)"),
            use_container_width=True,
        )

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(single_line_chart(roll["Date"], roll["Rolling12mKMT"],
                                           "Rolling 12-month disappearance (k MT)"),
                         use_container_width=True)
    with c4:
        st.plotly_chart(
            cumulative_chart(cum_sel, "Cumulative by crop year", current=current_crop_year),
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
            - Data starts January 2020 everywhere — Aug–Dec 2019 was a one-off ICE Europe
              certified-stock re-certification event that contaminates both that period and
              the stock-change reading right after it, so it's dropped rather than shown.
            - The crop-year range slider defaults to the last 6 years; widen it for the
              full 2020-onward history.
            """
        )

# ── ECF Stocks ────────────────────────────────────────────────────────────────
with tab_stocks:
    st.markdown('<h1 class="coffee-title">ICE Europe Certified Stocks</h1>', unsafe_allow_html=True)
    st.markdown('<p class="coffee-caption">Monthly certified stocks by coffee type, 60kg bags — data from Jan 2020</p>',
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
        "Data starts January 2020 — Aug–Dec 2019 was a one-off ICE Europe "
        "certified-stock re-certification event, dropped rather than shown as real seasonality."
    )
