# Coffee Certs & Disappearance

Europe coffee "disappearance" (Net Imports − Stock Change) dashboard, plus the
underlying ICE Europe certified-stocks split by coffee type.

## Structure

- `Automator/tdm_eu_ingest.py` — pulls TDM export + import flows for the
  EU-28-external-trade bloc reporter (`E28`) plus UK/Norway/Switzerland,
  saves to `Database/tdm_coffee_eu.parquet`. Requires `TDM_API_KEY`
  (env var or `.env` file at repo root — see `.env.example`).
- `Database/Coffee Stocks.xlsx` — manual monthly ICE Europe certified stocks
  (Robusta / Natural Arabica / Washed Arabica / Total Europe), sheet `ECF`.
- `Dashboard/app.py` — Streamlit app: "Disappearance" tab (Net Imports −
  Stock Change, with/without 1-month lag) and "ECF Stocks" tab (stock level
  heatmap, month-over-month change table/chart, dual-axis type breakdown).
- `validate_xlsx.py` / `publish_update.bat` — validate + push the manual
  Excel file (and refreshed parquet) to GitHub for Streamlit Cloud to
  auto-redeploy.

## Updating data

1. Add the latest month to `Database/Coffee Stocks.xlsx` (sheet `ECF`).
2. Run `Automator/refresh_tdm.bat` (or `python tdm_eu_ingest.py`) to refresh
   trade flows.
3. Run `publish_update.bat` to validate, commit, and push.

## Methodology

- **Net Imports** = TDM Imports − TDM Exports, summed across the `E28`
  (EU-28 external trade) reporter plus UK/NO/CH, all coffee HS codes.
- **Stock Change** = month-over-month change in ICE Europe certified stocks
  ("Total Europe" row).
- **Disappearance** = Net Imports − Stock Change.
- **Lag toggle**: "With 1M Lag" pairs the prior month's Net Imports with the
  current month's Stock Change.

## Known limitations / next steps

- Robusta/Arabica split for disappearance isn't available yet — TDM trade
  flows aren't split by coffee type, only the manual stocks are. Planned
  approach: infer type from trade partner (e.g. Vietnam origin → Robusta).
- NAM (US) and Japan stocks/disappearance not yet added.
