import gzip
import io
import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ============================================================

# PAGE CONFIG

# ============================================================

st.set_page_config(
page_title="FO PRO Trader Assistant",
page_icon="📊",
layout="wide",
initial_sidebar_state="expanded",
)

# ============================================================

# CONSTANTS

# ============================================================

IST = ZoneInfo("Asia/Kolkata")

API_BASE = "https://api.upstox.com"
API_V2 = f"{API_BASE}/v2"
API_V3 = f"{API_BASE}/v3"

DB_FILE = os.path.join(os.getcwd(), "fo_trade_journal.db")

DEFAULT_EXPIRY_LOOKAHEAD = 90

RISK_PROFILES = {
"Conservative": {
"sl": 0.75,
"t1": 1.30,
"t2": 1.60,
},
"Balanced": {
"sl": 0.70,
"t1": 1.40,
"t2": 1.80,
},
"Aggressive": {
"sl": 0.65,
"t1": 1.55,
"t2": 2.10,
},
}

# ============================================================

# CSS

# ============================================================

st.markdown(
"""

<style>

.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

.topbar {
    background: linear-gradient(135deg,#111827,#1f2937);
    padding: 18px 22px;
    border-radius: 14px;
    margin-bottom: 15px;
    color: white;
    box-shadow: 0 4px 18px rgba(0,0,0,.12);
}

.topbar-title {
    font-size: 28px;
    font-weight: 800;
    line-height: 1.15;
}

.topbar-sub {
    margin-top: 5px;
    font-size: 13px;
    opacity: .82;
}

.status-live {
    background: #166534;
    color: white;
    padding: 11px 16px;
    border-radius: 10px;
    font-weight: 700;
    margin: 10px 0 15px 0;
}

.status-closed {
    background: #991b1b;
    color: white;
    padding: 11px 16px;
    border-radius: 10px;
    font-weight: 700;
    margin: 10px 0 15px 0;
}

.card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,.18);
    border-radius: 14px;
    padding: 15px;
    margin-bottom: 12px;
}

.section-title {
    font-size: 17px;
    font-weight: 800;
    margin-bottom: 10px;
}

.metric-label {
    font-size: 12px;
    opacity: .70;
}

.metric-value {
    font-size: 20px;
    font-weight: 800;
}

.trade-call {
    background: #14532d;
    color: white;
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    font-size: 28px;
    font-weight: 900;
}

.trade-put {
    background: #991b1b;
    color: white;
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    font-size: 28px;
    font-weight: 900;
}

.trade-neutral {
    background: #374151;
    color: white;
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    font-size: 28px;
    font-weight: 900;
}

.small-note {
    font-size: 12px;
    opacity: .72;
}

.scanner-card {
    border: 1px solid rgba(128,128,128,.18);
    border-radius: 10px;
    padding: 9px;
    margin-bottom: 7px;
}

</style>

""",
unsafe_allow_html=True,
)

# ============================================================

# TOP BAR

# ============================================================

