"""
Hardmine — TDM EU Coffee Trade Flow Ingest (Exports + Imports)
================================================================
Pulls both export and import flows for the EU-28-external-trade bloc reporter
plus UK/Norway/Switzerland so Net Imports = Imports - Exports can be computed
at the "Total Europe" level for the Coffee Disappearance dashboard.

Requires TDM_API_KEY (env var, or a .env file at the repo root — see .env.example).

Usage:
    python tdm_eu_ingest.py            # incremental update (default)
    python tdm_eu_ingest.py --full     # full historical pull from 201501

Saves to:
    Database/tdm_coffee_eu.parquet

Schedule via Windows Task Scheduler to run daily/monthly.
"""

import argparse
import io
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# ── Logging ──────────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "tdm_eu_ingest.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

API_KEY = os.environ.get("TDM_API_KEY")
if not API_KEY:
    sys.exit(
        "TDM_API_KEY is not set. Put it in a .env file next to this repo's root "
        "(TDM_API_KEY=...), or set it as an environment variable / Task Scheduler "
        "action env before running this script."
    )
BASE_URL = "https://www1.tdmlogin.com/tdm/api/api.asp"

# TDM has no per-country reporter data for individual EU members (customs
# declarations inside the single market aren't split by member state in this
# dataset) — it instead publishes one pre-aggregated bloc reporter, "EU 28
# External Trade" (code E28), which is EU extra-trade only (intra-EU already
# netted out, so no double counting). GB/NO/CH report individually and are
# added on top to match the ICE-certs "Total Europe" universe (UK + EU +
# Norway + Switzerland warehouses).
REPORTERS = "E28,GB,NO,CH"
HS_CODES = ["090111", "090112", "090121", "090122", "210111", "210112"]
LEVEL = "6"
FREQUENCY = "M"
SEPARATOR = "T"
AGG_PARTNERS = "Y"   # partners=all, aggregated -> intra-Europe trade cancels
                     # out when Imports - Exports is summed across the bloc,
                     # leaving net flow with the rest of the world.
CONV = "1"

PERIOD_FULL_BEGIN = "201501"
PERIOD_END = "203012"

FILE_NAME = "tdm_coffee_eu.parquet"
FOLDER = Path(__file__).resolve().parent.parent / "Database"
OUT_FILE = FOLDER / FILE_NAME

COLUMNS = ["REPORTER", "PARTNER", "COMMODITY", "YEAR", "MONTH", "QTY1"]
DEDUP_KEYS = ["FLOW", "REPORTER", "PARTNER", "COMMODITY", "YEAR", "MONTH"]

COMMODITY_TAG = {
    90112: "Green Beans",
    90111: "Green Beans",
    90121: "Roast & Ground",
    90122: "Roast & Ground",
    210111: "Instant & Mixes",
    210112: "Instant & Mixes",
}

GBE_MULTIPLIER = {
    90112: 1.00,
    90111: 1.05,
    90121: 1.19,
    90122: 1.25,
    210111: 2.60,
    210112: 2.60,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def build_url(flow: str, period_begin: str) -> str:
    return (
        f"{BASE_URL}"
        f"?key={API_KEY}"
        f"&flow={flow}"
        f"&reporter={REPORTERS}"
        f"&partners=all"
        f"&periodBegin={period_begin}"
        f"&periodEnd={PERIOD_END}"
        f"&hsCode={','.join(HS_CODES)}"
        f"&levelDetail={LEVEL}"
        f"&frequency={FREQUENCY}"
        f"&separator={SEPARATOR}"
        f"&aggregatePartners={AGG_PARTNERS}"
        f"&conv={CONV}"
    )


def fetch_tdm(flow: str, period_begin: str) -> pd.DataFrame:
    """Download trade data from TDM API for one flow (E=export, I=import)."""
    url = build_url(flow, period_begin)
    log.info("Fetching TDM %s data from %s ...", "exports" if flow == "E" else "imports", period_begin)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    df = pd.read_csv(
        io.StringIO(resp.content.decode("utf-16")),
        sep="\t",
        low_memory=False,
    )
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"API response missing expected columns: {missing}")
    df = df[COLUMNS].copy()
    df["FLOW"] = flow
    log.info("  -> %d rows fetched", len(df))
    return df


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    df["COMMODITY_TAG"] = df["COMMODITY"].map(COMMODITY_TAG)
    df["GBE"] = df["QTY1"] * df["COMMODITY"].map(GBE_MULTIPLIER)
    return df


def incremental_period_begin(existing: pd.DataFrame) -> str:
    latest_year = int(existing["YEAR"].max())
    return f"{latest_year}01"


def merge_and_dedup(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    merged = pd.concat([old, new], ignore_index=True)
    before = len(merged)
    merged = merged.drop_duplicates(subset=DEDUP_KEYS, keep="last")
    log.info("  Dedup: %d -> %d rows (-%d duplicates)", before, len(merged), before - len(merged))
    return merged

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Hardmine TDM EU Coffee Ingest (Exports + Imports)")
    parser.add_argument(
        "--full",
        action="store_true",
        help=f"Full historical pull from {PERIOD_FULL_BEGIN} (use on first run)",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("Hardmine TDM EU Ingest  |  %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    log.info("Mode: %s", "FULL HISTORICAL" if args.full else "INCREMENTAL")

    FOLDER.mkdir(parents=True, exist_ok=True)

    if args.full or not OUT_FILE.exists():
        if not OUT_FILE.exists():
            log.info("No existing parquet found — running full historical pull.")
        period_begin = PERIOD_FULL_BEGIN
    else:
        existing_check = pd.read_parquet(OUT_FILE, columns=["YEAR"])
        period_begin = incremental_period_begin(existing_check)
        log.info("Existing DB found. Incremental pull from %s.", period_begin)

    new_data = pd.concat(
        [fetch_tdm("E", period_begin), fetch_tdm("I", period_begin)],
        ignore_index=True,
    )
    log.info("Adding derived columns (COMMODITY_TAG, GBE) ...")
    new_data = add_derived_columns(new_data)

    if OUT_FILE.exists() and not args.full:
        log.info("Loading existing parquet ...")
        old_data = pd.read_parquet(OUT_FILE)
        rows_before = len(old_data)
        log.info("  -> %d rows in existing DB", rows_before)
        df = merge_and_dedup(old_data, new_data)
    else:
        rows_before = 0
        df = new_data.copy()

    df.to_parquet(OUT_FILE, engine="pyarrow", index=False)
    log.info("Saved -> %s", OUT_FILE)
    log.info(
        "Final DB: %d rows  |  %d unique FLOW/YEAR/MONTH periods",
        len(df),
        df[["FLOW", "YEAR", "MONTH"]].drop_duplicates().shape[0],
    )
    log.info("=" * 60)


if __name__ == "__main__":
    main()
