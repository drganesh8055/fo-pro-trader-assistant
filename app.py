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

rows = []

for c in candles:
    if len(c) < 6:
        continue

    rows.append(
        {
            "timestamp": c[0],
            "open": safe_float(c[1]),
            "high": safe_float(c[2]),
            "low": safe_float(c[3]),
            "close": safe_float(c[4]),
            "volume": safe_float(c[5]),
        }
    )

if not rows:
    return pd.DataFrame()

df = pd.DataFrame(rows)

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce",
)

df = df.dropna(subset=["timestamp"])
df = df.sort_values("timestamp").reset_index(drop=True)

return df
```

@st.cache_data(ttl=60, show_spinner=False)
def get_intraday_5m(instrument_key):
to_date = date.today()
from_date = to_date - timedelta(days=10)

```
url = (
    f"{API_V3}/historical-candle/"
    f"{instrument_key}/5minute/"
    f"{to_date}/{from_date}"
)

try:
    data = api_get(url)
    return parse_candle_response(data)
except Exception:
    return pd.DataFrame()
```

@st.cache_data(ttl=120, show_spinner=False)
def get_30m_candles(instrument_key):
to_date = date.today()
from_date = to_date - timedelta(days=90)

```
url = (
    f"{API_V3}/historical-candle/"
    f"{instrument_key}/30minute/"
    f"{to_date}/{from_date}"
)

try:
    data = api_get(url)
    return parse_candle_response(data)
except Exception:
    return pd.DataFrame()
```

@st.cache_data(ttl=300, show_spinner=False)
def get_daily_candles(instrument_key):
to_date = date.today()
from_date = to_date - timedelta(days=220)

```
url = (
    f"{API_V3}/historical-candle/"
    f"{instrument_key}/day/"
    f"{to_date}/{from_date}"
)

try:
    data = api_get(url)
    return parse_candle_response(data)
except Exception:
    return pd.DataFrame()
```

# ============================================================

# TECHNICAL INDICATORS

# ============================================================

def calculate_rsi(series, period=14):
delta = series.diff()

```
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

avg_gain = gain.rolling(period).mean()
avg_loss = loss.rolling(period).mean()

rs = avg_gain / avg_loss.replace(0, np.nan)

rsi = 100 - (100 / (1 + rs))

return rsi
```

def calculate_atr(df, period=14):
if df.empty:
return pd.Series(dtype=float)

```
high = df["high"]
low = df["low"]
close = df["close"]

prev_close = close.shift(1)

tr1 = high - low
tr2 = (high - prev_close).abs()
tr3 = (low - prev_close).abs()

tr = pd.concat(
    [tr1, tr2, tr3],
    axis=1,
).max(axis=1)

return tr.rolling(period).mean()
```

def calculate_adx(df, period=14):
if len(df) < period * 2:
return np.nan

```
high = df["high"]
low = df["low"]
close = df["close"]

up_move = high.diff()
down_move = -low.diff()

plus_dm = pd.Series(
    np.where(
        (up_move > down_move) & (up_move > 0),
        up_move,
        0,
    ),
    index=df.index,
)

minus_dm = pd.Series(
    np.where(
        (down_move > up_move) & (down_move > 0),
        down_move,
        0,
    ),
    index=df.index,
)

tr1 = high - low
tr2 = (high - close.shift()).abs()
tr3 = (low - close.shift()).abs()

tr = pd.concat(
    [tr1, tr2, tr3],
    axis=1,
).max(axis=1)

atr = tr.rolling(period).mean()

plus_di = 100 * (
    plus_dm.rolling(period).mean() /
    atr.replace(0, np.nan)
)

minus_di = 100 * (
    minus_dm.rolling(period).mean() /
    atr.replace(0, np.nan)
)

dx = (
    (plus_di - minus_di).abs()
    /
    (plus_di + minus_di).replace(0, np.nan)
) * 100

adx = dx.rolling(period).mean()

return safe_float(adx.iloc[-1])
```

def technical_snapshot(df):
if df.empty or len(df) < 30:
return {
"trend": "Neutral",
"rsi": np.nan,
"ema20": np.nan,
"ema50": np.nan,
"atr": np.nan,
"adx": np.nan,
"vwap": np.nan,
"momentum": np.nan,
"volume_ratio": np.nan,
}

```
close = df["close"]

ema20 = close.ewm(span=20, adjust=False).mean()
ema50 = close.ewm(span=50, adjust=False).mean()

rsi = calculate_rsi(close)
atr = calculate_atr(df)
adx = calculate_adx(df)

typical_price = (
    df["high"] +
    df["low"] +
    df["close"]
) / 3

cumulative_volume = df["volume"].cumsum()

vwap = (
    typical_price * df["volume"]
).cumsum() / cumulative_volume.replace(0, np.nan)

momentum = pct_change(
    close.iloc[-1],
    close.iloc[-6],
)

volume_avg = df["volume"].rolling(20).mean()

volume_ratio = (
    df["volume"].iloc[-1] /
    volume_avg.iloc[-1]
    if safe_float(volume_avg.iloc[-1]) != 0
    else np.nan
)

last_close = safe_float(close.iloc[-1])
last_ema20 = safe_float(ema20.iloc[-1])
last_ema50 = safe_float(ema50.iloc[-1])
last_vwap = safe_float(vwap.iloc[-1])

bullish_votes = 0
bearish_votes = 0

if np.isfinite(last_close) and np.isfinite(last_ema20):
    if last_close > last_ema20:
        bullish_votes += 1
    elif last_close < last_ema20:
        bearish_votes += 1

if np.isfinite(last_close) and np.isfinite(last_ema50):
    if last_close > last_ema50:
        bullish_votes += 1
    elif last_close < last_ema50:
        bearish_votes += 1

if np.isfinite(last_close) and np.isfinite(last_vwap):
    if last_close > last_vwap:
        bullish_votes += 1
    elif last_close < last_vwap:
        bearish_votes += 1

if safe_float(rsi) > 55:
    bullish_votes += 1
elif safe_float(rsi) < 45:
    bearish_votes += 1

if safe_float(momentum) > 0.15:
    bullish_votes += 1
elif safe_float(momentum) < -0.15:
    bearish_votes += 1

if bullish_votes >= bearish_votes + 2:
    trend = "Bullish"
elif bearish_votes >= bullish_votes + 2:
    trend = "Bearish"
else:
    trend = "Neutral"

return {
    "trend": trend,
    "rsi": safe_float(rsi.iloc[-1]),
    "ema20": last_ema20,
    "ema50": last_ema50,
    "atr": safe_float(atr.iloc[-1]),
    "adx": safe_float(adx),
    "vwap": last_vwap,
    "momentum": safe_float(momentum),
    "volume_ratio": safe_float(volume_ratio),
}
```

# ============================================================

# TREND / TIMEFRAME

# ============================================================

def overall_trend(tf5, tf30, tfd):
trends = [
tf5.get("trend"),
tf30.get("trend"),
tfd.get("trend"),
]

```
bullish = trends.count("Bullish")
bearish = trends.count("Bearish")

