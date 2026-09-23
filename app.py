import gzip
import io
import json
import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

# ============================================================
# FO PRO TRADER ASSISTANT — LIVE UPSTOX VERSION
# UI redesigned to match the reference screenshot
# ============================================================

st.set_page_config(
    page_title="FO PRO Trader Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

IST = ZoneInfo("Asia/Kolkata")

# ============================================================
# GLOBAL SETTINGS
# ============================================================

API_BASE = "https://api.upstox.com"
FNO_MASTER_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
)

_API_REQUEST_LOCK = threading.Lock()
_LAST_API_REQUEST = 0.0
_MIN_API_GAP = 0.50

# ============================================================
# CSS — MATCHES THE SCREENSHOT EXACTLY
# ============================================================

st.markdown(
    """
<style>
/* ========== GLOBAL ========== */
.stApp {
    background: #f0f4f9 !important;
}

.block-container {
    max-width: 1280px !important;
    padding: 0.6rem 1.1rem 2rem 1.1rem !important;
}

h1, h2, h3, h4 {
    letter-spacing: -0.02em;
    color: #0f172a;
}

/* Hide default Streamlit elements that break the design */
#MainMenu, footer, header {visibility: hidden;}
div[data-testid="stToolbar"] {display: none;}

/* ========== SIDEBAR ========== */
[data-testid="stSidebar"] {
    background: #0b1730 !important;
    min-width: 240px !important;
}

[data-testid="stSidebar"] * {
    color: #ffffff !important;
}

[data-testid="stSidebar"] .stButton > button {
    background: #ffffff !important;
    color: #0b1730 !important;
    border: 0 !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
}

[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #ffffff !important;
    color: #111827 !important;
    border-radius: 8px !important;
}

/* Sidebar logo area */
.sidebar-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 18px 16px 12px 16px;
    margin-bottom: 8px;
}

.sidebar-logo-icon {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, #22c55e, #16a34a);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 900;
}

.sidebar-logo-text {
    font-size: 18px;
    font-weight: 800;
    line-height: 1.1;
}

.sidebar-logo-sub {
    font-size: 11px;
    color: #94a3b8 !important;
    font-weight: 500;
}

/* Nav item style */
.nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 11px 16px;
    margin: 2px 10px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    color: #cbd5e1 !important;
    transition: all 0.15s;
}

.nav-item.active {
    background: #1e40af !important;
    color: #ffffff !important;
}

.nav-item:hover {
    background: rgba(255,255,255,0.08);
}

/* ========== TOP HEADER BAR ========== */
.top-bar {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 12px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.top-bar-left {
    display: flex;
    align-items: center;
    gap: 14px;
}

.symbol-pill {
    background: #f1f5f9;
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 700;
    font-size: 14px;
    color: #0f172a;
}

.spot-price {
    font-size: 22px;
    font-weight: 800;
    color: #0f172a;
}

.spot-change {
    font-size: 14px;
    font-weight: 700;
    color: #16a34a;
}

.live-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #64748b;
    font-weight: 600;
}

.live-dot {
    width: 8px;
    height: 8px;
    background: #22c55e;
    border-radius: 50%;
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.4; }
    100% { opacity: 1; }
}

/* ========== MASTER TRADE DECISION ========== */
.master-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 14px;
    box-shadow: 0 2px 8px rgba(15,23,42,0.04);
}

.master-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 800;
    color: #334155;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 14px;
}

.decision-row {
    display: flex;
    align-items: center;
    gap: 18px;
    flex-wrap: wrap;
}

.call-buy-pill {
    background: linear-gradient(135deg, #16a34a, #22c55e);
    color: white;
    font-size: 22px;
    font-weight: 900;
    padding: 12px 28px;
    border-radius: 50px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 14px rgba(22,163,74,0.35);
}

.put-buy-pill {
    background: linear-gradient(135deg, #dc2626, #ef4444);
    color: white;
    font-size: 22px;
    font-weight: 900;
    padding: 12px 28px;
    border-radius: 50px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 14px rgba(220,38,38,0.35);
}

.neutral-pill {
    background: #e2e8f0;
    color: #475569;
    font-size: 22px;
    font-weight: 900;
    padding: 12px 28px;
    border-radius: 50px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
}

.decision-meta {
    display: flex;
    gap: 28px;
    flex-wrap: wrap;
}

.meta-item {
    text-align: left;
}

.meta-label {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
}

.meta-value {
    font-size: 18px;
    font-weight: 800;
    color: #0f172a;
    margin-top: 2px;
}

.trade-ready-box {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    border-radius: 12px;
    padding: 10px 16px;
    margin-left: auto;
}

.trade-ready-title {
    font-size: 12px;
    font-weight: 800;
    color: #059669;
    display: flex;
    align-items: center;
    gap: 6px;
}

.trade-ready-sub {
    font-size: 12px;
    color: #047857;
    margin-top: 2px;
}

/* ========== SECTION CARDS ========== */
.section-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 14px;
    box-shadow: 0 1px 4px rgba(15,23,42,0.03);
    height: 100%;
}

.section-title {
    font-size: 13px;
    font-weight: 800;
    color: #1e293b;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* ========== TRADE PLAN ========== */
.plan-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 12px;
}

.plan-cell {
    background: #f8fafc;
    border-radius: 10px;
    padding: 10px 12px;
    text-align: center;
}

.plan-cell-label {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
}

.plan-cell-value {
    font-size: 16px;
    font-weight: 800;
    color: #0f172a;
    margin-top: 3px;
}

/* ========== CHECKLIST TABLE ========== */
.check-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

.check-table th {
    text-align: left;
    padding: 8px 10px;
    color: #64748b;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    border-bottom: 1px solid #e2e8f0;
}

.check-table td {
    padding: 9px 10px;
    border-bottom: 1px solid #f1f5f9;
    color: #334155;
}

.pass-badge {
    background: #dcfce7;
    color: #166534;
    font-size: 11px;
    font-weight: 800;
    padding: 3px 9px;
    border-radius: 999px;
}

.fail-badge {
    background: #fee2e2;
    color: #991b1b;
    font-size: 11px;
    font-weight: 800;
    padding: 3px 9px;
    border-radius: 999px;
}

/* ========== ENTRY CONDITION ========== */
.entry-box {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 12px;
    padding: 14px 16px;
    font-size: 13px;
    color: #166534;
    line-height: 1.5;
}

.waiting-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #ecfdf5;
    color: #059669;
    font-size: 12px;
    font-weight: 700;
    padding: 6px 12px;
    border-radius: 999px;
    margin-top: 10px;
}

/* ========== MARKET LEVELS ========== */
.level-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
    font-size: 13px;
}

.level-label {
    color: #64748b;
    font-weight: 600;
}

.level-value {
    font-weight: 800;
    color: #0f172a;
}

.res-line { color: #dc2626; font-weight: 800; }
.sup-line { color: #16a34a; font-weight: 800; }

/* ========== WHY THIS SETUP ========== */
.why-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
    font-size: 13px;
    color: #334155;
}

.why-check {
    color: #16a34a;
    font-weight: 900;
    font-size: 15px;
}

/* ========== OPTION CHAIN ========== */
.chain-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}

/* ========== FOOTER NOTE ========== */
.footer-note {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 12px;
    color: #64748b;
    margin-top: 8px;
}

/* ========== MOBILE ========== */
@media (max-width: 768px) {
    .plan-grid { grid-template-columns: repeat(2, 1fr); }
    .decision-row { flex-direction: column; align-items: flex-start; }
    .trade-ready-box { margin-left: 0; margin-top: 10px; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# EXCEPTIONS
# ============================================================

class UpstoxError(Exception):
    pass

class UpstoxRateLimitError(UpstoxError):
    pass

# ============================================================
# BASIC HELPERS
# ============================================================

def safe_float(value, default=np.nan):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if not value:
                return default
        x = float(value)
        if not np.isfinite(x):
            return default
        return x
    except Exception:
        return default

def fmt_price(value):
    x = safe_float(value)
    if np.isnan(x):
        return "N/A"
    return f"₹{x:,.2f}"

def fmt_num(value, decimals=2):
    x = safe_float(value)
    if np.isnan(x):
        return "N/A"
    return f"{x:,.{decimals}f}"

def fmt_pct(value, decimals=1):
    x = safe_float(value)
    if np.isnan(x):
        return "N/A"
    return f"{x:.{decimals}f}%"

def fmt_integer(value):
    x = safe_float(value)
    if np.isnan(x):
        return "N/A"
    return f"{int(round(x)):,}"

def alias_symbol(symbol):
    mapping = {
        "NIFTY50": "NIFTY",
        "NIFTY": "NIFTY",
        "NIFTYBANK": "BANKNIFTY",
        "BANKNIFTY": "BANKNIFTY",
        "NIFTYFIN": "FINNIFTY",
        "FINNIFTY": "FINNIFTY",
        "MIDCAPNIFTY": "MIDCPNIFTY",
        "MIDCPNIFTY": "MIDCPNIFTY",
    }
    return mapping.get(symbol.upper().strip(), symbol.upper().strip())

def now_ist():
    return datetime.now(IST)

def market_is_open():
    now = now_ist()
    if now.weekday() >= 5:
        return False
    start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return start <= now <= end

def render_html(html):
    st.markdown(html, unsafe_allow_html=True)

# ============================================================
# AUTH
# ============================================================

def get_token():
    try:
        token = st.secrets.get("UPSTOX_ACCESS_TOKEN", "")
    except Exception:
        token = ""
    token = str(token).strip()
    if not token:
        raise UpstoxError("UPSTOX_ACCESS_TOKEN is missing from Streamlit Secrets.")
    return token

# ============================================================
# API
# ============================================================

def api_get(path, params=None, timeout=20):
    global _LAST_API_REQUEST
    token = get_token()
    with _API_REQUEST_LOCK:
        elapsed = time.time() - _LAST_API_REQUEST
        if elapsed < _MIN_API_GAP:
            time.sleep(_MIN_API_GAP - elapsed)
        try:
            response = requests.get(
                API_BASE + path,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                params=params or {},
                timeout=timeout,
            )
        except requests.exceptions.Timeout:
            raise UpstoxError("Upstox request timed out. Please try again shortly.")
        except requests.exceptions.RequestException as exc:
            raise UpstoxError(f"Network error while contacting Upstox: {exc}")
        finally:
            _LAST_API_REQUEST = time.time()

    if response.status_code == 429:
        raise UpstoxRateLimitError("Upstox rate limit reached. Please wait before refreshing.")
    if response.status_code != 200:
        body = response.text[:700]
        raise UpstoxError(f"Upstox API {response.status_code}: {body}")
    try:
        return response.json()
    except Exception:
        raise UpstoxError("Upstox returned an invalid JSON response.")

# ============================================================
# INSTRUMENT SEARCH
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def search_underlying(symbol):
    symbol = alias_symbol(symbol)
    attempts = [
        {"query": symbol, "exchanges": "NSE", "segments": "EQ"},
        {"query": symbol, "exchanges": "NSE", "segments": "INDEX"},
    ]
    candidates = []
    for params in attempts:
        try:
            result = api_get("/v2/instruments/search", params=params, timeout=15)
            data = result.get("data", [])
            if isinstance(data, list):
                candidates.extend(data)
        except UpstoxError:
            continue
    if not candidates:
        raise UpstoxError(f"Could not find NSE instrument for {symbol}.")
    exact = [x for x in candidates if str(x.get("trading_symbol", "")).upper() == symbol]
    if exact:
        return exact[0]
    index_candidates = [
        x for x in candidates
        if str(x.get("segment", "")).upper() == "NSE_INDEX"
        or str(x.get("instrument_type", "")).upper() == "INDEX"
    ]
    if index_candidates:
        return index_candidates[0]
    return candidates[0]

# ============================================================
# OPTION CONTRACTS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_contracts(underlying_key):
    result = api_get("/v2/option/contract", params={"instrument_key": underlying_key}, timeout=20)
    data = result.get("data", [])
    if not isinstance(data, list):
        raise UpstoxError("Invalid option contract response.")
    return data

def available_expiries(contracts):
    values = []
    for row in contracts:
        expiry = row.get("expiry")
        if expiry:
            values.append(str(expiry)[:10])
    unique = sorted(set(values))
    today = now_ist().date()
    future = []
    for value in unique:
        try:
            d = date.fromisoformat(value)
            if d >= today:
                future.append(value)
        except Exception:
            continue
    return future

# ============================================================
# OPTION CHAIN
# ============================================================

@st.cache_data(ttl=45, show_spinner=False)
def get_option_chain(underlying_key, expiry):
    result = api_get(
        "/v2/option/chain",
        params={"instrument_key": underlying_key, "expiry_date": expiry},
        timeout=20,
    )
    data = result.get("data", [])
    if not isinstance(data, list):
        raise UpstoxError("Invalid option chain response.")
    return data

def extract_market(option):
    if not isinstance(option, dict):
        return {}
    market = option.get("market_data")
    if isinstance(market, dict):
        return market
    return option

def extract_greeks(option):
    if not isinstance(option, dict):
        return {}
    greeks = option.get("option_greeks")
    if isinstance(greeks, dict):
        return greeks
    greeks = option.get("greeks")
    if isinstance(greeks, dict):
        return greeks
    return {}

def get_field(option, field, default=np.nan):
    market = extract_market(option)
    greeks = extract_greeks(option)
    for source in (option, market, greeks):
        if field in source:
            return source.get(field)
    return default

def extract_pop(option):
    candidates = []
    market = extract_market(option)
    greeks = extract_greeks(option)
    for source in (option, market, greeks):
        for key in ("pop", "probability_of_profit", "probabilityOfProfit", "probability"):
            if key in source:
                candidates.append(source.get(key))
    for value in candidates:
        x = safe_float(value)
        if np.isnan(x):
            continue
        if 0 < x <= 1:
            x *= 100
        if 0 <= x <= 100:
            return x
    return np.nan

def normalize_chain(rows):
    records = []
    if not isinstance(rows, list):
        return pd.DataFrame()
    for row in rows:
        if not isinstance(row, dict):
            continue
        strike = safe_float(row.get("strike_price", row.get("strike")))
        if np.isnan(strike):
            continue
        ce = row.get("call_options") or row.get("ce") or row.get("call") or {}
        pe = row.get("put_options") or row.get("pe") or row.get("put") or {}
        ce_market = extract_market(ce)
        pe_market = extract_market(pe)
        ce_greek = extract_greeks(ce)
        pe_greek = extract_greeks(pe)
        records.append({
            "Strike": strike,
            "CE Key": ce.get("instrument_key", ce.get("instrument_token", "")),
            "CE LTP": safe_float(ce_market.get("ltp", ce.get("ltp"))),
            "CE Bid": safe_float(ce_market.get("bid_price", ce.get("bid_price"))),
            "CE Ask": safe_float(ce_market.get("ask_price", ce.get("ask_price"))),
            "CE OI": safe_float(ce_market.get("oi", ce.get("oi"))),
            "CE Prev OI": safe_float(ce_market.get("prev_oi", ce.get("prev_oi"))),
            "CE Chg OI": safe_float(ce_market.get("change_in_oi", ce_market.get("chg_oi", ce.get("change_in_oi")))),
            "CE Volume": safe_float(ce_market.get("volume", ce.get("volume"))),
            "CE IV": safe_float(ce_greek.get("iv", ce_market.get("iv", ce.get("iv")))),
            "CE Delta": safe_float(ce_greek.get("delta", ce.get("delta"))),
            "CE PoP": extract_pop(ce),
            "PE Key": pe.get("instrument_key", pe.get("instrument_token", "")),
            "PE LTP": safe_float(pe_market.get("ltp", pe.get("ltp"))),
            "PE Bid": safe_float(pe_market.get("bid_price", pe.get("bid_price"))),
            "PE Ask": safe_float(pe_market.get("ask_price", pe.get("ask_price"))),
            "PE OI": safe_float(pe_market.get("oi", pe.get("oi"))),
            "PE Prev OI": safe_float(pe_market.get("prev_oi", pe.get("prev_oi"))),
            "PE Chg OI": safe_float(pe_market.get("change_in_oi", pe_market.get("chg_oi", pe.get("change_in_oi")))),
            "PE Volume": safe_float(pe_market.get("volume", pe.get("volume"))),
            "PE IV": safe_float(pe_greek.get("iv", pe_market.get("iv", pe.get("iv")))),
            "PE Delta": safe_float(pe_greek.get("delta", pe.get("delta"))),
            "PE PoP": extract_pop(pe),
        })
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "Strike" not in df.columns:
        return pd.DataFrame()
    df = df.sort_values("Strike").reset_index(drop=True)
    return df

# ============================================================
# QUOTE
# ============================================================

@st.cache_data(ttl=30, show_spinner=False)
def get_quote(instrument_key):
    result = api_get("/v3/market-quote/quotes", params={"instrument_key": instrument_key}, timeout=15)
    data = result.get("data", {})
    if not isinstance(data, dict):
        return {}
    if instrument_key in data:
        return data[instrument_key]
    if len(data) == 1:
        return next(iter(data.values()))
    return {}

def quote_price(quote):
    if not quote:
        return np.nan
    for key in ("last_price", "last_traded_price", "ltp"):
        x = safe_float(quote.get(key))
        if not np.isnan(x):
            return x
    return np.nan

def quote_previous_close(quote):
    if not quote:
        return np.nan
    ohlc = quote.get("ohlc", {})
    if isinstance(ohlc, dict):
        for key in ("close", "previous_close"):
            x = safe_float(ohlc.get(key))
            if not np.isnan(x):
                return x
    for key in ("prev_close", "previous_close", "close_price"):
        x = safe_float(quote.get(key))
        if not np.isnan(x):
            return x
    return np.nan

# ============================================================
# CANDLES
# ============================================================

def candle_to_df(result):
    data = result.get("data", {})
    candles = []
    if isinstance(data, dict):
        candles = data.get("candles", [])
    if not isinstance(candles, list) or not candles:
        return pd.DataFrame()
    records = []
    for c in candles:
        if not isinstance(c, list) or len(c) < 6:
            continue
        records.append({
            "timestamp": c[0],
            "open": safe_float(c[1]),
            "high": safe_float(c[2]),
            "low": safe_float(c[3]),
            "close": safe_float(c[4]),
            "volume": safe_float(c[5]),
            "oi": safe_float(c[6]) if len(c) > 6 else np.nan,
        })
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp", "close"])
    return df.sort_values("timestamp").reset_index(drop=True)

@st.cache_data(ttl=90, show_spinner=False)
def get_5m_candles(instrument_key):
    end = now_ist().date()
    start = end - timedelta(days=15)
    result = api_get(
        f"/v3/historical-candle/{instrument_key}/5minute/{end.isoformat()}/{start.isoformat()}",
        timeout=20,
    )
    return candle_to_df(result)

@st.cache_data(ttl=600, show_spinner=False)
def get_30m_candles(instrument_key):
    end = now_ist().date()
    start = end - timedelta(days=90)
    result = api_get(
        f"/v3/historical-candle/{instrument_key}/30minute/{end.isoformat()}/{start.isoformat()}",
        timeout=20,
    )
    return candle_to_df(result)

@st.cache_data(ttl=1800, show_spinner=False)
def get_daily_candles(instrument_key):
    end = now_ist().date()
    start = end - timedelta(days=220)
    result = api_get(
        f"/v3/historical-candle/{instrument_key}/day/{end.isoformat()}/{start.isoformat()}",
        timeout=20,
    )
    return candle_to_df(result)

# ============================================================
# TECHNICALS
# ============================================================

def _rsi(series, period=14):
    series = pd.Series(series).astype(float)
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_atr(df, period=14):
    if df.empty:
        return np.nan
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return safe_float(tr.rolling(period).mean().iloc[-1])

def calculate_adx(df, period=14):
    if len(df) < period * 2:
        return np.nan
    high = df["high"]
    low = df["low"]
    close = df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(period).mean() / atr
    denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denominator
    adx = dx.rolling(period).mean()
    return safe_float(adx.iloc[-1])

def calculate_vwap(df):
    if df.empty:
        return np.nan
    work = df.copy()
    typical = (work["high"] + work["low"] + work["close"]) / 3
    volume = work["volume"].fillna(0)
    denominator = volume.cumsum()
    if denominator.iloc[-1] <= 0:
        return np.nan
    return safe_float((typical * volume).cumsum().iloc[-1] / denominator.iloc[-1])

def technicals(df, spot):
    if df.empty or len(df) < 5:
        return {
            "rsi": np.nan, "ema20": np.nan, "ema50": np.nan, "atr": np.nan,
            "trend": "Unknown", "adx": np.nan, "momentum": np.nan,
            "volume_ratio": np.nan, "vwap": np.nan,
        }
    close = df["close"].astype(float)
    ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    rsi_series = _rsi(close)
    rsi = safe_float(rsi_series.iloc[-1]) if len(rsi_series) else np.nan
    atr = calculate_atr(df)
    adx = calculate_adx(df)
    vwap = calculate_vwap(df)
    recent = close.tail(min(5, len(close)))
    momentum = ((recent.iloc[-1] - recent.iloc[0]) / recent.iloc[0] * 100) if len(recent) >= 2 else 0
    volume_ratio = np.nan
    if "volume" in df.columns:
        vol = df["volume"].replace(0, np.nan)
        if len(vol) >= 20:
            avg_volume = vol.rolling(20).mean().iloc[-1]
            if safe_float(avg_volume, 0) > 0:
                volume_ratio = safe_float(vol.iloc[-1]) / avg_volume
    spot = safe_float(spot)
    if not np.isnan(spot) and not np.isnan(ema20) and not np.isnan(ema50):
        if spot > ema20 > ema50:
            trend = "Bullish"
        elif spot < ema20 < ema50:
            trend = "Bearish"
        else:
            trend = "Sideways"
    else:
        trend = "Unknown"
    return {
        "rsi": rsi, "ema20": safe_float(ema20), "ema50": safe_float(ema50),
        "atr": safe_float(atr), "trend": trend, "adx": safe_float(adx),
        "momentum": safe_float(momentum), "volume_ratio": safe_float(volume_ratio),
        "vwap": safe_float(vwap),
    }

def overall_trend(tf5, tf30, daily):
    trends = [tf5.get("trend"), 
