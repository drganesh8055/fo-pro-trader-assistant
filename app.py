import gzip
import json
import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

# Optional auto refresh
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None


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
# GLOBAL SETTINGS
# ============================================================

IST = ZoneInfo("Asia/Kolkata")

FNO_MASTER_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
)

API_BASE = "https://api.upstox.com"

_API_REQUEST_LOCK = threading.Lock()
_LAST_API_REQUEST = 0.0
_MIN_API_GAP = 0.50


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>

html, body, [class*="css"] {
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI",
                 Roboto, Helvetica, Arial, sans-serif;
}

.stApp {
    background: #f4f7fb;
}

.block-container {
    max-width: 1180px;
    margin: 0 auto;
    padding: 0.65rem 0.85rem 2rem;
}

/* Remove excessive Streamlit spacing */
div[data-testid="stVerticalBlock"] {
    gap: 0.55rem;
}

div[data-testid="stHorizontalBlock"] {
    gap: 0.65rem;
}

/* Header */
.fo-header {
    background: linear-gradient(135deg, #071a33 0%, #0d2a4f 100%);
    color: white;
    border-radius: 18px;
    padding: 18px 21px;
    margin-bottom: 12px;
    box-shadow: 0 8px 24px rgba(7, 26, 51, 0.14);
}

.fo-header-title {
    font-size: 25px;
    font-weight: 800;
    letter-spacing: -0.4px;
    margin: 0;
}

.fo-header-sub {
    font-size: 12px;
    opacity: 0.78;
    margin-top: 4px;
}

/* Status */
.status-live {
    background: linear-gradient(135deg, #e8f8ef, #dff5e8);
    border: 1px solid #b7e5c8;
    color: #126b39;
    border-radius: 14px;
    padding: 12px 15px;
    margin-bottom: 10px;
}

.status-closed {
    background: linear-gradient(135deg, #f2f4f7, #e9edf2);
    border: 1px solid #d6dce4;
    color: #536273;
    border-radius: 14px;
    padding: 12px 15px;
    margin-bottom: 10px;
}

.status-error {
    background: #fff0f0;
    border: 1px solid #f1c1c1;
    color: #a52222;
    border-radius: 14px;
    padding: 12px 15px;
    margin-bottom: 10px;
}

.status-title {
    font-size: 11px;
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 0.6px;
}

.status-value {
    font-size: 17px;
    font-weight: 800;
    margin-top: 2px;
}

/* Cards */
.card {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 16px;
    padding: 15px;
    box-shadow: 0 3px 12px rgba(15, 31, 51, 0.045);
    margin-bottom: 10px;
}

.card-title {
    color: #14253d;
    font-size: 14px;
    font-weight: 800;
    margin-bottom: 8px;
}

.card-subtitle {
    color: #728096;
    font-size: 11px;
}

/* Decision */
.decision-card {
    background: white;
    border: 1px solid #e3e8ee;
    border-radius: 18px;
    padding: 18px;
    box-shadow: 0 5px 18px rgba(15, 31, 51, 0.06);
    margin-bottom: 11px;
}

.decision-no {
    border-left: 6px solid #718096;
}

.decision-call {
    border-left: 6px solid #149447;
}

.decision-put {
    border-left: 6px solid #d23b3b;
}

.decision-wait {
    border-left: 6px solid #d79b18;
}

.decision-label {
    font-size: 10px;
    color: #738095;
    text-transform: uppercase;
    font-weight: 800;
    letter-spacing: 0.7px;
}

.decision-value {
    font-size: 29px;
    line-height: 1.05;
    font-weight: 900;
    color: #17283f;
    margin-top: 3px;
}

.decision-call .decision-value {
    color: #128441;
}

.decision-put .decision-value {
    color: #c53232;
}

.decision-wait .decision-value {
    color: #a8790d;
}

.decision-sub {
    font-size: 12px;
    color: #6d7989;
    margin-top: 7px;
}

.decision-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 13px;
}

.stat-pill {
    background: #f5f7fa;
    border: 1px solid #e4e9ef;
    border-radius: 10px;
    padding: 7px 10px;
    min-width: 88px;
}

.stat-pill span {
    display: block;
    font-size: 9px;
    color: #7b8798;
    text-transform: uppercase;
    font-weight: 700;
}

.stat-pill b {
    display: block;
    font-size: 13px;
    color: #18283d;
    margin-top: 2px;
}

/* Metric */
.metric-card {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 14px;
    padding: 12px;
    min-height: 75px;
}

.metric-label {
    font-size: 9px;
    color: #7a8798;
    text-transform: uppercase;
    font-weight: 800;
    letter-spacing: 0.4px;
}

.metric-value {
    font-size: 18px;
    color: #17283f;
    font-weight: 850;
    margin-top: 4px;
}

/* Trade plan */
.plan-card {
    background: white;
    border: 1px solid #e3e8ef;
    border-radius: 16px;
    padding: 15px;
    margin-bottom: 10px;
}

.plan-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
}

.plan-title {
    font-size: 16px;
    font-weight: 850;
    color: #17283f;
}

.badge {
    display: inline-block;
    border-radius: 999px;
    padding: 5px 9px;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.35px;
}

.badge-green {
    background: #e7f7ed;
    color: #16723d;
}

.badge-red {
    background: #fceaea;
    color: #a82e2e;
}

.badge-yellow {
    background: #fff5d9;
    color: #8b6707;
}

.badge-gray {
    background: #eef1f5;
    color: #586779;
}

.plan-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 7px;
}

.plan-item {
    background: #f7f9fb;
    border-radius: 9px;
    padding: 8px;
}

.plan-item span {
    display: block;
    color: #7b8798;
    font-size: 9px;
    font-weight: 700;
}

.plan-item b {
    display: block;
    color: #17283f;
    font-size: 13px;
    margin-top: 3px;
}

.plan-warning {
    margin-top: 10px;
    background: #fff7e3;
    border: 1px solid #f0dfad;
    color: #7c6016;
    border-radius: 9px;
    padding: 8px 10px;
    font-size: 10px;
}

.plan-reference {
    margin-top: 10px;
    background: #f2f5f8;
    border: 1px solid #e1e6ec;
    color: #637083;
    border-radius: 9px;
    padding: 8px 10px;
    font-size: 10px;
}

/* Checklist */
.check-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 7px 0;
    border-bottom: 1px solid #eef1f4;
}

.check-item:last-child {
    border-bottom: 0;
}

.check-icon {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: 900;
    flex-shrink: 0;
}

.check-ok {
    background: #e5f6eb;
    color: #13743b;
}

.check-bad {
    background: #fbe8e8;
    color: #b22c2c;
}

.check-text {
    font-size: 11px;
    color: #556274;
}

/* OI */
.oi-map {
    background: #f8fafc;
    border-radius: 12px;
    padding: 12px;
}

.oi-row {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 6px 0;
    font-size: 11px;
    border-bottom: 1px solid #edf1f5;
}

.oi-row:last-child {
    border-bottom: 0;
}

.oi-support {
    color: #16733d;
    font-weight: 800;
}

.oi-resistance {
    color: #b32e2e;
    font-weight: 800;
}

/* Section title */
.section-title {
    font-size: 16px;
    font-weight: 850;
    color: #14253d;
    margin: 12px 0 7px;
}

/* Small explanatory text */
.helper {
    color: #7a8798;
    font-size: 10px;
    line-height: 1.45;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #f8fafc;
}

section[data-testid="stSidebar"] .block-container {
    padding: 1rem 0.85rem;
}

/* Buttons */
.stButton > button {
    border-radius: 10px;
    font-weight: 750;
    min-height: 38px;
}

/* Dataframe */
div[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
}

/* Inputs */
.stTextInput input,
.stSelectbox div[data-baseweb="select"],
.stNumberInput input {
    border-radius: 9px;
}