if bullish >= 2 and bullish > bearish:
    return "Bullish"

if bearish >= 2 and bearish > bullish:
    return "Bearish"

return "Neutral"
```

def timeframe_score(tf, direction):
trend = tf.get("trend")

```
if direction == "Bullish":
    if trend == "Bullish":
        return 1
    if trend == "Neutral":
        return 0
    return -1

if direction == "Bearish":
    if trend == "Bearish":
        return 1
    if trend == "Neutral":
        return 0
    return -1

return 0
```

# ============================================================

# OI LEVELS

# ============================================================

def oi_levels(chain, spot):
if not chain:
return np.nan, np.nan, np.nan, {}

```
rows = []

for row in chain:
    strike = safe_float(row.get("strike_price"))

    if not np.isfinite(strike):
        continue

    ce = row.get("call_options") or row.get("CE") or {}
    pe = row.get("put_options") or row.get("PE") or {}

    ce_md = ce.get("market_data") or {}
    pe_md = pe.get("market_data") or {}

    ce_oi = safe_float(
        ce_md.get("oi")
        or ce.get("oi")
        or row.get("ce_oi")
    )

    pe_oi = safe_float(
        pe_md.get("oi")
        or pe.get("oi")
        or row.get("pe_oi")
    )

    rows.append(
        {
            "strike": strike,
            "ce_oi": ce_oi,
            "pe_oi": pe_oi,
        }
    )

if not rows:
    return np.nan, np.nan, np.nan, {}

df = pd.DataFrame(rows)

df["distance"] = (
    df["strike"] - safe_float(spot)
).abs()

support_df = df[df["strike"] <= safe_float(spot)]

resistance_df = df[df["strike"] >= safe_float(spot)]

if not support_df.empty:
    support_row = support_df.sort_values(
        "pe_oi",
        ascending=False,
    ).iloc[0]

    support = safe_float(
        support_row["strike"]
    )
else:
    support = np.nan

if not resistance_df.empty:
    resistance_row = resistance_df.sort_values(
        "ce_oi",
        ascending=False,
    ).iloc[0]

    resistance = safe_float(
        resistance_row["strike"]
    )
else:
    resistance = np.nan

total_ce = df["ce_oi"].replace(
    [np.inf, -np.inf],
    np.nan,
).sum()

total_pe = df["pe_oi"].replace(
    [np.inf, -np.inf],
    np.nan,
).sum()

if total_ce > 0:
    pcr = total_pe / total_ce
else:
    pcr = np.nan

oi_wall_info = {
    "max_ce_oi": safe_float(df["ce_oi"].max()),
    "max_pe_oi": safe_float(df["pe_oi"].max()),
    "ce_wall": safe_float(
        df.loc[df["ce_oi"].idxmax(), "strike"]
    )
    if df["ce_oi"].notna().any()
    else np.nan,
    "pe_wall": safe_float(
        df.loc[df["pe_oi"].idxmax(), "strike"]
    )
    if df["pe_oi"].notna().any()
    else np.nan,
}

return support, resistance, pcr, oi_wall_info
```

def nearest_row(chain, spot, side="CE"):
if not chain:
return None

```
rows = []

for row in chain:
    strike = safe_float(row.get("strike_price"))

    if not np.isfinite(strike):
        continue

    rows.append(
        (
            abs(strike - safe_float(spot)),
            row,
        )
    )

if not rows:
    return None

rows.sort(key=lambda x: x[0])

for _, row in rows:
    if side == "CE":
        option = (
            row.get("call_options")
            or row.get("CE")
        )
    else:
        option = (
            row.get("put_options")
            or row.get("PE")
        )

    if option:
        return row

return rows[0][1]
```

# ============================================================

# NORMALIZE OPTION CHAIN

# ============================================================

def normalize_option(option):
if not option:
return {}

```
md = option.get("market_data") or {}

greeks = option.get("option_greeks") or {}

return {
    "instrument_key": option.get("instrument_key"),
    "ltp": safe_float(
        md.get("ltp")
        or option.get("ltp")
    ),
    "bid": safe_float(
        md.get("bid_price")
        or md.get("bid")
    ),
    "ask": safe_float(
        md.get("ask_price")
        or md.get("ask")
    ),
    "oi": safe_float(
        md.get("oi")
        or option.get("oi")
    ),
    "prev_oi": safe_float(
        md.get("prev_oi")
        or option.get("prev_oi")
    ),
    "volume": safe_float(
        md.get("volume")
        or option.get("volume")
    ),
    "iv": safe_float(
        greeks.get("iv")
        or option.get("iv")
    ),
    "delta": safe_float(
        greeks.get("delta")
        or option.get("delta")
    ),
    "theta": safe_float(
        greeks.get("theta")
        or option.get("theta")
    ),
    "gamma": safe_float(
        greeks.get("gamma")
        or option.get("gamma")
    ),
    "vega": safe_float(
        greeks.get("vega")
        or option.get("vega")
    ),
}
```

def normalize_chain(chain):
rows = []

```
for row in chain:
    strike = safe_float(
        row.get("strike_price")
    )

    if not np.isfinite(strike):
        continue

    ce = normalize_option(
        row.get("call_options")
        or row.get("CE")
        or {}
    )

    pe = normalize_option(
        row.get("put_options")
        or row.get("PE")
        or {}
    )

    ce["strike"] = strike
    pe["strike"] = strike

    ce["side"] = "CE"
    pe["side"] = "PE"

    ce["oi_change"] = (
        ce["oi"] - ce["prev_oi"]
        if np.isfinite(ce["oi"])
        and np.isfinite(ce["prev_oi"])
        else np.nan
    )

    pe["oi_change"] = (
        pe["oi"] - pe["prev_oi"]
        if np.isfinite(pe["oi"])
        and np.isfinite(pe["prev_oi"])
        else np.nan
    )

    rows.append(ce)
    rows.append(pe)

return pd.DataFrame(rows)
```

# ============================================================

# OPTION SCORING

# ============================================================

def score_option(
option,
direction,
spot,
tf5,
tf30,
tfd,
pcr,
):
tf = tf5

```
score = 0.0
reasons = []

ltp = safe_float(option.get("ltp"))
delta = safe_float(option.get("delta"))
iv = safe_float(option.get("iv"))
volume = safe_float(option.get("volume"))
oi = safe_float(option.get("oi"))
bid = safe_float(option.get("bid"))
ask = safe_float(option.get("ask"))
strike = safe_float(option.get("strike"))

# --------------------------------------------------------
# Timeframe alignment
# --------------------------------------------------------

alignment = (
    timeframe_score(tf5, direction)
    + timeframe_score(tf30, direction)
    + timeframe_score(tfd, direction)
)

if alignment >= 2:
    score += 25
    reasons.append("strong timeframe alignment")
elif alignment == 1:
    score += 15
    reasons.append("partial timeframe alignment")
elif alignment == 0:
    score += 5
    reasons.append("mixed timeframe structure")
else:
    score -= 10
    reasons.append("timeframe conflict")

