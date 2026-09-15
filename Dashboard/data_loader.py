from pathlib import Path

import pandas as pd
import streamlit as st

DATABASE_DIR = Path(__file__).resolve().parent.parent / "Database"
STOCKS_PATH = DATABASE_DIR / "Coffee Stocks.xlsx"
TDM_EU_PARQUET = DATABASE_DIR / "tdm_coffee_eu.parquet"
ORIGIN_TYPE_SPLIT_PARQUET = DATABASE_DIR / "origin_type_split.parquet"

STOCKS_SHEET = "ECF"
TOTAL_ROW = "Total Europe"

# Aug–Dec 2019 was a one-off ECF certified-stock re-certification event that
# distorts every month it touches (and the Jan-2020 stock-change reading
# right after it) — dropped everywhere rather than shown as real seasonality.
STOCKS_CUTOFF = pd.Timestamp("2020-01-01")

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_NUM = {m: i + 1 for i, m in enumerate(MONTH_ABBR)}

# Period bases available on the Calendar/Crop-year toggle.
CALENDAR = 1
CROP_YEAR = 10

# Unit toggle: MT (native) or 60kg bags.
UNIT_MT = "MT"
UNIT_BAGS = "Bags (60kg)"
BAGS_PER_MT = 1000 / 60


def to_unit(value, unit):
    """Convert a value (or Series/array) from MT to the display unit."""
    return value if unit == UNIT_MT else value * BAGS_PER_MT


def unit_col(unit):
    """Column name in load_stocks()'s output for the chosen display unit."""
    return "MT" if unit == UNIT_MT else "Bags"


def period_month_order(start_month):
    return [MONTH_ABBR[(start_month - 1 + i) % 12] for i in range(12)]


def period_label(year, month, start_month):
    if start_month == 1:
        return str(year)
    start = year - 1 if month < start_month else year
    return f"{str(start)[2:]}/{str(start + 1)[2:]}"


def period_month_num(month, start_month):
    return ((month - start_month) % 12) + 1


def _period_sort_key(label, start_month):
    if start_month == 1:
        return int(label)
    return int("20" + label.split("/")[0])


@st.cache_data(ttl=600)
def load_stocks_raw():
    """Full ECF stocks sheet, all 'Type of Coffee' rows, tidy + dated."""
    df = pd.read_excel(STOCKS_PATH, sheet_name=STOCKS_SHEET)
    df["MonthNum"] = df["Month"].map(MONTH_NUM)
    df = df.dropna(subset=["MonthNum"])
    df["MonthNum"] = df["MonthNum"].astype(int)
    df["Year"] = df["Year"].astype(int)
    df["Date"] = pd.to_datetime(dict(year=df["Year"], month=df["MonthNum"], day=1))
    df = df.sort_values("Date").drop_duplicates(subset=["Year", "MonthNum", "Type of Coffee"], keep="last")
    df = df[df["Date"] >= STOCKS_CUTOFF]
    return df.reset_index(drop=True)


def stock_types():
    """'Type of Coffee' options available in the ECF stocks sheet."""
    df = load_stocks_raw()
    order = ["Total Europe", "Robusta", "Natural Arabica", "Washed Arabica"]
    present = set(df["Type of Coffee"].unique())
    return [t for t in order if t in present]


@st.cache_data(ttl=600)
def load_stocks(type_=TOTAL_ROW):
    """Monthly ECF certified stocks for one 'Type of Coffee' (MT)."""
    df = load_stocks_raw()
    df = df[df["Type of Coffee"] == type_].copy()
    df["StockChange"] = df["MT"].diff()
    df["BagsChange"] = df["Bags"].diff()
    return df[["Date", "Year", "MonthNum", "MT", "Bags", "StockChange", "BagsChange"]].reset_index(drop=True)