/* Mobile */
@media (max-width: 760px) {

    .block-container {
        padding: 0.45rem 0.55rem 1.5rem;
    }

    .fo-header {
        border-radius: 13px;
        padding: 14px;
    }

    .fo-header-title {
        font-size: 20px;
    }

    .decision-card {
        padding: 14px;
        border-radius: 14px;
    }

    .decision-value {
        font-size: 24px;
    }

    .plan-grid {
        grid-template-columns: repeat(2, 1fr);
    }

    .stat-pill {
        min-width: 75px;
    }
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HTML RENDER HELPER
# ============================================================

def render_html(html: str):
    """
    Central HTML renderer.

    Important:
    All custom HTML in this app must go through this function.
    This prevents raw HTML from appearing as text.
    """
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# ERRORS
# ============================================================

class UpstoxError(Exception):
    pass


class UpstoxRateLimitError(UpstoxError):
    pass


# ============================================================
# BASIC HELPERS
# ============================================================

def now_ist():
    return datetime.now(IST)


def market_is_open():
    now = now_ist()

    if now.weekday() >= 5:
        return False

    start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    end = now.replace(hour=15, minute=30, second=0, microsecond=0)

    return start <= now <= end


def safe_float(value, default=np.nan):
    try:
        if value is None:
            return default

        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()

        result = float(value)

        if not np.isfinite(result):
            return default

        return result
    except Exception:
        return default


def fmt_price(value):
    value = safe_float(value)

    if np.isnan(value):
        return "—"

    return f"₹{value:,.2f}"


def fmt_num(value, decimals=0):
    value = safe_float(value)

    if np.isnan(value):
        return "—"

    if decimals == 0:
        return f"{value:,.0f}"

    return f"{value:,.{decimals}f}"


def fmt_pct(value, decimals=1):
    value = safe_float(value)

    if np.isnan(value):
        return "—"

    return f"{value:.{decimals}f}%"


def alias_symbol(symbol):
    aliases = {
        "NIFTY50": "NIFTY",
        "NIFTY": "NIFTY",
        "NIFTYBANK": "BANKNIFTY",
        "BANKNIFTY": "BANKNIFTY",
        "NIFTYFIN": "FINNIFTY",
        "FINNIFTY": "FINNIFTY",
        "MIDCAPNIFTY": "MIDCPNIFTY",
        "MIDCPNIFTY": "MIDCPNIFTY",
    }

    value = str(symbol or "").strip().upper()

    return aliases.get(value, value)


# ============================================================
# UPSTOX AUTH
# ============================================================

def get_token():
    try:
        token = st.secrets["UPSTOX_ACCESS_TOKEN"]
    except Exception:
        raise UpstoxError(
            "UPSTOX_ACCESS_TOKEN is missing from Streamlit Secrets."
        )

    token = str(token).strip()

    if not token:
        raise UpstoxError(
            "UPSTOX_ACCESS_TOKEN is empty in Streamlit Secrets."
        )

    return token


def get_headers():
    return {
        "Authorization": f"Bearer {get_token()}",
        "Accept": "application/json",
        "User-Agent": "FO-Pro-Trader-Assistant",
    }


# ============================================================
# API REQUEST
# ============================================================

def api_get(path, params=None, timeout=20):
    global _LAST_API_REQUEST

    url = path if path.startswith("http") else API_BASE + path

    with _API_REQUEST_LOCK:

        elapsed = time.monotonic() - _LAST_API_REQUEST

        if elapsed < _MIN_API_GAP:
            time.sleep(_MIN_API_GAP - elapsed)

        try:
            response = requests.get(
                url,
                headers=get_headers(),
                params=params or {},
                timeout=timeout,
            )
        except requests.exceptions.Timeout:
            raise UpstoxError(
                "Network timeout while contacting Upstox. "
                "Please try again."
            )
        except requests.exceptions.RequestException as exc:
            raise UpstoxError(
                f"Network error while contacting Upstox: {exc}"
            )

        _LAST_API_REQUEST = time.monotonic()

    if response.status_code == 429:
        raise UpstoxRateLimitError(
            "Upstox rate limit reached. Please wait about 30 seconds "
            "before refreshing."
        )

    if response.status_code != 200:
        body = response.text[:500]

        raise UpstoxError(
            f"Upstox API {response.status_code}: {body}"
        )

    try:
        return response.json()
    except Exception:
        raise UpstoxError(
            "Upstox returned an invalid JSON response."
        )


# ============================================================
# INSTRUMENT SEARCH
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def search_underlying(symbol):
    symbol = alias_symbol(symbol)

    if not symbol:
        raise UpstoxError("Please enter an instrument.")

    results = []

    # First try equity/index segments
    for segment in ["EQ", "INDEX"]:
        try:
            response = api_get(
                "/v2/instruments/search",
                params={
                    "query": symbol,
                    "exchanges": "NSE",
                    "segments": segment,
                },
            )

            data = response.get("data", [])

            if isinstance(data, list):
                results.extend(data)

        except UpstoxError:
            continue

    if not results:
        raise UpstoxError(
            f"Could not find NSE instrument for {symbol}."
        )

    # Exact trading symbol first
    exact = [
        item
        for item in results
        if str(item.get("trading_symbol", "")).upper() == symbol.upper()
    ]

    if exact:
        return exact[0]

    # Exact name
    exact_name = [
        item
        for item in results
        if str(item.get("name", "")).upper() == symbol.upper()
    ]

    if exact_name:
        return exact_name[0]

    # Prefer index
    indexes = [
        item
        for item in results
        if str(item.get("instrument_type", "")).upper() == "INDEX"
    ]

    if indexes:
        return indexes[0]

    return results[0]


# ============================================================
# OPTION CONTRACTS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_contracts(underlying_key):
    response = api_get(
        "/v2/option/contract",
        params={
            "instrument_key": underlying_key,
        },
    )

    data = response.get("data", [])

    if not isinstance(data, list):
        raise UpstoxError("Invalid option contract response.")

    return data


def available_expiries(contracts):
    expiries = set()

    for item in contracts:

        expiry = (
            item.get("expiry")
            or item.get("expiry_date")
            or item.get("expiration_date")
        )

        if expiry:
            expiries.add(str(expiry)[:10])

    today = now_ist().date()

    valid = []

    for expiry in expiries:
        try:
            d = date.fromisoformat(expiry)

            if d >= today:
                valid.append(expiry)

        except Exception:
            continue

    return sorted(valid)


# ============================================================
# OPTION CHAIN
# ============================================================

@st.cache_data(ttl=45, show_spinner=False)
def get_option_chain(underlying_key, expiry):
    response = api_get(
        "/v2/option/chain",
        params={
            "instrument_key": underlying_key,
            "expiry_date": expiry,
        },
    )

    data = response.get("data", [])

    if not isinstance(data, list):
        raise UpstoxError("Invalid option-chain response.")

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


def option_value(option, *keys):
    market = extract_market(option)
    greeks = extract_greeks(option)

    for source in [market, greeks, option]:

        if not isinstance(source, dict):
            continue

        for key in keys:

            if key in source:
                value = source.get(key)

                if value is not None:
                    return value

    return None


# ============================================================
# NORMALIZE OPTION CHAIN
# ============================================================

def normalize_chain(rows):

    columns = [
        "Strike",

        "CE Key",
        "CE LTP",
        "CE Bid",
        "CE Ask",
        "CE OI",
        "CE Chg OI",
        "CE Volume",
        "CE IV",
        "CE Delta",
        "CE PoP",

        "PE Key",
        "PE LTP",
        "PE Bid",
        "PE Ask",
        "PE OI",
        "PE Chg OI",
        "PE Volume",
        "PE IV",
        "PE Delta",
        "PE PoP",
    ]

    records = []

    if not isinstance(rows, list):
        return pd.DataFrame(columns=columns)

    for item in rows:

        if not isinstance(item, dict):
            continue

        strike = safe_float(
            item.get("strike_price")
            or item.get("strike")
        )

        if np.isnan(strike):
            continue

        call = (
            item.get("call_options")
            or item.get("ce")
            or item.get("call")
            or {}
        )

        put = (
            item.get("put_options")
            or item.get("pe")
            or item.get("put")
            or {}
        )

        ce_market = extract_market(call)
        ce_greeks = extract_greeks(call)

        pe_market = extract_market(put)
        pe_greeks = extract_greeks(put)

        def get_from(source1, source2, *names):

            for source in [source1, source2]:

                if not isinstance(source, dict):
                    continue

                for name in names:
                    if name in source and source[name] is not None:
                        return source[name]

            return np.nan

        record = {
            "Strike": strike,

            "CE Key": call.get("instrument_key"),
            "CE LTP": safe_float(
                get_from(ce_market, call, "ltp", "last_price")
            ),
            "CE Bid": safe_float(
                get_from(ce_market, call, "bid_price", "bid")
            ),
            "CE Ask": safe_float(
                get_from(ce_market, call, "ask_price", "ask")
            ),
            "CE OI": safe_float(
                get_from(ce_market, call, "oi", "open_interest")
            ),
            "CE Chg OI": safe_float(
                get_from(
                    ce_market,
                    call,
                    "change_in_oi",
                    "chg_oi",
                    "oi_change",
                )
            ),
            "CE Volume": safe_float(
                get_from(ce_market, call, "volume")
            ),
            "CE IV": safe_float(
                get_from(ce_greeks, ce_market, "iv", "implied_volatility")
            ),
            "CE Delta": safe_float(
                get_from(ce_greeks, call, "delta")
            ),
            "CE PoP": safe_float(
                get_from(
                    ce_greeks,
                    ce_market,
                    "pop",
                    "probability_of_profit",
                    "probability_profit",
                )
            ),

            "PE Key": put.get("instrument_key"),
            "PE LTP": safe_float(
                get_from(pe_market, put, "ltp", "last_price")
            ),
            "PE Bid": safe_float(
                get_from(pe_market, put, "bid_price", "bid")
            ),
            "PE Ask": safe_float(
                get_from(pe_market, put, "ask_price", "ask")
            ),
            "PE OI": safe_float(
                get_from(pe_market, put, "oi", "open_interest")
            ),
            "PE Chg OI": safe_float(
                get_from(
                    pe_market,
                    put,
                    "change_in_oi",
                    "chg_oi",
                    "oi_change",
                )
            ),
            "PE Volume": safe_float(
                get_from(pe_market, put, "volume")
            ),
            "PE IV": safe_float(
                get_from(pe_greeks, pe_market, "iv", "implied_volatility")
            ),
            "PE Delta": safe_float(
                get_from(pe_greeks, put, "delta")
            ),
            "PE PoP": safe_float(
                get_from(
                    pe_greeks,
                    pe_market,
                    "pop",
                    "probability_of_profit",
                    "probability_profit",
                )
            ),
        }

        records.append(record)

    if not records:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(records)

    for column in columns:
        if column not in df.columns:
            df[column] = np.nan

    return df[columns].sort_values("Strike").reset_index(drop=True)


# ============================================================
# QUOTE
# ============================================================

@st.cache_data(ttl=30, show_spinner=False)
def get_quote(instrument_key):

    response = api_get(
        "/v3/market-quote/quotes",
        params={
            "instrument_key": instrument_key,
        },
    )

    data = response.get("data", {})

    if not isinstance(data, dict):
        return {}

    # Upstox usually keys the response by instrument key
    if instrument_key in data:
        return data[instrument_key]

    if data:
        return next(iter(data.values()))

    return {}


def parse_quote(quote):

    if not isinstance(quote, dict):
        return np.nan, np.nan, np.nan, np.nan

    last = safe_float(
        quote.get("last_price")
        or quote.get("ltp")
    )

    prev_close = safe_float(
        quote.get("prev_close_price")
        or quote.get("previous_close")
        or quote.get("cp")
    )

    net_change = safe_float(
        quote.get("net_change")
        or quote.get("change")
    )

    change_pct = safe_float(
        quote.get("percent_change")
        or quote.get("change_percent")
    )

    ohlc = quote.get("ohlc")

    if isinstance(ohlc, dict):

        if np.isnan(prev_close):
            prev_close = safe_float(
                ohlc.get("close")
            )

        if np.isnan(last):
            last = safe_float(
                ohlc.get("close")
            )

    if np.isnan(net_change) and not np.isnan(last) and not np.isnan(prev_close):
        net_change = last - prev_close

    if (
        np.isnan(change_pct)
        and not np.isnan(last)
        and not np.isnan(prev_close)
        and prev_close != 0
    ):
        change_pct = ((last - prev_close) / prev_close) * 100

    return last, prev_close, net_change, change_pct


# ============================================================
# CANDLES
# ============================================================

def candles_to_df(response):

    data = response.get("data", {})

    if isinstance(data, dict):
        candles = data.get("candles", [])
    elif isinstance(data, list):
        candles = data
    else:
        candles = []

    if not candles:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "oi",
            ]
        )

    records = []

    for candle in candles:

        if not isinstance(candle, (list, tuple)):
            continue

        if len(candle) < 6:
            continue

        records.append(
            {
                "timestamp": candle[0],
                "open": safe_float(candle[1]),
                "high": safe_float(candle[2]),
                "low": safe_float(candle[3]),
                "close": safe_float(candle[4]),
                "volume": safe_float(candle[5]),
                "oi": safe_float(candle[6]) if len(candle) > 6 else np.nan,
            }
        )

    df = pd.DataFrame(records)

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    df = df.dropna(subset=["timestamp", "close"])

    return df.sort_values("timestamp").reset_index(drop=True)