# --------------------------------------------------------
# Delta
# --------------------------------------------------------

abs_delta = abs(delta) if np.isfinite(delta) else np.nan

if np.isfinite(abs_delta):
    if 0.45 <= abs_delta <= 0.70:
        score += 20
        reasons.append("healthy delta")
    elif 0.35 <= abs_delta <= 0.80:
        score += 12
        reasons.append("acceptable delta")
    else:
        score -= 8
        reasons.append("weak delta")

# --------------------------------------------------------
# PCR
# --------------------------------------------------------

if np.isfinite(pcr):
    if direction == "Bullish":
        if pcr >= 1.05:
            score += 12
            reasons.append("PCR supports bullish bias")
        elif pcr >= 0.90:
            score += 6
            reasons.append("PCR mildly bullish")
        elif pcr < 0.75:
            score -= 8
            reasons.append("PCR weak for bullish trade")

    elif direction == "Bearish":
        if pcr <= 0.95:
            score += 12
            reasons.append("PCR supports bearish bias")
        elif pcr <= 1.10:
            score += 6
            reasons.append("PCR mildly bearish")
        elif pcr > 1.30:
            score -= 8
            reasons.append("PCR weak for bearish trade")

# --------------------------------------------------------
# Volume
# --------------------------------------------------------

if np.isfinite(volume) and volume > 0:
    if np.isfinite(oi) and oi > 0:
        volume_oi_ratio = volume / oi
    else:
        volume_oi_ratio = np.nan

    if np.isfinite(volume_oi_ratio):
        if volume_oi_ratio >= 0.35:
            score += 12
            reasons.append("good option activity")
        elif volume_oi_ratio >= 0.15:
            score += 7
            reasons.append("moderate option activity")
        else:
            score += 3
    else:
        score += 3
else:
    score -= 8
    reasons.append("low/no option volume")

# --------------------------------------------------------
# Spread
# --------------------------------------------------------

if (
    np.isfinite(bid)
    and np.isfinite(ask)
    and ask > 0
    and bid >= 0
):
    spread_pct = (
        (ask - bid)
        / ask
    ) * 100

    if spread_pct <= 2:
        score += 10
        reasons.append("tight spread")
    elif spread_pct <= 4:
        score += 5
        reasons.append("acceptable spread")
    else:
        score -= 10
        reasons.append("wide spread")
else:
    spread_pct = np.nan

# --------------------------------------------------------
# IV
# --------------------------------------------------------

if np.isfinite(iv):
    if iv < 18:
        score += 3
    elif iv <= 35:
        score += 7
        reasons.append("reasonable IV")
    elif iv <= 50:
        score += 3
    else:
        score -= 5
        reasons.append("high IV")

# --------------------------------------------------------
# Distance from spot
# --------------------------------------------------------

if np.isfinite(strike) and np.isfinite(spot):
    distance_pct = (
        abs(strike - spot)
        / spot
    ) * 100

    if distance_pct <= 1.0:
        score += 8
        reasons.append("near ATM")
    elif distance_pct <= 2.0:
        score += 5
    elif distance_pct <= 3.0:
        score += 2
    else:
        score -= 5

else:
    distance_pct = np.nan

# --------------------------------------------------------
# Underlying trend
# --------------------------------------------------------

underlying_trend = overall_trend(
    tf5,
    tf30,
    tfd,
)

if underlying_trend == direction:
    score += 8
    reasons.append("underlying trend agrees")
elif underlying_trend != "Neutral":
    score -= 8
    reasons.append("underlying trend conflicts")

score = max(0, min(100, score))

# --------------------------------------------------------
# Upstox PoP
# --------------------------------------------------------

# Upstox may provide probability fields under
# different names depending on response structure.
pop = safe_float(
    option.get("pop")
    or option.get("probability_of_profit")
    or option.get("probability")
)

if not np.isfinite(pop):
    # Do NOT call this a statistical probability.
    # This is only a fallback estimate used for filtering.
    if np.isfinite(abs_delta):
        estimated_pop = (
            50
            + ((abs_delta - 0.50) * 35)
        )
    else:
        estimated_pop = 50

    pop = max(
        35,
        min(75, estimated_pop),
    )

return {
    "score": round(score, 1),
    "reasons": reasons,
    "alignment": alignment,
    "spread_pct": spread_pct,
    "distance_pct": distance_pct,
    "delta": delta,
    "iv": iv,
    "volume": volume,
    "oi": oi,
    "ltp": ltp,
    "strike": strike,
    "pop": pop,
}
```

# ============================================================

# PLAN

# ============================================================

def build_plan(
scored,
direction,
support,
resistance,
risk_profile,
spot,
):
if not scored:
return None

```
ltp = safe_float(scored.get("ltp"))

if not np.isfinite(ltp) or ltp <= 0:
    return None

profile = RISK_PROFILES.get(
    risk_profile,
    RISK_PROFILES["Balanced"],
)

sl = ltp * profile["sl"]
t1 = ltp * profile["t1"]
t2 = ltp * profile["t2"]

trigger_hit = False

if direction == "Bullish":
    if np.isfinite(resistance):
        trigger_hit = spot >= resistance
    else:
        trigger_hit = True

    trigger_text = (
        f"Break/hold above resistance "
        f"{format_price(resistance)}"
        if np.isfinite(resistance)
        else "Price confirmation required"
    )

else:
    if np.isfinite(support):
        trigger_hit = spot <= support
    else:
        trigger_hit = True

    trigger_text = (
        f"Break/hold below support "
        f"{format_price(support)}"
        if np.isfinite(support)
        else "Price confirmation required"
    )

hard_fail = []

if scored["score"] < 72:
    hard_fail.append(
        "setup score below 72"
    )

if scored["alignment"] < 2:
    hard_fail.append(
        "fewer than 2 aligned timeframes"
    )

opposite = (
    "Bearish"
    if direction == "Bullish"
    else "Bullish"
)

if direction == "Bullish":
    # handled by caller with tf snapshots
    pass

if scored["spread_pct"] > 4:
    hard_fail.append(
        "wide option spread"
    )

delta = safe_float(scored["delta"])

if (
    not np.isfinite(delta)
    or not (
        0.35 <= abs(delta) <= 0.80
    )
):
    hard_fail.append(
        "poor delta"
    )

pop = safe_float(scored["pop"])

if (
    not np.isfinite(pop)
    or pop < 55
):
    hard_fail.append(
        "low Upstox PoP"
    )

if scored["volume"] <= 0:
    hard_fail.append(
        "no option volume"
    )

readiness = (
    "READY"
    if not hard_fail and trigger_hit
    else (
        "WAIT FOR TRIGGER"
        if not hard_fail
        else "NO TRADE"
    )
)