def stocks_calendar_table(type_, unit="Bags"):
    """Calendar-year (rows) x calendar-month 1..12 (columns) pivot of stock
    levels, plus a month-over-month change table — feeds the 'ECF Stocks
    Split' heatmap + red/green change table."""
    df = load_stocks(type_)
    level = df.pivot_table(index="Year", columns="MonthNum", values=unit, aggfunc="last")
    level = level.reindex(columns=range(1, 13))
    change_unit = df.pivot_table(index="Year", columns="MonthNum", values=unit, aggfunc="last")
    change_unit = change_unit.reindex(columns=range(1, 13)).diff(axis=1)
    # Jan's change needs December of the PRIOR year, not a blank.
    years = sorted(level.index)
    for i, y in enumerate(years):
        if i == 0:
            continue
        prev_dec = level.loc[years[i - 1], 12] if 12 in level.columns else float("nan")
        jan_val = level.loc[y, 1] if 1 in level.columns else float("nan")
        if pd.notna(jan_val) and pd.notna(prev_dec):
            change_unit.loc[y, 1] = jan_val - prev_dec
    avg_row = change_unit.mean(axis=0, skipna=True)
    return level, change_unit, avg_row


def stocks_total_series(unit=UNIT_BAGS):
    """Monthly Total Europe stock level + its rolling 12m average — one
    axis, two series (a level and its own smoothed trend)."""
    col = "Bags" if unit == UNIT_BAGS else "MT"
    total = load_stocks("Total Europe")[["Date", col]].sort_values("Date").rename(columns={col: "Level"})
    total["RollingAvg"] = total["Level"].rolling(12, min_periods=3).mean()
    return total.reset_index(drop=True)


def stocks_composition_series(unit=UNIT_BAGS):
    """Monthly Robusta / Natural Arabica / Washed Arabica stock levels, same
    unit and comparable magnitude as each other — a legitimate single
    shared axis, no Total line (that's its own chart)."""
    col = "Bags" if unit == UNIT_BAGS else "MT"
    out = None
    for t in ("Robusta", "Natural Arabica", "Washed Arabica"):
        sub = load_stocks(t)[["Date", col]].rename(columns={col: t})
        out = sub if out is None else out.merge(sub, on="Date", how="outer")
    return out.sort_values("Date").reset_index(drop=True)


@st.cache_data(ttl=600)
def load_net_imports():
    """Monthly Net Imports (Imports - Exports) for 'Europe' from the TDM
    EU ingest parquet, summed across all coffee HS codes (green + R&G +
    instant) in green-bean-equivalent terms (GBE, metric tons) — matching
    the basis ECF certified stocks are held in. Raw QTY1 would mix physical
    forms (roast & ground is ~1.19x denser, instant ~2.6x, by GBE weight),
    understating Net Imports by a few percent in a way that drifts over
    time rather than being a constant offset."""
    if not TDM_EU_PARQUET.exists():
        return pd.DataFrame(columns=["Date", "Year", "MonthNum", "Imports", "Exports", "NetImports"])

    raw = pd.read_parquet(TDM_EU_PARQUET, columns=["YEAR", "MONTH", "FLOW", "GBE"])
    raw = raw.groupby(["YEAR", "MONTH", "FLOW"], as_index=False)["GBE"].sum().rename(columns={"GBE": "QTY"})
    pivot = raw.pivot_table(index=["YEAR", "MONTH"], columns="FLOW", values="QTY", fill_value=0.0).reset_index()
    pivot = pivot.rename(columns={"YEAR": "Year", "MONTH": "MonthNum", "E": "Exports", "I": "Imports"})
    for col in ("Imports", "Exports"):
        if col not in pivot.columns:
            pivot[col] = 0.0
    pivot["NetImports"] = pivot["Imports"] - pivot["Exports"]
    pivot["Date"] = pd.to_datetime(dict(year=pivot["Year"], month=pivot["MonthNum"], day=1))
    pivot = pivot.sort_values("Date").reset_index(drop=True)
    return pivot[["Date", "Year", "MonthNum", "Imports", "Exports", "NetImports"]]


def _finalize_disappearance(merged, lag: bool, start_month: int):
    """Shared tail end of build_disappearance() / build_disappearance_by_type():
    apply the optional 1-month lag, compute Disappearance, and label periods.

    lag=True:  Net Imports is taken from the PRIOR month, matched against the
               CURRENT month's stock change (Net Imports lead stocks by ~1
               month in customs reporting vs certification).
    lag=False: same-month Net Imports and Stock Change.
    """
    if lag:
        merged = merged.sort_values("Date")
        merged["NetImports"] = merged["NetImports"].shift(1)

    merged["Disappearance"] = merged["NetImports"] - merged["StockChange"]
    merged["Period"] = merged.apply(lambda r: period_label(int(r["Year"]), int(r["MonthNum"]), start_month), axis=1)
    merged["PeriodMonthNum"] = merged["MonthNum"].apply(lambda m: period_month_num(m, start_month))
    merged["PeriodMonth"] = merged["PeriodMonthNum"].map(dict(enumerate(period_month_order(start_month), start=1)))
    return merged.sort_values("Date").reset_index(drop=True)