@st.cache_data(ttl=90, show_spinner=False)
def get_intraday_candles(instrument_key):

    response = api_get(
        f"/v3/historical-candle/intraday/{instrument_key}/minutes/5",
    )

    return candles_to_df(response)


@st.cache_data(ttl=600, show_spinner=False)
def get_30m_candles(instrument_key):

    end_date = now_ist().date()
    start_date = end_date - timedelta(days=90)

    response = api_get(
        f"/v3/historical-candle/{instrument_key}/30minute/"
        f"{end_date}/{start_date}",
    )

    return candles_to_df(response)


@st.cache_data(ttl=1800, show_spinner=False)
def get_daily_candles(instrument_key):

    end_date = now_ist().date()
    start_date = end_date - timedelta(days=220)

    response = api_get(
        f"/v3/historical-candle/{instrument_key}/day/"
        f"{end_date}/{start_date}",
    )

    return candles_to_df(response)


# ============================================================
# TECHNICALS
# ============================================================

def _rsi(series, period=14):

    series = pd.Series(series, dtype="float64")

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_adx(df, period=14):

    if df is None or len(df) < period + 2:
        return np.nan

    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where(
        (up_move > down_move) & (up_move > 0),
        up_move,
        0,
    )

    minus_dm = np.where(
        (down_move > up_move) & (down_move > 0),
        down_move,
        0,
    )

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1,
    ).max(axis=1)

    atr = tr.rolling(period).mean()

    plus_di = (
        pd.Series(plus_dm, index=df.index)
        .rolling(period)
        .mean()
        / atr
    ) * 100

    minus_di = (
        pd.Series(minus_dm, index=df.index)
        .rolling(period)
        .mean()
        / atr
    ) * 100

    dx = (
        (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(0, np.nan)
    ) * 100

    adx = dx.rolling(period).mean()

    return safe_float(adx.iloc[-1])


def technicals(df, spot):

    result = {
        "rsi": np.nan,
        "ema20": np.nan,
        "ema50": np.nan,
        "atr": np.nan,
        "trend": "Unknown",
        "adx": np.nan,
        "momentum": 0.0,
        "volume_ratio": np.nan,
        "vwap": np.nan,
    }

    if df is None or df.empty or len(df) < 20:
        return result

    close = df["close"].astype(float)

    result["rsi"] = safe_float(
        _rsi(close).iloc[-1]
    )

    result["ema20"] = safe_float(
        close.ewm(span=20, adjust=False).mean().iloc[-1]
    )

    result["ema50"] = safe_float(
        close.ewm(span=50, adjust=False).mean().iloc[-1]
    )

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["close"].shift()).abs()
    tr3 = (df["low"] - df["close"].shift()).abs()

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1,
    ).max(axis=1)

    result["atr"] = safe_float(
        tr.rolling(14).mean().iloc[-1]
    )

    spot_value = safe_float(spot)

    if not np.isnan(spot_value):
        if (
            not np.isnan(result["ema20"])
            and not np.isnan(result["ema50"])
        ):
            if spot_value > result["ema20"] > result["ema50"]:
                result["trend"] = "Bullish"
            elif spot_value < result["ema20"] < result["ema50"]:
                result["trend"] = "Bearish"
            else:
                result["trend"] = "Sideways"

    if len(close) >= 6:
        previous = safe_float(close.iloc[-6])

        if previous != 0 and not np.isnan(previous):
            result["momentum"] = (
                (safe_float(close.iloc[-1]) - previous)
                / previous
            ) * 100

    if "volume" in df.columns:

        volume = df["volume"].astype(float)

        recent_volume = safe_float(volume.iloc[-1])

        average_volume = safe_float(
            volume.tail(20).mean()
        )

        if (
            not np.isnan(recent_volume)
            and not np.isnan(average_volume)
            and average_volume > 0
        ):
            result["volume_ratio"] = (
                recent_volume / average_volume
            )

    typical_price = (
        df["high"] + df["low"] + df["close"]
    ) / 3

    if "volume" in df.columns:

        volume = df["volume"].fillna(0)

        cumulative_volume = volume.cumsum()

        cumulative_value = (
            typical_price * volume
        ).cumsum()

        if safe_float(cumulative_volume.iloc[-1]) > 0:
            result["vwap"] = safe_float(
                cumulative_value.iloc[-1]
                / cumulative_volume.iloc[-1]
            )

    result["adx"] = calculate_adx(df)

    return result


def overall_trend(tf5, tf30, daily):

    trends = [
        tf5.get("trend"),
        tf30.get("trend"),
        daily.get("trend"),
    ]

    bullish = trends.count("Bullish")
    bearish = trends.count("Bearish")

    if bullish >= 2 and bearish == 0:
        return "Bullish"

    if bearish >= 2 and bullish == 0:
        return "Bearish"

    return "Mixed"


def timeframe_score(side, tf5, tf30, daily):

    desired = "Bullish" if side == "CE" else "Bearish"

    score = 0

    for tf in [tf5, tf30, daily]:

        trend = tf.get("trend")

        if trend == desired:
            score += 10

        elif trend == "Sideways":
            score += 3

        elif trend in {"Bullish", "Bearish"}:
            score -= 8

    return int(np.clip(score, 0, 30))


# ============================================================
# OI LEVELS
# ============================================================

def oi_levels(chain, spot):

    spot = safe_float(spot)

    result = {
        "support": np.nan,
        "resistance": np.nan,
        "major_support": np.nan,
        "major_resistance": np.nan,
        "pcr": np.nan,
        "support_walls": [],
        "resistance_walls": [],
    }

    if chain is None or chain.empty:
        return result

    if np.isnan(spot):
        return result

    local = chain[
        (chain["Strike"] >= spot * 0.90)
        & (chain["Strike"] <= spot * 1.10)
    ].copy()

    if local.empty:
        local = chain.copy()

    puts_below = local[
        local["Strike"] <= spot
    ].copy()

    calls_above = local[
        local["Strike"] >= spot
    ].copy()

    if not puts_below.empty:

        puts_below = puts_below.dropna(
            subset=["PE OI"]
        )

        if not puts_below.empty:

            row = puts_below.sort_values(
                "PE OI",
                ascending=False,
            ).iloc[0]

            result["major_support"] = safe_float(
                row["Strike"]
            )

    if not calls_above.empty:

        calls_above = calls_above.dropna(
            subset=["CE OI"]
        )

        if not calls_above.empty:

            row = calls_above.sort_values(
                "CE OI",
                ascending=False,
            ).iloc[0]

            result["major_resistance"] = safe_float(
                row["Strike"]
            )

    if (
        not np.isnan(result["major_support"])
    ):
        result["support"] = result["major_support"]
    else:
        lower = local[
            local["Strike"] <= spot
        ]

        if not lower.empty:
            result["support"] = safe_float(
                lower["Strike"].max()
            )

    if (
        not np.isnan(result["major_resistance"])
    ):
        result["resistance"] = result["major_resistance"]
    else:
        upper = local[
            local["Strike"] >= spot
        ]

        if not upper.empty:
            result["resistance"] = safe_float(
                upper["Strike"].min()
            )

    ce_oi = safe_float(
        chain["CE OI"].fillna(0).sum(),
        0,
    )

    pe_oi = safe_float(
        chain["PE OI"].fillna(0).sum(),
        0,
    )

    if ce_oi > 0:
        result["pcr"] = pe_oi / ce_oi

    # OI walls
    for _, row in local.sort_values(
        "PE OI",
        ascending=False,
    ).head(5).iterrows():

        strike = safe_float(row["Strike"])
        oi = safe_float(row["PE OI"])

        if (
            not np.isnan(strike)
            and not np.isnan(oi)
            and oi > 0
        ):
            result["support_walls"].append(
                (strike, oi)
            )

    for _, row in local.sort_values(
        "CE OI",
        ascending=False,
    ).head(5).iterrows():

        strike = safe_float(row["Strike"])
        oi = safe_float(row["CE OI"])

        if (
            not np.isnan(strike)
            and not np.isnan(oi)
            and oi > 0
        ):
            result["resistance_walls"].append(
                (strike, oi)
            )

    return result


# ============================================================
# NEAREST OPTION
# ============================================================

def nearest_row(chain, spot):

    if chain is None or chain.empty:
        return None

    spot = safe_float(spot)

    if np.isnan(spot):
        return None

    index = (
        chain["Strike"] - spot
    ).abs().idxmin()

    return chain.loc[index]


# ============================================================
# OPTION SCORE
# ============================================================

