import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="F&O Pro Trader Assistant",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CONSTANTS
# ============================================================

IST = ZoneInfo("Asia/Kolkata")

UPSTOX_BASE = "https://api.upstox.com"

RISK_PROFILES = {
    "Conservative": {
        "sl": 0.18,
        "t1": 0.25,
        "t2": 0.40,
    },
    "Balanced": {
        "sl": 0.22,
        "t1": 0.35,
        "t2": 0.55,
    },
    "Aggressive": {
        "sl": 0.28,
        "t1": 0.45,
        "t2": 0.70,
    },
}

# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
<style>

    /* ---------- GLOBAL ---------- */

    .stApp {
        background: #f5f7fb;
    }

    .main .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }

    html, body, [class*="css"] {
        font-family: "Inter", "Segoe UI", Arial, sans-serif;
    }

    /* ---------- HEADER ---------- */

    .top-header {
        background: linear-gradient(135deg, #102a56 0%, #174b8f 100%);
        padding: 18px 24px;
        border-radius: 14px;
        color: white;
        margin-bottom: 18px;
        box-shadow: 0 5px 18px rgba(16,42,86,0.15);
    }

    .top-header-title {
        font-size: 25px;
        font-weight: 750;
        letter-spacing: -0.3px;
    }

    .top-header-subtitle {
        font-size: 13px;
        opacity: 0.82;
        margin-top: 3px;
    }

    .top-live {
        text-align: right;
        font-size: 13px;
        padding-top: 8px;
    }

    .live-pill {
        display: inline-block;
        background: rgba(16,185,129,0.22);
        border: 1px solid rgba(110,231,183,0.45);
        color: #d1fae5;
        border-radius: 20px;
        padding: 7px 13px;
        font-weight: 700;
        margin-right: 8px;
    }

    /* ---------- STOCK HERO ---------- */

    .stock-hero {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 22px 24px;
        margin-bottom: 18px;
        box-shadow: 0 3px 12px rgba(15,23,42,0.05);
    }

    .stock-name {
        font-size: 31px;
        font-weight: 800;
        color: #12213f;
        letter-spacing: -0.7px;
    }

    .stock-subtitle {
        font-size: 15px;
        color: #64748b;
        margin-top: 2px;
    }

    .hero-price-label {
        font-size: 12px;
        color: #64748b;
        margin-bottom: 3px;
    }

    .hero-price {
        font-size: 27px;
        font-weight: 800;
        color: #12213f;
    }

    .hero-time {
        font-size: 12px;
        color: #64748b;
    }

    /* ---------- SECTION ---------- */

    .section-title {
        font-size: 19px;
        font-weight: 750;
        color: #173b70;
        margin: 20px 0 10px 2px;
    }

    .section-subtitle {
        font-size: 13px;
        color: #64748b;
        margin: -6px 0 12px 2px;
    }

    /* ---------- METRIC CARDS ---------- */

    .metric-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        min-height: 105px;
        box-shadow: 0 2px 9px rgba(15,23,42,0.04);
    }

    .metric-label {
        font-size: 12px;
        color: #64748b;
        font-weight: 600;
        margin-bottom: 8px;
    }

    .metric-value {
        font-size: 21px;
        font-weight: 800;
        color: #172554;
    }

    .metric-small {
        font-size: 12px;
        margin-top: 5px;
        color: #64748b;
    }

    .green-value {
        color: #059669;
    }

    .red-value {
        color: #dc2626;
    }

    .purple-value {
        color: #7c3aed;
    }

    /* ---------- DECISION ---------- */

    .decision-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 20px;
        box-shadow: 0 2px 10px rgba(15,23,42,0.04);
        min-height: 175px;
    }

    .decision-label {
        font-size: 12px;
        color: #64748b;
        font-weight: 650;
        margin-bottom: 10px;
    }

    .decision-text {
        font-size: 27px;
        font-weight: 800;
        color: #334155;
    }

    .decision-sub {
        margin-top: 9px;
        color: #64748b;
        font-size: 13px;
    }

    /* ---------- SCORE ---------- */

    .score-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 20px;
        box-shadow: 0 2px 10px rgba(15,23,42,0.04);
        min-height: 175px;
    }

    .score-row {
        margin-bottom: 16px;
    }

    .score-title {
        display: flex;
        justify-content: space-between;
        font-size: 13px;
        font-weight: 700;
        color: #334155;
        margin-bottom: 7px;
    }

    .score-track {
        height: 9px;
        background: #e2e8f0;
        border-radius: 10px;
        overflow: hidden;
    }

    .score-bull {
        height: 100%;
        background: #10b981;
        border-radius: 10px;
    }

    .score-bear {
        height: 100%;
        background: #ef4444;
        border-radius: 10px;
    }

    /* ---------- TRADE PLAN ---------- */

    .trade-plan {
        background: white;
        border: 1px solid #dbeafe;
        border-radius: 14px;
        padding: 20px;
        box-shadow: 0 3px 12px rgba(30,64,175,0.05);
    }

    .trade-direction {
        font-size: 22px;
        font-weight: 800;
        margin-bottom: 15px;
    }

    .call-direction {
        color: #059669;
    }

    .put-direction {
        color: #dc2626;
    }

    .trade-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 14px;
        text-align: center;
        min-height: 90px;
    }

    .trade-box-label {
        font-size: 11px;
        color: #64748b;
        font-weight: 650;
    }

    .trade-box-value {
        font-size: 19px;
        font-weight: 800;
        color: #172554;
        margin-top: 7px;
    }

    /* ---------- REASONS ---------- */

    .reason-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 19px 21px;
        box-shadow: 0 2px 9px rgba(15,23,42,0.04);
    }

    .reason-item {
        font-size: 13px;
        color: #334155;
        padding: 9px 0;
        border-bottom: 1px solid #f1f5f9;
    }

    .reason-item:last-child {
        border-bottom: none;
    }

    /* ---------- STATUS ---------- */

    .status-open {
        background: #ecfdf5;
        color: #047857;
        border: 1px solid #a7f3d0;
        border-radius: 20px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 750;
        display: inline-block;
    }

    .status-closed {
        background: #f1f5f9;
        color: #475569;
        border: 1px solid #cbd5e1;
        border-radius: 20px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 750;
        display: inline-block;
    }

    .status-stale {
        background: #fff7ed;
        color: #c2410c;
        border: 1px solid #fed7aa;
        border-radius: 20px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 750;
        display: inline-block;
    }

    /* ---------- INFO BAR ---------- */

    .info-bar {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: #1e40af;
        border-radius: 10px;
        padding: 11px 14px;
        font-size: 12px;
        margin-top: 12px;
    }

    /* ---------- FOOTER ---------- */

    .footer-bar {
        background: #eef2ff;
        border-radius: 10px;
        padding: 12px 15px;
        color: #475569;
        font-size: 11px;
        margin-top: 20px;
        text-align: center;
    }

    /* ---------- SIDEBAR ---------- */

    section[data-testid="stSidebar"] {
        background: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }

    .sidebar-title {
        font-size: 18px;
        font-weight: 800;
        color: #173b70;
        margin-bottom: 5px;
    }

    .sidebar-help {
        font-size: 12px;
        color: #64748b;
        line-height: 1.5;
    }

    /* ---------- TABLE ---------- */

    .chain-caption {
        font-size: 12px;
        color: #64748b;
        margin-bottom: 7px;
    }

