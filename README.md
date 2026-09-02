# F&O Pro Trader Assistant — MVP

## What is included
A browser dashboard for a non-technical trader:
- scans multiple F&O setups
- scores each setup 0–100
- ranks BUY CE / BUY PE candidates
- considers trend, support/resistance, OI, OI change, volume, IV, liquidity and risk/reward
- has a strict NO-TRADE filter
- has demo data and CSV upload

## Run on Windows
1. Install Python 3.11+.
2. Open Command Prompt in this folder.
3. Run: `pip install -r requirements.txt`
4. Run: `streamlit run app.py`

## Very important
Demo values are synthetic. Do not use demo mode for trading.

The high-accuracy production version needs live licensed market data and historical calibration. NSE's official option-chain service provides option-chain information, while broker/data APIs can provide real-time OI, Greeks, IV, volume and bid/ask data.

A real probability-of-profit number should NOT be guessed from a score. It should be statistically calibrated by backtesting thousands of historical setups and measuring whether target was reached before stop, then validated with walk-forward testing.

Recommended path:
Live data -> feature engine -> market regime -> option-chain/OI analysis -> setup score -> historical probability model -> risk engine -> paper trading -> broker execution.