return {
    "entry": ltp,
    "sl": sl,
    "t1": t1,
    "t2": t2,
    "trigger_hit": trigger_hit,
    "trigger_text": trigger_text,
    "hard_fail": hard_fail,
    "readiness": readiness,
    "direction": direction,
    "score": scored["score"],
    "pop": scored["pop"],
    "delta": scored["delta"],
    "iv": scored["iv"],
    "strike": scored["strike"],
    "volume": scored["volume"],
    "spread_pct": scored["spread_pct"],
    "alignment": scored["alignment"],
    "reasons": scored["reasons"],
}
```

# ============================================================

# DECISION JOURNAL DATABASE

# ============================================================

def db_connect():
conn = sqlite3.connect(
DB_FILE,
timeout=10,
check_same_thread=False,
)
return conn

def init_database():
conn = db_connect()

```
cur = conn.cursor()

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        symbol TEXT,
        instrument_key TEXT,
        expiry TEXT,
        spot REAL,

        decision TEXT,
        direction TEXT,

        ce_score REAL,
        pe_score REAL,

        selected_strike REAL,
        selected_option_key TEXT,
        selected_side TEXT,

        pop REAL,
        delta REAL,
        iv REAL,
        pcr REAL,

        support REAL,
        resistance REAL,

        entry REAL,
        stop_loss REAL,
        target1 REAL,
        target2 REAL,

        trigger_hit INTEGER,
        readiness TEXT,

        alignment INTEGER,
        spread_pct REAL,
        volume REAL,

        ce_reasons TEXT,
        pe_reasons TEXT,
        reason_text TEXT,

        outcome TEXT,
        exit_price REAL,
        exit_timestamp TEXT,

        tracking_until TEXT
    )
    """
)

conn.commit()
conn.close()
```

init_database()

def insert_decision(record):
columns = [
"timestamp",
"symbol",
"instrument_key",
"expiry",
"spot",
"decision",
"direction",
"ce_score",
"pe_score",
"selected_strike",
"selected_option_key",
"selected_side",
"pop",
"delta",
"iv",
"pcr",
"support",
"resistance",
"entry",
"stop_loss",
"target1",
"target2",
"trigger_hit",
"readiness",
"alignment",
"spread_pct",
"volume",
"ce_reasons",
"pe_reasons",
"reason_text",
"outcome",
"exit_price",
"exit_timestamp",
"tracking_until",
]

```
values = tuple(
    record.get(col)
    for col in columns
)

placeholders = ",".join(
    ["?"] * len(columns)
)

conn = db_connect()

cur = conn.cursor()

cur.execute(
    f"""
    INSERT INTO decisions
    ({",".join(columns)})
    VALUES ({placeholders})
    """,
    values,
)

conn.commit()
conn.close()
```

def should_log_decision(
symbol,
expiry,
decision,
side,
strike,
entry,
):
conn = db_connect()

```
cur = conn.cursor()

cur.execute(
    """
    SELECT timestamp, decision,
           selected_side,
           selected_strike,
           entry
    FROM decisions
    WHERE symbol = ?
      AND expiry = ?
    ORDER BY id DESC
    LIMIT 1
    """,
    (
        symbol,
        str(expiry),
    ),
)

row = cur.fetchone()

conn.close()

if not row:
    return True

try:
    previous_time = datetime.fromisoformat(
        row[0]
    )

    if previous_time.tzinfo is None:
        previous_time = previous_time.replace(
            tzinfo=IST
        )

    age_minutes = (
        datetime.now(IST)
        - previous_time.astimezone(IST)
    ).total_seconds() / 60

except Exception:
    age_minutes = 999

if age_minutes >= 10:
    return True

same_decision = (
    str(row[1]) == str(decision)
    and str(row[2]) == str(side)
    and abs(
        safe_float(row[3], 0)
        - safe_float(strike, 0)
    ) < 0.01
)

if same_decision:
    return False

return True
```

def update_outcomes():
"""
Paper-trade outcome tracker.

```
WIN:
    T1 reached before SL.

LOSS:
    SL reached before T1.

TIMEOUT_PROFIT:
    Tracking window ended with option premium
    above entry.

TIMEOUT_LOSS:
    Tracking window ended with option premium
    below entry.

TIMEOUT_FLAT:
    Tracking window ended approximately at entry.

Only CALL BUY / PUT BUY records are tracked.
WAIT FOR TRIGGER and NO TRADE are not treated as trades.
"""

conn = db_connect()

cur = conn.cursor()

cur.execute(
    """
    SELECT
        id,
        selected_option_key,
        entry,
        stop_loss,
        target1,
        tracking_until
    FROM decisions
    WHERE decision IN ('CALL BUY','PUT BUY')
      AND outcome IS NULL
    """
)

rows = cur.fetchall()

for row in rows:
    (
        record_id,
        option_key,
        entry,
        stop_loss,
        target1,
        tracking_until,
    ) = row

    if not option_key:
        continue

    entry = safe_float(entry)
    stop_loss = safe_float(stop_loss)
    target1 = safe_float(target1)

    if (
        not np.isfinite(entry)
        or not np.isfinite(stop_loss)
        or not np.isfinite(target1)
    ):
        continue

    current_price = np.nan

    try:
        quote_data = get_quote(
            option_key
        )

        current_price = quote_ltp(
            quote_data
        )

    except Exception:
        continue

    if not np.isfinite(current_price):
        continue

    outcome = None
    exit_price = None

    # For an option BUY:
    # premium falling to SL = loss
    # premium rising to T1 = win

    if current_price <= stop_loss:
        outcome = "LOSS"
        exit_price = current_price

    elif current_price >= target1:
        outcome = "WIN"
        exit_price = current_price

    else:
        try:
            tracking_dt = datetime.fromisoformat(
                tracking_until
            )

            if tracking_dt.tzinfo is None:
                tracking_dt = tracking_dt.replace(
                    tzinfo=IST
                )

            if datetime.now(IST) >= tracking_dt:
                exit_price = current_price

                difference = (
                    current_price - entry
                ) / entry

                if difference > 0.005:
                    outcome = "TIMEOUT_PROFIT"
                elif difference < -0.005:
                    outcome = "TIMEOUT_LOSS"
                else:
                    outcome = "TIMEOUT_FLAT"

        except Exception:
            pass

    if outcome:
        cur.execute(
            """
            UPDATE decisions
            SET outcome = ?,
                exit_price = ?,
                exit_timestamp = ?
            WHERE id = ?
            """,
            (
                outcome,
                exit_price,
                datetime.now(IST).isoformat(),
                record_id,
            ),
        )

conn.commit()
conn.close()
```

# ============================================================

# DECISION LOGGING

# ============================================================

def log_current_decision(
symbol,
instrument_key,
expiry,
spot,
decision,
direction,
ce_score,
pe_score,
ce_scored,
pe_scored,
selected_plan,
selected_option_key,
pcr,
support,
resistance,
):
if selected_plan:
selected_side = (
"CE"
if selected_plan["direction"] == "Bullish"
else "PE"
)

