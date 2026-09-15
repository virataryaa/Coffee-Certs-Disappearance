from pathlib import Path

import pandas as pd
import streamlit as st

DATABASE_DIR = Path(__file__).resolve().parent.parent / "Database"
STOCKS_PATH = DATABASE_DIR / "Coffee Stocks.xlsx"
TDM_EU_PARQUET = DATABASE_DIR / "tdm_coffee_eu.parquet"

STOCKS_SHEET = "ECF"
TOTAL_ROW = "Total Europe"

MONTH_NUM = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)}

# Crop year (Oct -> Sep) — same convention as the TDM ingest scripts.
CROP_MONTH_MAP = {1: "Oct", 2: "Nov", 3: "Dec", 4: "Jan", 5: "Feb", 6: "Mar",
                  7: "Apr", 8: "May", 9: "Jun", 10: "Jul", 11: "Aug", 12: "Sep"}
CROP_MONTH_ORDER = [CROP_MONTH_MAP[i] for i in range(1, 13)]


def _crop_year(year, month):
    start = year - 1 if month < 10 else year
    return f"{str(start)[2:]}/{str(start + 1)[2:]}"


def _crop_month_num(month):
    return ((month + 2) % 12) + 1


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
    return df.reset_index(drop=True)


def stock_types():
    """'Type of Coffee' options available in the ECF stocks sheet."""
    df = load_stocks_raw()
    order = ["Total Europe", "Robusta", "Natural Arabica", "Washed Arabica"]
    present = set(df["Type of Coffee"].unique())
    return [t for t in order if t in present]


@st.cache_data(ttl=600)
def load_stocks(type_=TOTAL_ROW):
    """Monthly ICE Europe certified stocks for one 'Type of Coffee' (MT)."""
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


def stocks_total_series():
    """Monthly Total Europe stock level + its rolling 12m average — one
    axis, two series (a level and its own smoothed trend)."""
    total = load_stocks("Total Europe")[["Date", "Bags"]].sort_values("Date")
    total["RollingAvg"] = total["Bags"].rolling(12, min_periods=3).mean()
    return total.reset_index(drop=True)


def stocks_composition_series():
    """Monthly Robusta / Natural Arabica / Washed Arabica stock levels, same
    unit (bags) and comparable magnitude as each other — a legitimate single
    shared axis, no Total line (that's its own chart)."""
    out = None
    for t in ("Robusta", "Natural Arabica", "Washed Arabica"):
        sub = load_stocks(t)[["Date", "Bags"]].rename(columns={"Bags": t})
        out = sub if out is None else out.merge(sub, on="Date", how="outer")
    return out.sort_values("Date").reset_index(drop=True)


@st.cache_data(ttl=600)
def load_net_imports():
    """Monthly Net Imports (Imports - Exports) for 'Europe' from the TDM
    EU ingest parquet, summed across all coffee HS codes (green + R&G + instant),
    in raw quantity (QTY1, metric tons)."""
    if not TDM_EU_PARQUET.exists():
        return pd.DataFrame(columns=["Date", "Year", "MonthNum", "Imports", "Exports", "NetImports"])

    raw = pd.read_parquet(TDM_EU_PARQUET, columns=["YEAR", "MONTH", "FLOW", "QTY1"])
    raw = raw.groupby(["YEAR", "MONTH", "FLOW"], as_index=False)["QTY1"].sum().rename(columns={"QTY1": "QTY"})
    pivot = raw.pivot_table(index=["YEAR", "MONTH"], columns="FLOW", values="QTY", fill_value=0.0).reset_index()
    pivot = pivot.rename(columns={"YEAR": "Year", "MONTH": "MonthNum", "E": "Exports", "I": "Imports"})
    for col in ("Imports", "Exports"):
        if col not in pivot.columns:
            pivot[col] = 0.0
    pivot["NetImports"] = pivot["Imports"] - pivot["Exports"]
    pivot["Date"] = pd.to_datetime(dict(year=pivot["Year"], month=pivot["MonthNum"], day=1))
    pivot = pivot.sort_values("Date").reset_index(drop=True)
    return pivot[["Date", "Year", "MonthNum", "Imports", "Exports", "NetImports"]]


