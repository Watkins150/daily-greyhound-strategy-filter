# Daily Greyhound Strategy Filter

Dedicated production repository for the UK Daily Greyhound Strategy Filter.

## Daily schedule — Europe/London
- **09:00** — Sporting Life racecard scrape
- **09:15** — Timeform analysis scrape
- **09:30** — strategy matching, Timeform filtering, audit logging and BF Bot CSV publication

## Manual run
GitHub **Actions → Manual - Run Full Pipeline → Run workflow**.

## Main output
`strategy_filtered_tips.csv`

Raw URL:
`https://raw.githubusercontent.com/Watkins150/daily-greyhound-strategy-filter/main/strategy_filtered_tips.csv`

## Audit outputs
- `strategy_filter_summary.json` — raw candidate and exclusion counts
- `strategy_filter_audit.csv` — every Step-2 candidate and final status
- `strategy_filter_removed.csv` — excluded candidates only
- `strategy_filter_run.log` — execution log
- `history/YYYY-MM-DD/` — archived daily outputs

## Strategy baseline
13 UK lay strategies, Sheffield excluded, with exact strategy-specific MinPrice/MaxPrice carried into the BF Bot CSV.