```
    selected_strike = selected_plan["strike"]
    pop = selected_plan["pop"]
    delta = selected_plan["delta"]
    iv = selected_plan["iv"]
    entry = selected_plan["entry"]
    sl = selected_plan["sl"]
    t1 = selected_plan["t1"]
    t2 = selected_plan["t2"]
    trigger_hit = selected_plan["trigger_hit"]
    readiness = selected_plan["readiness"]
    alignment = selected_plan["alignment"]
    spread_pct = selected_plan["spread_pct"]
    volume = selected_plan["volume"]

    if selected_plan["hard_fail"]:
        reason_text = (
            " | ".join(
                selected_plan["hard_fail"]
            )
        )
    elif not trigger_hit:
        reason_text = "Waiting for entry trigger"
    else:
        reason_text = "All entry gates satisfied"

else:
    selected_side = None
    selected_strike = np.nan
    pop = np.nan
    delta = np.nan
    iv = np.nan
    entry = np.nan
    sl = np.nan
    t1 = np.nan
    t2 = np.nan
    trigger_hit = False
    readiness = "NO TRADE"
    alignment = 0
    spread_pct = np.nan
    volume = np.nan
    reason_text = "No valid option candidate"

side_for_dedup = selected_side
strike_for_dedup = selected_strike

if not should_log_decision(
    symbol,
    expiry,
    decision,
    side_for_dedup,
    strike_for_dedup,
    entry,
):
    return

tracking_until = (
    datetime.now(IST)
    + timedelta(
        hours=6
    )
).isoformat()

record = {
    "timestamp": datetime.now(IST).isoformat(),
    "symbol": symbol,
    "instrument_key": instrument_key,
    "expiry": str(expiry),
    "spot": spot,

    "decision": decision,
    "direction": direction,

    "ce_score": ce_score,
    "pe_score": pe_score,

    "selected_strike": selected_strike,
    "selected_option_key": selected_option_key,
    "selected_side": selected_side,

    "pop": pop,
    "delta": delta,
    "iv": iv,
    "pcr": pcr,

    "support": support,
    "resistance": resistance,

    "entry": entry,
    "stop_loss": sl,
    "target1": t1,
    "target2": t2,

    "trigger_hit": int(bool(trigger_hit)),
    "readiness": readiness,

    "alignment": alignment,
    "spread_pct": spread_pct,
    "volume": volume,

    "ce_reasons": json.dumps(
        ce_scored.get("reasons", [])
        if ce_scored
        else []
    ),

    "pe_reasons": json.dumps(
        pe_scored.get("reasons", [])
        if pe_scored
        else []
    ),

    "reason_text": reason_text,

    "outcome": None,
    "exit_price": None,
    "exit_timestamp": None,

    "tracking_until": tracking_until,
}

insert_decision(record)
```

# ============================================================

# SCANNER

# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def get_nse_instrument_master():
url = (
"https://assets.upstox.com/"
"market-quote/instruments/exchange/"
"complete.json.gz"
)

```
response = requests.get(
    url,
    timeout=30,
)

response.raise_for_status()

with gzip.GzipFile(
    fileobj=io.BytesIO(response.content)
) as gz:
    raw = gz.read()

return json.loads(
    raw.decode("utf-8")
)
```

def scanner_universe():
try:
data = get_nse_instrument_master()
except Exception:
return []

```
rows = []

for item in data:
    if not isinstance(item, dict):
        continue

    segment = str(
        item.get("segment", "")
    ).upper()

    instrument_type = str(
        item.get("instrument_type", "")
    ).upper()

    trading_symbol = str(
        item.get("trading_symbol", "")
    ).upper()

    if (
        segment == "NSE_FO"
        and instrument_type in {
            "FUT",
            "OPTIDX",
            "OPTSTK",
        }
    ):
        rows.append(
            item
        )

symbols = sorted(
    {
        x.get("trading_symbol")
        for x in rows
        if x.get("trading_symbol")
    }
)

return symbols
```

def scanner_candidates():
"""
Lightweight scanner.

```
It uses the same decision engine but limits the
number of instruments so the Upstox API is not
overloaded.
"""

symbols = scanner_universe()

if not symbols:
    return []

results = []

# Keep scanning controlled.
symbols = symbols[:80]

for symbol in symbols:
    try:
        instrument = search_instrument(
            symbol
        )

        if not instrument:
            continue

        instrument_key = instrument.get(
            "instrument_key"
        )

        if not instrument_key:
            continue

        contracts = get_option_contracts(
            instrument_key
        )

        expiries = get_expiries(
            contracts
        )

        if not expiries:
            continue

        expiry = expiries[0]

        chain = get_option_chain(
            instrument_key,
            expiry,
        )

        if not chain:
            continue

        quote_data = get_quote(
            instrument_key
        )

        spot = quote_ltp(
            quote_data
        )

        if not np.isfinite(spot):
            continue

        support, resistance, pcr, _ = (
            oi_levels(
                chain,
                spot,
            )
        )

        df5 = get_intraday_5m(
            instrument_key
        )

        df30 = get_30m_candles(
            instrument_key
        )

        dfd = get_daily_candles(
            instrument_key
        )

        tf5 = technical_snapshot(df5)
        tf30 = technical_snapshot(df30)
        tfd = technical_snapshot(dfd)

        norm = normalize_chain(
            chain
        )

        if norm.empty:
            continue

        ce_df = norm[
            norm["side"] == "CE"
        ]

        pe_df = norm[
            norm["side"] == "PE"
        ]

        best_ce = None
        best_pe = None

        for _, option in ce_df.iterrows():
            distance = (
                abs(
                    safe_float(
                        option["strike"]
                    ) - spot
                ) / spot
            ) * 100

            if distance > 3:
                continue

            scored = score_option(
                option.to_dict(),
                "Bullish",
                spot,
                tf5,
                tf30,
                tfd,
                pcr,
            )

            if (
                best_ce is None
                or scored["score"]
                > best_ce["score"]
            ):
                best_ce = scored

        for _, option in pe_df.iterrows():
            distance = (
                abs(
                    safe_float(
                        option["strike"]
                    ) - spot
                ) / spot
            ) * 100

            if distance > 3:
                continue

            scored = score_option(
                option.to_dict(),
                "Bearish",
                spot,
                tf5,
                tf30,
                tfd,
                pcr,
            )

            if (
                best_pe is None
                or scored["score"]
                > best_pe["score"]
            ):
                best_pe = scored

        if not best_ce and not best_pe:
            continue

        best = max(
            [
                x for x in
                [best_ce, best_pe]
                if x is not None
            ],
            key=lambda x: (
                x["pop"],
                x["score"],
            ),
        )

        # Scanner filter intentionally remains
        # >75% as configured in the current app.
        if safe_float(best["pop"]) <= 75:
            continue

        results.append(
            {
                "Symbol": symbol,
                "Expiry": str(expiry),
                "Side": (
                    "CALL"
                    if best is best_ce
                    else "PUT"
                ),
                "Strike": best["strike"],
                "PoP": best["pop"],
                "Score": best["score"],
                "Delta": best["delta"],
                "IV": best["iv"],
                "Spot": spot,
                "Distance %": best[
                    "distance_pct"
                ],
            }
        )

    except Exception:
        continue

results.sort(
    key=lambda x: (
        safe_float(x["PoP"], 0),
        safe_float(x["Score"], 0),
        -safe_float(
            x["Distance %"],
            999,
        ),
    ),
    reverse=True,
)