@st.cache_data(ttl=600)
def build_disappearance(lag: bool):
    """Merge Net Imports (TDM) with Stocks change (manual certs) and compute
    monthly Disappearance = Net Imports - Stock Change.

    lag=True:  Net Imports is taken from the PRIOR month, matched against the
               CURRENT month's stock change (Net Imports lead stocks by ~1
               month in customs reporting vs certification).
    lag=False: same-month Net Imports and Stock Change.
    """
    stocks = load_stocks()
    net = load_net_imports()
    if net.empty:
        return pd.DataFrame(columns=["Date", "Year", "MonthNum", "NetImports", "StockChange", "Disappearance"])

    merged = stocks.merge(net[["Date", "NetImports"]], on="Date", how="inner")
    if lag:
        merged = merged.sort_values("Date")
        merged["NetImports"] = merged["NetImports"].shift(1)

    merged["Disappearance"] = merged["NetImports"] - merged["StockChange"]
    merged["CropYear"] = merged.apply(lambda r: _crop_year(int(r["Year"]), int(r["MonthNum"])), axis=1)
    merged["CropMonthNum"] = merged["MonthNum"].apply(_crop_month_num)
    merged["CropMonth"] = merged["CropMonthNum"].map(CROP_MONTH_MAP)
    return merged.sort_values("Date").reset_index(drop=True)


def crop_year_table(df):
    """Crop-year (rows) x crop-month (Oct..Sep, columns) pivot of Disappearance,
    plus a Total and % YoY column — feeds the styled HTML table."""
    pivot = df.pivot_table(index="CropYear", columns="CropMonth", values="Disappearance", aggfunc="sum")
    pivot = pivot.reindex(columns=CROP_MONTH_ORDER)
    order = df[["CropYear"]].drop_duplicates()
    order["start"] = order["CropYear"].apply(lambda s: int("20" + s.split("/")[0]))
    order = order.sort_values("start")["CropYear"].tolist()
    pivot = pivot.reindex(order)
    pivot["Total"] = pivot[CROP_MONTH_ORDER].sum(axis=1, skipna=True, min_count=1)
    pivot["YoY %"] = pivot["Total"].pct_change() * 100
    return pivot.reset_index()


def complete_crop_years(pivot):
    """Crop years with all 12 months populated — the reference set for
    Min/Max/Avg bands (an in-progress year would otherwise drag the average
    down for the months it hasn't reached yet)."""
    full = pivot.set_index("CropYear")[CROP_MONTH_ORDER]
    return full.index[full.notna().all(axis=1)].tolist()


def ytd_table(df, months_available):
    """Same-window (Oct..latest reported crop month) YTD total per crop year."""
    cols = CROP_MONTH_ORDER[:months_available]
    sub = df[df["CropMonth"].isin(cols)]
    ytd = sub.groupby("CropYear")["Disappearance"].sum(min_count=1)
    order = df[["CropYear"]].drop_duplicates()
    order["start"] = order["CropYear"].apply(lambda s: int("20" + s.split("/")[0]))
    order = order.sort_values("start")["CropYear"].tolist()
    return ytd.reindex(order)


def cumulative_by_crop_year(df):
    """Crop-year cumulative sum, month by month (Oct=1 .. Sep=12), for the
    cumulative line chart."""
    pivot = df.pivot_table(index="CropMonthNum", columns="CropYear", values="Disappearance", aggfunc="sum")
    pivot = pivot.reindex(range(1, 13))
    pivot.index = [CROP_MONTH_MAP[i] for i in pivot.index]
    cum = pivot.cumsum(skipna=True)
    order = df[["CropYear"]].drop_duplicates()
    order["start"] = order["CropYear"].apply(lambda s: int("20" + s.split("/")[0]))
    order = order.sort_values("start")["CropYear"].tolist()
    return cum[order]


def rolling_12m(df):
    s = df.set_index("Date")["Disappearance"].sort_index()
    return (s.rolling(12, min_periods=12).sum() / 1000).reset_index(name="Rolling12mKMT")