def score_option(
    chain_row,
    side,
    spot,
    tf5,
    tf30,
    daily,
    pcr,
    support,
    resistance,
):
    prefix = "CE" if side == "CE" else "PE"

    score = 0.0

    premium = safe_float(
        chain_row.get(f"{prefix} Ask")
    )

    if np.isnan(premium) or premium <= 0:
        premium = safe_float(
            chain_row.get(f"{prefix} LTP")
        )

    bid = safe_float(
        chain_row.get(f"{prefix} Bid")
    )

    ask = safe_float(
        chain_row.get(f"{prefix} Ask")
    )

    oi = safe_float(
        chain_row.get(f"{prefix} OI"),
        0,
    )

    chg_oi = safe_float(
        chain_row.get(f"{prefix} Chg OI")
    )

    volume = safe_float(
        chain_row.get(f"{prefix} Volume"),
        0,
    )

    iv = safe_float(
        chain_row.get(f"{prefix} IV")
    )

    delta = safe_float(
        chain_row.get(f"{prefix} Delta")
    )

    pop = safe_float(
        chain_row.get(f"{prefix} PoP")
    )

    strike = safe_float(
        chain_row.get("Strike")
    )

    # --------------------------------------------------------
    # Timeframe alignment — 30 points
    # --------------------------------------------------------

    alignment = timeframe_score(
        side,
        tf5,
        tf30,
        daily,
    )

    score += alignment

    # --------------------------------------------------------
    # Momentum / trend strength — 15
    # --------------------------------------------------------

    desired = "Bullish" if side == "CE" else "Bearish"

    momentum = (
        tf5.get("momentum", 0)
        + tf30.get("momentum", 0)
    ) / 2

    momentum_score = 0

    if (
        desired == "Bullish"
        and momentum > 0.15
    ):
        momentum_score = 15
    elif (
        desired == "Bearish"
        and momentum < -0.15
    ):
        momentum_score = 15
    elif abs(momentum) < 0.15:
        momentum_score = 7
    else:
        momentum_score = 0

    score += momentum_score

    # --------------------------------------------------------
    # VWAP — 10
    # --------------------------------------------------------

    vwap = safe_float(
        tf5.get("vwap")
    )

    vwap_gap_pct = np.nan

    if (
        not np.isnan(vwap)
        and vwap != 0
        and not np.isnan(spot)
    ):
        vwap_gap_pct = (
            (spot - vwap)
            / vwap
        ) * 100

        if (
            side == "CE"
            and spot > vwap
        ):
            score += 10

        elif (
            side == "PE"
            and spot < vwap
        ):
            score += 10

        elif abs(vwap_gap_pct) < 0.20:
            score += 5

    # --------------------------------------------------------
    # PCR — 10
    # --------------------------------------------------------

    if not np.isnan(pcr):

        if side == "CE":

            if 0.85 <= pcr <= 1.30:
                score += 10
            elif pcr > 1.30:
                score += 6
            elif pcr < 0.70:
                score += 2
            else:
                score += 5

        else:

            if 0.70 <= pcr <= 1.15:
                score += 10
            elif pcr < 0.70:
                score += 7
            elif pcr > 1.40:
                score += 3
            else:
                score += 5

    # --------------------------------------------------------
    # Option OI change — 5
    # --------------------------------------------------------

    if not np.isnan(chg_oi):

        if chg_oi > 0:
            score += 5
        elif chg_oi > -100:
            score += 2

    # --------------------------------------------------------
    # Option quality / liquidity — 20
    # --------------------------------------------------------

    quality = 0

    if volume >= 10000:
        quality += 8
    elif volume >= 5000:
        quality += 6
    elif volume >= 1000:
        quality += 4
    elif volume > 0:
        quality += 1

    if oi >= 10000:
        quality += 6
    elif oi >= 5000:
        quality += 4
    elif oi >= 1000:
        quality += 2

    spread_pct = np.nan

    if (
        not np.isnan(bid)
        and not np.isnan(ask)
        and ask > 0
    ):
        spread_pct = (
            (ask - bid)
            / ask
        ) * 100

        if spread_pct <= 1:
            quality += 6
        elif spread_pct <= 2:
            quality += 4
        elif spread_pct <= 3:
            quality += 2

    score += min(20, quality)

    # --------------------------------------------------------
    # Strike placement + room — 10
    # --------------------------------------------------------

    distance_pct = np.nan
    room_pct = np.nan
    strike_quality = 0

    if (
        not np.isnan(strike)
        and not np.isnan(spot)
        and spot != 0
    ):
        distance_pct = (
            abs(strike - spot)
            / spot
        ) * 100

        if distance_pct <= 1:
            strike_quality = 10
        elif distance_pct <= 2:
            strike_quality = 8
        elif distance_pct <= 3:
            strike_quality = 5
        elif distance_pct <= 5:
            strike_quality = 2

        if side == "CE" and not np.isnan(resistance):
            room_pct = (
                (resistance - spot)
                / spot
            ) * 100

        elif side == "PE" and not np.isnan(support):
            room_pct = (
                (spot - support)
                / spot
            ) * 100

    score += strike_quality

    # --------------------------------------------------------
    # PoP — up to 10
    # --------------------------------------------------------

    if not np.isnan(pop):

        if pop >= 75:
            score += 10
        elif pop >= 70:
            score += 8
        elif pop >= 65:
            score += 6
        elif pop >= 60:
            score += 4
        elif pop >= 55:
            score += 2

    final_score = int(
        np.clip(
            (score / 110) * 100,
            0,
            100,
        )
    )

    return {
        "score": final_score,
        "premium": premium,
        "delta": delta,
        "iv": iv,
        "pop": pop,
        "chg_oi": chg_oi,
        "volume": volume,
        "oi": oi,
        "spread_pct": spread_pct,
        "alignment": alignment,
        "distance_pct": distance_pct,
        "quality": quality,
        "vwap": vwap,
        "vwap_gap_pct": vwap_gap_pct,
        "room_pct": room_pct,
        "strike_quality": strike_quality,
    }


# ============================================================
# TRADE PLAN
# ============================================================

def build_plan(
    chain_row,
    side,
    score_data,
    spot,
    support,
    resistance,
    tf5,
    risk_profile,
):
    if chain_row is None:
        return None

    risk_profiles = {
        "Conservative": (0.72, 1.25, 1.55),
        "Balanced": (0.70, 1.35, 1.75),
        "Aggressive": (0.65, 1.50, 2.00),
    }

    sl_factor, t1_factor, t2_factor = risk_profiles.get(
        risk_profile,
        risk_profiles["Balanced"],
    )

    score = safe_float(
        score_data.get("score")
    )

    premium = safe_float(
        score_data.get("premium")
    )

    if np.isnan(premium) or premium <= 0:
        return None

    delta = safe_float(
        score_data.get("delta")
    )

    iv = safe_float(
        score_data.get("iv")
    )

    pop = safe_float(
        score_data.get("pop")
    )

    spread_pct = safe_float(
        score_data.get("spread_pct")
    )

    volume = safe_float(
        score_data.get("volume"),
        0,
    )

    oi = safe_float(
        score_data.get("oi"),
        0,
    )

    alignment = safe_float(
        score_data.get("alignment"),
        0,
    )

    vwap = safe_float(
        score_data.get("vwap")
    )

    room_pct = safe_float(
        score_data.get("room_pct")
    )

    strike = safe_float(
        chain_row.get("Strike")
    )

    chg_oi = safe_float(
        score_data.get("chg_oi")
    )

    atr = safe_float(
        tf5.get("atr")
    )

    # --------------------------------------------------------
    # Risk calculations
    # --------------------------------------------------------

    sl = premium * sl_factor
    target1 = premium * t1_factor
    target2 = premium * t2_factor

    risk = premium - sl

    reward1 = target1 - premium
    reward2 = target2 - premium

    rr1 = (
        reward1 / risk
        if risk > 0
        else np.nan
    )

    rr2 = (
        reward2 / risk
        if risk > 0
        else np.nan
    )

    # --------------------------------------------------------
    # Trigger
    # --------------------------------------------------------

    atr_buffer = (
        atr * 0.15
        if not np.isnan(atr)
        else spot * 0.0015
    )

    if side == "CE":

        if not np.isnan(resistance):
            trigger_level = resistance + atr_buffer
        else:
            trigger_level = spot + atr_buffer

        trigger = (
            f"Break & hold above "
            f"{fmt_price(trigger_level)}"
        )

    else:

        if not np.isnan(support):
            trigger_level = support - atr_buffer
        else:
            trigger_level = spot - atr_buffer

        trigger = (
            f"Break & hold below "
            f"{fmt_price(trigger_level)}"
        )

    trigger_hit = False

    if not np.isnan(spot):

        if side == "CE":
            trigger_hit = spot >= trigger_level
        else:
            trigger_hit = spot <= trigger_level

    # --------------------------------------------------------
    # Candle confirmation
    # --------------------------------------------------------

    short_term_trend = tf5.get("trend")

    momentum = safe_float(
        tf5.get("momentum"),
        0,
    )

    rsi = safe_float(
        tf5.get("rsi")
    )

    volume_ratio = safe_float(
        tf5.get("volume_ratio")
    )

    candle_confirmed = False

    if side == "CE":

        candle_confirmed = (
            short_term_trend == "Bullish"
            and momentum > 0
            and (
                np.isnan(rsi)
                or rsi >= 50
            )
        )

    else:

        candle_confirmed = (
            short_term_trend == "Bearish"
            and momentum < 0
            and (
                np.isnan(rsi)
                or rsi <= 50
            )
        )

    volume_confirmed = (
        np.isnan(volume_ratio)
        or volume_ratio >= 1.10
    )

    # --------------------------------------------------------
    # Hard fails
    # --------------------------------------------------------

    fail_reasons = []

    if score < 72:
        fail_reasons.append(
            "Score below 72"
        )

    if alignment < 2:
        fail_reasons.append(
            "Insufficient timeframe alignment"
        )

    if side == "CE" and short_term_trend == "Bearish":
        fail_reasons.append(
            "5-minute trend conflicts with CALL"
        )

    if side == "PE" and short_term_trend == "Bullish":
        fail_reasons.append(
            "5-minute trend conflicts with PUT"
        )

    if (
        not np.isnan(spread_pct)
        and spread_pct > 3
    ):
        fail_reasons.append(
            "Option spread above 3%"
        )

    if (
        not np.isnan(delta)
        and not (
            0.35 <= abs(delta) <= 0.80
        )
    ):
        fail_reasons.append(
            "Delta outside preferred range"
        )

    if (
        np.isnan(pop)
        or pop < 55
    ):
        fail_reasons.append(
            "PoP below 55%"
        )

    if volume < 1000:
        fail_reasons.append(
            "Option volume too low"
        )

    if oi <= 0:
        fail_reasons.append(
            "Option OI unavailable"
        )

    # VWAP conflict
    if not np.isnan(vwap):

        if (
            side == "CE"
            and spot < vwap
        ):
            fail_reasons.append(
                "Price below VWAP"
            )

        if (
            side == "PE"
            and spot > vwap
        ):
            fail_reasons.append(
                "Price above VWAP"
            )

    # OI wall too close
    if (
        not np.isnan(room_pct)
        and room_pct < 0.5
    ):
        fail_reasons.append(
            "OI wall too close"
        )

    # --------------------------------------------------------
    # Readiness
    # --------------------------------------------------------

    if fail_reasons:
        readiness = "NO TRADE"

    elif not trigger_hit:
        readiness = "WAIT FOR TRIGGER"

    elif not candle_confirmed:
        readiness = "WAIT FOR CONFIRMATION"

    elif not volume_confirmed:
        readiness = "WAIT FOR CONFIRMATION"

    else:
        readiness = "READY"

    # --------------------------------------------------------
    # Exit rule
    # --------------------------------------------------------

    if side == "CE":
        exit_rule = (
            f"Exit if price closes below "
            f"{fmt_price(vwap)} VWAP or SL is hit"
            if not np.isnan(vwap)
            else "Exit if momentum reverses or SL is hit"
        )
    else:
        exit_rule = (
            f"Exit if price closes above "
            f"{fmt_price(vwap)} VWAP or SL is hit"
            if not np.isnan(vwap)
            else "Exit if momentum reverses or SL is hit"
        )

    return {
        "side": side,
        "strike": strike,
        "entry": premium,
        "sl": sl,
        "target1": target1,
        "target2": target2,
        "pop": pop,
        "delta": delta,
        "iv": iv,
        "score": score,
        "rr1": rr1,
        "rr2": rr2,
        "trigger": trigger,
        "trigger_level": trigger_level,
        "trigger_hit": trigger_hit,
        "candle_confirmed": candle_confirmed,
        "volume_confirmed": volume_confirmed,
        "readiness": readiness,
        "fail_reasons": fail_reasons,
        "exit": exit_rule,
        "oi": oi,
        "chg_oi": chg_oi,
        "volume": volume,
        "spread_pct": spread_pct,
        "alignment": alignment,
        "vwap": vwap,
        "room_pct": room_pct,
    }


