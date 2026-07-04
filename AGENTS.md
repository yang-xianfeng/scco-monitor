# AGENTS.md

## Repo

SCCO Monitor — correlation coefficient between SCCO market cap and copper-anchored
fair cap. GitHub Actions daily; CSV persistence; Plotly HTML via GitHub Pages.

## Commands

```bash
python main.py
python -m pytest tests/ -v
```

## Structure

```
main.py              # thin entry
scco_monitor/
  config.py          # thresholds/env/paths
  fetcher.py         # yfinance daily + 15min
  core.py            # ratio calc + signal
  storage.py         # CSV upsert/append
  backtest.py        # zone transition tracker
  notifier.py        # feishu/telegram
  chart.py           # Plotly HTML
```

## Key facts

- **Pure coefficient** — no portfolio, no cost basis, no position advice
- **Configurable thresholds** via env vars `THRESHOLD_SAFE`/`_WATCH`/`_HOT`
- **Deps:** yfinance, requests, pandas only
- **CSV store**, no database
- **Pages source must be "GitHub Actions"**
- **31 tests** — no config file needed for test runner

## New in v3.0

- Renamed from "Cola coefficient" to "相关性系数" (correlation coefficient)
- Thresholds 1.08/1.18/1.28 (env-configurable)
- Removed USER_COST, position advice, portfolio backtest
- Clean single-responsibility modules