@st.cache_data(ttl=600)
def build_disappearance(lag: bool, start_month: int = CROP_YEAR):
    """Merge Net Imports (TDM) with Stocks change (manual ECF certs) and
    compute monthly Disappearance = Net Imports - Stock Change, labeled on
    whichever period basis (Calendar = start_month 1, Crop year = 10)."""
    stocks = load_stocks()
    net = load_net_imports()
    if net.empty:
        return pd.DataFrame(columns=["Date", "Year", "MonthNum", "NetImports", "StockChange", "Disappearance"])

    merged = stocks.merge(net[["Date", "NetImports"]], on="Date", how="inner")
    return _finalize_disappearance(merged, lag, start_month)


@st.cache_data(ttl=600)
def load_robusta_share_monthly():
    """Monthly Robusta share of TDM's classified import volume — Brazil's
    ratio is dynamic (from Cecafe), India/Uganda are locked, ~19 origins are
    near-pure Robusta or Arabica. The ~8% of import volume with no rule yet
    (Indonesia, re-export hubs, etc.) is implicitly assumed to share the same
    type mix as the classified ~92%, since it isn't itself typed."""
    if not ORIGIN_TYPE_SPLIT_PARQUET.exists():
        return pd.DataFrame(columns=["Date", "RobustaShare"])
    df = pd.read_parquet(ORIGIN_TYPE_SPLIT_PARQUET)
    g = df.groupby(["YEAR", "MONTH"], as_index=False).agg(
        Robusta=("ROBUSTA_QTY", "sum"), Arabica=("ARABICA_QTY", "sum"))
    classified = g["Robusta"] + g["Arabica"]
    g["RobustaShare"] = (g["Robusta"] / classified).where(classified > 0)
    g["Date"] = pd.to_datetime(dict(year=g["YEAR"], month=g["MONTH"], day=1))
    g = g.sort_values("Date")
    g["RobustaShare"] = g["RobustaShare"].ffill().bfill()
    return g[["Date", "RobustaShare"]]


def load_stocks_by_group(group: str):
    """ECF stocks for 'Robusta' or 'Arabica' (Natural + Washed Arabica
    combined) — same shape as load_stocks() so it drops into the same
    disappearance pipeline."""
    if group == "Robusta":
        return load_stocks("Robusta")
    raw = load_stocks_raw()
    sub = raw[raw["Type of Coffee"].isin(["Natural Arabica", "Washed Arabica"])]
    g = sub.groupby(["Date", "Year", "MonthNum"], as_index=False)[["MT", "Bags"]].sum()
    g = g.sort_values("Date")
    g["StockChange"] = g["MT"].diff()
    g["BagsChange"] = g["Bags"].diff()
    return g.reset_index(drop=True)


@st.cache_data(ttl=600)
def build_disappearance_by_type(group: str, lag: bool, start_month: int = CROP_YEAR):
    """Same as build_disappearance() but for one coffee type (Robusta or
    Arabica). TDM Imports are origin-attributable (PARTNER = origin country,
    see Automator/build_type_split.py), so they're split using the monthly
    Robusta share directly. Exports (Europe re-exporting to the rest of the
    world) are NOT origin-attributable — PARTNER there is the destination —
    so as an approximation the same month's import-side Robusta share is
    applied to Exports too, on the assumption Europe re-exports roughly the
    type mix it's currently holding."""
    net = load_net_imports()
    share = load_robusta_share_monthly()
    if net.empty or share.empty:
        return pd.DataFrame(columns=["Date", "Year", "MonthNum", "NetImports", "StockChange", "Disappearance"])

    merged_net = net.merge(share, on="Date", how="left")
    merged_net["RobustaShare"] = merged_net["RobustaShare"].ffill().bfill()
    frac = merged_net["RobustaShare"] if group == "Robusta" else (1 - merged_net["RobustaShare"])
    merged_net["NetImports"] = merged_net["Imports"] * frac - merged_net["Exports"] * frac

    stocks = load_stocks_by_group(group)
    merged = stocks.merge(merged_net[["Date", "NetImports"]], on="Date", how="inner")
    return _finalize_disappearance(merged, lag, start_month)


