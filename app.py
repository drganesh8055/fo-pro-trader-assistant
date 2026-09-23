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
    trends = [tf5.get("trend"), tf30.get("trend"), daily.get("trend")]
    bullish = trends.count("Bullish")
    bearish = trends.count("Bearish")
    if bullish >= 2 and bearish == 0:
        return "Bullish"
    if bearish >= 2 and bullish == 0:
        return "Bearish"
    if bullish > bearish and bearish == 0:
        return "Bullish"
    if bearish > bullish and bullish == 0:
        return "Bearish"
    return "Mixed"

def timeframe_score(side, tf5, tf30, daily):
    desired = "Bullish" if side == "CE" else "Bearish"
    score = 0
    for tf in (tf5, tf30, daily):
        trend = tf.get("trend")
        if trend == desired:
            score += 10
        elif trend == "Sideways":
            score += 3
        elif trend == "Unknown":
            score += 0
        else:
            score -= 8
    return int(np.clip(score, 0, 30))

# ============================================================
# OPTION / OI
# ============================================================

def nearest_row(chain, spot):
    if chain.empty or "Strike" not in chain.columns:
        return None
    spot = safe_float(spot)
    if np.isnan(spot):
        return chain.iloc[len(chain) // 2]
    idx = (chain["Strike"] - spot).abs().idxmin()
    return chain.loc[idx]

def oi_levels(chain, spot):
    result = {"support": np.nan, "resistance": np.nan, "pcr": np.nan, "put_walls": [], "call_walls": []}
    if chain.empty:
        return result
    spot = safe_float(spot)
    if np.isnan(spot):
        return result
    local = chain[(chain["Strike"] >= spot * 0.90) & (chain["Strike"] <= spot * 1.10)].copy()
    if local.empty:
        local = chain.copy()
    support_candidates = local[local["Strike"] <= spot].dropna(subset=["PE OI"])
    if not support_candidates.empty:
        support_candidates = support_candidates.sort_values(["PE OI", "Strike"], ascending=[False, True])
        result["support"] = safe_float(support_candidates.iloc[0]["Strike"])
    resistance_candidates = local[local["Strike"] >= spot].dropna(subset=["CE OI"])
    if not resistance_candidates.empty:
        resistance_candidates = resistance_candidates.sort_values(["CE OI", "Strike"], ascending=[False, True])
        result["resistance"] = safe_float(resistance_candidates.iloc[0]["Strike"])
    total_pe = safe_float(chain["PE OI"].sum(), 0)
    total_ce = safe_float(chain["CE OI"].sum(), 0)
    if total_ce > 0:
        result["pcr"] = total_pe / total_ce
    put_walls = chain[["Strike", "PE OI"]].dropna().sort_values("PE OI", ascending=False).head(3)
    for _, row in put_walls.iterrows():
        result["put_walls"].append((safe_float(row["Strike"]), safe_float(row["PE OI"])))
    call_walls = chain[["Strike", "CE OI"]].dropna().sort_values("CE OI", ascending=False).head(3)
    for _, row in call_walls.iterrows():
        result["call_walls"].append((safe_float(row["Strike"]), safe_float(row["CE OI"])))
    return result

# ============================================================
# OPTION SCORING
# ============================================================

def score_option(side, row, tf5, tf30, daily, overall_direction, pcr, spot, support, resistance):
    prefix = "CE" if side == "CE" else "PE"
    premium = safe_float(row.get(f"{prefix} LTP"))
    bid = safe_float(row.get(f"{prefix} Bid"))
    ask = safe_float(row.get(f"{prefix} Ask"))
    oi = safe_float(row.get(f"{prefix} OI"), 0)
    chg_oi = safe_float(row.get(f"{prefix} Chg OI"))
    volume = safe_float(row.get(f"{prefix} Volume"), 0)
    iv = safe_float(row.get(f"{prefix} IV"))
    delta = safe_float(row.get(f"{prefix} Delta"))
    pop = safe_float(row.get(f"{prefix} PoP"))
    strike = safe_float(row.get("Strike"))
    alignment = timeframe_score(side, tf5, tf30, daily)
    score = float(alignment)
    desired = "Bullish" if side == "CE" else "Bearish"
    tf5_trend = tf5.get("trend")
    if tf5_trend == desired:
        score += 8
    elif tf5_trend == "Sideways":
        score += 3
    if overall_direction == desired:
        score += 7
    elif overall_direction == "Mixed":
        score += 2
    vwap = safe_float(tf5.get("vwap"))
    vwap_gap_pct = np.nan
    if not np.isnan(vwap) and vwap != 0:
        vwap_gap_pct = (spot - vwap) / vwap * 100
        if side == "CE":
            if spot >= vwap:
                score += 10
        else:
            if spot <= vwap:
                score += 10
    if not np.isnan(pcr):
        if side == "CE":
            if pcr >= 0.90:
                score += 10
            elif pcr >= 0.70:
                score += 6
            elif pcr >= 0.50:
                score += 3
        else:
            if pcr <= 0.80:
                score += 10
            elif pcr <= 1.00:
                score += 6
            elif pcr <= 1.20:
                score += 3
    if not np.isnan(chg_oi):
        if chg_oi > 0:
            score += 5
        elif chg_oi < 0:
            score += 1
    quality = 0
    if oi > 0:
        quality += 5
    if volume >= 1000:
        quality += 5
    spread_pct = np.nan
    if not np.isnan(bid) and not np.isnan(ask) and ask > 0 and bid >= 0:
        mid = (bid + ask) / 2
        if mid > 0:
            spread_pct = (ask - bid) / mid * 100
            if spread_pct <= 1:
                quality += 5
            elif spread_pct <= 2:
                quality += 4
            elif spread_pct <= 3:
                quality += 2
    if not np.isnan(premium) and premium > 0:
        quality += 5
    score += quality
    strike_quality = 0
    distance_pct = np.nan
    if not np.isnan(strike) and spot > 0:
        distance_pct = abs(strike - spot) / spot * 100
        if distance_pct <= 1:
            strike_quality = 10
        elif distance_pct <= 2:
            strike_quality = 8
        elif distance_pct <= 3:
            strike_quality = 5
        elif distance_pct <= 5:
            strike_quality = 2
    score += strike_quality
    if not np.isnan(pop):
        score += min(10, max(0, pop / 10))
    score = int(np.clip(score / 1.10, 0, 100))
    room_pct = np.nan
    if side == "CE":
        if not np.isnan(resistance) and resistance > spot:
            room_pct = (resistance - spot) / spot * 100
    else:
        if not np.isnan(support) and support < spot:
            room_pct = (spot - support) / spot * 100
    return {
        "score": score, "premium": premium, "delta": delta, "iv": iv, "pop": pop,
        "chg_oi": chg_oi, "volume": volume, "oi": oi, "spread_pct": spread_pct,
        "alignment": alignment, "distance_pct": distance_pct, "quality": quality,
        "vwap": vwap, "vwap_gap_pct": vwap_gap_pct, "room_pct": room_pct,
        "strike_quality": strike_quality,
    }

# ============================================================
# TRADE PLAN
# ============================================================

def build_plan(side, strike, option_data, score_data, tf5, support, resistance, atr, risk_profile):
    risk_profiles = {
        "Conservative": (0.72, 1.25, 1.55),
        "Balanced": (0.70, 1.35, 1.75),
        "Aggressive": (0.65, 1.50, 2.00),
    }
    sl_factor, t1_factor, t2_factor = risk_profiles.get(risk_profile, risk_profiles["Balanced"])
    premium = safe_float(score_data.get("premium"))
    ask = safe_float(option_data.get("CE Ask" if side == "CE" else "PE Ask"))
    entry = ask if not np.isnan(ask) and ask > 0 else premium
    if np.isnan(entry) or entry <= 0:
        return None
    sl = entry * sl_factor
    target1 = entry * t1_factor
    target2 = entry * t2_factor
    risk = entry - sl
    rr1 = (target1 - entry) / risk if risk > 0 else np.nan
    rr2 = (target2 - entry) / risk if risk > 0 else np.nan
    spot = safe_float(tf5.get("last_spot", np.nan))
    atr = safe_float(atr)
    if np.isnan(atr) or atr <= 0:
        atr = max(abs(spot) * 0.0015 if not np.isnan(spot) else 1, 0.05)
    trigger_buffer = max(atr * 0.15, abs(spot) * 0.0015 if not np.isnan(spot) else 0.05)
    if side == "CE":
        trigger_level = resistance + trigger_buffer if not np.isnan(resistance) else spot + trigger_buffer
        trigger = f"Break & hold above {fmt_price(trigger_level)}"
        direction_ok = safe_float(tf5.get("momentum"), 0) > 0 and tf5.get("trend") != "Bearish"
    else:
        trigger_level = support - trigger_buffer if not np.isnan(support) else spot - trigger_buffer
        trigger = f"Break & hold below {fmt_price(trigger_level)}"
        direction_ok = safe_float(tf5.get("momentum"), 0) < 0 and tf5.get("trend") != "Bullish"
    score = safe_float(score_data.get("score"), 0)
    alignment = safe_float(score_data.get("alignment"), 0)
    spread_pct = safe_float(score_data.get("spread_pct"))
    delta = safe_float(score_data.get("delta"))
    pop = safe_float(score_data.get("pop"))
    volume = safe_float(score_data.get("volume"), 0)
    oi = safe_float(score_data.get("oi"), 0)
    vwap = safe_float(score_data.get("vwap"))
    fail_reasons = []
    if score < 72:
        fail_reasons.append(f"Score below 72 ({int(score)}/100)")
    if alignment < 2:
        fail_reasons.append("Insufficient timeframe alignment")
    if not direction_ok:
        fail_reasons.append(f"5-minute trend conflicts with {'CALL' if side == 'CE' else 'PUT'}")
    if not np.isnan(spread_pct) and spread_pct > 3:
        fail_reasons.append("Option spread above 3%")
    if not np.isnan(delta):
        if not 0.35 <= abs(delta) <= 0.80:
            fail_reasons.append("Delta outside preferred range")
    if np.isnan(pop):
        fail_reasons.append("PoP unavailable from option data")
    elif pop < 55:
        fail_reasons.append(f"PoP below 55% ({pop:.1f}%)")
    if volume < 1000:
        fail_reasons.append("Option volume below 1,000")
    if oi <= 0:
        fail_reasons.append("Option OI unavailable")
    if not np.isnan(vwap):
        if side == "CE" and spot < vwap:
            fail_reasons.append("Price below VWAP")
        if side == "PE" and spot > vwap:
            fail_reasons.append("Price above VWAP")
    room_pct = safe_float(score_data.get("room_pct"))
    if not np.isnan(room_pct) and room_pct < 0.5:
        fail_reasons.append("OI wall too close")
    trigger_hit = False
    if not np.isnan(spot):
        if side == "CE":
            trigger_hit = spot >= trigger_level
        else:
            trigger_hit = spot <= trigger_level
    volume_ratio = safe_float(tf5.get("volume_ratio"))
    volume_confirmed = not np.isnan(volume_ratio) and volume_ratio >= 1.10
    rsi = safe_float(tf5.get("rsi"))
    candle_confirmed = direction_ok
    if side == "CE" and not np.isnan(rsi):
        candle_confirmed = candle_confirmed and rsi >= 50
    if side == "PE" and not np.isnan(rsi):
        candle_confirmed = candle_confirmed and rsi <= 50
    hard_fail = len(fail_reasons) > 0
    if hard_fail:
        readiness = "NO TRADE"
    elif trigger_hit and candle_confirmed and volume_confirmed:
        readiness = "READY"
    elif not trigger_hit:
        readiness = "WAIT FOR TRIGGER"
    else:
        readiness = "WAIT FOR CONFIRMATION"
    if side == "CE":
        exit_rule = (
            f"Exit if price closes below {fmt_price(vwap)} VWAP or SL is hit"
            if not np.isnan(vwap) else "Exit if price closes below trigger structure or SL is hit"
        )
    else:
        exit_rule = (
            f"Exit if price closes above {fmt_price(vwap)} VWAP or SL is hit"
            if not np.isnan(vwap) else "Exit if price closes above trigger structure or SL is hit"
        )
    return {
        "side": side, "strike": strike, "entry": entry, "sl": sl,
        "target1": target1, "target2": target2, "pop": pop, "delta": delta,
        "iv": safe_float(score_data.get("iv")), "score": score, "rr1": rr1, "rr2": rr2,
        "trigger": trigger, "trigger_level": trigger_level, "trigger_hit": trigger_hit,
        "candle_confirmed": candle_confirmed, "volume_confirmed": volume_confirmed,
        "readiness": readiness, "fail_reasons": fail_reasons, "exit": exit_rule,
        "oi": oi, "chg_oi": safe_float(score_data.get("chg_oi")), "volume": volume,
        "spread_pct": spread_pct, "alignment": alignment, "vwap": vwap, "room_pct": room_pct,
    }

# ============================================================
# F&O MASTER
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_fno_underlyings():
    try:
        response = requests.get(FNO_MASTER_URL, timeout=30)
        if response.status_code != 200:
            raise UpstoxError(f"Could not download NSE F&O master file (HTTP {response.status_code}).")
        raw = gzip.decompress(response.content)
        data = json.loads(raw.decode("utf-8"))
    except UpstoxError:
        raise
    except Exception as exc:
        raise UpstoxError(f"Unable to read NSE F&O master file: {exc}")
    if isinstance(data, dict):
        data = data.get("data", data)
    if not isinstance(data, list):
        raise UpstoxError("Invalid NSE F&O master data.")
    today = now_ist().date()
    result = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        segment = str(item.get("segment", "")).upper()
        instrument_type = str(item.get("instrument_type", "")).upper()
        if segment != "NSE_FO":
            continue
        if instrument_type not in {"CE", "PE", "FUT"}:
            continue
        underlying_type = str(item.get("underlying_type", "")).upper()
        if underlying_type and underlying_type != "EQUITY":
            continue
        symbol = item.get("underlying_symbol") or item.get("trading_symbol")
        underlying_key = item.get("underlying_key")
        expiry = item.get("expiry")
        if not symbol or not underlying_key:
            continue
        if expiry:
            try:
                expiry_date = date.fromisoformat(str(expiry)[:10])
                if expiry_date < today:
                    continue
            except Exception:
                pass
        result[str(symbol).upper()] = {
            "symbol": str(symbol).upper(),
            "underlying_key": underlying_key,
            "expiry": str(expiry)[:10] if expiry else "",
        }
    return list(result.values())

# ============================================================
# FULL MARKET SCANNER
# ============================================================

def scan_full_fno_pop_market(min_pop=75.0):
    universe = get_fno_underlyings()
    results = []
    total = len(universe)
    progress = st.progress(0)
    status = st.empty()
    for i, item in enumerate(universe):
        symbol = item["symbol"]
        underlying_key = item["underlying_key"]
        status.caption(f"Scanning {i + 1}/{total}: {symbol}")
        try:
            contracts = get_contracts(underlying_key)
            expiries = available_expiries(contracts)
            if not expiries:
                continue
            expiry = expiries[0]
            raw_chain = get_option_chain(underlying_key, expiry)
            chain = normalize_chain(raw_chain)
            if chain.empty:
                continue
            valid_strikes = chain["Strike"].dropna()
            if valid_strikes.empty:
                continue
            spot = safe_float(valid_strikes.median())
            candidates = []
            for _, row in chain.iterrows():
                for side in ("CE", "PE"):
                    prefix = side
                    pop = safe_float(row.get(f"{prefix} PoP"))
                    if np.isnan(pop) or pop < min_pop:
                        continue
                    volume = safe_float(row.get(f"{prefix} Volume"), 0)
                    oi = safe_float(row.get(f"{prefix} OI"), 0)
                    if volume < 1000 or oi <= 0:
                        continue
                    premium = safe_float(row.get(f"{prefix} LTP"))
                    if np.isnan(premium) or premium <= 0:
                        continue
                    delta = safe_float(row.get(f"{prefix} Delta"))
                    score = pop * 0.65 + min(volume / 100000, 10) + (min(abs(delta) * 10, 10) if not np.isnan(delta) else 0)
                    candidates.append({
                        "Symbol": symbol,
                        "Side": "CALL BUY" if side == "CE" else "PUT BUY",
                        "Strike": safe_float(row["Strike"]),
                        "Expiry": expiry,
                        "PoP": pop,
                        "Delta": delta,
                        "Premium": premium,
                        "Volume": volume,
                        "OI": oi,
                        "_score": score,
                    })
            if candidates:
                best = sorted(candidates, key=lambda x: (x["PoP"], x["Volume"], -abs(x["Strike"] - spot)), reverse=True)[0]
                results.append(best)
        except (UpstoxError, UpstoxRateLimitError, requests.RequestException):
            pass
        progress.progress(min(1.0, (i + 1) / max(total, 1)))
        time.sleep(0.80)
    progress.empty()
    status.empty()
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    df = df.sort_values(["PoP", "Volume"], ascending=[False, False]).drop_duplicates(subset=["Symbol"]).head(5).reset_index(drop=True)
    display_cols = ["Symbol", "Side", "Strike", "Expiry", "PoP", "Delta", "Premium", "Volume", "OI"]
    return df[display_cols]

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    render_html("""
    <div class="sidebar-logo">
        <div class="sidebar-logo-icon">📈</div>
        <div>
            <div class="sidebar-logo-text">FO PRO</div>
            <div class="sidebar-logo-sub">Trader Assistant</div>
        </div>
    </div>
    """)

    st.markdown("---")

    # Fake nav for visual match
    render_html("""
    <div class="nav-item active">🏠 &nbsp; Dashboard</div>
    <div class="nav-item">📋 &nbsp; Option Chain</div>
    <div class="nav-item">🔍 &nbsp; Scanner</div>
    <div class="nav-item">📊 &nbsp; Market Analysis</div>
    <div class="nav-item">📝 &nbsp; Trade Plan</div>
    <div class="nav-item">⚡ &nbsp; Entry / Exit</div>
    <div class="nav-item">🛡️ &nbsp; Support & Resistance</div>
    <div class="nav-item">✅ &nbsp; Check List</div>
    <div class="nav-item">🧠 &nbsp; How Engine Thinks</div>
    <div class="nav-item">⚙️ &nbsp; Settings</div>
    """)

    st.markdown("---")

    st.markdown("### 🔥 Top 5 F&O PoP Scanner")
    st.caption("Full NSE equity F&O scan • PoP > 75%")

    if st.button("🔎 Scan Full F&O Market", use_container_width=True):
        try:
            with st.spinner("Scanning NSE equity F&O market..."):
                st.session_state["scanner_results"] = scan_full_fno_pop_market(min_pop=75.0)
        except UpstoxRateLimitError as exc:
            st.error(str(exc))
        except UpstoxError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Scanner error: {exc}")

    scanner_results = st.session_state.get("scanner_results")
    if isinstance(scanner_results, pd.DataFrame) and not scanner_results.empty:
        st.dataframe(
            scanner_results,
            use_container_width=True,
            hide_index=True,
            column_config={
                "PoP": st.column_config.NumberColumn("PoP %", format="%.1f%%"),
                "Delta": st.column_config.NumberColumn("Delta", format="%.2f"),
                "Premium": st.column_config.NumberColumn("Premium", format="₹%.2f"),
                "Volume": st.column_config.NumberColumn("Volume", format="%d"),
                "OI": st.column_config.NumberColumn("OI", format="%d"),
            },
        )

    st.markdown("---")
    st.markdown("### 🔍 Analyze Instrument")

    default_symbol = st.session_state.get("selected_symbol", "NIFTY")
    symbol = st.text_input("Instrument", value=default_symbol, placeholder="NIFTY / BANKNIFTY / RELIANCE").upper().strip()
    risk_profile = st.selectbox("Risk Profile", ["Conservative", "Balanced", "Aggressive"], index=1)

    analyze_clicked = st.button("🚀 Analyze", use_container_width=True)
    if analyze_clicked:
        st.session_state["selected_symbol"] = symbol
        st.session_state["run_analysis"] = True

    refresh_clicked = st.button("🔄 Refresh Analysis", use_container_width=True)
    if refresh_clicked:
        st.cache_data.clear()
        st.session_state["run_analysis"] = True

    st.checkbox("Auto refresh every 60 seconds", key="auto_refresh")

    st.caption("Analysis uses live Upstox REST data. No simulated prices.")

    # Bottom status
    render_html("""
    <div style="position:absolute; bottom:20px; left:16px; right:16px;">
        <div style="background:#132040; border-radius:10px; padding:12px; font-size:12px;">
            <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                <span style="width:8px;height:8px;background:#22c55e;border-radius:50%;display:inline-block;"></span>
                <b>Upstox Connected</b>
            </div>
            <div style="color:#94a3b8;">Live Market Data</div>
            <div style="margin-top:8px; font-weight:700; font-size:15px;">NIFTY 50</div>
            <div style="color:#94a3b8; font-size:11px;">FO PRO Trader Assistant<br>Version 1.0</div>
        </div>
    </div>
    """)

# ============================================================
# OPTIONAL AUTO REFRESH
# ============================================================

if st.session_state.get("auto_refresh"):
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=60000, key="fo_pro_auto_refresh")
    except Exception:
        pass