return results[:5]
```

# ============================================================

# SIDEBAR

# ============================================================

with st.sidebar:

```
st.markdown(
    "## 🔎 Analyze Instrument"
)

symbol_input = st.text_input(
    "Stock / Index",
    value="HDFCBANK",
    placeholder="e.g. HDFCBANK",
)

risk_profile = st.selectbox(
    "Risk Profile",
    list(RISK_PROFILES.keys()),
    index=1,
)

analyze_clicked = st.button(
    "🔍 Analyze",
    use_container_width=True,
)

st.markdown("---")

st.markdown(
    "### ⚡ F&O Scanner"
)

scanner_enabled = st.toggle(
    "High-PoP Scanner",
    value=False,
    help=(
        "Scans a limited F&O universe and "
        "shows candidates with PoP >75%."
    ),
)

if scanner_enabled:
    if st.button(
        "Run Scanner",
        use_container_width=True,
    ):
        st.session_state[
            "run_scanner"
        ] = True

st.markdown("---")

refresh_clicked = st.button(
    "🔄 Refresh Data",
    use_container_width=True,
)

auto_refresh = st.checkbox(
    "Auto Refresh",
    value=False,
)

if auto_refresh:
    st_autorefresh(
        interval=20000,
        key="fo_auto_refresh",
    )

st.markdown("---")

st.caption(
    "Live Upstox REST data • "
    "No automatic orders are placed."
)
```

# ============================================================

# REFRESH

# ============================================================

if refresh_clicked:
st.cache_data.clear()
st.rerun()

# ============================================================

# OUTCOME TRACKING

# ============================================================

try:
update_outcomes()
except Exception:
pass

# ============================================================

# SCANNER UI

# ============================================================

if scanner_enabled:

```
st.markdown(
    '<div class="card"><div class="section-title">'
    "⚡ High-PoP F&O Scanner"
    "</div>"
    '<div class="small-note">'
    "Scanner threshold: PoP &gt; 75%. "
    "Results are candidates for further analysis, "
    "not guaranteed trades."
    "</div></div>",
    unsafe_allow_html=True,
)

if st.session_state.get(
    "run_scanner",
    False,
):
    with st.spinner(
        "Scanning F&O candidates..."
    ):
        scanner_results = scanner_candidates()

    st.session_state[
        "scanner_results"
    ] = scanner_results

    st.session_state[
        "run_scanner"
    ] = False

scanner_results = st.session_state.get(
    "scanner_results",
    [],
)

if scanner_results:
    for item in scanner_results:
        st.markdown(
            f"""
```

<div class="scanner-card">
<b>{item["Symbol"]}</b>
&nbsp; {item["Side"]}
&nbsp; {format_price(item["Strike"])}
<br>
PoP: <b>{format_num(item["PoP"],1)}%</b>
&nbsp; Score: <b>{format_num(item["Score"],1)}</b>
&nbsp; Delta: {format_num(item["Delta"],2)}
<br>
Spot: {format_price(item["Spot"])}
&nbsp; Distance: {format_num(item["Distance %"],2)}%
</div>
""",
                unsafe_allow_html=True,
            )
    else:
        st.info(
            "Click Run Scanner to scan candidates."
        )

# ============================================================

# MAIN ANALYSIS

# ============================================================

symbol = normalize_key(
symbol_input
)

if not symbol:
st.info(
"Enter a stock or index on the left "
"and click Analyze."
)
st.stop()

# Analyze on first load as well as button click.

try:

```
with st.spinner(
    f"Analyzing {symbol}..."
):

    instrument = search_instrument(
        symbol
    )

    if not instrument:
        st.error(
            f"Could not find {symbol} in Upstox."
        )
        st.stop()

    instrument_key = instrument.get(
        "instrument_key"
    )

    display_symbol = (
        instrument.get("trading_symbol")
        or instrument.get("short_name")
        or symbol
    )

    contracts = get_option_contracts(
        instrument_key
    )

    expiries = get_expiries(
        contracts
    )

    if not expiries:
        st.error(
            "No F&O expiry found for this instrument."
        )
        st.stop()

    expiry = expiries[0]

    chain = get_option_chain(
        instrument_key,
        expiry,
    )

    quote_data = get_quote(
        instrument_key
    )

    spot = quote_ltp(
        quote_data
    )

    if not np.isfinite(spot):
        st.error(
            "Could not obtain live spot price."
        )
        st.stop()

    # ----------------------------------------------------
    # Technical data
    # ----------------------------------------------------

    df5 = get_intraday_5m(
        instrument_key
    )

    df30 = get_30m_candles(
        instrument_key
    )

    dfd = get_daily_candles(
        instrument_key
    )

    tf5 = technical_snapshot(df5)
    tf30 = technical_snapshot(df30)
    tfd = technical_snapshot(dfd)

    overall_direction = overall_trend(
        tf5,
        tf30,
        tfd,
    )

    # ----------------------------------------------------
    # OI
    # ----------------------------------------------------

    support, resistance, pcr, oi_wall_info = (
        oi_levels(
            chain,
            spot,
        )
    )

    # ----------------------------------------------------
    # Normalize chain
    # ----------------------------------------------------

    option_df = normalize_chain(
        chain
    )

    if option_df.empty:
        st.error(
            "No option-chain data returned."
        )
        st.stop()

    ce_df = option_df[
        option_df["side"] == "CE"
    ].copy()

    pe_df = option_df[
        option_df["side"] == "PE"
    ].copy()

    # ----------------------------------------------------
    # Best CE
    # ----------------------------------------------------

    ce_candidates = []

    for _, option in ce_df.iterrows():

        distance = (
            abs(
                safe_float(
                    option["strike"]
                ) - spot
            )
            / spot
        ) * 100

        if distance > 3:
            continue

        scored = score_option(
            option.to_dict(),
            "Bullish",
            spot,
            tf5,
            tf30,
            tfd,
            pcr,
        )

        scored["instrument_key"] = (
            option.get(
                "instrument_key"
            )
        )

        ce_candidates.append(
            scored
        )

    # ----------------------------------------------------
    # Best PE
    # ----------------------------------------------------

    pe_candidates = []

    for _, option in pe_df.iterrows():

        distance = (
            abs(
                safe_float(
                    option["strike"]
                ) - spot
            )
            / spot
        ) * 100

        if distance > 3:
            continue

        scored = score_option(
            option.to_dict(),
            "Bearish",
            spot,
            tf5,
            tf30,
            tfd,
            pcr,
        )

        scored["instrument_key"] = (
            option.get(
                "instrument_key"
            )
        )

        pe_candidates.append(
            scored
        )

    best_ce = (
        max(
            ce_candidates,
            key=lambda x: x["score"],
        )
        if ce_candidates
        else None
    )

    best_pe = (
        max(
            pe_candidates,
            key=lambda x: x["score"],
        )
        if pe_candidates
        else None
    )

    ce_score = (
        best_ce["score"]
        if best_ce
        else 0
    )

    pe_score = (
        best_pe["score"]
        if best_pe
        else 0
    )

    # ----------------------------------------------------
    # Plans
    # ----------------------------------------------------

    ce_plan = build_plan(
        best_ce,
        "Bullish",
        support,
        resistance,
        risk_profile,
        spot,
    )

    pe_plan = build_plan(
        best_pe,
        "Bearish",
        support,
        resistance,
        risk_profile,
        spot,
    )

    # Additional hard trend-conflict gate.
    if ce_plan:
        if (
            tf5.get("trend")
            == "Bearish"
            or tf30.get("trend")
            == "Bearish"
        ):
            ce_plan["hard_fail"].append(
                "short-term trend conflict"
            )
            ce_plan["readiness"] = (
                "NO TRADE"
            )

    if pe_plan:
        if (
            tf5.get("trend")
            == "Bullish"
            or tf30.get("trend")
            == "Bullish"
        ):
            pe_plan["hard_fail"].append(
                "short-term trend conflict"
            )
            pe_plan["readiness"] = (
                "NO TRADE"
            )

    # ----------------------------------------------------
    # Decision
    # ----------------------------------------------------

    if (
        ce_plan
        and ce_score >= 72
        and ce_score >= pe_score + 8
        and overall_direction == "Bullish"
        and ce_plan["readiness"]
        in {
            "READY",
            "WAIT FOR TRIGGER",
        }
    ):
        decision = (
            "CALL BUY"
            if ce_plan["readiness"]
            == "READY"
            else "WAIT FOR TRIGGER"
        )

        selected_plan = ce_plan
        selected_scored = best_ce

    elif (
        pe_plan
        and pe_score >= 72
        and pe_score >= ce_score + 8
        and overall_direction == "Bearish"
        and pe_plan["readiness"]
        in {
            "READY",
            "WAIT FOR TRIGGER",
        }
    ):
        decision = (
            "PUT BUY"
            if pe_plan["readiness"]
            == "READY"
            else "WAIT FOR TRIGGER"
        )

        selected_plan = pe_plan
        selected_scored = best_pe

    else:
        decision = "NO TRADE"

        if (
            ce_plan
            and (
                not pe_plan
                or ce_score >= pe_score
            )
        ):
            selected_plan = ce_plan
            selected_scored = best_ce
        elif pe_plan:
            selected_plan = pe_plan
            selected_scored = best_pe
        else:
            selected_plan = None
            selected_scored = None

    # ----------------------------------------------------
    # Log decision
    # ----------------------------------------------------

    selected_option_key = None

    if selected_scored:
        selected_option_key = (
            selected_scored.get(
                "instrument_key"
            )
        )

    try:
        log_current_decision(
            symbol=display_symbol,
            instrument_key=instrument_key,
            expiry=expiry,
            spot=spot,
            decision=decision,
            direction=overall_direction,
            ce_score=ce_score,
            pe_score=pe_score,
            ce_scored=best_ce,
            pe_scored=best_pe,
            selected_plan=selected_plan,
            selected_option_key=selected_option_key,
            pcr=pcr,
            support=support,
            resistance=resistance,
        )
    except Exception:
        pass
```

