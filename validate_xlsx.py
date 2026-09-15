"""Sanity-checks Database/Coffee Stocks.xlsx before it gets pushed.

Run standalone: python validate_xlsx.py
Exit code 0 = safe to push. Exit code 1 = problems found, do not push.
"""
import sys
from pathlib import Path

import pandas as pd

XLSX_PATH = Path(__file__).resolve().parent / "Database" / "Coffee Stocks.xlsx"
SHEET_NAME = "ECF"

REQUIRED_COLS = ["Year", "Month", "Type of Coffee", "MT", "Bags"]
KNOWN_TYPES = {"Robusta", "Natural Arabica", "Washed Arabica", "Total Europe"}
KNOWN_MONTHS = {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"}
YEAR_MIN, YEAR_MAX = 2015, 2035

TOTAL_TOLERANCE_ABS = 2.0  # MT


def main():
    errors = []
    warnings = []

    if not XLSX_PATH.exists():
        print(f"FAIL: {XLSX_PATH} does not exist.")
        return 1

    try:
        df = pd.read_excel(XLSX_PATH, sheet_name=SHEET_NAME)
    except Exception as e:
        print(f"FAIL: could not parse '{SHEET_NAME}' sheet - {e}")
        return 1

    for col in REQUIRED_COLS:
        if col not in df.columns:
            errors.append(f"Missing required column '{col}'.")
    if errors:
        _report(errors, warnings)
        return 1

    bad_year = df[~df["Year"].apply(lambda v: pd.notna(v) and float(v).is_integer()
                                     and YEAR_MIN <= int(v) <= YEAR_MAX)]
    for _, r in bad_year.iterrows():
        errors.append(f"Row with bad Year value: {r['Year']!r} (Month={r.get('Month')}, Type={r.get('Type of Coffee')}).")

    bad_month = set(df["Month"].dropna().unique()) - KNOWN_MONTHS
    if bad_month:
        errors.append(f"Unexpected Month value(s): {sorted(bad_month)} — expected 3-letter abbreviations.")

    bad_types = set(df["Type of Coffee"].dropna().unique()) - KNOWN_TYPES
    if bad_types:
        errors.append(f"Unexpected 'Type of Coffee' value(s): {sorted(bad_types)} — typo? Expected only {sorted(KNOWN_TYPES)}.")

    dupes = df[df.duplicated(subset=["Year", "Month", "Type of Coffee"], keep=False)]
    if not dupes.empty:
        for _, row in dupes.iterrows():
            errors.append(f"Duplicate row: Year={row['Year']}, Month={row['Month']}, Type='{row['Type of Coffee']}'.")

    non_blank = df["MT"].dropna()
    non_numeric = non_blank[pd.to_numeric(non_blank, errors="coerce").isna()]
    if not non_numeric.empty:
        bad_rows = df.loc[non_numeric.index, ["Year", "Month", "Type of Coffee"]]
        for _, r in bad_rows.iterrows():
            errors.append(f"Non-numeric MT value for Year={r['Year']}, Month={r['Month']}, Type='{r['Type of Coffee']}'.")

    if errors:
        _report(errors, warnings)
        return 1

    # Reconciliation: Robusta + Natural Arabica + Washed Arabica should equal
    # the "Total Europe" row for each (Year, Month).
    parts_types = {"Robusta", "Natural Arabica", "Washed Arabica"}
    for (year, month), group in df.groupby(["Year", "Month"]):
        total_rows = group[group["Type of Coffee"] == "Total Europe"]
        if total_rows.empty:
            continue
        total_val = total_rows["MT"].iloc[0]
        parts_present = group.loc[group["Type of Coffee"].isin(parts_types), "MT"]
        parts_sum = parts_present.sum(skipna=True)
        if pd.isna(total_val) or parts_present.dropna().empty:
            # Some early months only ever had the Total Europe row filled in,
            # no Robusta/Arabica breakdown — not a data-entry error.
            continue
        if abs(parts_sum - total_val) > TOTAL_TOLERANCE_ABS:
            errors.append(
                f"Total mismatch: Year={year}, Month={month} — Robusta+Natural+Washed = {parts_sum:,.1f} MT "
                f"but Total Europe row = {total_val:,.1f} MT."
            )

    latest = df[["Year", "Month"]].drop_duplicates()
    latest["MonthNum"] = latest["Month"].map({m: i + 1 for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])})
    latest_ym = latest.sort_values(["Year", "MonthNum"]).iloc[-1]
    latest_rows = df[(df["Year"] == latest_ym["Year"]) & (df["Month"] == latest_ym["Month"])]
    if latest_rows["MT"].notna().sum() == 0:
        warnings.append(
            f"Latest period ({int(latest_ym['Year'])}-{latest_ym['Month']}) has zero data — "
            f"fine if not yet reported, worth a second look otherwise."
        )

    return _report(errors, warnings)


def _report(errors, warnings):
    if warnings:
        print("Warnings (won't block the push):")
        for w in warnings:
            print(f"  - {w}")
        print()
    if errors:
        print("FAIL - fix these before pushing:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PASS - Coffee Stocks.xlsx looks good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
