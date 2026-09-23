import pandas as pd
import streamlit as st

import numpy as np

from data_loader import (
    build_disappearance, build_disappearance_by_type, period_table, ytd_by_period,
    cumulative_by_period, rolling_12m, rolling_window, complete_periods, period_month_order,
    load_kc_rc_ratio, load_net_imports,
    CALENDAR, CROP_YEAR, UNIT_MT, UNIT_BAGS, to_unit, unit_col, KC_FACTOR, BAGS_PER_MT,
    TDM_EU_PARQUET, ORIGIN_TYPE_SPLIT_PARQUET, KC_RC_RATIO_PARQUET,
    stock_types, stocks_calendar_table, load_stocks,
    stocks_total_series, stocks_composition_series,
    excess_imports_series, stock_change_series_bags, best_excess_imports_fit,
)
from charts import (
    seasonal_chart, cumulative_chart, latest_vs_band_chart, rolling_multi_chart,
    single_line_chart, bars_with_secondary_line_chart, line_with_secondary_line_chart,
    two_line_chart, multi_series_chart, diverging_bar_chart, scatter_with_r2,
    r2_heatmap_chart, corr_heatmap_chart, scatter_with_projection,
    BLUE, ORANGE, AQUA, INK,
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
p.coffee-section { font-size: 12px; font-weight: 600; color: #52514e; margin: 14px 0 2px; }
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


def show_chart(fig, title, detail=""):
    """Chart + a single-line title (see table_html.chart_header_html) right
    above it — real DOM text, never clips like a Plotly-internal title can.
    `detail` is for a fact specific to THIS chart (a window length, a unit
    scale) — never a restatement of the sidebar's basis/unit/lag, which is
    already visible to the reader on every chart otherwise."""
    st.markdown(chart_header_html(title, detail), unsafe_allow_html=True)
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


def _period_context(df, start_month):
    """Common per-tab derived state: pivot table, period list, current
    period, ref years, and the slider-selected window."""
    month_order = period_month_order(start_month)
    pivot = period_table(df, start_month=start_month)
    all_periods = pivot["Period"].tolist()
    if not all_periods:
        return None
    current = all_periods[-1]
    n_months = int(df.loc[df["Period"] == current, "PeriodMonthNum"].max())
    ref_years = complete_periods(pivot, start_month=start_month)[-10:]
    rng = period_range if period_range else (all_periods[0], all_periods[-1])
    sel_periods = [p for p in all_periods if rng[0] <= p <= rng[1]]
    wide = pivot.set_index("Period")[month_order].T
    return dict(month_order=month_order, pivot=pivot, all_periods=all_periods, current=current,
                n_months=n_months, ref_years=ref_years, sel_periods=sel_periods, wide=wide)


def render_disappearance(build_fn, title, caption, key_prefix, footnote=None):
    """Table + charts for one Net-Imports/Stock-Change series, in the
    globally chosen period basis / unit / lag / period range."""
    st.markdown(f'<h1 class="coffee-title">{title}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="coffee-caption">{caption}</p>', unsafe_allow_html=True)

    df = build_fn(lag, start_month)
    if df.empty:
        st.warning("No overlapping data available for this selection yet.")
        return
    df = df.copy()
    df["Disappearance"] = to_unit(df["Disappearance"], unit_label)
    df["NetImports"] = to_unit(df["NetImports"], unit_label)

    ctx = _period_context(df, start_month)
    if ctx is None:
        st.warning("Not enough history to build a full period yet.")
        return
    month_order, pivot, all_periods = ctx["month_order"], ctx["pivot"], ctx["all_periods"]
    current, n_months, ref_years = ctx["current"], ctx["n_months"], ctx["ref_years"]
    sel_periods, wide = ctx["sel_periods"], ctx["wide"]

    ytd = ytd_by_period(df, n_months, start_month=start_month, valid_periods=all_periods)
    roll = rolling_12m(df)
    wide_sel = wide[sel_periods]
    cum = cumulative_by_period(df, start_month=start_month, valid_periods=all_periods)
    cum_sel = cum[[p for p in sel_periods if p in cum.columns]]

    st.markdown(
        heatmap_table_html(
            pivot, month_order,
            title="Monthly disappearance",
            subtitle="Disappearance = Net Imports (TDM) − Stock Change (ECF certified stocks).",
            ref_years=ref_years, current_period=current, ytd_months=n_months,
        ),
        unsafe_allow_html=True,
    )
    if footnote:
        with st.expander("Assumptions & methodology", expanded=False):
            st.markdown(footnote)

    show_chart(seasonal_chart(wide_sel, current=current), "Seasonal pattern")

    c1, c2 = st.columns(2)
    with c1:
        show_chart(single_line_chart(ytd.index, ytd.values), "YTD trend")
    with c2:
        show_chart(latest_vs_band_chart(wide, current, ref_years),
                   f"{current} vs Min/Max/Avg", f"L{len(ref_years)}Y")

    c3, c4 = st.columns(2)
    with c3:
        show_chart(single_line_chart(roll["Date"], roll["Rolling12mKMT"]), "Rolling 12-month", f"k {y_unit}")
    with c4:
        show_chart(cumulative_chart(cum_sel, current=current), "Cumulative")

    c5, c6 = st.columns(2)
    with c5:
        show_chart(
            two_line_chart(df["Date"], df["NetImports"], "Net Imports (GBE)", df["Disappearance"], "Disappearance"),
            "Net Imports vs Disappearance", y_unit,
        )
    with c6:
        scatter_fig, r2 = scatter_with_r2(df["NetImports"], df["Disappearance"], "Net Imports", "Disappearance")
        show_chart(scatter_fig, "Net Imports vs Disappearance (scatter)", f"R² = {r2:.2f}")


TYPE_FOOTNOTE = (
    "**Imports** are allocated by origin country (see `Automator/build_type_split.py`): "
    "Brazil uses a dynamic monthly ratio from Cecafe Monthly's Brazil→Europe Type split; "
    "India is locked at 60% Robusta / 40% Arabica; Uganda at 80% / 20%; ~20 other origins "
    "are treated as near-pure by geography (e.g. Vietnam and Indonesia = Robusta, Colombia = Arabica). "
    "~95% of import volume is classified this way — the remainder is assumed to share that "
    "month's classified mix.\n\n"
    "**Exports** aren't origin-attributable (the TDM partner field is the destination, not "
    "the origin), so the same month's import-side type mix is applied to Exports too, as an "
    "approximation — Europe is assumed to re-export roughly the type mix it's currently holding."
)

tab_disapp, tab_type, tab_stocks, tab_projection = st.tabs(
    ["Disappearance", "Arabica / Robusta", "ECF Stocks", "ECF Projection"]
)

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

    type_dfs, type_ctx = {}, {}
    for t in ("Robusta", "Arabica"):
        d = build_disappearance_by_type(t, lag=lag, start_month=start_month)
        d = d.copy()
        d["Disappearance"] = to_unit(d["Disappearance"], unit_label)
        type_dfs[t] = d
        type_ctx[t] = _period_context(d, start_month)

    win_col, _ = st.columns([2, 4])
    with win_col:
        window_label = st.radio("Rolling window", ["1m", "3m", "6m", "12m"], horizontal=True,
                                 label_visibility="collapsed", key="roll_window")
    window = int(window_label.rstrip("m"))
    rolling_series = {t: (r["Date"], r["Rolling"]) for t, d in type_dfs.items()
                       for r in [rolling_window(d, window)]}
    show_chart(rolling_multi_chart(rolling_series), f"Rolling {window_label}", "Robusta vs Arabica")

    # ── Per-type: table + seasonal + YTD ────────────────────────────────────
    for t in ("Robusta", "Arabica"):
        ctx = type_ctx[t]
        if ctx is None:
            st.warning(f"Not enough {t} history yet.")
            continue
        df_t = type_dfs[t]
        ytd_t = ytd_by_period(df_t, ctx["n_months"], start_month=start_month, valid_periods=ctx["all_periods"])
        st.markdown(
            heatmap_table_html(
                ctx["pivot"], ctx["month_order"], title=f"{t} monthly disappearance",
                ref_years=ctx["ref_years"], current_period=ctx["current"], ytd_months=ctx["n_months"],
            ),
            unsafe_allow_html=True,
        )
        show_chart(seasonal_chart(ctx["wide"][ctx["sel_periods"]], current=ctx["current"]),
                   f"{t} seasonal pattern")
        show_chart(single_line_chart(ytd_t.index, ytd_t.values), f"{t} YTD trend")

    # ── Shared comparison: Robusta vs Arabica side by side ──────────────────
    if type_ctx["Robusta"] and type_ctx["Arabica"]:
        st.markdown('<p class="coffee-section">Robusta vs Arabica — comparison</p>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        for col, t in zip((c1, c2), ("Robusta", "Arabica")):
            ctx = type_ctx[t]
            with col:
                show_chart(latest_vs_band_chart(ctx["wide"], ctx["current"], ctx["ref_years"]),
                           f"{t} vs Min/Max/Avg", f"L{len(ctx['ref_years'])}Y")
        c3, c4 = st.columns(2)
        for col, t in zip((c3, c4), ("Robusta", "Arabica")):
            ctx = type_ctx[t]
            cum_t = cumulative_by_period(type_dfs[t], start_month=start_month, valid_periods=ctx["all_periods"])
            cum_t_sel = cum_t[[p for p in ctx["sel_periods"] if p in cum_t.columns]]
            with col:
                show_chart(cumulative_chart(cum_t_sel, current=ctx["current"]), f"{t} cumulative")

    # ── Cross-check: monthly disappearance (bars) vs KC-RC spread (line) ────
    if KC_RC_RATIO_PARQUET.exists():
        st.markdown('<p class="coffee-section">Disappearance vs KC-RC arb</p>', unsafe_allow_html=True)
        arb_col1, arb_col2, arb_col3 = st.columns([2, 2, 2])
        with arb_col1:
            arb_unit = st.radio("Spread unit", ["$/MT", "¢/lb"], horizontal=True,
                                 label_visibility="collapsed", key="arb_unit")
        with arb_col2:
            arb_shift = st.number_input(
                "Arb lag (months)", min_value=-12, max_value=12, value=0, step=1, key="arb_shift",
            )
        with arb_col3:
            arb_smooth = st.number_input(
                "Rolling avg (months)", min_value=1, max_value=12, value=1, step=1, key="arb_smooth",
            )
        st.caption(
            "Positive lag = Arb is lagging by N months (shows an older arb value against current "
            "disappearance); negative = Arb leads. Rolling avg smooths the arb and Robusta-share lines."
        )

        rob_d = type_dfs["Robusta"][["Date", "Disappearance"]].rename(columns={"Disappearance": "Robusta"})
        ara_d = type_dfs["Arabica"][["Date", "Disappearance"]].rename(columns={"Disappearance": "Arabica"})
        spread_df = load_kc_rc_ratio().copy()
        # Shift the arb's own calendar date forward/back before merging — a
        # positive lag re-labels Jan's arb as April's (N=3), so the arb value
        # shown next to April's disappearance is actually 3 months old.
        spread_df["Date"] = spread_df["Date"] + pd.DateOffset(months=int(arb_shift))
        spread_df["SpreadDisplay"] = (
            spread_df["KC_RC_Spread"] / KC_FACTOR if arb_unit == "¢/lb" else spread_df["KC_RC_Spread"]
        )
        spread_df["SpreadDisplay"] = spread_df["SpreadDisplay"].rolling(arb_smooth, min_periods=1).mean()
        shift_note = f", lag {arb_shift:+d}m" if arb_shift else ""
        smooth_note = f", {arb_smooth}m avg" if arb_smooth > 1 else ""
        line_label = f"KC-RC spread ({arb_unit}{shift_note}{smooth_note})"

        merged = rob_d.merge(ara_d, on="Date", how="inner").merge(
            spread_df[["Date", "SpreadDisplay"]], on="Date", how="inner")
        if not merged.empty:
            bar_series = {
                "Robusta": merged["Robusta"].rolling(arb_smooth, min_periods=1).mean(),
                "Arabica": merged["Arabica"].rolling(arb_smooth, min_periods=1).mean(),
            }
            show_chart(
                bars_with_secondary_line_chart(
                    merged["Date"], bar_series,
                    merged["Date"], merged["SpreadDisplay"], line_label, line_color=INK,
                ),
                "Monthly disappearance vs KC-RC spread", f"bars: {y_unit} · line: {arb_unit}, right axis{smooth_note}",
            )

            share_df = rob_d.merge(ara_d, on="Date", how="inner")
            total = share_df["Robusta"] + share_df["Arabica"]
            share_df["RobustaSharePct"] = (share_df["Robusta"] / total * 100).where(total > 0)
            share_df["RobustaSharePct"] = share_df["RobustaSharePct"].rolling(arb_smooth, min_periods=1).mean()
            share_merged = share_df.merge(spread_df[["Date", "SpreadDisplay"]], on="Date", how="inner")
            show_chart(
                line_with_secondary_line_chart(
                    share_merged["Date"], share_merged["RobustaSharePct"], "Robusta % of disappearance",
                    share_merged["Date"], share_merged["SpreadDisplay"], line_label,
                    color1=BLUE, color2=INK,
                ),
                "Robusta share of disappearance vs KC-RC spread", f"%, left{smooth_note} · {arb_unit}{shift_note}, right",
            )

            scatter_fig, r2 = scatter_with_r2(
                share_merged["SpreadDisplay"], share_merged["RobustaSharePct"],
                line_label, "Robusta % of disappearance",
            )
            show_chart(
                scatter_fig, "Robusta share vs KC-RC spread (scatter)", f"R² = {r2:.2f}",
            )

            lag_grid = list(range(0, 25))
            smooth_grid = list(range(1, 13))
            base_spread = load_kc_rc_ratio()[["Date", "KC_RC_Spread"]].copy()
            base_spread["SpreadRaw"] = (
                base_spread["KC_RC_Spread"] / KC_FACTOR if arb_unit == "¢/lb" else base_spread["KC_RC_Spread"]
            )
            raw_share = rob_d.merge(ara_d, on="Date", how="inner")
            raw_total = raw_share["Robusta"] + raw_share["Arabica"]
            raw_share["SharePctRaw"] = (raw_share["Robusta"] / raw_total * 100).where(raw_total > 0)
            r2_grid, corr_grid = [], []
            for smooth in smooth_grid:
                r2_row, corr_row = [], []
                share_smoothed = raw_share[["Date", "SharePctRaw"]].copy()
                share_smoothed["SharePctRaw"] = share_smoothed["SharePctRaw"].rolling(smooth, min_periods=1).mean()
                for lag in lag_grid:
                    sp = base_spread[["Date", "SpreadRaw"]].copy()
                    sp["Date"] = sp["Date"] + pd.DateOffset(months=lag)
                    sp["Smoothed"] = sp["SpreadRaw"].rolling(smooth, min_periods=1).mean()
                    m = share_smoothed.merge(sp[["Date", "Smoothed"]], on="Date", how="inner").dropna()
                    corr = float(m["Smoothed"].corr(m["SharePctRaw"])) if len(m) >= 2 and m["Smoothed"].std() > 0 else 0.0
                    r2_row.append(corr ** 2)
                    corr_row.append(corr)
                r2_grid.append(r2_row)
                corr_grid.append(corr_row)
            with st.expander("Pearson correlation grid: Robusta share vs KC-RC spread", expanded=True):
                show_chart(
                    corr_heatmap_chart(corr_grid, lag_grid, smooth_grid, "Arb lag (months)", "Rolling avg (months)"),
                    "Pearson correlation grid", "lag 0-24m x rolling avg 1-12m",
                )
            with st.expander("R² grid: Robusta share vs KC-RC spread", expanded=False):
                show_chart(
                    r2_heatmap_chart(r2_grid, lag_grid, smooth_grid, "Arb lag (months)", "Rolling avg (months)"),
                    "R² grid", "lag 0-24m x rolling avg 1-12m",
                )
        else:
            st.info("Not enough overlapping history between disappearance and price data yet.")

    with st.expander("Assumptions & methodology", expanded=False):
        st.markdown(TYPE_FOOTNOTE)

# ── ECF Stocks ────────────────────────────────────────────────────────────────
with tab_stocks:
    st.markdown('<h1 class="coffee-title">ECF Stocks</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="coffee-caption">Monthly ECF certified stocks by coffee type — data from Jan 2020</p>',
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
        show_chart(diverging_bar_chart(stocks["Date"], stocks[change_col]), f"{type_} — month-over-month change")
    with s2:
        total = stocks_total_series(unit=unit_label)
        show_chart(
            two_line_chart(total["Date"], total["Level"], "Total Europe", total["RollingAvg"], "12m average"),
            "Total Europe stocks & 12m average",
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
        "Stocks by coffee type",
    )

    st.caption(
        "Data starts January 2020 — Aug–Dec 2019 was a one-off ECF certified-stock "
        "re-certification event, dropped rather than shown as real seasonality."
    )

# ── ECF Projection ────────────────────────────────────────────────────────────
with tab_projection:
    st.markdown('<h1 class="coffee-title">ECF Projection</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="coffee-caption">ECF certified stocks release bi-monthly, ~1 month after the '
        "period ends — the next release adds two new months of data at once. This estimates that "
        "pending 2-month stock change from EU “excess imports” (TDM reports these sooner) "
        "before ECF confirms it.</p>",
        unsafe_allow_html=True,
    )

    stock_levels = load_stocks("Total Europe").sort_values("Date").reset_index(drop=True)
    net = load_net_imports()
    if stock_levels.empty or net.empty:
        st.info("Not enough stock or import history yet to build a projection.")
    else:
        stock_chg = stock_change_series_bags()
        last_row = stock_levels.iloc[-1]
        last_date, last_level_bags = last_row["Date"], last_row["Bags"]
        pending_dates = [last_date + pd.DateOffset(months=1), last_date + pd.DateOffset(months=2)]

        # Auto-tuned against history: trailing-average window, include/exclude
        # current month, extra smoothing on the excess-imports side, and a
        # small lead/lag — whichever combination maximizes R². The stock side
        # stays a fixed rolling-2m change (the real bi-monthly cadence) so
        # "predicted value" still means "the 2 pending months' combined change."
        fit = best_excess_imports_fit()
        if fit is None:
            st.info("Not enough overlapping history yet to fit a projection model.")
        else:
            ei = excess_imports_series(fit["include_current"], fit["window"]).sort_values("Date").reset_index(drop=True)
            ei["X"] = ei["ExcessImports"].rolling(fit["excess_roll"], min_periods=fit["excess_roll"]).mean()
            sc = stock_chg[["Date", "Rolling2m"]].rename(columns={"Rolling2m": "Y"}).copy()
            sc["Date"] = sc["Date"] + pd.DateOffset(months=fit["lag"])
            merged = ei[["Date", "X"]].merge(sc, on="Date", how="inner").dropna()
            r2 = fit["r2"]

            variant_note = "including" if fit["include_current"] else "excluding"
            lag_note = f", lag {fit['lag']:+d}m" if fit["lag"] else ""
            st.caption(
                f"Auto-tuned: {fit['window']}m trailing import baseline ({variant_note} current month), "
                f"{fit['excess_roll']}m smoothing on excess imports{lag_note} "
                f"(best historical fit: R² = {r2:.2f}, n={fit['n']} months)."
            )

            show_chart(
                two_line_chart(
                    merged["Date"], merged["X"] / 1e6, "Excess imports (smoothed)",
                    merged["Y"] / 1e6, "ECF stock change (rolling 2m)",
                ),
                "Excess imports vs ECF stock change", "Mn Bags",
            )

            # A brand-new month's TDM figure can show up before customs
            # reporting has caught up — Imports far below the trailing average
            # signals an incomplete/preliminary read, not a real import
            # collapse, and would otherwise feed a wildly overstated input
            # into the regression. Only the pending months actually feeding
            # the model's required lookback window matter here.
            target_date = pending_dates[-1]
            source_date = target_date + pd.DateOffset(months=fit["lag"])
            lookback = [source_date - pd.DateOffset(months=i) for i in range(fit["excess_roll"])]
            relevant_pending = [d for d in pending_dates if d in lookback]

            net_sorted = net.sort_values("Date").reset_index(drop=True)
            net_sorted["ImportsTrailingAvg"] = net_sorted["Imports"].rolling(12, min_periods=6).mean()
            net_idx = net_sorted.set_index("Date")
            have_import_months = set(net_sorted["Date"])
            missing_months, incomplete_months = [], []
            for d in relevant_pending:
                if d not in have_import_months:
                    missing_months.append(d)
                elif net_idx.loc[d, "Imports"] < 0.3 * net_idx.loc[d, "ImportsTrailingAvg"]:
                    incomplete_months.append(d)
            unusable = missing_months or incomplete_months or source_date not in set(ei["Date"])

            if unusable:
                if missing_months:
                    st.warning(
                        "TDM import data doesn't cover " +
                        ", ".join(d.strftime("%b %Y") for d in missing_months) +
                        " yet — needed for the projection's lookback window."
                    )
                if incomplete_months:
                    st.warning(
                        ", ".join(d.strftime("%b %Y") for d in incomplete_months) +
                        " TDM import data looks incomplete (customs reporting hasn't caught up yet) "
                        "rather than a real collapse — waiting for a fuller read before projecting."
                    )
                show_chart(
                    scatter_with_r2(merged["X"] / 1e6, merged["Y"] / 1e6,
                                     "Excess imports (Mn Bags)", "ECF stock change (Mn Bags)")[0],
                    "Excess imports vs ECF stock change (scatter)", f"R² = {r2:.2f}",
                )
            else:
                x_new = float(ei.loc[ei["Date"] == source_date, "X"].iloc[0])
                slope, intercept = np.polyfit(merged["X"], merged["Y"], 1)
                predicted_avg_change = slope * x_new + intercept
                predicted_total_change = predicted_avg_change * 2
                predicted_level = last_level_bags + predicted_total_change

                k1, k2, k3, k4 = st.columns(4)
                k1.metric(f"Last known ({last_date.strftime('%b %Y')})", f"{last_level_bags / 1e6:.2f} Mn bags")
                k2.metric(
                    f"Projected ({pending_dates[1].strftime('%b %Y')})",
                    f"{predicted_level / 1e6:.2f} Mn bags",
                    f"{predicted_total_change / 1e6:+.2f} Mn bags",
                )
                k3.metric("Excess imports input", f"{x_new / 1e6:+.2f} Mn bags",
                           help=f"{fit['excess_roll']}m-smoothed excess imports as of {source_date.strftime('%b %Y')}")
                k4.metric("Model fit", f"R² = {r2:.2f}")

                show_chart(
                    scatter_with_projection(
                        merged["X"] / 1e6, merged["Y"] / 1e6,
                        "Excess imports (Mn Bags)", "ECF stock change (Mn Bags)",
                        proj_point=(x_new / 1e6, predicted_avg_change / 1e6),
                    )[0],
                    "Excess imports vs ECF stock change (scatter)",
                    f"R² = {r2:.2f} · orange star = projection for {pending_dates[0].strftime('%b')}"
                    f"-{pending_dates[1].strftime('%b %Y')}",
                )

    st.caption(
        "Excess imports = monthly EU net imports minus their own trailing average, regressed "
        "against ECF's rolling 2-month stock change; parameters (window, smoothing, lead/lag) are "
        "auto-tuned to maximize historical R². The projection assumes that fitted relationship "
        "holds for the two months ECF hasn't reported yet."
    )