# ============================================================
# MAIN ANALYSIS
# ============================================================

if "run_analysis" not in st.session_state:
    st.session_state["run_analysis"] = True

if not st.session_state["run_analysis"]:
    st.info("Enter an instrument in the sidebar and click Analyze.")
    st.stop()

symbol = st.session_state.get("selected_symbol", "NIFTY")

try:
    with st.spinner(f"Analyzing {symbol} using live Upstox data..."):
        underlying = search_underlying(symbol)
        underlying_key = underlying.get("instrument_key")
        if not underlying_key:
            raise UpstoxError("Upstox did not return an instrument key.")

        contracts = get_contracts(underlying_key)
        expiries = available_expiries(contracts)
        if not expiries:
            raise UpstoxError(f"No active option expiry found for {symbol}.")
        expiry = expiries[0]

        raw_chain = get_option_chain(underlying_key, expiry)
        chain = normalize_chain(raw_chain)
        if chain.empty or "Strike" not in chain.columns:
            raise UpstoxError("Upstox returned an empty or invalid option chain.")

        quote = get_quote(underlying_key)
        spot = quote_price(quote)
        previous_close = quote_previous_close(quote)

        if np.isnan(spot):
            spot = safe_float(underlying.get("last_price"))
        if np.isnan(spot):
            raise UpstoxError("Live underlying price was not available from Upstox.")
        if np.isnan(previous_close):
            previous_close = spot

        change = spot - previous_close
        change_pct = change / previous_close * 100 if previous_close != 0 else np.nan

        try:
            candles_5m = get_5m_candles(underlying_key)
        except Exception:
            candles_5m = pd.DataFrame()
        try:
            candles_30m = get_30m_candles(underlying_key)
        except Exception:
            candles_30m = pd.DataFrame()
        try:
            candles_daily = get_daily_candles(underlying_key)
        except Exception:
            candles_daily = pd.DataFrame()

        tf5 = technicals(candles_5m if not candles_5m.empty else pd.DataFrame(), spot)
        tf30 = technicals(candles_30m if not candles_30m.empty else pd.DataFrame(), spot)
        daily = technicals(candles_daily if not candles_daily.empty else pd.DataFrame(), spot)
        tf5["last_spot"] = spot

        overall_direction = overall_trend(tf5, tf30, daily)
        levels = oi_levels(chain, spot)
        support = safe_float(levels.get("support"))
        resistance = safe_float(levels.get("resistance"))
        pcr = safe_float(levels.get("pcr"))

        atm_row = nearest_row(chain, spot)
        if atm_row is None:
            raise UpstoxError("Could not determine ATM option.")
        atm_strike = safe_float(atm_row["Strike"])

        candidate_chain = chain[
            (chain["Strike"] >= atm_strike - (abs(chain["Strike"].diff().dropna().median()) * 5 if len(chain) > 2 else 50))
            & (chain["Strike"] <= atm_strike + (abs(chain["Strike"].diff().dropna().median()) * 5 if len(chain) > 2 else 50))
        ].copy()
        if candidate_chain.empty:
            candidate_chain = chain.copy()

        ce_best = None
        pe_best = None
        ce_score = -1
        pe_score = -1

        for _, row in candidate_chain.iterrows():
            ce_data = score_option("CE", row, tf5, tf30, daily, overall_direction, pcr, spot, support, resistance)
            pe_data = score_option("PE", row, tf5, tf30, daily, overall_direction, pcr, spot, support, resistance)
            if ce_data["score"] > ce_score:
                ce_score = ce_data["score"]
                ce_best = (row.copy(), ce_data)
            if pe_data["score"] > pe_score:
                pe_score = pe_data["score"]
                pe_best = (row.copy(), pe_data)

        atr = safe_float(tf5.get("atr"))
        ce_plan = None
        pe_plan = None

        if ce_best is not None:
            ce_row, ce_data = ce_best
            ce_plan = build_plan("CE", safe_float(ce_row["Strike"]), ce_row, ce_data, tf5, support, resistance, atr, risk_profile)
        if pe_best is not None:
            pe_row, pe_data = pe_best
            pe_plan = build_plan("PE", safe_float(pe_row["Strike"]), pe_row, pe_data, tf5, support, resistance, atr, risk_profile)

        # Decision logic
        best_plan = None
        if (ce_plan and ce_score >= 72 and ce_score >= pe_score + 8 and overall_direction == "Bullish"
                and ce_plan["readiness"] in {"READY", "WAIT FOR TRIGGER", "WAIT FOR CONFIRMATION"}):
            decision = "CALL BUY" if ce_plan["readiness"] == "READY" else ce_plan["readiness"]
            best_plan = ce_plan
        elif (pe_plan and pe_score >= 72 and pe_score >= ce_score + 8 and overall_direction == "Bearish"
              and pe_plan["readiness"] in {"READY", "WAIT FOR TRIGGER", "WAIT FOR CONFIRMATION"}):
            decision = "PUT BUY" if pe_plan["readiness"] == "READY" else pe_plan["readiness"]
            best_plan = pe_plan
        else:
            decision = "NO TRADE"
            if ce_plan and pe_plan:
                best_plan = ce_plan if ce_score >= pe_score else pe_plan
            else:
                best_plan = ce_plan or pe_plan

        if best_plan:
            best_score = safe_float(best_plan.get("score"), 0)
            align = safe_float(best_plan.get("alignment"), 0)
            confidence = best_score * 0.70 + (align / 3.0) * 20
            if overall_direction in {"Bullish", "Bearish"}:
                confidence += 5
            if decision == "NO TRADE":
                confidence = min(confidence, best_score)
            confidence = int(np.clip(confidence, 0, 100))
        else:
            confidence = 0

        # ====================================================
        # TOP BAR
        # ====================================================
        change_color = "#16a34a" if change >= 0 else "#dc2626"
        change_sign = "+" if change >= 0 else ""
        live_text = "Live Data" if market_is_open() else "Market Closed"
        now_str = now_ist().strftime("%b %d, %Y  %I:%M %p")

        render_html(f"""
        <div class="top-bar">
            <div class="top-bar-left">
                <div class="symbol-pill">{symbol} ▾</div>
                <div class="spot-price">{fmt_price(spot)}</div>
                <div class="spot-change" style="color:{change_color}">{change_sign}{fmt_num(change, 2)} ({change_sign}{fmt_pct(change_pct)})</div>
            </div>
            <div class="live-badge">
                <div class="live-dot"></div>
                {live_text} &nbsp;•&nbsp; {now_str}
            </div>
        </div>
        """)

        # ====================================================
        # MASTER TRADE DECISION
        # ====================================================
        if decision == "CALL BUY":
            pill = f'<div class="call-buy-pill">↗ CALL BUY</div>'
            ready_title = "TRADE READY"
            ready_sub = "Buy only after entry trigger is confirmed."
        elif decision == "PUT BUY":
            pill = f'<div class="put-buy-pill">↘ PUT BUY</div>'
            ready_title = "TRADE READY"
            ready_sub = "Sell only after entry trigger is confirmed."
        else:
            pill = f'<div class="neutral-pill">{decision}</div>'
            ready_title = "NO TRADE"
            ready_sub = "Conditions not aligned for a valid setup."

        setup_score = int(best_plan["score"]) if best_plan else 0
        trend_text = overall_direction.upper() if overall_direction else "MIXED"

        render_html(f"""
        <div class="master-card">
            <div class="master-title">🎯 MASTER TRADE DECISION</div>
            <div class="decision-row">
                {pill}
                <div class="decision-meta">
                    <div class="meta-item">
                        <div class="meta-label">Setup Score</div>
                        <div class="meta-value">{setup_score}/100</div>
                    </div>
                    <div class="meta-item">
                        <div class="meta-label">Confidence</div>
                        <div class="meta-value">{confidence}/100</div>
                    </div>
                    <div class="meta-item">
                        <div class="meta-label">Market Trend</div>
                        <div class="meta-value" style="color:#16a34a">{trend_text}</div>
                    </div>
                </div>
                <div class="trade-ready-box">
                    <div class="trade-ready-title">✓ {ready_title}</div>
                    <div class="trade-ready-sub">{ready_sub}</div>
                </div>
            </div>
            <div style="margin-top:10px; font-size:13px; color:#64748b;">
                {"Bullish setup • Confirmation required" if decision.startswith("CALL") else "Bearish setup • Confirmation required" if decision.startswith("PUT") else "No clear directional edge"}
            </div>
        </div>
        """)

        # ====================================================
        # TWO COLUMN LAYOUT: TRADE PLAN + CHECKLIST
        # ====================================================
        col1, col2 = st.columns([1.15, 1])

        with col1:
            # TRADE PLAN
            if best_plan:
                side_label = "CALL BUY" if best_plan["side"] == "CE" else "PUT BUY"
                strike_txt = fmt_num(best_plan["strike"], 0)
                render_html(f"""
                <div class="section-card">
                    <div class="section-title">＋ TRADE PLAN</div>
                    <div style="display:flex; align-items:center; gap:10px; margin-bottom:14px;">
                        <b style="font-size:15px;">{symbol} {strike_txt} CE</b>
                        <span style="background:#dcfce7; color:#166534; font-size:11px; font-weight:800; padding:3px 10px; border-radius:999px;">{side_label} (Selected)</span>
                    </div>
                    <div class="plan-grid">
                        <div class="plan-cell">
                            <div class="plan-cell-label">Entry</div>
                            <div class="plan-cell-value">{fmt_price(best_plan["entry"])}</div>
                        </div>
                        <div class="plan-cell">
                            <div class="plan-cell-label">Stop Loss</div>
                            <div class="plan-cell-value">{fmt_price(best_plan["sl"])}</div>
                        </div>
                        <div class="plan-cell">
                            <div class="plan-cell-label">Target 1</div>
                            <div class="plan-cell-value">{fmt_price(best_plan["target1"])}</div>
                        </div>
                        <div class="plan-cell">
                            <div class="plan-cell-label">Target 2</div>
                            <div class="plan-cell-value">{fmt_price(best_plan["target2"])}</div>
                        </div>
                    </div>
                    <div class="plan-grid">
                        <div class="plan-cell">
                            <div class="plan-cell-label">PoP</div>
                            <div class="plan-cell-value">{fmt_pct(best_plan["pop"])}</div>
                        </div>
                        <div class="plan-cell">
                            <div class="plan-cell-label">Delta</div>
                            <div class="plan-cell-value">{fmt_num(best_plan["delta"], 2)}</div>
                        </div>
                        <div class="plan-cell">
                            <div class="plan-cell-label">IV</div>
                            <div class="plan-cell-value">{fmt_pct(best_plan["iv"])}</div>
                        </div>
                        <div class="plan-cell">
                            <div class="plan-cell-label">R:R (T2)</div>
                            <div class="plan-cell-value">1 : {fmt_num(best_plan["rr2"], 2)}</div>
                        </div>
                    </div>
                </div>
                """)
            else:
                render_html('<div class="section-card"><div class="section-title">＋ TRADE PLAN</div><p style="color:#64748b;">No valid plan available.</p></div>')

            # ENTRY CONDITION
            if best_plan:
                trigger_txt = best_plan["trigger"]
                dist = abs(safe_float(best_plan.get("trigger_level"), 0) - spot) if not np.isnan(spot) else 0
                render_html(f"""
                <div class="section-card">
                    <div class="section-title">⚡ ENTRY CONDITION</div>
                    <div class="entry-box">
                        Enter ONLY when {symbol} breaks and sustains above {fmt_num(best_plan.get("trigger_level"), 0)}
                        with 5-minute bullish confirmation + preferably above-average volume.
                    </div>
                    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-top:12px;">
                        <div class="plan-cell">
                            <div class="plan-cell-label">Current Spot</div>
                            <div class="plan-cell-value">{fmt_price(spot)}</div>
                        </div>
                        <div class="plan-cell">
                            <div class="plan-cell-label">Trigger</div>
                            <div class="plan-cell-value">{fmt_num(best_plan.get("trigger_level"), 0)}</div>
                        </div>
                        <div class="plan-cell">
                            <div class="plan-cell-label">Distance</div>
                            <div class="plan-cell-value">{fmt_num(dist, 1)}</div>
                        </div>
                    </div>
                    <div class="waiting-badge">⏳ Waiting for entry trigger...</div>
                </div>
                """)

        with col2:
            # TRADE CHECKLIST
            if best_plan:
                checks = [
                    ("Market Direction", overall_direction == ("Bullish" if best_plan["side"] == "CE" else "Bearish"), overall_direction),
                    ("Multi-Timeframe", best_plan.get("alignment", 0) >= 2, f"{int(best_plan.get('alignment',0))}/3 aligned"),
                    ("OI Structure", True, f"Support at {fmt_num(support,0)}" if not np.isnan(support) else "—"),
                    ("VWAP", (best_plan["side"] == "CE" and spot >= safe_float(tf5.get("vwap"), 0)) or
                             (best_plan["side"] == "PE" and spot <= safe_float(tf5.get("vwap"), 999999)),
                     f"Price above {fmt_num(tf5.get('vwap'),0)}" if not np.isnan(safe_float(tf5.get("vwap"))) else "—"),
                    ("Momentum", best_plan.get("candle_confirmed", False), "Bullish" if best_plan["side"] == "CE" else "Bearish"),
                    ("Option Quality", best_plan.get("volume", 0) >= 1000, "Liquid/healthy"),
                ]
                rows_html = ""
                for i, (name, ok, obs) in enumerate(checks, 1):
                    badge = '<span class="pass-badge">PASS</span>' if ok else '<span class="fail-badge">FAIL</span>'
                    rows_html += f"""
                    <tr>
                        <td>{i}</td>
                        <td>{name}</td>
                        <td>{badge}</td>
                        <td>{obs}</td>
                    </tr>
                    """
                pass_count = sum(1 for _, ok, _ in checks if ok)
                render_html(f"""
                <div class="section-card">
                    <div class="section-title" style="justify-content:space-between;">
                        <span>✅ TRADE CHECKLIST</span>
                        <span style="background:#dcfce7; color:#166534; font-size:12px; font-weight:800; padding:4px 10px; border-radius:999px;">{pass_count}/6 PASS</span>
                    </div>
                    <table class="check-table">
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Check</th>
                                <th>Status</th>
                                <th>Observation</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_html}
                        </tbody>
                    </table>
                </div>
                """)

            # MARKET LEVELS + BIAS
            render_html(f"""
            <div class="section-card">
                <div class="section-title">📍 MARKET LEVELS</div>
                <div class="level-row">
                    <span class="level-label">Resistance</span>
                    <span class="res-line">{fmt_num(resistance, 0)}</span>
                </div>
                <div class="level-row">
                    <span class="level-label">Current Price</span>
                    <span class="level-value">{fmt_num(spot, 0)}</span>
                </div>
                <div class="level-row">
                    <span class="level-label">Support</span>
                    <span class="sup-line">{fmt_num(support, 0)}</span>
                </div>
            </div>
            """)

            render_html(f"""
            <div class="section-card">
                <div class="section-title">📊 MARKET BIAS</div>
                <div style="font-size:22px; font-weight:900; color:#16a34a; margin-bottom:10px;">↗ {overall_direction.upper()}</div>
                <div class="level-row"><span class="level-label">PCR</span><span class="level-value">{fmt_num(pcr, 2)}</span></div>
                <div class="level-row"><span class="level-label">VWAP</span><span class="level-value">{fmt_num(tf5.get("vwap"), 0)}</span></div>
                <div class="level-row"><span class="level-label">ATR</span><span class="level-value">{fmt_num(tf5.get("atr"), 0)}</span></div>
            </div>
            """)

        # ====================================================
        # WHY THIS SETUP + KEY CHART PLACEHOLDER
        # ====================================================
        col3, col4 = st.columns([1, 1.2])

        with col3:
            why_items = [
                "Bullish short-term trend" if overall_direction == "Bullish" else "Mixed short-term trend",
                "Multiple timeframes aligned" if best_plan and best_plan.get("alignment", 0) >= 2 else "Timeframes not fully aligned",
                "Price structure supports CALL direction" if best_plan and best_plan["side"] == "CE" else "Price structure supports PUT direction",
                "VWAP supports bullish bias" if overall_direction == "Bullish" else "VWAP neutral / bearish",
                "Option liquidity and Greeks acceptable",
                "Entry trigger still required" if best_plan and not best_plan.get("trigger_hit") else "Entry trigger confirmed",
            ]
            why_html = "".join([f'<div class="why-item"><span class="why-check">✓</span> {item}</div>' for item in why_items])
            render_html(f"""
            <div class="section-card">
                <div class="section-title">💡 WHY THIS SETUP?</div>
                {why_html}
            </div>
            """)

        with col4:
            render_html(f"""
            <div class="section-card">
                <div class="section-title">📈 KEY CHART ({symbol} 5m)</div>
                <div style="height:180px; background:#f8fafc; border-radius:10px; display:flex; align-items:center; justify-content:center; color:#94a3b8; font-size:13px;">
                    Candlestick chart (5-min) — connect real chart library for live view
                </div>
            </div>
            """)

        # ====================================================
        # LIVE OPTION CHAIN
        # ====================================================
        st.markdown("")
        render_html("""
        <div class="section-card">
            <div class="chain-header">
                <div class="section-title" style="margin:0;">📋 Live Option Chain (Around ATM)</div>
                <div style="font-size:12px; color:#64748b;">Strike Range: ±3 Strikes ▾</div>
            </div>
        """)

        strikes = sorted(chain["Strike"].dropna().unique(), key=lambda x: abs(x - spot))[:7]
        display_chain = chain[chain["Strike"].isin(strikes)].sort_values("Strike")

        if not display_chain.empty:
            table = display_chain[[
                "Strike", "CE LTP", "CE OI", "CE Chg OI",
                "PE LTP", "PE OI", "PE Chg OI"
            ]].copy()

            # Format for display
            def fmt_oi(x):
                x = safe_float(x)
                if np.isnan(x):
                    return "—"
                if abs(x) >= 100000:
                    return f"{x/100000:.1f}L"
                return f"{int(x):,}"

            table["CE OI"] = table["CE OI"].apply(fmt_oi)
            table["PE OI"] = table["PE OI"].apply(fmt_oi)
            table["CE Chg OI"] = table["CE Chg OI"].apply(lambda x: f"{safe_float(x):+.1f}" if not np.isnan(safe_float(x)) else "—")
            table["PE Chg OI"] = table["PE Chg OI"].apply(lambda x: f"{safe_float(x):+.1f}" if not np.isnan(safe_float(x)) else "—")
            table["CE LTP"] = table["CE LTP"].apply(lambda x: f"{safe_float(x):.2f}" if not np.isnan(safe_float(x)) else "—")
            table["PE LTP"] = table["PE LTP"].apply(lambda x: f"{safe_float(x):.2f}" if not np.isnan(safe_float(x)) else "—")
            table["Strike"] = table["Strike"].apply(lambda x: f"{int(x)}")

            # Highlight ATM row
            st.dataframe(
                table.rename(columns={
                    "Strike": "Strike",
                    "CE LTP": "CE LTP",
                    "CE OI": "CE OI (L)",
                    "CE Chg OI": "ΔOI",
                    "PE LTP": "PE LTP",
                    "PE OI": "PE OI (L)",
                    "PE Chg OI": "ΔOI",
                }),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No option chain data available.")

        render_html("""
            <div class="footer-note">
                ℹ️ This is a decision support tool. Always confirm with your own analysis and risk management before placing a trade.
            </div>
        </div>
        """)

except UpstoxRateLimitError as exc:
    st.error(f"⏳ {exc}")
    st.info("The app has stopped making additional requests. Wait briefly and use Refresh Analysis.")
except UpstoxError as exc:
    st.error(f"⚠️ {exc}")
except Exception as exc:
    st.error("⚠️ Unexpected application error")
    st.caption(f"Technical detail: {type(exc).__name__}: {exc}")
