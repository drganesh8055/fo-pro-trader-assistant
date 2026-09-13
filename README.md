# Option Trade Assistant — Live NSE public-data build

## Goal
Browser -> URL -> enter stock -> ANALYZE -> CE/PE/WAIT/NO TRADE + Entry/SL/Targets/Exit.

## Data
This version deliberately does not require Dhan's paid Data API. It uses NSE's public web endpoints on a best-effort basis.

Important: NSE may rate-limit/block automated requests and its Terms of Use govern use of site content. This is not a guaranteed real-time feed. For reliable production trading, use an authorized market-data API.

## Run locally
pip install -r requirements.txt
streamlit run app.py

## Deploy
Upload `app.py` and `requirements.txt` to a Streamlit-compatible host (for example Streamlit Community Cloud) and open the generated HTTPS URL.

## Security
No broker token is required by this build and it does not place orders.

## Disclaimer
The score is a rule-based decision aid, not a probability of profit or guarantee. Verify prices/liquidity with your broker before trading.