st.markdown(
"""

<div class="topbar">
    <div class="topbar-title">📊 FO PRO Trader Assistant</div>
    <div class="topbar-sub">
        Options Analysis • Upstox REST API • Live market data •
        Probability • OI • Technicals • Risk Management
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ============================================================

# API

# ============================================================

def get_token():
try:
token = st.secrets["UPSTOX_ACCESS_TOKEN"]
return str(token).strip()
except Exception:
return ""

TOKEN = get_token()

HEADERS = {
"Accept": "application/json",
"Authorization": f"Bearer {TOKEN}",
}

def api_get(url, params=None, timeout=20):
if not TOKEN:
raise RuntimeError(
"UPSTOX_ACCESS_TOKEN is missing from Streamlit secrets."
)

```
response = requests.get(
    url,
    headers=HEADERS,
    params=params,
    timeout=timeout,
)

if response.status_code != 200:
    raise RuntimeError(
        f"Upstox API error {response.status_code}: "
        f"{response.text[:500]}"
    )

data = response.json()

if isinstance(data, dict) and data.get("status") == "error":
    raise RuntimeError(str(data))

return data
```

# ============================================================

# MARKET STATUS

# ============================================================

def market_is_open():
now = datetime.now(IST)

```
if now.weekday() >= 5:
    return False

market_open = now.replace(
    hour=9,
    minute=15,
    second=0,
    microsecond=0,
)

market_close = now.replace(
    hour=15,
    minute=30,
    second=0,
    microsecond=0,
)

return market_open <= now <= market_close
```

if market_is_open():
st.markdown(
'<div class="status-live">● LIVE DATA</div>',
unsafe_allow_html=True,
)
else:
st.markdown(
'<div class="status-closed">● MARKET CLOSED</div>',
unsafe_allow_html=True,
)

# ============================================================

# BASIC HELPERS

# ============================================================

def safe_float(value, default=np.nan):
try:
if value is None:
return default
return float(value)
except Exception:
return default

def pct_change(value, base):
value = safe_float(value)
base = safe_float(base)

```
if not np.isfinite(value) or not np.isfinite(base) or base == 0:
    return np.nan

return ((value - base) / base) * 100.0
```

def format_price(value):
value = safe_float(value)

```
if not np.isfinite(value):
    return "—"

return f"₹{value:,.2f}"
```

def format_num(value, decimals=2):
value = safe_float(value)

```
if not np.isfinite(value):
    return "—"

return f"{value:,.{decimals}f}"
```

def normalize_key(value):
return str(value).strip().upper()

# ============================================================

# INSTRUMENT SEARCH

# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def search_instrument(query):
query = normalize_key(query)

```
data = api_get(
    f"{API_V2}/instruments/search",
    params={
        "query": query,
        "exchanges": "NSE",
        "segments": "EQ,INDEX",
    },
)

rows = data.get("data", [])

if not rows:
    return None

exact = [
    x for x in rows
    if normalize_key(
        x.get("trading_symbol")
        or x.get("short_name")
        or x.get("name")
        or ""
    ) == query
]

if exact:
    return exact[0]

return rows[0]
```

# ============================================================

# OPTION CONTRACTS

# ============================================================

@st.cache_data(ttl=120, show_spinner=False)
def get_option_contracts(instrument_key):
data = api_get(
f"{API_V2}/option/contract",
params={
"instrument_key": instrument_key,
},
)

```
return data.get("data", [])
```

def get_expiries(contracts):
expiries = set()

```
for item in contracts:
    expiry = item.get("expiry")

    if expiry:
        try:
            expiries.add(pd.to_datetime(expiry).date())
        except Exception:
            pass

return sorted(expiries)
```

# ============================================================

# OPTION CHAIN

# ============================================================

@st.cache_data(ttl=20, show_spinner=False)
def get_option_chain(instrument_key, expiry):
data = api_get(
f"{API_V2}/option/chain",
params={
"instrument_key": instrument_key,
"expiry_date": str(expiry),
},
)

```
return data.get("data", [])
```

# ============================================================

# QUOTE

# ============================================================

@st.cache_data(ttl=20, show_spinner=False)
def get_quote(instrument_key):
data = api_get(
f"{API_V3}/market-quote/quotes",
params={
"instrument_key": instrument_key,
},
)

```
rows = data.get("data", {})

if isinstance(rows, dict):
    if instrument_key in rows:
        return rows[instrument_key]

    if rows:
        return next(iter(rows.values()))

return {}
```

def quote_ltp(quote_data):
if not quote_data:
return np.nan

```
return safe_float(
    quote_data.get("last_price")
    or quote_data.get("ltp")
    or quote_data.get("last_traded_price")
)
```

# ============================================================

# CANDLES

# ============================================================

def parse_candle_response(data):
candles = data.get("data", {}).get("candles", [])

```
if not candles:
    return pd.DataFrame()
```