def _drop_leading_incomplete(pivot, month_cols):
    """Drop period rows from the front that don't have all 12 months
    populated (the first period after STOCKS_CUTOFF is a partial year, e.g.
    19/20 only has Feb-Sep 2020 — comparing its Total/YTD against a real
    full year would be misleading). Never touches the current, still-in-
    progress period at the end."""
    while len(pivot) > 1 and pivot.iloc[0][month_cols].isna().any():
        pivot = pivot.iloc[1:].reset_index(drop=True)
    return pivot


def period_table(df, start_month: int = CROP_YEAR):
    """Period (rows) x period-month (columns) pivot of Disappearance, plus
    Total/YoY% and YTD/YoY% columns — feeds the styled HTML table."""
    month_order = period_month_order(start_month)
    # aggfunc="mean" (not "sum") — each (Period, PeriodMonth) cell is exactly
    # one Date's reading, and pivot_table's sum() silently turns an all-NaN
    # group into 0.0 rather than NaN (mean() doesn't).
    pivot = df.pivot_table(index="Period", columns="PeriodMonth", values="Disappearance", aggfunc="mean")
    pivot = pivot.reindex(columns=month_order)
    order = df[["Period"]].drop_duplicates()
    order["start"] = order["Period"].apply(lambda s: _period_sort_key(s, start_month))
    order = order.sort_values("start")["Period"].tolist()
    pivot = pivot.reindex(order).reset_index()
    pivot = _drop_leading_incomplete(pivot, month_order)
    pivot["Total"] = pivot[month_order].sum(axis=1, skipna=True, min_count=1)
    pivot["Total YoY %"] = pivot["Total"].pct_change() * 100
    return pivot


def ytd_by_period(df, months_available, start_month: int = CROP_YEAR, valid_periods=None):
    """Same-window (first `months_available` months of the period) YTD total
    per period — used for the standalone YTD-trend line chart. `valid_periods`
    should be the already-trimmed period_table() index, so a partial leading
    period (e.g. 19/20, missing Oct-Dec) doesn't show a misleadingly low YTD."""
    month_order = period_month_order(start_month)
    cols = month_order[:months_available]
    sub = df[df["PeriodMonth"].isin(cols)]
    ytd = sub.groupby("Period")["Disappearance"].sum(min_count=1)
    order = df[["Period"]].drop_duplicates()
    order["start"] = order["Period"].apply(lambda s: _period_sort_key(s, start_month))
    order = order.sort_values("start")["Period"].tolist()
    if valid_periods is not None:
        order = [p for p in order if p in valid_periods]
    return ytd.reindex(order)


def complete_periods(pivot, start_month: int = CROP_YEAR):
    """Periods with all 12 months populated — the reference set for
    Min/Max/Avg bands (an in-progress period would otherwise drag the
    average down for the months it hasn't reached yet)."""
    month_order = period_month_order(start_month)
    full = pivot.set_index("Period")[month_order]
    return full.index[full.notna().all(axis=1)].tolist()


def cumulative_by_period(df, start_month: int = CROP_YEAR, valid_periods=None):
    """Period cumulative sum, month by month, for the cumulative line chart."""
    month_order = period_month_order(start_month)
    pivot = df.pivot_table(index="PeriodMonthNum", columns="Period", values="Disappearance", aggfunc="mean")
    pivot = pivot.reindex(range(1, 13))
    pivot.index = month_order
    cum = pivot.cumsum(skipna=True)
    order = df[["Period"]].drop_duplicates()
    order["start"] = order["Period"].apply(lambda s: _period_sort_key(s, start_month))
    order = order.sort_values("start")["Period"].tolist()
    if valid_periods is not None:
        order = [p for p in order if p in valid_periods]
    return cum[[p for p in order if p in cum.columns]]


def rolling_window(df, window):
    """Rolling `window`-month sum of Disappearance, in the same unit as
    df["Disappearance"] already is (caller applies to_unit() beforehand)."""
    s = df.set_index("Date")["Disappearance"].sort_index()
    return s.rolling(window, min_periods=window).sum().reset_index(name="Rolling")


def rolling_12m(df):
    r = rolling_window(df, 12)
    return r.rename(columns={"Rolling": "Rolling12mKMT"}).assign(Rolling12mKMT=lambda d: d["Rolling12mKMT"] / 1000)
