import streamlit as st

from data_loader import (
    build_disappearance, crop_year_table, ytd_table, cumulative_by_crop_year,
    rolling_12m, CROP_MONTH_ORDER, TDM_EU_PARQUET, STOCKS_PATH,
    stock_types, stocks_calendar_table, stocks_dual_axis_data,
)
from charts import (
    monthly_lines, cumulative_chart, ytd_trend_chart, min_max_avg_chart, rolling_12m_chart,
    stocks_change_bar_chart, stocks_dual_axis_chart,
)
from table_html import disappearance_table_html, ytd_summary_table_html, stocks_level_table_html, stocks_change_table_html

st.set_page_config(page_title="Coffee Certs & Disappearance", layout="wide")

CSS = """
<style>
.stApp { background-color: #ffffff; }
.block-container { max-width: 1500px; padding-top: 2rem; }
.coffee-header { display:flex; justify-content:space-between; align-items:center;
                  background:#0f1f33; padding:14px 22px; border-radius:6px; margin-bottom:14px; }
.coffee-header h1 { color:#ffffff; font-size:22px; font-weight:800; letter-spacing:0.02em; margin:0; }
.coffee-header .badge { background:#7a1f1f; color:#f5d76e; font-weight:700; font-size:13px;
                          padding:6px 14px; border-radius:4px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

tab_disapp, tab_stocks = st.tabs(["Disappearance", "ECF Stocks"])

with tab_disapp:
    if "lag" not in st.session_state:
        st.session_state["lag"] = False

    lag = st.session_state["lag"]

    header_col1, header_col2 = st.columns([5, 1])
    with header_col1:
        st.markdown(
            f'<div class="coffee-header"><h1>Europe Disappearance</h1>'
            f'<span class="badge">{"With 1M Lag" if lag else "Without Lag"}</span></div>',
            unsafe_allow_html=True,
        )
    with header_col2:
        st.write("")
        if st.button("Toggle Lag" if not lag else "Toggle Lag ", use_container_width=True):
            st.session_state["lag"] = not lag
            st.rerun()

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
    n_months = int(df.sort_values("Date")["CropMonthNum"].iloc[-1])  # months reported in latest crop year
    current_crop_year = pivot["CropYear"].iloc[-1]

    ytd = ytd_table(df, n_months)
    cum = cumulative_by_crop_year(df)
    roll = rolling_12m(df)

    st.markdown(
        disappearance_table_html(
            pivot, CROP_MONTH_ORDER,
            title=f"Europe Disappearance (Monthly) | {'With 1M Lag' if lag else 'Without Lag'}",
            subtitle="Disappearance = Net Imports (TDM) − Stock Change (ICE Europe certs). Units: MT.",
        ),
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns([1, 3])
    with col_a:
        st.markdown(
            ytd_summary_table_html(ytd, title="YTD", unit="(MT)"),
            unsafe_allow_html=True,
        )
    with col_b:
        st.plotly_chart(
            monthly_lines(pivot.set_index("CropYear")[CROP_MONTH_ORDER].T, "Europe Disappearance (Monthly) | Without Lag" if not lag else "Europe Disappearance (Monthly) | With Lag"),
            use_container_width=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(ytd_trend_chart(ytd, "Europe Disappearance | YTD"), use_container_width=True)
    with c2:
        st.plotly_chart(
            min_max_avg_chart(pivot.set_index("CropYear")[CROP_MONTH_ORDER].T, current_crop_year, "With Min, Max & 5Yr Avg"),
            use_container_width=True,
        )

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(rolling_12m_chart(roll, "Rolling 12m Sum of Disappearance (k MT)"), use_container_width=True)
    with c4:
        st.plotly_chart(cumulative_chart(cum, "Europe Disappearance | Cumulative"), use_container_width=True)

    with st.expander("Data sources & methodology"):
        st.markdown(
            f"""
            - **Net Imports** = TDM Imports − TDM Exports for "EU 28 External Trade" (E28,
              the pre-aggregated extra-EU bloc reporter) + UK + Norway + Switzerland
              (all coffee HS codes: green, roast & ground, instant), from `{TDM_EU_PARQUET.name}`.
            - **Stock Change** = month-over-month change in ICE Europe certified stocks,
              "Total Europe" row, from `{STOCKS_PATH.name}` (sheet: ECF).
            - **Disappearance** = Net Imports − Stock Change.
            - **Lag toggle**: "With 1M Lag" uses the prior month's Net Imports against
              the current month's Stock Change (customs data vs. certification timing).
            """
        )

with tab_stocks:
    st.markdown(
        '<div class="coffee-header"><h1>ECF EU Stocks Split</h1></div>',
        unsafe_allow_html=True,
    )

    type_ = st.radio("Type of Coffee", stock_types(), horizontal=True, key="stock_type")

    level, change, avg_row = stocks_calendar_table(type_, unit="Bags")

    st.markdown(
        stocks_level_table_html(level, f"{type_} ECF Stocks (60kg Bags)"),
        unsafe_allow_html=True,
    )
    st.markdown(
        stocks_change_table_html(change, avg_row, f"{type_} ECF Stocks Change (60kg Bags)"),
        unsafe_allow_html=True,
    )

    s1, s2 = st.columns([1, 1])
    with s1:
        st.plotly_chart(
            stocks_change_bar_chart(change, f"{type_} ECF Stocks Change (60kg Bags)"),
            use_container_width=True,
        )
    with s2:
        dual = stocks_dual_axis_data()
        st.plotly_chart(
            stocks_dual_axis_chart(dual, "Total ECF Stocks (Right Axis) & Coffee Type Breakup (Left Axis)"),
            use_container_width=True,
        )