# ============================================================
# FULL F&O MASTER
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_fno_underlyings():

    try:
        response = requests.get(
            FNO_MASTER_URL,
            timeout=30,
            headers={
                "User-Agent": "FO-Pro-Trader-Assistant"
            },
        )
    except requests.exceptions.RequestException as exc:
        raise UpstoxError(
            f"Unable to download NSE F&O instrument list: {exc}"
        )

    if response.status_code != 200:
        raise UpstoxError(
            f"NSE F&O instrument list returned "
            f"HTTP {response.status_code}."
        )

    try:
        raw = gzip.decompress(
            response.content
        )

        data = json.loads(
            raw.decode("utf-8")
        )

    except Exception as exc:
        raise UpstoxError(
            f"Unable to read NSE F&O instrument list: {exc}"
        )

    if not isinstance(data, list):
        raise UpstoxError(
            "Invalid NSE F&O instrument list."
        )

    today = now_ist().date()

    underlyings = {}

    for item in data:

        if not isinstance(item, dict):
            continue

        segment = str(
            item.get("segment", "")
        ).upper()

        if segment != "NSE_FO":
            continue

        instrument_type = str(
            item.get("instrument_type", "")
        ).upper()

        if instrument_type not in {
            "CE",
            "PE",
            "FUT",
        }:
            continue

        underlying_type = str(
            item.get("underlying_type", "")
        ).upper()

        if underlying_type and underlying_type != "EQUITY":
            continue

        underlying_key = (
            item.get("underlying_key")
            or item.get("underlying_instrument_key")
        )

        symbol = (
            item.get("underlying_symbol")
            or item.get("underlying_trading_symbol")
            or item.get("trading_symbol")
        )

        expiry = item.get("expiry")

        if not underlying_key or not symbol or not expiry:
            continue

        try:
            expiry_date = date.fromisoformat(
                str(expiry)[:10]
            )
        except Exception:
            continue

        if expiry_date < today:
            continue

        key = str(underlying_key)

        underlyings[key] = {
            "underlying_key": key,
            "symbol": str(symbol).upper(),
            "expiry": str(expiry)[:10],
        }

    return list(underlyings.values())


# ============================================================
# SCANNER
# ============================================================

def scan_full_fno_pop_market(
    min_pop=75.0,
    max_stocks=None,
):

    universe = get_fno_underlyings()

    if max_stocks:
        universe = universe[:max_stocks]

    results = []

    progress = st.progress(
        0,
        text="Preparing F&O scanner...",
    )

    total = len(universe)

    for index, item in enumerate(universe):

        symbol = item["symbol"]
        underlying_key = item["underlying_key"]

        try:

            progress.progress(
                min(
                    int(
                        ((index + 1) / max(total, 1))
                        * 100
                    ),
                    100,
                ),
                text=(
                    f"Scanning {symbol} "
                    f"({index + 1}/{total})"
                ),
            )

            contracts = get_contracts(
                underlying_key
            )

            expiries = available_expiries(
                contracts
            )

            if not expiries:
                continue

            expiry = expiries[0]

            raw_chain = get_option_chain(
                underlying_key,
                expiry,
            )

            chain = normalize_chain(
                raw_chain
            )

            if chain.empty:
                continue

            spot = safe_float(
                chain["Strike"].median()
            )

            # Better spot from quote
            try:
                quote = get_quote(
                    underlying_key
                )

                quote_spot, _, _, _ = parse_quote(
                    quote
                )

                if not np.isnan(quote_spot):
                    spot = quote_spot

            except Exception:
                pass

            if np.isnan(spot):
                continue

            best = None

            for _, row in chain.iterrows():

                for side in ["CE", "PE"]:

                    prefix = side

                    pop = safe_float(
                        row.get(f"{prefix} PoP")
                    )

                    if (
                        np.isnan(pop)
                        or pop < min_pop
                    ):
                        continue

                    premium = safe_float(
                        row.get(f"{prefix} Ask")
                    )

                    if (
                        np.isnan(premium)
                        or premium <= 0
                    ):
                        premium = safe_float(
                            row.get(f"{prefix} LTP")
                        )

                    if (
                        np.isnan(premium)
                        or premium <= 0
                    ):
                        continue

                    volume = safe_float(
                        row.get(f"{prefix} Volume"),
                        0,
                    )

                    oi = safe_float(
                        row.get(f"{prefix} OI"),
                        0,
                    )

                    delta = safe_float(
                        row.get(f"{prefix} Delta")
                    )

                    if oi <= 0:
                        continue

                    # Scanner uses a balanced simplified
                    # quality calculation because full
                    # technical analysis for every stock
                    # would create excessive API traffic.
                    scanner_score = 0

                    if pop >= 80:
                        scanner_score += 40
                    elif pop >= 75:
                        scanner_score += 35

                    if volume >= 10000:
                        scanner_score += 20
                    elif volume >= 5000:
                        scanner_score += 15
                    elif volume >= 1000:
                        scanner_score += 10

                    if oi >= 10000:
                        scanner_score += 20
                    elif oi >= 5000:
                        scanner_score += 15
                    elif oi >= 1000:
                        scanner_score += 10

                    if (
                        not np.isnan(delta)
                        and 0.35 <= abs(delta) <= 0.80
                    ):
                        scanner_score += 20

                    candidate = {
                        "Symbol": symbol,
                        "Side": (
                            "CALL BUY"
                            if side == "CE"
                            else "PUT BUY"
                        ),
                        "Strike": safe_float(
                            row.get("Strike")
                        ),
                        "Expiry": expiry,
                        "PoP %": pop,
                        "Premium": premium,
                        "Delta": delta,
                        "Volume": volume,
                        "OI": oi,
                        "Score": scanner_score,
                    }

                    if (
                        best is None
                        or candidate["PoP %"]
                        > best["PoP %"]
                        or (
                            candidate["PoP %"]
                            == best["PoP %"]
                            and candidate["Volume"]
                            > best["Volume"]
                        )
                    ):
                        best = candidate

            if best:
                results.append(best)

        except UpstoxRateLimitError:
            progress.empty()
            raise

        except Exception:
            pass

        # Scanner pacing
        time.sleep(0.8)

    progress.empty()

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    df = df.sort_values(
        ["PoP %", "Volume", "Score"],
        ascending=[False, False, False],
    )

    # One row per unique stock
    df = (
        df.drop_duplicates(
            subset=["Symbol"],
            keep="first",
        )
        .head(5)
        .reset_index(drop=True)
    )

    return df


# ============================================================
# UI HELPERS
# ============================================================