</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
<div class="top-header">
    <div class="top-header-title">📈 F&O Pro Trader Assistant</div>
    <div class="top-header-subtitle">
        Options Analysis&nbsp;&nbsp;•&nbsp;&nbsp;Powered by Upstox
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ============================================================
# SESSION STATE
# ============================================================

if "active_symbol" not in st.session_state:
    st.session_state.active_symbol = ""

if "active_risk" not in st.session_state:
    st.session_state.active_risk = "Balanced"

if "active_result" not in st.session_state:
    st.session_state.active_result = None

if "active_chain" not in st.session_state:
    st.session_state.active_chain = None

if "last_error" not in st.session_state:
    st.session_state.last_error = ""

if "last_successful_refresh" not in st.session_state:
    st.session_state.last_successful_refresh = None

# ============================================================
# UPSTOX TOKEN
# ============================================================

def get_token():
    try:
        return st.secrets["UPSTOX_ACCESS_TOKEN"]
    except Exception:
        return None


TOKEN = get_token()

# ============================================================
# API HELPERS
# ============================================================

def upstox_headers():
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
        "User-Agent": "FO-Pro-Trader-Assistant",
    }


def api_get(url, params=None, timeout=20):
    if not TOKEN:
        raise RuntimeError(
            "UPSTOX_ACCESS_TOKEN is missing from Streamlit Secrets."
        )

    response = requests.get(
        url,
        headers=upstox_headers(),
        params=params,
        timeout=timeout,
    )

    if response.status_code != 200:
        try:
            detail = response.json()
        except Exception:
            detail = response.text

        raise RuntimeError(
            f"Upstox API error {response.status_code}: {detail}"
        )

    return response.json()


# ============================================================
# TIME HELPERS
# ============================================================

def format_iso_ist(value):
    if not value:
        return "N/A"

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(IST).strftime(
            "%d-%b-%Y %I:%M:%S %p IST"
        )

    except Exception:
        return str(value)


def format_ms_ist(value):
    if value in [None, "", 0, "0"]:
        return "N/A"

    try:
        ms = float(value)

        if ms < 10000000000:
            ms = ms * 1000

        dt = datetime.fromtimestamp(
            ms / 1000,
            tz=timezone.utc,
        )

        return dt.astimezone(IST).strftime(
            "%d-%b-%Y %I:%M:%S %p IST"
        )

    except Exception:
        return "N/A"


def now_ist():
    return datetime.now(IST)


# ============================================================
# FIND UNDERLYING
# ============================================================

def find_underlying(symbol):
    symbol = symbol.strip().upper()

    if not symbol:
        raise RuntimeError("Please enter a stock or index.")

    searches = [
        {
            "q": symbol,
            "segments": "EQ",
            "records": 30,
        },
        {
            "q": symbol,
            "segments": "INDEX",
            "records": 30,
        },
    ]

    candidates = []

    for params in searches:
        data = api_get(
            f"{UPSTOX_BASE}/v2/instruments/search",
            params=params,
        )

        results = data.get("data", [])

        if isinstance(results, list):
            candidates.extend(results)

    if not candidates:
        raise RuntimeError(
            f"Could not find NSE stock/index: {symbol}"
        )

    # Exact trading symbol match
    for item in candidates:
        if str(item.get("trading_symbol", "")).upper() == symbol:
            return item

    # Exact short name match
    for item in candidates:
        if str(item.get("short_name", "")).upper() == symbol:
            return item

    # Exact name match
    for item in candidates:
        if str(item.get("name", "")).upper() == symbol:
            return item

    # Otherwise choose the first NSE equity/index result
    for item in candidates:
        seg = str(item.get("segment", "")).upper()

        if seg in ["NSE_EQ", "NSE_INDEX"]:
            return item

    return candidates[0]


# ============================================================
# FULL MARKET QUOTE
# ============================================================

def get_full_quote_v3(instrument_key):
    data = api_get(
        f"{UPSTOX_BASE}/v3/market-quote/quotes",
        params={
            "instrument_key": instrument_key,
        },
    )

    quote_data = data.get("data", {})

    if not quote_data:
        raise RuntimeError(
            "Upstox returned no market quote data."
        )

    # Usually keyed by instrument key
    if instrument_key in quote_data:
        return quote_data[instrument_key]

    # Fallback
    first_value = next(iter(quote_data.values()))

    if isinstance(first_value, dict):
        return first_value

    raise RuntimeError(
        "Could not read Upstox market quote."
    )


# ============================================================
# MARKET CONTEXT
# ============================================================