except Exception as e:

```
st.error(
    f"Analysis error: {e}"
)

st.caption(
    "Check the Upstox access token, "
    "instrument, expiry and API response."
)

st.stop()
```

# ============================================================

# MAIN HEADER

# ============================================================

st.markdown(
f"""

<div class="card">
    <div class="section-title">
        📊 {display_symbol} — F&O Options Analysis
    </div>
    <div class="small-note">
        Expiry: {expiry} &nbsp; • &nbsp;
        Updated: {datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S")} IST
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ============================================================

# DECISION BANNER

# ============================================================

if decision == "CALL BUY":

```
st.markdown(
    '<div class="trade-call">🟢 CALL BUY</div>',
    unsafe_allow_html=True,
)
```

elif decision == "PUT BUY":

```
st.markdown(
    '<div class="trade-put">🔴 PUT BUY</div>',
    unsafe_allow_html=True,
)
```

elif decision == "WAIT FOR TRIGGER":

```
st.markdown(
    '<div class="trade-neutral">🟡 WAIT FOR TRIGGER</div>',
    unsafe_allow_html=True,
)
```

else:

```
st.markdown(
    '<div class="trade-neutral">⚪ NO TRADE</div>',
    unsafe_allow_html=True,
)
```

st.markdown("")

# ============================================================

# TOP METRICS

# ============================================================

m1, m2, m3, m4, m5 = st.columns(5)

with m1:
st.metric(
"Last Traded",
format_price(spot),
)

with m2:
st.metric(
"Market Bias",
overall_direction,
)

with m3:
st.metric(
"PCR",
format_num(pcr, 2),
)

with m4:
st.metric(
"OI Support",
format_price(support),
)

with m5:
st.metric(
"OI Resistance",
format_price(resistance),
)

# ============================================================

# BEST TRADE TAB

# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
[
"⭐ Best Trade",
"📋 Live Option Chain",
"📈 Market Analysis",
"🧠 How Engine Thinks",
]
)

with tab1:

```
st.markdown(
    "### 🎯 Trade Setup"
)

if selected_plan:

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Option Strike",
            format_price(
                selected_plan["strike"]
            ),
        )

    with c2:
        st.metric(
            "PoP",
            f"{format_num(selected_plan['pop'],1)}%",
        )

    with c3:
        st.metric(
            "Setup Score",
            f"{format_num(selected_plan['score'],1)}/100",
        )

    st.markdown("")

    p1, p2, p3, p4 = st.columns(4)

    with p1:
        st.metric(
            "Entry",
            format_price(
                selected_plan["entry"]
            ),
        )

    with p2:
        st.metric(
            "Stop Loss",
            format_price(
                selected_plan["sl"]
            ),
        )

    with p3:
        st.metric(
            "Target 1",
            format_price(
                selected_plan["t1"]
            ),
        )

    with p4:
        st.metric(
            "Target 2",
            format_price(
                selected_plan["t2"]
            ),
        )

    st.markdown("")

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        st.metric(
            "Delta",
            format_num(
                selected_plan["delta"],
                2,
            ),
        )

    with a2:
        st.metric(
            "IV",
            format_num(
                selected_plan["iv"],
                2,
            ),
        )

    with a3:
        st.metric(
            "Alignment",
            f"{selected_plan['alignment']}/3",
        )

    with a4:
        st.metric(
            "Spread",
            (
                f"{format_num(selected_plan['spread_pct'],2)}%"
                if np.isfinite(
                    safe_float(
                        selected_plan[
                            "spread_pct"
                        ]
                    )
                )
                else "—"
            ),
        )

    st.markdown(
        f"""
```

<div class="card">
<div class="section-title">Entry Trigger</div>
{selected_plan["trigger_text"]}
<br><br>
<b>Status:</b> {selected_plan["readiness"]}
</div>
""",
            unsafe_allow_html=True,
        )

```
    if selected_plan["hard_fail"]:

        st.warning(
            " • ".join(
                selected_plan["hard_fail"]
            )
        )

    st.markdown(
        f"""
```

<div class="card">
<div class="section-title">Exit Rule</div>
Exit if Stop Loss is hit, Target 1 / Target 2 is achieved,
or the underlying trend materially invalidates the setup.
</div>
""",
            unsafe_allow_html=True,
        )

```
    st.markdown(
        "### 🔎 Setup Reasons"
    )

    for reason in selected_plan[
        "reasons"
    ]:
        st.write(
            f"• {reason}"
        )

else:

    st.info(
        "No valid option setup was found."
    )
```

# ============================================================

# LIVE OPTION CHAIN

# ============================================================

with tab2:

```
st.markdown(
    "### 📋 Live Option Chain"
)

chain_display = option_df.copy()

chain_display = chain_display[
    [
        "strike",
        "side",
        "ltp",
        "bid",
        "ask",
        "oi",
        "oi_change",
        "volume",
        "iv",
        "delta",
    ]
]

chain_display.columns = [
    "Strike",
    "Side",
    "LTP",
    "Bid",
    "Ask",
    "OI",
    "Chg OI",
    "Volume",
    "IV",
    "Delta",
]

chain_display = chain_display.sort_values(
    [
        "Strike",
        "Side",
    ]
)

st.dataframe(
    chain_display,
    use_container_width=True,
    hide_index=True,
)
```

# ============================================================

# MARKET ANALYSIS

# ============================================================

with tab3:

```
st.markdown(
    "### 📈 Multi-Timeframe Analysis"
)

tf_table = pd.DataFrame(
    [
        {
            "Timeframe": "5 Minute",
            "Trend": tf5["trend"],
            "RSI": tf5["rsi"],
            "EMA 20": tf5["ema20"],
            "EMA 50": tf5["ema50"],
            "ATR": tf5["atr"],
            "ADX": tf5["adx"],
            "VWAP": tf5["vwap"],
            "Momentum %": tf5["momentum"],
        },
        {
            "Timeframe": "30 Minute",
            "Trend": tf30["trend"],
            "RSI": tf30["rsi"],
            "EMA 20": tf30["ema20"],
            "EMA 50": tf30["ema50"],
            "ATR": tf30["atr"],
            "ADX": tf30["adx"],
            "VWAP": tf30["vwap"],
            "Momentum %": tf30["momentum"],
        },
        {
            "Timeframe": "Daily",
            "Trend": tfd["trend"],
            "RSI": tfd["rsi"],
            "EMA 20": tfd["ema20"],
            "EMA 50": tfd["ema50"],
            "ATR": tfd["atr"],
            "ADX": tfd["adx"],
            "VWAP": tfd["vwap"],
            "Momentum %": tfd["momentum"],
        },
    ]
)

st.dataframe(
    tf_table,
    use_container_width=True,
    hide_index=True,
)

st.markdown(
    "### 🧱 OI Structure"
)

o1, o2, o3 = st.columns(3)

with o1:
    st.metric(
        "Support",
        format_price(support),
    )

with o2:
    st.metric(
        "Resistance",
        format_price(resistance),
    )

with o3:
    st.metric(
        "PCR",
        format_num(pcr, 2),
    )

st.markdown(
    "### 🏛 OI Walls"
)

w1, w2 = st.columns(2)

with w1:
    st.metric(
        "Highest CE OI Strike",
        format_price(
            oi_wall_info.get(
                "ce_wall"
            )
        ),
    )

with w2:
    st.metric(
        "Highest PE OI Strike",
        format_price(
            oi_wall_info.get(
                "pe_wall"
            )
        ),
    )
```

# ============================================================

# HOW ENGINE THINKS

# ============================================================

with tab4:

```
st.markdown(
    "### 🧠 Decision Engine"
)

st.markdown(
    """
```

The engine combines several independent checks before allowing
a directional trade.

**1. Multi-timeframe trend**

* 5-minute
* 30-minute
* Daily

**2. Option quality**

* Delta
* IV
* Volume
* Bid/ask spread
* Distance from spot

**3. Options positioning**

* PCR
* OI support
* OI resistance
* CE/PE OI walls

**4. Setup score**

A setup score of **72/100 or higher** is required for a
directional trade.

**5. Directional confirmation**

The selected side must have:

* at least an 8-point score advantage over the opposite side
* matching overall market direction
* acceptable Delta
* acceptable spread
* sufficient volume
* acceptable PoP

**6. Entry trigger**

Even a high-quality setup can remain in
**WAIT FOR TRIGGER** until price confirmation occurs.

**7. NO TRADE**

NO TRADE is intentional when the required conditions are not
simultaneously satisfied.

The engine does not treat a high score alone as proof that a
trade will win.
"""
)

```
if best_ce:
    st.markdown(
        "### CALL Candidate"
    )

    st.write(
        f"Score: {format_num(ce_score,1)}/100"
    )

    st.write(
        "Reasons:"
    )

    for r in best_ce["reasons"]:
        st.write(
            f"• {r}"
        )

if best_pe:
    st.markdown(
        "### PUT Candidate"
    )

    st.write(
        f"Score: {format_num(pe_score,1)}/100"
    )

    st.write(
        "Reasons:"
    )

    for r in best_pe["reasons"]:
        st.write(
            f"• {r}"
        )
```

# ============================================================

# JOURNAL SUMMARY — BACKEND MEASUREMENT

# ============================================================

try:

```
conn = db_connect()

journal = pd.read_sql_query(
    """
    SELECT *
    FROM decisions
    ORDER BY id DESC
    LIMIT 500
    """,
    conn,
)

conn.close()

if not journal.empty:

    st.markdown("---")

    st.markdown(
        "### 📊 Decision Tracking"
    )

    completed = journal[
        journal["outcome"].notna()
    ].copy()

    wins = int(
        (
            completed["outcome"]
            == "WIN"
        ).sum()
    )

    losses = int(
        (
            completed["outcome"]
            == "LOSS"
        ).sum()
    )

    completed_trades = wins + losses

    if completed_trades > 0:
        win_rate = (
            wins
            / completed_trades
        ) * 100
    else:
        win_rate = np.nan

    j1, j2, j3, j4 = st.columns(4)

    with j1:
        st.metric(
            "Logged Decisions",
            len(journal),
        )

    with j2:
        st.metric(
            "Completed T1/SL",
            completed_trades,
        )

    with j3:
        st.metric(
            "Wins",
            wins,
        )

    with j4:
        st.metric(
            "Observed Win Rate",
            (
                f"{win_rate:.1f}%"
                if np.isfinite(win_rate)
                else "Not enough data"
            ),
        )

    st.caption(
        "Observed win rate is based only on this app's "
        "paper-tracked decisions and is not a guarantee "
        "of future performance."
    )
```

except Exception:
pass

# ============================================================

# FOOTER

# ============================================================

st.markdown(
"""

<hr>
<div style="text-align:center;opacity:.6;font-size:12px;">
FO PRO Trader Assistant • Live Upstox REST Data •
Decision support only • No automatic orders
</div>
""",
    unsafe_allow_html=True,
)
