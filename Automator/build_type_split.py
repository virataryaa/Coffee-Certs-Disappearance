"""
Hardmine — Coffee Type Split (Arabica / Robusta) by Origin
=============================================================
Allocates TDM EU import volumes (flow=I, by PARTNER = origin country) into
Arabica vs Robusta. TDM's HS codes don't carry a type, so this is a
best-effort split built from three rules, in priority order:

  1. DYNAMIC — Brazil only. Brazil grows both types in volume, so a fixed
     ratio would miss real month-to-month shifts (frost damage, Conilon
     crop swings, etc). Instead this pulls Brazil's actual monthly
     Arabica/Robusta split for Europe-bound exports from Cecafe Monthly
     (Belgium/Germany/Italy/Netherlands/Spain/UK — the destinations Cecafe
     tracks), shifted forward one month (ocean transit — a bag Cecafe logs
     as exported in month M isn't in TDM's EU import data until ~M+1), and
     applies that ratio to TDM's Brazil-origin import volume. Recent months
     TDM has but Cecafe hasn't reported yet fall back to the trailing
     12-month average ratio.

  2. FIXED (locked) — India (60% Robusta / 40% Arabica) and Uganda (80%
     Robusta / 20% Arabica): both structurally mixed, but without a Brazil-
     style monthly indicator, so a single locked ratio is used throughout.

  3. FIXED (near-pure) — origins that are >95% one type by geography/
     botany (e.g. Vietnam = Robusta, Colombia = Arabica). See FIXED_SPLIT.

Everything else (including re-export/processing hubs like Switzerland,
Germany, Italy, Spain, the US — these show up as PARTNER for roast/instant
HS codes but aren't coffee-growing origins) is left UNCLASSIFIED rather
than guessed. The coverage report at the end shows what fraction of total
import volume is actually typed.

Usage:
    python build_type_split.py

Reads:
    Database/tdm_coffee_eu.parquet                         (this repo)
    ../../Cecafe Monthly/Database/Cecafe Monthly.xlsx        (sibling repo, local only)

Saves to:
    Database/origin_type_split.parquet
"""

import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s",
                     datefmt="%Y-%m-%d %H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

DATABASE_DIR = Path(__file__).resolve().parent.parent / "Database"
TDM_EU_PARQUET = DATABASE_DIR / "tdm_coffee_eu.parquet"
OUT_FILE = DATABASE_DIR / "origin_type_split.parquet"

# Sibling repo — read locally only when this script runs; the dashboard
# itself never touches this path (Streamlit Cloud only has this repo).
CECAFE_XLSX = Path(__file__).resolve().parents[2] / "Cecafe Monthly" / "Database" / "Cecafe Monthly.xlsx"
CECAFE_EUROPE_DESTINATIONS = ["Belgium", "Germany", "Italy", "Netherlands", "Spain", "UK"]

# (robusta_share, arabica_share) — near-pure origins by geography/botany.
FIXED_SPLIT = {
    # Robusta
    "Vietnam": (1.00, 0.00),
    "Cote d'Ivoire": (1.00, 0.00),
    "Cameroon": (1.00, 0.00),
    "Congo (DROC)": (1.00, 0.00),
    "Laos": (1.00, 0.00),
    # Arabica
    "Colombia": (0.00, 1.00),
    "Honduras": (0.00, 1.00),
    "Ethiopia": (0.00, 1.00),
    "Guatemala": (0.00, 1.00),
    "Costa Rica": (0.00, 1.00),
    "Peru": (0.00, 1.00),
    "Mexico": (0.00, 1.00),
    "Nicaragua": (0.00, 1.00),
    "El Salvador": (0.00, 1.00),
    "Ecuador": (0.00, 1.00),
    "Tanzania": (0.00, 1.00),
    "Kenya": (0.00, 1.00),
    "Rwanda": (0.00, 1.00),
    "Burundi": (0.00, 1.00),
    "Papua New Guinea": (0.00, 1.00),
    # Locked mixed splits
    "India": (0.60, 0.40),
    "Uganda": (0.80, 0.20),
}
DYNAMIC_PARTNER = "Brazil"