def extract_market_context(quote):
    last_price = quote.get("last_price")

    if last_price is None:
        last_price = quote.get("ltp")

    prev_close = quote.get("prev_close_price")

    if prev_close is None:
        prev_close = quote.get("cp")

    average_price = quote.get("average_price")

    net_change = quote.get("net_change")

    volume = quote.get("volume")

    ohlc = quote.get("ohlc", {})

    open_price = None
    high_price = None
    low_price = None
    close_price = None

    if isinstance(ohlc, dict):
        open_price = ohlc.get("open")
        high_price = ohlc.get("high")
        low_price = ohlc.get("low")
        close_price = ohlc.get("close")

    elif isinstance(ohlc, list) and ohlc:
        first = ohlc[0]

        if isinstance(first, dict):
            open_price = first.get("open")
            high_price = first.get("high")
            low_price = first.get("low")
            close_price = first.get("close")

    try:
        last_price = float(last_price)
    except Exception:
        last_price = 0.0

    try:
        prev_close = float(prev_close)
    except Exception:
        prev_close = 0.0

    try:
        average_price = float(average_price)
    except Exception:
        average_price = 0.0

    try:
        net_change = float(net_change)
    except Exception:
        net_change = (
            last_price - prev_close
            if prev_close
            else 0.0
        )

    try:
        volume = float(volume)
    except Exception:
        volume = 0

    try:
        open_price = float(open_price)
    except Exception:
        open_price = 0.0

    try:
        high_price = float(high_price)
    except Exception:
        high_price = 0.0

    try:
        low_price = float(low_price)
    except Exception:
        low_price = 0.0

    if prev_close:
        pct_change = (
            (last_price - prev_close)
            / prev_close
        ) * 100
    else:
        pct_change = 0.0

    if open_price:
        price_vs_open = (
            (last_price - open_price)
            / open_price
        ) * 100
    else:
        price_vs_open = 0.0

    if average_price:
        price_vs_average = (
            (last_price - average_price)
            / average_price
        ) * 100
    else:
        price_vs_average = 0.0

    if high_price > low_price:
        range_position = (
            (last_price - low_price)
            / (high_price - low_price)
        ) * 100
    else:
        range_position = 50.0

    return {
        "last_price": last_price,
        "prev_close": prev_close,
        "average_price": average_price,
        "net_change": net_change,
        "pct_change": pct_change,
        "volume": volume,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "price_vs_open": price_vs_open,
        "price_vs_average": price_vs_average,
        "range_position": range_position,
        "last_trade_time": quote.get("last_trade_time"),
        "snapshot_time": quote.get("timestamp"),
    }


# ============================================================
# OPTION CONTRACTS
# ============================================================

def get_option_contracts(underlying_key):
    data = api_get(
        f"{UPSTOX_BASE}/v2/option/contract",
        params={
            "instrument_key": underlying_key,
        },
    )

    contracts = data.get("data", [])

    if not isinstance(contracts, list):
        return []

    return contracts


# ============================================================
# EXPIRY
# ============================================================

def get_nearest_expiry(contracts):
    today = now_ist().date()

    expiries = []

    for contract in contracts:
        expiry = contract.get("expiry")

        if not expiry:
            continue

        try:
            expiry_date = datetime.strptime(
                expiry,
                "%Y-%m-%d",
            ).date()

            if expiry_date >= today:
                expiries.append(expiry_date)

        except Exception:
            continue

    if not expiries:
        return None

    return min(expiries)


# ============================================================
# OPTION CHAIN
# ============================================================

def get_option_chain(
    underlying_key,
    expiry_date,
):
    data = api_get(
        f"{UPSTOX_BASE}/v2/option/chain",
        params={
            "instrument_key": underlying_key,
            "expiry_date": expiry_date,
        },
    )

    chain = data.get("data", [])

    if not isinstance(chain, list):
        return []

    return chain


# ============================================================
# NORMALIZE OPTION CHAIN
# ============================================================