def metric_card(label, value):
    render_html(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """
    )


def decision_class_for(decision):

    if decision == "CALL BUY":
        return "decision-call"

    if decision == "PUT BUY":
        return "decision-put"

    if decision in {
        "WAIT FOR TRIGGER",
        "WAIT FOR CONFIRMATION",
    }:
        return "decision-wait"

    return "decision-no"


def render_decision(
    decision,
    direction,
    best_plan,
    ce_score,
    pe_score,
    confidence,
):

    css_class = decision_class_for(
        decision
    )

    if decision == "NO TRADE":
        subtitle = (
            "Conditions are not sufficiently aligned "
            "for a valid setup."
        )
    elif decision == "CALL BUY":
        subtitle = (
            "Bullish conditions aligned with the "
            "option-selection engine."
        )
    elif decision == "PUT BUY":
        subtitle = (
            "Bearish conditions aligned with the "
            "option-selection engine."
        )
    else:
        subtitle = (
            "The setup is developing, but confirmation "
            "is still required."
        )

    strike_text = "—"
    pop_text = "—"
    score_text = "—"

    if best_plan:

        if not np.isnan(
            safe_float(best_plan.get("strike"))
        ):
            strike_text = (
                f"{best_plan['strike']:.0f}"
            )

        pop_text = fmt_pct(
            best_plan.get("pop")
        )

        score_text = (
            f"{safe_float(best_plan.get('score'), 0):.0f}/100"
        )

    render_html(
        f"""
        <div class="decision-card {css_class}">
            <div class="decision-label">
                Trade Decision
            </div>

            <div class="decision-value">
                {decision}
            </div>

            <div class="decision-sub">
                {subtitle}
            </div>

            <div class="decision-stats">

                <div class="stat-pill">
                    <span>Market Bias</span>
                    <b>{direction}</b>
                </div>

                <div class="stat-pill">
                    <span>Confidence</span>
                    <b>{confidence:.0f}%</b>
                </div>

                <div class="stat-pill">
                    <span>Candidate Strike</span>
                    <b>{strike_text}</b>
                </div>

                <div class="stat-pill">
                    <span>PoP</span>
                    <b>{pop_text}</b>
                </div>

                <div class="stat-pill">
                    <span>Score</span>
                    <b>{score_text}</b>
                </div>

                <div class="stat-pill">
                    <span>CALL Score</span>
                    <b>{ce_score}/100</b>
                </div>

                <div class="stat-pill">
                    <span>PUT Score</span>
                    <b>{pe_score}/100</b>
                </div>

            </div>
        </div>
        """
    )


def render_trade_status(decision, best_plan):

    if decision == "CALL BUY":
        title = "TRADE STATUS"
        badge = "READY"
        badge_class = "badge-green"

    elif decision == "PUT BUY":
        title = "TRADE STATUS"
        badge = "READY"
        badge_class = "badge-red"

    elif decision in {
        "WAIT FOR TRIGGER",
        "WAIT FOR CONFIRMATION",
    }:
        title = "TRADE STATUS"
        badge = decision
        badge_class = "badge-yellow"

    else:
        title = "TRADE STATUS"
        badge = "NO TRADE"
        badge_class = "badge-gray"

    trigger = "—"
    readiness = "NO TRADE"

    if best_plan:

        trigger = best_plan.get(
            "trigger",
            "—",
        )

        readiness = best_plan.get(
            "readiness",
            "NO TRADE",
        )

    render_html(
        f"""
        <div class="card">
            <div class="plan-header">
                <div class="card-title">
                    {title}
                </div>
                <span class="badge {badge_class}">
                    {badge}
                </span>
            </div>

            <div class="helper">
                <b>Entry condition:</b>
                {trigger}
            </div>

            <div class="helper" style="margin-top:6px;">
                <b>Engine state:</b>
                {readiness}
            </div>
        </div>
        """
    )


def render_checklist(
    best_plan,
    direction,
):

    if best_plan is None:
        items = [
            ("bad", "No valid option candidate available.")
        ]
    else:

        items = []

        score = safe_float(
            best_plan.get("score")
        )

        alignment = safe_float(
            best_plan.get("alignment")
        )

        pop = safe_float(
            best_plan.get("pop")
        )

        spread = safe_float(
            best_plan.get("spread_pct")
        )

        volume = safe_float(
            best_plan.get("volume")
        )

        trigger_hit = bool(
            best_plan.get("trigger_hit")
        )

        candle_confirmed = bool(
            best_plan.get("candle_confirmed")
        )

        volume_confirmed = bool(
            best_plan.get("volume_confirmed")
        )

        items.append(
            (
                "ok" if score >= 72 else "bad",
                f"Score ≥ 72 ({score:.0f}/100)",
            )
        )

        items.append(
            (
                "ok" if alignment >= 2 else "bad",
                f"Timeframe alignment ({alignment:.0f}/3)",
            )
        )

        items.append(
            (
                "ok" if pop >= 55 else "bad",
                f"PoP ≥ 55% ({fmt_pct(pop)})",
            )
        )

        items.append(
            (
                "ok"
                if np.isnan(spread) or spread <= 3
                else "bad",
                (
                    "Spread within 3%"
                    if np.isnan(spread)
                    else f"Spread {spread:.2f}%"
                ),
            )
        )

        items.append(
            (
                "ok" if volume >= 1000 else "bad",
                f"Volume ≥ 1,000 ({fmt_num(volume)})",
            )
        )

        items.append(
            (
                "ok" if trigger_hit else "bad",
                "Trigger confirmed"
                if trigger_hit
                else "Waiting for trigger",
            )
        )

        items.append(
            (
                "ok" if candle_confirmed else "bad",
                "5-minute confirmation"
                if candle_confirmed
                else "5-minute confirmation pending",
            )
        )

        items.append(
            (
                "ok" if volume_confirmed else "bad",
                "Volume confirmation"
                if volume_confirmed
                else "Volume confirmation pending",
            )
        )

    html = """
    <div class="card">
        <div class="card-title">TRADE CHECKLIST</div>
    """

    for state, text_value in items:

        icon = "✓" if state == "ok" else "!"

        html += f"""
        <div class="check-item">
            <span class="check-icon {'check-ok' if state == 'ok' else 'check-bad'}">
                {icon}
            </span>
            <span class="check-text">
                {text_value}
            </span>
        </div>
        """

    html += "</div>"

    render_html(html)


def render_plan(
    title,
    plan,
    reference_only=False,
):

    if plan is None:

        render_html(
            f"""
            <div class="plan-card">
                <div class="plan-title">
                    {title}
                </div>

                <div class="helper">
                    No valid option setup available.
                </div>
            </div>
            """
        )

        return

    readiness = plan.get(
        "readiness",
        "NO TRADE",
    )

    if readiness == "READY":
        badge_class = (
            "badge-green"
            if plan["side"] == "CE"
            else "badge-red"
        )

    elif readiness.startswith("WAIT"):
        badge_class = "badge-yellow"

    else:
        badge_class = "badge-gray"

    side_label = (
        "CALL BUY"
        if plan["side"] == "CE"
        else "PUT BUY"
    )

    fail_text = ""

    if plan.get("fail_reasons"):

        fail_text = (
            "<div class='plan-warning'>"
            "<b>Engine checks:</b> "
            + " • ".join(
                str(x)
                for x in plan["fail_reasons"]
            )
            + "</div>"
        )

    reference_text = ""

    if reference_only:

        reference_text = """
        <div class="plan-reference">
            REFERENCE ONLY — This candidate does not
            represent an approved trade. Follow the
            main Trade Decision and trigger conditions.
        </div>
        """

    render_html(
        f"""
        <div class="plan-card">

            <div class="plan-header">

                <div class="plan-title">
                    {title}
                </div>

                <span class="badge {badge_class}">
                    {readiness}
                </span>

            </div>

            <div class="helper" style="margin-bottom:10px;">
                {side_label} • Strike
                <b>{safe_float(plan.get("strike"), 0):.0f}</b>
            </div>

            <div class="plan-grid">

                <div class="plan-item">
                    <span>Entry</span>
                    <b>{fmt_price(plan.get("entry"))}</b>
                </div>

                <div class="plan-item">
                    <span>Stop Loss</span>
                    <b>{fmt_price(plan.get("sl"))}</b>
                </div>

                <div class="plan-item">
                    <span>Target 1</span>
                    <b>{fmt_price(plan.get("target1"))}</b>
                </div>

                <div class="plan-item">
                    <span>Target 2</span>
                    <b>{fmt_price(plan.get("target2"))}</b>
                </div>

                <div class="plan-item">
                    <span>PoP</span>
                    <b>{fmt_pct(plan.get("pop"))}</b>
                </div>

                <div class="plan-item">
                    <span>Delta</span>
                    <b>{safe_float(plan.get("delta"), np.nan):.2f}
                    </b>
                </div>

                <div class="plan-item">
                    <span>IV</span>
                    <b>{fmt_pct(plan.get("iv"))}</b>
                </div>

                <div class="plan-item">
                    <span>Risk / Reward</span>
                    <b>
                        {safe_float(plan.get("rr1"), np.nan):.2f}R
                    </b>
                </div>

            </div>

            <div class="helper" style="margin-top:10px;">
                <b>Entry Trigger:</b>
                {plan.get("trigger", "—")}
            </div>

            <div class="helper" style="margin-top:6px;">
                <b>Exit Rule:</b>
                {plan.get("exit", "—")}
            </div>

            {fail_text}

            {reference_text}

        </div>
        """
    )


def render_oi_map(oi_data, spot):

    support = oi_data.get(
        "support"
    )

    resistance = oi_data.get(
        "resistance"
    )

    pcr = oi_data.get(
        "pcr"
    )

    support_rows = oi_data.get(
        "support_walls",
        [],
    )

    resistance_rows = oi_data.get(
        "resistance_walls",
        [],
    )

    html = f"""
    <div class="card">

        <div class="card-title">
            SUPPORT / RESISTANCE OI MAP
        </div>

        <div class="oi-map">

            <div class="oi-row">
                <span>Current Spot</span>
                <b>{fmt_price(spot)}</b>
            </div>

            <div class="oi-row">
                <span class="oi-support">
                    Major Support
                </span>
                <b class="oi-support">
                    {fmt_price(support)}
                </b>
            </div>

            <div class="oi-row">
                <span class="oi-resistance">
                    Major Resistance
                </span>
                <b class="oi-resistance">
                    {fmt_price(resistance)}
                </b>
            </div>

            <div class="oi-row">
                <span>PCR</span>
                <b>{safe_float(pcr, np.nan):.2f}</b>
            </div>

        </div>
    """

    if support_rows:

        html += """
        <div class="helper"
             style="margin-top:10px;margin-bottom:4px;">
            Top Put OI walls
        </div>
        """

        for strike, oi in support_rows[:3]:

            html += f"""
            <div class="oi-row">
                <span>{strike:.0f} PE</span>
                <b class="oi-support">
                    {fmt_num(oi)}
                </b>
            </div>
            """

    if resistance_rows:

        html += """
        <div class="helper"
             style="margin-top:10px;margin-bottom:4px;">
            Top Call OI walls
        </div>
        """

        for strike, oi in resistance_rows[:3]:

            html += f"""
            <div class="oi-row">
                <span>{strike:.0f} CE</span>
                <b class="oi-resistance">
                    {fmt_num(oi)}
                </b>
            </div>
            """

    html += "</div>"

    render_html(html)


# ============================================================
# HEADER
# ============================================================

render_html(
    """
    <div class="fo-header">

        <div class="fo-header-title">
            📊 FO PRO Trader Assistant
        </div>

        <div class="fo-header-sub">
            LIVE UPSTOX • F&O ANALYSIS • OPTIONS PROBABILITY ENGINE
        </div>

    </div>
    """
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🔥 Top 5 F&O PoP Scanner"
    )

    st.caption(
        "Full NSE equity F&O scan • PoP > 75%"
    )

    if "scanner_results" not in st.session_state:
        st.session_state.scanner_results = None

    if "scanner_error" not in st.session_state:
        st.session_state.scanner_error = None

    if st.button(
        "🔎 Scan Full F&O Market",
        use_container_width=True,
    ):

        st.session_state.scanner_error = None

        try:
            st.session_state.scanner_results = (
                scan_full_fno_pop_market(
                    min_pop=75.0
                )
            )

        except UpstoxRateLimitError as exc:

            st.session_state.scanner_error = str(exc)

        except Exception as exc:

            st.session_state.scanner_error = str(exc)

    if st.session_state.scanner_error:

        st.error(
            st.session_state.scanner_error
        )

    scanner_df = (
        st.session_state.scanner_results
    )

    if (
        scanner_df is not None
        and not scanner_df.empty
    ):

        display_df = scanner_df.copy()

        display_df["Strike"] = (
            display_df["Strike"]
            .round(0)
            .astype("Int64")
        )

        display_df["PoP %"] = (
            display_df["PoP %"]
            .round(1)
        )

        display_df["Premium"] = (
            display_df["Premium"]
            .round(2)
        )

        display_df["Delta"] = (
            display_df["Delta"]
            .round(2)
        )

        st.dataframe(
            display_df[
                [
                    "Symbol",
                    "Side",
                    "Strike",
                    "PoP %",
                    "Premium",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "Scanner results are candidates only. "
            "Run Analyze before considering a setup."
        )

    st.divider()

    st.markdown(
        "### 🔍 Analyze Instrument"
    )

    symbol_input = st.text_input(
        "Instrument",
        value=st.session_state.get(
            "selected_symbol",
            "KOTAKBANK",
        ),
        placeholder="e.g. KOTAKBANK",
    )

    risk_profile = st.selectbox(
        "Risk Profile",
        [
            "Conservative",
            "Balanced",
            "Aggressive",
        ],
        index=1,
    )

    analyze_clicked = st.button(
        "📈 Analyze",
        type="primary",
        use_container_width=True,
    )

    if st.button(
        "🔄 Refresh Data",
        use_container_width=True,
    ):

        st.cache_data.clear()
        st.rerun()

    auto_refresh = st.checkbox(
        "Auto refresh every 60 seconds",
        value=False,
    )

    if auto_refresh and st_autorefresh is not None:

        try:
            st_autorefresh(
                interval=60_000,
                key="fo_auto_refresh_60",
            )
        except Exception:
            st.caption(
                "Auto-refresh component unavailable."
            )

    elif auto_refresh:

        st.caption(
            "Install streamlit-autorefresh to enable "
            "automatic refresh."
        )

    st.caption(
        "Analysis uses live Upstox REST data. "
        "No simulated market prices are used."
    )


# ============================================================
# SELECT SYMBOL
# ============================================================

if analyze_clicked:

    symbol_input = alias_symbol(
        symbol_input
    )

    if symbol_input:
        st.session_state.selected_symbol = (
            symbol_input
        )

else:

    symbol_input = st.session_state.get(
        "selected_symbol",
        alias_symbol(symbol_input),
    )


# ============================================================
# DATA STATUS
# ============================================================

if market_is_open():

    render_html(
        """
        <div class="status-live">

            <div class="status-title">
                Data Status
            </div>

            <div class="status-value">
                ● LIVE DATA
            </div>

        </div>
        """
    )

else:

    render_html(
        """
        <div class="status-closed">

            <div class="status-title">
                Data Status
            </div>

            <div class="status-value">
                ● MARKET CLOSED
            </div>

        </div>
        """
    )


# ============================================================
# ANALYSIS
# ============================================================

try:

    instrument = search_underlying(
        symbol_input
    )

    underlying_key = instrument.get(
        "instrument_key"
    )

    display_symbol = (
        instrument.get("trading_symbol")
        or instrument.get("name")
        or symbol_input
    )

    if not underlying_key:
        raise UpstoxError(
            "Upstox did not return an instrument key."
        )

    # --------------------------------------------------------
    # Contracts / expiry
    # --------------------------------------------------------

    contracts = get_contracts(
        underlying_key
    )

    expiries = available_expiries(
        contracts
    )

    if not expiries:
        raise UpstoxError(
            f"No active option expiry found for {display_symbol}."
        )

    selected_expiry = expiries[0]

    # --------------------------------------------------------
    # Chain
    # --------------------------------------------------------

    raw_chain = get_option_chain(
        underlying_key,
        selected_expiry,
    )

    chain = normalize_chain(
        raw_chain
    )

    if (
        chain.empty
        or "Strike" not in chain.columns
    ):
        raise UpstoxError(
            "Upstox returned an empty or invalid option chain."
        )

    # --------------------------------------------------------
    # Quote
    # --------------------------------------------------------

    quote = get_quote(
        underlying_key
    )

    spot, previous_close, net_change, change_pct = (
        parse_quote(quote)
    )

    # Fallback spot
    if np.isnan(spot):

        try:

            median_strike = safe_float(
                chain["Strike"].median()
            )

            spot = median_strike

        except Exception:
            spot = np.nan

    if np.isnan(spot):
        raise UpstoxError(
            "Unable to determine current spot price."
        )

    # --------------------------------------------------------
    # Candles / technicals
    # --------------------------------------------------------

    try:
        df5 = get_intraday_candles(
            underlying_key
        )
    except Exception:
        df5 = pd.DataFrame()

    try:
        df30 = get_30m_candles(
            underlying_key
        )
    except Exception:
        df30 = pd.DataFrame()

    try:
        dfdaily = get_daily_candles(
            underlying_key
        )
    except Exception:
        dfdaily = pd.DataFrame()

    tf5 = technicals(
        df5,
        spot,
    )

    tf30 = technicals(
        df30,
        spot,
    )

    daily = technicals(
        dfdaily,
        spot,
    )

    overall_direction = overall_trend(
        tf5,
        tf30,
        daily,
    )

    # --------------------------------------------------------
    # OI
    # --------------------------------------------------------

    oi_data = oi_levels(
        chain,
        spot,
    )

    support = oi_data.get(
        "support"
    )

    resistance = oi_data.get(
        "resistance"
    )

    pcr = oi_data.get(
        "pcr"
    )

    # --------------------------------------------------------
    # ATM / candidates
    # --------------------------------------------------------

    atm_row = nearest_row(
        chain,
        spot,
    )

    if atm_row is None:
        raise UpstoxError(
            "Unable to determine ATM option."
        )

    # Candidates within +/- 5 strikes
    atm_index = (
        chain["Strike"] - spot
    ).abs().idxmin()

    position = chain.index.get_loc(
        atm_index
    )

    start = max(
        0,
        position - 5,
    )

    end = min(
        len(chain),
        position + 6,
    )

    candidate_chain = chain.iloc[
        start:end
    ].copy()

    # --------------------------------------------------------
    # Best CE
    # --------------------------------------------------------

    best_ce = None
    best_ce_data = None

    for _, row in candidate_chain.iterrows():

        score_data = score_option(
            row,
            "CE",
            spot,
            tf5,
            tf30,
            daily,
            pcr,
            support,
            resistance,
        )

        if (
            best_ce_data is None
            or score_data["score"]
            > best_ce_data["score"]
        ):

            best_ce = row
            best_ce_data = score_data

    # --------------------------------------------------------
    # Best PE
    # --------------------------------------------------------

    best_pe = None
    best_pe_data = None

    for _, row in candidate_chain.iterrows():

        score_data = score_option(
            row,
            "PE",
            spot,
            tf5,
            tf30,
            daily,
            pcr,
            support,
            resistance,
        )

        if (
            best_pe_data is None
            or score_data["score"]
            > best_pe_data["score"]
        ):

            best_pe = row
            best_pe_data = score_data

    if best_ce is None:
        raise UpstoxError(
            "Unable to calculate CALL candidate."
        )

    if best_pe is None:
        raise UpstoxError(
            "Unable to calculate PUT candidate."
        )

    ce_score = int(
        best_ce_data["score"]
    )

    pe_score = int(
        best_pe_data["score"]
    )

    # --------------------------------------------------------
    # Plans
    # --------------------------------------------------------

    ce_plan = build_plan(
        best_ce,
        "CE",
        best_ce_data,
        spot,
        support,
        resistance,
        tf5,
        risk_profile,
    )

    pe_plan = build_plan(
        best_pe,
        "PE",
        best_pe_data,
        spot,
        support,
        resistance,
        tf5,
        risk_profile,
    )

    # --------------------------------------------------------
    # Decision logic
    # --------------------------------------------------------

    if (
        ce_plan
        and ce_score >= 72
        and ce_score >= pe_score + 8
        and overall_direction == "Bullish"
        and ce_plan["readiness"]
        in {
            "READY",
            "WAIT FOR TRIGGER",
            "WAIT FOR CONFIRMATION",
        }
    ):

        decision = (
            "CALL BUY"
            if ce_plan["readiness"] == "READY"
            else ce_plan["readiness"]
        )

        best_plan = ce_plan

    elif (
        pe_plan
        and pe_score >= 72
        and pe_score >= ce_score + 8
        and overall_direction == "Bearish"
        and pe_plan["readiness"]
        in {
            "READY",
            "WAIT FOR TRIGGER",
            "WAIT FOR CONFIRMATION",
        }
    ):

        decision = (
            "PUT BUY"
            if pe_plan["readiness"] == "READY"
            else pe_plan["readiness"]
        )

        best_plan = pe_plan

    else:

        decision = "NO TRADE"

        best_plan = (
            ce_plan
            if ce_score >= pe_score
            else pe_plan
        )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    best_score = max(
        ce_score,
        pe_score,
    )

    best_alignment = 0

    if best_plan:

        best_alignment = safe_float(
            best_plan.get("alignment"),
            0,
        )

    confidence = (
        best_score * 0.70
        + (best_alignment / 3) * 20
    )

    if (
        overall_direction in {
            "Bullish",
            "Bearish",
        }
    ):
        confidence += 5

    confidence = float(
        np.clip(
            confidence,
            0,
            100,
        )
    )

    # ========================================================
    # TOP MARKET SUMMARY
    # ========================================================

    st.markdown(
        f"### {display_symbol}"
    )

    st.caption(
        f"Expiry: {selected_expiry} • "
        f"Risk Profile: {risk_profile} • "
        f"Updated: {now_ist().strftime('%d %b %Y, %I:%M:%S %p')} IST"
    )

    # --------------------------------------------------------
    # Price metrics
    # --------------------------------------------------------

    metric_columns = st.columns(6)

    with metric_columns[0]:
        metric_card(
            "Spot",
            fmt_price(spot),
        )

    with metric_columns[1]:
        metric_card(
            "Change",
            fmt_price(net_change),
        )

    with metric_columns[2]:
        metric_card(
            "Change %",
            fmt_pct(change_pct),
        )

    with metric_columns[3]:
        metric_card(
            "PCR",
            (
                f"{pcr:.2f}"
                if not np.isnan(pcr)
                else "—"
            ),
        )

    with metric_columns[4]:
        metric_card(
            "Support",
            fmt_price(support),
        )

    with metric_columns[5]:
        metric_card(
            "Resistance",
            fmt_price(resistance),
        )

    # ========================================================
    # DECISION
    # ========================================================

    render_decision(
        decision,
        overall_direction,
        best_plan,
        ce_score,
        pe_score,
        confidence,
    )

    # ========================================================
    # TRADE STATUS + CHECKLIST
    # ========================================================

    left, right = st.columns(
        [1.15, 0.85]
    )

    with left:

        render_trade_status(
            decision,
            best_plan,
        )

    with right:

        render_checklist(
            best_plan,
            overall_direction,
        )

    # ========================================================
    # TRADE PLAN
    # ========================================================

    st.markdown(
        '<div class="section-title">🎯 TRADE PLAN</div>',
        unsafe_allow_html=True,
    )

    if decision == "CALL BUY":

        render_plan(
            "CALL BUY",
            ce_plan,
        )

    elif decision == "PUT BUY":

        render_plan(
            "PUT BUY",
            pe_plan,
        )

    else:

        # Clearly mark candidates as reference-only
        if ce_plan:

            render_plan(
                "CALL CANDIDATE",
                ce_plan,
                reference_only=True,
            )

        if pe_plan:

            render_plan(
                "PUT CANDIDATE",
                pe_plan,
                reference_only=True,
            )

    # ========================================================
    # SUPPORT / RESISTANCE
    # ========================================================

    st.markdown(
        '<div class="section-title">📍 OI STRUCTURE</div>',
        unsafe_allow_html=True,
    )

    render_oi_map(
        oi_data,
        spot,
    )

    # ========================================================
    # ENGINE SUMMARY
    # ========================================================

    st.markdown(
        '<div class="section-title">🧠 ENGINE SUMMARY</div>',
        unsafe_allow_html=True,
    )

    summary_columns = st.columns(4)

    with summary_columns[0]:

        metric_card(
            "5M Trend",
            tf5.get(
                "trend",
                "Unknown",
            ),
        )

    with summary_columns[1]:

        metric_card(
            "30M Trend",
            tf30.get(
                "trend",
                "Unknown",
            ),
        )

    with summary_columns[2]:

        metric_card(
            "Daily Trend",
            daily.get(
                "trend",
                "Unknown",
            ),
        )

    with summary_columns[3]:

        metric_card(
            "RSI",
            (
                f"{tf5['rsi']:.1f}"
                if not np.isnan(
                    safe_float(tf5.get("rsi"))
                )
                else "—"
            ),
        )

    # ========================================================
    # TECHNICAL DETAILS
    # ========================================================

    details_left, details_right = st.columns(
        2
    )

    with details_left:

        render_html(
            f"""
            <div class="card">

                <div class="card-title">
                    Technical Snapshot
                </div>

                <div class="oi-row">
                    <span>5M EMA20</span>
                    <b>{fmt_price(tf5.get("ema20"))}</b>
                </div>

                <div class="oi-row">
                    <span>5M EMA50</span>
                    <b>{fmt_price(tf5.get("ema50"))}</b>
                </div>

                <div class="oi-row">
                    <span>5M VWAP</span>
                    <b>{fmt_price(tf5.get("vwap"))}</b>
                </div>

                <div class="oi-row">
                    <span>5M ATR</span>
                    <b>{fmt_price(tf5.get("atr"))}</b>
                </div>

                <div class="oi-row">
                    <span>ADX</span>
                    <b>
                        {
                            f"{safe_float(tf5.get('adx')):.1f}"
                            if not np.isnan(
                                safe_float(tf5.get("adx"))
                            )
                            else "—"
                        }
                    </b>
                </div>

                <div class="oi-row">
                    <span>Volume Ratio</span>
                    <b>
                        {
                            f"{safe_float(tf5.get('volume_ratio')):.2f}x"
                            if not np.isnan(
                                safe_float(tf5.get("volume_ratio"))
                            )
                            else "—"
                        }
                    </b>
                </div>

            </div>
            """
        )

    with details_right:

        render_html(
            f"""
            <div class="card">

                <div class="card-title">
                    Option Quality
                </div>

                <div class="oi-row">
                    <span>CALL Score</span>
                    <b>{ce_score}/100</b>
                </div>

                <div class="oi-row">
                    <span>CALL PoP</span>
                    <b>
                        {fmt_pct(best_ce_data.get("pop"))}
                    </b>
                </div>

                <div class="oi-row">
                    <span>PUT Score</span>
                    <b>{pe_score}/100</b>
                </div>

                <div class="oi-row">
                    <span>PUT PoP</span>
                    <b>
                        {fmt_pct(best_pe_data.get("pop"))}
                    </b>
                </div>

                <div class="oi-row">
                    <span>CALL Delta</span>
                    <b>
                        {
                            f"{safe_float(best_ce_data.get('delta')):.2f}"
                            if not np.isnan(
                                safe_float(best_ce_data.get("delta"))
                            )
                            else "—"
                        }
                    </b>
                </div>

                <div class="oi-row">
                    <span>PUT Delta</span>
                    <b>
                        {
                            f"{safe_float(best_pe_data.get('delta')):.2f}"
                            if not np.isnan(
                                safe_float(best_pe_data.get("delta"))
                            )
                            else "—"
                        }
                    </b>
                </div>

            </div>
            """
        )

    # ========================================================
    # OPTION CHAIN
    # ========================================================

    st.markdown(
        '<div class="section-title">📋 LIVE OPTION CHAIN</div>',
        unsafe_allow_html=True,
    )

    chain_display = candidate_chain.copy()

    # Safe nullable integer conversion
    for col in [
        "Strike",
        "CE OI",
        "CE Chg OI",
        "CE Volume",
        "PE OI",
        "PE Chg OI",
        "PE Volume",
    ]:

        if col in chain_display.columns:
            chain_display[col] = (
                pd.to_numeric(
                    chain_display[col],
                    errors="coerce",
                )
                .round(0)
                .astype("Int64")
            )

    # Round numerical fields
    for col in [
        "CE LTP",
        "CE Bid",
        "CE Ask",
        "CE IV",
        "CE Delta",
        "CE PoP",
        "PE LTP",
        "PE Bid",
        "PE Ask",
        "PE IV",
        "PE Delta",
        "PE PoP",
    ]:

        if col in chain_display.columns:
            chain_display[col] = pd.to_numeric(
                chain_display[col],
                errors="coerce",
            ).round(2)

    preferred_columns = [
        "Strike",

        "CE LTP",
        "CE OI",
        "CE Chg OI",
        "CE Volume",
        "CE IV",
        "CE Delta",
        "CE PoP",

        "PE LTP",
        "PE OI",
        "PE Chg OI",
        "PE Volume",
        "PE IV",
        "PE Delta",
        "PE PoP",
    ]

    visible_columns = [
        col
        for col in preferred_columns
        if col in chain_display.columns
    ]

    st.dataframe(
        chain_display[visible_columns],
        use_container_width=True,
        hide_index=True,
        height=430,
    )

    st.caption(
        "Option chain is centered around the current spot "
        "and shows approximately ±5 strikes."
    )


# ============================================================
# ERROR HANDLING
# ============================================================

except UpstoxRateLimitError as exc:

    render_html(
        f"""
        <div class="status-error">

            <div class="status-title">
                UPSTOX RATE LIMIT
            </div>

            <div class="status-value">
                Please wait before refreshing
            </div>

            <div class="helper"
                 style="margin-top:6px;color:#8f2c2c;">
                {str(exc)}
            </div>

        </div>
        """
    )

except UpstoxError as exc:

    render_html(
        f"""
        <div class="status-error">

            <div class="status-title">
                DATA ERROR
            </div>

            <div class="status-value">
                Unable to complete analysis
            </div>

            <div class="helper"
                 style="margin-top:6px;color:#8f2c2c;">
                {str(exc)}
            </div>

        </div>
        """
    )

except Exception as exc:

    render_html(
        f"""
        <div class="status-error">

            <div class="status-title">
                APPLICATION ERROR
            </div>

            <div class="status-value">
                Analysis could not be completed
            </div>

            <div class="helper"
                 style="margin-top:6px;color:#8f2c2c;">
                {str(exc)}
            </div>

        </div>
        """
    )