def brazil_europe_ratio() -> pd.DataFrame:
    """Brazil's actual monthly Robusta share of Europe-bound exports, from
    Cecafe Monthly (Year, Month, RobustaShare). Falls back to a trailing
    12-month average for any month TDM has that Cecafe hasn't reported yet."""
    if not CECAFE_XLSX.exists():
        raise FileNotFoundError(
            f"Cecafe Monthly.xlsx not found at {CECAFE_XLSX} — needed to compute "
            "Brazil's dynamic Arabica/Robusta split."
        )
    df = pd.read_excel(CECAFE_XLSX, sheet_name="Database")
    sub = df[df["Destination"].isin(CECAFE_EUROPE_DESTINATIONS)]
    g = sub.groupby(["Year", "Month", "Type"])["Bags (K)"].sum().unstack("Type").fillna(0.0)
    for t in ("Robusta", "Arabica"):
        if t not in g.columns:
            g[t] = 0.0
    total = g["Robusta"] + g["Arabica"]
    g["RobustaShare"] = (g["Robusta"] / total).where(total > 0)
    g = g.reset_index().sort_values(["Year", "Month"])
    g["RobustaShare"] = g["RobustaShare"].ffill()  # covers recent months TDM has, Cecafe doesn't yet

    # Shipping lag: a bag Cecafe records as exported from Brazil in month M
    # doesn't land in TDM's EU import data until ~month M+1 (ocean transit).
    # Shift the ratio forward one month so it's matched against the TDM
    # month it actually describes, not the month it was loaded onto a ship.
    apply_month = g["Month"] + 1
    apply_year = g["Year"] + (apply_month > 12).astype(int)
    apply_month = apply_month.where(apply_month <= 12, apply_month - 12)
    g["Year"], g["Month"] = apply_year, apply_month

    return g[["Year", "Month", "RobustaShare"]].rename(columns={"Year": "YEAR", "Month": "MONTH"})


def main():
    if not TDM_EU_PARQUET.exists():
        sys.exit(f"Missing {TDM_EU_PARQUET} — run tdm_eu_ingest.py first.")

    log.info("Loading TDM EU imports ...")
    df = pd.read_parquet(TDM_EU_PARQUET)
    imp = df[df["FLOW"] == "I"].groupby(["PARTNER", "YEAR", "MONTH"], as_index=False)["QTY1"].sum()

    log.info("Loading Brazil's dynamic Robusta share from Cecafe Monthly ...")
    brazil_ratio = brazil_europe_ratio()

    is_brazil = imp["PARTNER"] == DYNAMIC_PARTNER
    brazil_rows = imp[is_brazil].merge(brazil_ratio, on=["YEAR", "MONTH"], how="left")
    unmatched = brazil_rows["RobustaShare"].isna().sum()
    if unmatched:
        fallback = brazil_ratio["RobustaShare"].tail(12).mean()
        log.warning("  %d Brazil month(s) had no Cecafe ratio — using trailing-12m avg (%.1f%% Robusta)",
                    unmatched, fallback * 100)
        brazil_rows["RobustaShare"] = brazil_rows["RobustaShare"].fillna(fallback)
    brazil_rows["ROBUSTA_QTY"] = brazil_rows["QTY1"] * brazil_rows["RobustaShare"]
    brazil_rows["ARABICA_QTY"] = brazil_rows["QTY1"] * (1 - brazil_rows["RobustaShare"])
    brazil_rows["CLASSIFICATION"] = "dynamic"
    brazil_rows = brazil_rows.drop(columns=["RobustaShare"])

    fixed_rows = imp[~is_brazil].copy()
    robusta_share = fixed_rows["PARTNER"].map(lambda p: FIXED_SPLIT[p][0] if p in FIXED_SPLIT else float("nan"))
    arabica_share = fixed_rows["PARTNER"].map(lambda p: FIXED_SPLIT[p][1] if p in FIXED_SPLIT else float("nan"))
    fixed_rows["ROBUSTA_QTY"] = fixed_rows["QTY1"] * robusta_share
    fixed_rows["ARABICA_QTY"] = fixed_rows["QTY1"] * arabica_share
    fixed_rows["CLASSIFICATION"] = robusta_share.notna().map({True: "fixed", False: "unclassified"})

    out = pd.concat([brazil_rows, fixed_rows], ignore_index=True)
    out.to_parquet(OUT_FILE, engine="pyarrow", index=False)
    log.info("Saved -> %s", OUT_FILE)

    total_qty = out["QTY1"].sum()
    classified = out.loc[out["CLASSIFICATION"] != "unclassified", "QTY1"].sum()
    log.info("Coverage: %.1f%% of import volume classified by type", 100 * classified / total_qty)

    unclassified = (
        out[out["CLASSIFICATION"] == "unclassified"]
        .groupby("PARTNER")["QTY1"].sum().sort_values(ascending=False)
    )
    if not unclassified.empty:
        log.info("Largest unclassified origins (not typed — no rule yet):")
        for partner, qty in unclassified.head(10).items():
            log.info("  %-20s %12.1f  (%.1f%% of total)", partner, qty, 100 * qty / total_qty)


if __name__ == "__main__":
    main()
