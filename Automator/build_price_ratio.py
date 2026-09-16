"""
Hardmine — KC/RC Price Spread & Ratio (Arabica/Robusta futures)
==================================================================
A small derived output for comparing the market-implied Arabica/Robusta
price relationship against the physical Robusta/Arabica disappearance mix.
Reads the ICEBREAKER ARB dashboard's own front-month price data (a sibling
repo, local path — same pattern as build_type_split.py's read of Cecafe
Monthly.xlsx) and writes a small, self-contained monthly parquet into this
repo's own Database/, so the Streamlit Cloud deployment never needs to
reach the other repo at runtime.

KC (Arabica, ¢/lb) is converted to $/MT (x22.0462) before combining with
RC (Robusta, already $/MT) — same conversion the ARB dashboard itself uses.
Falls back to the 2nd-month price on days the 1st month isn't quoted
(common right before contract rollover).

Saves both:
  - KC_RC_Spread = KC($/MT) - RC($/MT)   ("Arabica Premium over Robusta",
    same quantity as the ARB dashboard's Spread Monitor)
  - KC_RC_Ratio  = KC($/MT) / RC($/MT)

Usage:
    python build_price_ratio.py

Reads:
    ../../LSEG/Arb/Database/front_KC.parquet   (sibling repo, local only)
    ../../LSEG/Arb/Database/front_RC.parquet   (sibling repo, local only)

Saves to:
    Database/kc_rc_ratio.parquet
"""

import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s",
                     datefmt="%Y-%m-%d %H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

DATABASE_DIR = Path(__file__).resolve().parent.parent / "Database"
OUT_FILE = DATABASE_DIR / "kc_rc_ratio.parquet"

ARB_DB = Path(__file__).resolve().parents[3] / "LSEG" / "Arb" / "Database"
KC_PARQUET = ARB_DB / "front_KC.parquet"
RC_PARQUET = ARB_DB / "front_RC.parquet"

KC_FACTOR = 22.0462  # cents/lb -> $/MT


def main():
    if not KC_PARQUET.exists() or not RC_PARQUET.exists():
        sys.exit(f"Missing {KC_PARQUET} or {RC_PARQUET} — is the LSEG/Arb repo present locally?")

    log.info("Loading KC/RC front-month prices ...")
    kc = pd.read_parquet(KC_PARQUET)
    rc = pd.read_parquet(RC_PARQUET)

    kc_px = kc["px1"].fillna(kc["px2"]).astype(float)
    rc_px = rc["px1"].fillna(rc["px2"]).astype(float)

    kc_mt = kc_px * KC_FACTOR
    daily = pd.DataFrame({"KC_MT": kc_mt, "RC_MT": rc_px}).dropna()
    daily.index = pd.to_datetime(daily.index)
    daily["Spread"] = daily["KC_MT"] - daily["RC_MT"]
    daily["Ratio"] = daily["KC_MT"] / daily["RC_MT"]

    monthly = daily[["Spread", "Ratio"]].resample("MS").mean().reset_index()
    monthly.columns = ["Date", "KC_RC_Spread", "KC_RC_Ratio"]

    monthly.to_parquet(OUT_FILE, engine="pyarrow", index=False)
    log.info("Saved -> %s", OUT_FILE)
    log.info("Range: %s to %s (%d months)", monthly["Date"].min().date(),
              monthly["Date"].max().date(), len(monthly))


if __name__ == "__main__":
    main()