def normalize_chain(chain):
    rows = []

    for item in chain:
        strike = item.get("strike_price")
        spot = item.get("underlying_spot_price")

        call = item.get("call_options") or {}
        put = item.get("put_options") or {}

        call_market = call.get("market_data") or {}
        put_market = put.get("market_data") or {}

        call_greeks = call.get("option_greeks") or {}
        put_greeks = put.get("option_greeks") or {}

        if strike is None:
            continue

        rows.append(
            {
                "strike": float(strike),
                "spot": float(spot or 0),

                "ce_ltp": float(
                    call_market.get("ltp") or 0
                ),
                "ce_oi": float(
                    call_market.get("oi") or 0
                ),
                "ce_prev_oi": float(
                    call_market.get("prev_oi") or 0
                ),
                "ce_volume": float(
                    call_market.get("volume") or 0
                ),
                "ce_iv": float(
                    call_greeks.get("iv") or 0
                ),
                "ce_delta": float(
                    call_greeks.get("delta") or 0
                ),
                "ce_pop": float(
                    call_greeks.get("pop") or 0
                ),
                "ce_bid": float(
                    call_market.get("bid_price") or 0
                ),
                "ce_ask": float(
                    call_market.get("ask_price") or 0
                ),
                "ce_instrument_key":
                    call.get("instrument_key"),

                "pe_ltp": float(
                    put_market.get("ltp") or 0
                ),
                "pe_oi": float(
                    put_market.get("oi") or 0
                ),
                "pe_prev_oi": float(
                    put_market.get("prev_oi") or 0
                ),
                "pe_volume": float(
                    put_market.get("volume") or 0
                ),
                "pe_iv": float(
                    put_greeks.get("iv") or 0
                ),
                "pe_delta": float(
                    put_greeks.get("delta") or 0
                ),
                "pe_pop": float(
                    put_greeks.get("pop") or 0
                ),
                "pe_bid": float(
                    put_market.get("bid_price") or 0
                ),
                "pe_ask": float(
                    put_market.get("ask_price") or 0
                ),
                "pe_instrument_key":
                    put.get("instrument_key"),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# MARKET STATUS
# ============================================================

def get_market_status(last_trade_time=None):
    current = now_ist()

    # Saturday / Sunday
    if current.weekday() >= 5:
        return "MARKET CLOSED"

    market_open = current.replace(
        hour=9,
        minute=15,
        second=0,
        microsecond=0,
    )

    market_close = current.replace(
        hour=15,
        minute=30,
        second=0,
        microsecond=0,
    )

    if current < market_open or current > market_close:
        return "MARKET CLOSED"

    # Check freshness of last trade
    if last_trade_time:
        try:
            if isinstance(last_trade_time, str):
                trade_dt = datetime.fromisoformat(
                    last_trade_time.replace(
                        "Z",
                        "+00:00",
                    )
                )

                if trade_dt.tzinfo is None:
                    trade_dt = trade_dt.replace(
                        tzinfo=timezone.utc
                    )
            else:
                trade_dt = datetime.fromtimestamp(
                    float(last_trade_time) / 1000,
                    tz=timezone.utc,
                )

            age_seconds = (
                datetime.now(timezone.utc)
                - trade_dt.astimezone(timezone.utc)
            ).total_seconds()

            if age_seconds > 600:
                return "DATA STALE"

        except Exception:
            pass

    return "MARKET OPEN"


# ============================================================
# ANALYSIS ENGINE
# ============================================================

def analyze_chain(df, market):
    if df.empty:
        raise RuntimeError(
            "Option chain returned no usable data."
        )

    spot = market["last_price"]

    # ATM
    df = df.copy()

    df["atm_distance"] = (
        abs(df["strike"] - spot)
    )

    atm_index = df["atm_distance"].idxmin()

    atm_strike = float(
        df.loc[atm_index, "strike"]
    )

    # Change OI
    df["ce_chg_oi"] = (
        df["ce_oi"] - df["ce_prev_oi"]
    )

    df["pe_chg_oi"] = (
        df["pe_oi"] - df["pe_prev_oi"]
    )

    total_ce_oi = df["ce_oi"].sum()
    total_pe_oi = df["pe_oi"].sum()

    if total_ce_oi > 0:
        pcr = total_pe_oi / total_ce_oi
    else:
        pcr = 0

    # OI walls
    ce_wall_row = df.loc[
        df["ce_oi"].idxmax()
    ]

    pe_wall_row = df.loc[
        df["pe_oi"].idxmax()
    ]

    call_resistance = float(
        ce_wall_row["strike"]
    )

    put_support = float(
        pe_wall_row["strike"]
    )

    # Near ATM
    lower = spot * 0.97
    upper = spot * 1.03

    near_atm = df[
        (df["strike"] >= lower)
        & (df["strike"] <= upper)
    ].copy()

    if near_atm.empty:
        near_atm = df.nsmallest(
            5,
            "atm_distance"
        ).copy()

    # ========================================================
    # SCORING
    # ========================================================

    bull = 50.0
    bear = 50.0

    reasons = []

    # PCR
    if pcr >= 1.20:
        bull += 9
        reasons.append(
            "PCR above 1.20 indicates stronger put OI relative to call OI."
        )
    elif pcr <= 0.80:
        bear += 9
        reasons.append(
            "PCR below 0.80 indicates stronger call OI pressure."
        )
    else:
        reasons.append(
            "PCR is in a relatively balanced zone."
        )

    # Change OI
    pe_change = near_atm["pe_chg_oi"].sum()
    ce_change = near_atm["ce_chg_oi"].sum()

    if pe_change > ce_change:
        bull += 8
        reasons.append(
            "Near-ATM put OI addition is stronger than call OI addition."
        )
    elif ce_change > pe_change:
        bear += 8
        reasons.append(
            "Near-ATM call OI addition is stronger than put OI addition."
        )
    else:
        reasons.append(
            "Near-ATM change in OI is relatively balanced."
        )

    # Volume
    pe_volume = near_atm["pe_volume"].sum()
    ce_volume = near_atm["ce_volume"].sum()

    if pe_volume > ce_volume * 1.15:
        bull += 7
        reasons.append(
            "Put-side option volume is stronger near ATM."
        )
    elif ce_volume > pe_volume * 1.15:
        bear += 7
        reasons.append(
            "Call-side option volume is stronger near ATM."
        )

    # OI walls
    if put_support < spot:
        bull += 5
        reasons.append(
            f"Largest put OI wall is below spot at {put_support:.0f}."
        )

    if call_resistance > spot:
        bear += 5
        reasons.append(
            f"Largest call OI wall is above spot at {call_resistance:.0f}."
        )

    # Underlying price action
    pct_change = market["pct_change"]

    if pct_change > 0.50:
        bull += 8
        reasons.append(
            f"Underlying is up {pct_change:.2f}% versus previous close."
        )
    elif pct_change < -0.50:
        bear += 8
        reasons.append(
            f"Underlying is down {abs(pct_change):.2f}% versus previous close."
        )
    else:
        reasons.append(
            "Underlying price change is relatively small."
        )

    # Price vs open
    if market["price_vs_open"] > 0.30:
        bull += 5
        reasons.append(
            "Price is trading above today's opening price."
        )
    elif market["price_vs_open"] < -0.30:
        bear += 5
        reasons.append(
            "Price is trading below today's opening price."
        )

    # Price vs average
    if market["price_vs_average"] > 0.30:
        bull += 4
        reasons.append(
            "Price is trading above the session average."
        )
    elif market["price_vs_average"] < -0.30:
        bear += 4
        reasons.append(
            "Price is trading below the session average."
        )

    # Day range
    if market["range_position"] >= 70:
        bull += 4
        reasons.append(
            "Price is positioned in the upper part of today's range."
        )
    elif market["range_position"] <= 30:
        bear += 4
        reasons.append(
            "Price is positioned in the lower part of today's range."
        )

    bull = min(100, round(bull))
    bear = min(100, round(bear))

    gap = abs(bull - bear)
    maximum = max(bull, bear)

    if maximum >= 72 and gap >= 14:
        decision = "TRADE CANDIDATE"
    elif maximum >= 62 and gap >= 8:
        decision = "WATCH"
    else:
        decision = "NO TRADE"

    if bull > bear:
        direction = "CALL"
    else:
        direction = "PUT"

    # Market status
    market_status = get_market_status(
        market.get("last_trade_time")
    )

    if market_status == "MARKET CLOSED":
        decision = "MARKET CLOSED"

    elif market_status == "DATA STALE":
        decision = "DATA STALE"

    # ========================================================
    # SELECT OPTION
    # ========================================================

    option_type = direction

    candidates = []

    for _, row in df.iterrows():

        if option_type == "CALL":
            ltp = row["ce_ltp"]
            volume = row["ce_volume"]
            bid = row["ce_bid"]
            ask = row["ce_ask"]
            pop = row["ce_pop"]
            delta = row["ce_delta"]
            iv = row["ce_iv"]
            oi = row["ce_oi"]
            chg_oi = row["ce_chg_oi"]
            instrument_key = row["ce_instrument_key"]

        else:
            ltp = row["pe_ltp"]
            volume = row["pe_volume"]
            bid = row["pe_bid"]
            ask = row["pe_ask"]
            pop = row["pe_pop"]
            delta = row["pe_delta"]
            iv = row["pe_iv"]
            oi = row["pe_oi"]
            chg_oi = row["pe_chg_oi"]
            instrument_key = row["pe_instrument_key"]

        if ltp > 0 and volume > 0:
            candidates.append(
                {
                    "strike": float(row["strike"]),
                    "ltp": float(ltp),
                    "volume": float(volume),
                    "bid": float(bid),
                    "ask": float(ask),
                    "pop": float(pop),
                    "delta": float(delta),
                    "iv": float(iv),
                    "oi": float(oi),
                    "chg_oi": float(chg_oi),
                    "instrument_key": instrument_key,
                    "distance": abs(
                        row["strike"] - spot
                    ),
                }
            )

    selected = None

    if candidates:
        # Prefer ATM, then liquidity
        candidates.sort(
            key=lambda x: (
                x["distance"],
                -x["volume"],
            )
        )

        selected = candidates[0]

    # ========================================================
    # TRADE PLAN
    # ========================================================

    trade_plan = None

    if selected:
        ltp = selected["ltp"]
        bid = selected["bid"]
        ask = selected["ask"]

        if bid > 0 and ask > 0:
            entry = (bid + ask) / 2
        else:
            entry = ltp

        if entry > 0 and bid > 0 and ask > 0:
            spread_pct = (
                (ask - bid) / entry
            ) * 100
        else:
            spread_pct = 0

        # Avoid poor liquidity
        if spread_pct > 10:
            decision = "NO TRADE"
            reasons.append(
                f"Option bid/ask spread is wide at {spread_pct:.1f}%."
            )

        profile = RISK_PROFILES["Balanced"]

        stop_loss = entry * (
            1 - profile["sl"]
        )

        target1 = entry * (
            1 + profile["t1"]
        )

        target2 = entry * (
            1 + profile["t2"]
        )

        if direction == "CALL":
            trigger = max(
                spot,
                atm_strike
            )
        else:
            trigger = min(
                spot,
                atm_strike
            )

        if decision == "TRADE CANDIDATE":
            entry_status = (
                "ENTER NOW / CONFIRM TRIGGER"
            )
        elif decision == "WATCH":
            entry_status = (
                "WAIT FOR CONFIRMATION"
            )
        elif decision == "MARKET CLOSED":
            entry_status = "WAIT FOR MARKET OPEN"
        elif decision == "DATA STALE":
            entry_status = "WAIT FOR FRESH DATA"
        else:
            entry_status = "NO TRADE"

        trade_plan = {
            "direction": direction,
            "strike": selected["strike"],
            "entry": entry,
            "sl": stop_loss,
            "target1": target1,
            "target2": target2,
            "pop": selected["pop"],
            "delta": selected["delta"],
            "iv": selected["iv"],
            "oi": selected["oi"],
            "chg_oi": selected["chg_oi"],
            "volume": selected["volume"],
            "bid": selected["bid"],
            "ask": selected["ask"],
            "spread_pct": spread_pct,
            "trigger": trigger,
            "instrument_key":
                selected["instrument_key"],
        }

    return {
        "spot": spot,
        "market": market,
        "pcr": pcr,
        "put_support": put_support,
        "call_resistance": call_resistance,
        "atm": atm_strike,
        "bull": bull,
        "bear": bear,
        "gap": gap,
        "decision": decision,
        "direction": direction,
        "reasons": reasons,
        "trade_plan": trade_plan,
        "market_status": market_status,
        "expiry_days": None,
    }


# ============================================================
# COMPLETE ANALYSIS
# ============================================================

def run_analysis(symbol, risk_profile):
    underlying = find_underlying(symbol)

    underlying_key = underlying.get(
        "instrument_key"
    )

    if not underlying_key:
        raise RuntimeError(
            "Upstox did not return an instrument key."
        )

    trading_symbol = (
        underlying.get("trading_symbol")
        or symbol
    )

    # Underlying quote
    quote = get_full_quote_v3(
        underlying_key
    )

    market = extract_market_context(
        quote
    )

    # Option contracts
    contracts = get_option_contracts(
        underlying_key
    )

    if not contracts:
        raise RuntimeError(
            f"No F&O option contracts found for {trading_symbol}."
        )

    expiry_date = get_nearest_expiry(
        contracts
    )

    if not expiry_date:
        raise RuntimeError(
            "Could not find a valid upcoming expiry."
        )

    expiry_string = expiry_date.strftime(
        "%Y-%m-%d"
    )

    # Chain
    raw_chain = get_option_chain(
        underlying_key,
        expiry_string,
    )

    chain_df = normalize_chain(
        raw_chain
    )

    if chain_df.empty:
        raise RuntimeError(
            "Option chain was received but could not be parsed."
        )

    result = analyze_chain(
        chain_df,
        market,
    )

    result["symbol"] = trading_symbol.upper()
    result["input_symbol"] = symbol.upper()
    result["underlying_key"] = underlying_key
    result["expiry"] = expiry_string

    result["expiry_days"] = (
        expiry_date - now_ist().date()
    ).days

    result["upstox_snapshot_time"] = (
        format_iso_ist(
            market.get("snapshot_time")
        )
    )

    result["underlying_last_trade_time"] = (
        format_ms_ist(
            market.get("last_trade_time")
        )
    )

    result["app_fetch_time"] = (
        now_ist().strftime(
            "%d-%b-%Y %I:%M:%S %p IST"
        )
    )

    # Selected option timestamp
    selected_option_last_trade = "N/A"

    if result.get("trade_plan"):
        selected_key = result["trade_plan"].get(
            "instrument_key"
        )

        if selected_key:
            try:
                selected_quote = get_full_quote_v3(
                    selected_key
                )

                selected_option_last_trade = (
                    format_ms_ist(
                        selected_quote.get(
                            "last_trade_time"
                        )
                    )
                )

            except Exception:
                selected_option_last_trade = "N/A"

    result["selected_option_last_trade"] = (
        selected_option_last_trade
    )

    # Risk profile
    profile = RISK_PROFILES.get(
        risk_profile,
        RISK_PROFILES["Balanced"],
    )

    if result.get("trade_plan"):
        tp = result["trade_plan"]

        entry = tp["entry"]

        tp["sl"] = entry * (
            1 - profile["sl"]
        )

        tp["target1"] = entry * (
            1 + profile["t1"]
        )

        tp["target2"] = entry * (
            1 + profile["t2"]
        )

        tp["risk_profile"] = risk_profile

    return result, chain_df


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        '<div class="sidebar-title">Analyze Instrument</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="sidebar-help">
        Enter an NSE stock or index symbol and click Analyze.
        <br><br>
        Examples: KOTAKBANK, HDFCBANK, RELIANCE,
        ICICIBANK, SBIN, INFY, TCS, NIFTY, BANKNIFTY
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    symbol_input = st.text_input(
        "Stock / Index",
        value=st.session_state.active_symbol,
        placeholder="e.g. KOTAKBANK",
    )

    risk_profile = st.selectbox(
        "Risk Profile",
        list(RISK_PROFILES.keys()),
        index=list(
            RISK_PROFILES.keys()
        ).index(
            st.session_state.active_risk
        ),
    )

    analyze_button = st.button(
        "📊  Analyze",
        type="primary",
        use_container_width=True,
    )

    st.markdown("### Quick Examples")

    quick_symbols = [
        "KOTAKBANK",
        "HDFCBANK",
        "RELIANCE",
        "ICICIBANK",
        "SBIN",
        "INFY",
        "TCS",
        "NIFTY",
        "BANKNIFTY",
    ]

    cols = st.columns(2)

    for i, quick in enumerate(quick_symbols):
        with cols[i % 2]:
            if st.button(
                quick,
                key=f"quick_{quick}",
                use_container_width=True,
            ):
                st.session_state.active_symbol = quick
                st.session_state.active_risk = risk_profile
                st.rerun()

    st.markdown("---")

    st.markdown(
        """
        <div class="info-bar">
        <b>Live data from Upstox</b><br>
        Real-time market quote, option chain,
        OI, Chg OI, IV, Delta, PoP and volume.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    st.caption(
        "No automatic orders are placed by this app."
    )


# ============================================================
# ANALYZE BUTTON
# ============================================================

if analyze_button:

    clean_symbol = symbol_input.strip().upper()

    if not clean_symbol:
        st.session_state.last_error = (
            "Please enter a stock or index."
        )
    else:
        st.session_state.active_symbol = (
            clean_symbol
        )

        st.session_state.active_risk = (
            risk_profile
        )

        st.session_state.last_error = ""

        try:
            with st.spinner(
                f"Fetching live Upstox data for {clean_symbol}..."
            ):
                result, chain_df = run_analysis(
                    clean_symbol,
                    risk_profile,
                )

            st.session_state.active_result = result
            st.session_state.active_chain = chain_df
            st.session_state.last_successful_refresh = (
                now_ist()
            )

        except Exception as e:
            st.session_state.last_error = str(e)

        st.rerun()


# ============================================================
# DISPLAY HELPERS
# ============================================================

def fmt_price(value):
    if value is None:
        return "N/A"

    try:
        return f"₹{float(value):,.2f}"
    except Exception:
        return "N/A"


def fmt_number(value):
    try:
        return f"{float(value):,.0f}"
    except Exception:
        return "0"


def fmt_pct(value):
    try:
        return f"{float(value):.2f}%"
    except Exception:
        return "N/A"


def decision_display(decision, direction):
    if decision == "TRADE CANDIDATE":
        if direction == "CALL":
            return "🟢 CALL — BUY"
        return "🟢 PUT — BUY"

    if decision == "WATCH":
        if direction == "CALL":
            return "🟡 CALL — BUY AFTER CONFIRMATION"
        return "🟡 PUT — BUY AFTER CONFIRMATION"

    if decision == "MARKET CLOSED":
        return "⚪ MARKET CLOSED"

    if decision == "DATA STALE":
        return "🟠 DATA STALE"

    return "⚪ NO TRADE"


# ============================================================
# DISPLAY ANALYSIS
# ============================================================

def display_analysis(result, chain_df):

    symbol = result["symbol"]
    market = result["market"]
    decision = result["decision"]
    direction = result["direction"]

    # --------------------------------------------------------
    # STOCK HERO
    # --------------------------------------------------------

    pct = market["pct_change"]

    if pct > 0:
        change_html = (
            f'<span style="color:#059669;font-weight:700;">'
            f'+{pct:.2f}% '
            f'(+₹{market["net_change"]:.2f})'
            f'</span>'
        )
    elif pct < 0:
        change_html = (
            f'<span style="color:#dc2626;font-weight:700;">'
            f'{pct:.2f}% '
            f'(-₹{abs(market["net_change"]):.2f})'
            f'</span>'
        )
    else:
        change_html = (
            '<span style="color:#64748b;font-weight:700;">'
            '0.00%'
            '</span>'
        )

    if result["market_status"] == "MARKET OPEN":
        status_html = (
            '<span class="status-open">'
            '● MARKET OPEN'
            '</span>'
        )
    elif result["market_status"] == "DATA STALE":
        status_html = (
            '<span class="status-stale">'
            '● DATA STALE'
            '</span>'
        )
    else:
        status_html = (
            '<span class="status-closed">'
            '● MARKET CLOSED'
            '</span>'
        )

    st.markdown(
        f"""
        <div class="stock-hero">
            <div style="display:flex;justify-content:space-between;
                        align-items:center;gap:20px;">

                <div>
                    <div class="stock-name">
                        {symbol.upper()}
                    </div>

                    <div class="stock-subtitle">
                        F&O Options Analysis
                    </div>

                    <div style="margin-top:12px;">
                        {status_html}
                        <span style="font-size:12px;
                                     color:#64748b;
                                     margin-left:8px;">
                            Live Upstox Data
                        </span>
                    </div>
                </div>

                <div style="display:flex;gap:55px;align-items:center;">

                    <div>
                        <div class="hero-price-label">
                            Last Traded
                        </div>

                        <div class="hero-price">
                            {fmt_price(market["last_price"])}
                        </div>

                        <div>
                            {change_html}
                        </div>
                    </div>

                    <div>
                        <div class="hero-price-label">
                            Updated
                        </div>

                        <div class="hero-time">
                            🕐 {result["underlying_last_trade_time"]}
                        </div>
                    </div>

                </div>

            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # MARKET SNAPSHOT
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">📊 Market Snapshot</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">LIVE PRICE</div>
                <div class="metric-value">
                    {fmt_price(market["last_price"])}
                </div>
                <div class="metric-small">
                    {change_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        if result["bull"] > result["bear"]:
            bias = "BULLISH"
        elif result["bear"] > result["bull"]:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">MARKET BIAS</div>
                <div class="metric-value">
                    {bias}
                </div>
                <div class="metric-small">
                    Bull {result["bull"]} /
                    Bear {result["bear"]}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">PCR</div>
                <div class="metric-value purple-value">
                    {result["pcr"]:.2f}
                </div>
                <div class="metric-small">
                    Put OI / Call OI
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">PUT OI SUPPORT</div>
                <div class="metric-value green-value">
                    {result["put_support"]:.0f}
                </div>
                <div class="metric-small">
                    Largest put OI wall
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c5:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">CALL OI RESISTANCE</div>
                <div class="metric-value red-value">
                    {result["call_resistance"]:.0f}
                </div>
                <div class="metric-small">
                    Largest call OI wall
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # DECISION + SCORE
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">🎯 Trade Decision</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.05, 1])

    with left:
        display_decision = decision_display(
            decision,
            direction,
        )

        st.markdown(
            f"""
            <div class="decision-card">
                <div class="decision-label">
                    ENGINE DECISION
                </div>

                <div class="decision-text">
                    {display_decision}
                </div>

                <div class="decision-sub">
                    Signal gap:
                    <b>{result["gap"]} points</b>
                    &nbsp;•&nbsp;
                    Expiry:
                    <b>{result["expiry"]}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:

        bull_width = min(100, result["bull"])
        bear_width = min(100, result["bear"])

        st.markdown(
            f"""
            <div class="score-card">

                <div class="score-row">
                    <div class="score-title">
                        <span>🟢 Bull Score</span>
                        <span>{result["bull"]}/100</span>
                    </div>

                    <div class="score-track">
                        <div class="score-bull"
                             style="width:{bull_width}%;">
                        </div>
                    </div>
                </div>

                <div class="score-row">
                    <div class="score-title">
                        <span>🔴 Bear Score</span>
                        <span>{result["bear"]}/100</span>
                    </div>

                    <div class="score-track">
                        <div class="score-bear"
                             style="width:{bear_width}%;">
                        </div>
                    </div>
                </div>

                <div style="font-size:12px;color:#64748b;">
                    Scores combine price action, PCR,
                    OI, change OI, volume and option-chain structure.
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # TRADE PLAN
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">💰 Trade Plan</div>',
        unsafe_allow_html=True,
    )

    tp = result.get("trade_plan")

    if tp:

        direction_class = (
            "call-direction"
            if tp["direction"] == "CALL"
            else "put-direction"
        )

        st.markdown(
            f"""
            <div class="trade-plan">

                <div class="trade-direction {direction_class}">
                    {("🟢" if tp["direction"] == "CALL"
                      else "🔴")}
                    {tp["direction"]}
                    &nbsp;•&nbsp;
                    {tp["strike"]:.0f} STRIKE
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")

        t1, t2, t3, t4, t5, t6 = st.columns(6)

        trade_values = [
            ("ENTRY", fmt_price(tp["entry"])),
            ("STOP LOSS", fmt_price(tp["sl"])),
            ("TARGET 1", fmt_price(tp["target1"])),
            ("TARGET 2", fmt_price(tp["target2"])),
            ("PoP", f'{tp["pop"]:.0f}%'),
            ("DELTA", f'{tp["delta"]:.3f}'),
        ]

        for col, (label, value) in zip(
            [t1, t2, t3, t4, t5, t6],
            trade_values,
        ):
            with col:
                st.markdown(
                    f"""
                    <div class="trade-box">
                        <div class="trade-box-label">
                            {label}
                        </div>
                        <div class="trade-box-value">
                            {value}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.write("")

        x1, x2, x3, x4 = st.columns(4)

        with x1:
            st.metric(
                "IV",
                f'{tp["iv"]:.2f}%',
            )

        with x2:
            st.metric(
                "OI",
                fmt_number(tp["oi"]),
            )

        with x3:
            st.metric(
                "Change OI",
                fmt_number(tp["chg_oi"]),
            )

        with x4:
            st.metric(
                "Volume",
                fmt_number(tp["volume"]),
            )

        st.markdown(
            f"""
            <div class="info-bar">
                <b>Entry Status:</b>
                {(
                    "🟢 " if decision == "TRADE CANDIDATE"
                    else "🟡 " if decision == "WATCH"
                    else ""
                )}
                {(
                    "ENTER NOW / CONFIRM TRIGGER"
                    if decision == "TRADE CANDIDATE"
                    else "WAIT FOR CONFIRMATION"
                    if decision == "WATCH"
                    else "NO TRADE"
                    if decision == "NO TRADE"
                    else "WAIT FOR MARKET / FRESH DATA"
                )}
                &nbsp;&nbsp;•&nbsp;&nbsp;
                Trigger reference:
                <b>{fmt_price(tp["trigger"])}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        st.markdown(
            """
            <div class="decision-card">
                <div class="decision-text">
                    ⚪ NO TRADE
                </div>
                <div class="decision-sub">
                    No sufficiently liquid option was selected
                    for a trade plan.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # REASONS + MARKET DETAILS
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">💡 Why the Engine Says This</div>',
        unsafe_allow_html=True,
    )

    r1, r2 = st.columns([1.35, 0.85])

    with r1:

        reason_html = ""

        for reason in result["reasons"]:
            reason_html += (
                '<div class="reason-item">'
                f'✓ &nbsp;{reason}'
                '</div>'
            )

        st.markdown(
            f"""
            <div class="reason-card">
                {reason_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with r2:

        st.markdown(
            f"""
            <div class="reason-card">

                <div style="font-size:14px;
                            font-weight:750;
                            color:#173b70;
                            margin-bottom:12px;">
                    ⚡ Market Status
                </div>

                <div style="display:flex;
                            justify-content:space-between;
                            padding:9px 0;
                            border-bottom:1px solid #f1f5f9;">
                    <span>Market</span>
                    <b>{result["market_status"]}</b>
                </div>

                <div style="display:flex;
                            justify-content:space-between;
                            padding:9px 0;
                            border-bottom:1px solid #f1f5f9;">
                    <span>Today's Change</span>
                    <b>{market["pct_change"]:.2f}%</b>
                </div>

                <div style="display:flex;
                            justify-content:space-between;
                            padding:9px 0;
                            border-bottom:1px solid #f1f5f9;">
                    <span>Day Range Position</span>
                    <b>{market["range_position"]:.0f}%</b>
                </div>

                <div style="display:flex;
                            justify-content:space-between;
                            padding:9px 0;">
                    <span>Expiry Days</span>
                    <b>{result["expiry_days"]}</b>
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # OI SUPPORT / RESISTANCE
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">📌 OI Support / Resistance</div>',
        unsafe_allow_html=True,
    )

    o1, o2, o3 = st.columns(3)

    with o1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">
                    PUT OI SUPPORT
                </div>
                <div class="metric-value green-value">
                    {result["put_support"]:.0f}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with o2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">
                    ATM
                </div>
                <div class="metric-value">
                    {result["atm"]:.0f}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with o3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">
                    CALL OI RESISTANCE
                </div>
                <div class="metric-value red-value">
                    {result["call_resistance"]:.0f}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # LIVE OPTION CHAIN
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">🔢 Live Option Chain</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="chain-caption">
            Expiry: <b>{result["expiry"]}</b>
            &nbsp;•&nbsp;
            Spot: <b>{fmt_price(result["spot"])}</b>
            &nbsp;•&nbsp;
            Live data from Upstox
        </div>
        """,
        unsafe_allow_html=True,
    )

    display_df = chain_df.copy()

    spot = result["spot"]

    # Show strikes around ATM
    display_df["distance"] = abs(
        display_df["strike"] - spot
    )

    display_df = display_df.sort_values(
        "distance"
    ).head(15)

    display_df = display_df.sort_values(
        "strike"
    )

    table = pd.DataFrame(
        {
            "CALL LTP": display_df["ce_ltp"],
            "CALL OI": display_df["ce_oi"],
            "CALL Chg OI": display_df["ce_chg_oi"],
            "CALL IV": display_df["ce_iv"],
            "STRIKE": display_df["strike"],
            "PUT LTP": display_df["pe_ltp"],
            "PUT OI": display_df["pe_oi"],
            "PUT Chg OI": display_df["pe_chg_oi"],
            "PUT IV": display_df["pe_iv"],
            "CALL PoP": display_df["ce_pop"],
            "PUT PoP": display_df["pe_pop"],
        }
    )

    table["CALL LTP"] = table["CALL LTP"].map(
        lambda x: f"₹{x:.2f}"
    )

    table["PUT LTP"] = table["PUT LTP"].map(
        lambda x: f"₹{x:.2f}"
    )

    table["CALL OI"] = table["CALL OI"].map(
        lambda x: f"{x:,.0f}"
    )

    table["PUT OI"] = table["PUT OI"].map(
        lambda x: f"{x:,.0f}"
    )

    table["CALL Chg OI"] = table["CALL Chg OI"].map(
        lambda x: f"{x:+,.0f}"
    )

    table["PUT Chg OI"] = table["PUT Chg OI"].map(
        lambda x: f"{x:+,.0f}"
    )

    table["CALL IV"] = table["CALL IV"].map(
        lambda x: f"{x:.2f}%"
    )

    table["PUT IV"] = table["PUT IV"].map(
        lambda x: f"{x:.2f}%"
    )

    table["CALL PoP"] = table["CALL PoP"].map(
        lambda x: f"{x:.0f}%"
    )

    table["PUT PoP"] = table["PUT PoP"].map(
        lambda x: f"{x:.0f}%"
    )

    table["STRIKE"] = table["STRIKE"].map(
        lambda x: f"{x:.0f}"
    )

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=520,
    )

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">🔍 Data & Signal Quality</div>',
        unsafe_allow_html=True,
    )

    q1, q2, q3 = st.columns(3)

    with q1:
        st.info(
            "PoP is taken directly from the "
            "Upstox option-chain response."
        )

    with q2:
        st.info(
            "OI, Change OI, IV, Delta and "
            "Volume come from the live option chain."
        )

    with q3:
        st.info(
            "The app can return NO TRADE when "
            "signals are conflicting or liquidity is poor."
        )

    # --------------------------------------------------------
    # TIMESTAMPS
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="footer-bar">
            🔄 Last successful refresh:
            <b>{result["app_fetch_time"]}</b>
            &nbsp; • &nbsp;
            Underlying last trade:
            <b>{result["underlying_last_trade_time"]}</b>
            &nbsp; • &nbsp;
            Auto refresh every <b>30 seconds</b>
            <br><br>
            This application is for educational and analytical
            purposes only. It does not place orders and is not
            a recommendation to buy or sell securities.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# AUTO REFRESH
# ============================================================

def refresh_analysis():
    if not st.session_state.active_symbol:
        return

    try:
        result, chain_df = run_analysis(
            st.session_state.active_symbol,
            st.session_state.active_risk,
        )

        st.session_state.active_result = result
        st.session_state.active_chain = chain_df
        st.session_state.last_error = ""
        st.session_state.last_successful_refresh = (
            now_ist()
        )

    except Exception as e:
        # Keep previous successful data on temporary errors
        st.session_state.last_error = str(e)


# ============================================================
# MAIN DISPLAY + AUTO REFRESH
# ============================================================

fragment = getattr(st, "fragment", None)

if fragment:

    @fragment(run_every="30s")
    def live_analysis_area():

        if st.session_state.active_result is not None:

            refresh_analysis()

            if (
                st.session_state.active_result is not None
                and st.session_state.active_chain is not None
            ):
                display_analysis(
                    st.session_state.active_result,
                    st.session_state.active_chain,
                )

        elif st.session_state.last_error:

            st.error(
                st.session_state.last_error
            )

        else:

            st.markdown(
                """
                <div class="stock-hero"
                     style="text-align:center;padding:55px 25px;">

                    <div style="font-size:45px;">
                        📈
                    </div>

                    <div class="stock-name"
                         style="font-size:25px;margin-top:10px;">
                        READY FOR ANALYSIS
                    </div>

                    <div class="stock-subtitle"
                         style="margin-top:8px;">
                        Enter a stock or index on the left
                        and click Analyze.
                    </div>

                </div>
                """,
                unsafe_allow_html=True,
            )


    live_analysis_area()

else:

    # Fallback for older Streamlit versions
    if st.session_state.active_result is not None:

        refresh_analysis()

        display_analysis(
            st.session_state.active_result,
            st.session_state.active_chain,
        )

    elif st.session_state.last_error:

        st.error(
            st.session_state.last_error
        )

    else:

        st.info(
            "Enter a stock/index and click Analyze."
        )
