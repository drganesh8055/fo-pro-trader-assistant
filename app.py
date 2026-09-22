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
# CSS
# ============================================================

st.markdown(
    """
<style>
/* =========================================================
   GLOBAL
   ========================================================= */

.stApp {
    background: #f4f7fb;
}

.block-container {
    max-width: 1180px;
    padding: 0.7rem 1rem 2rem 1rem;
}

h1, h2, h3, h4 {
    letter-spacing: -0.02em;
}

[data-testid="stSidebar"] {
    background: #0b1730;
}

[data-testid="stSidebar"] * {
    color: #ffffff !important;
}

[data-testid="stSidebar"] .stButton button {
    background: #ffffff;
    color: #0b1730 !important;
    border: 0;
    font-weight: 700;
}

[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #ffffff;
    color: #111827 !important;
}

/* =========================================================
   TOP HEADER
   ========================================================= */

.fo-header {
    background: linear-gradient(135deg, #0b1730, #14284c);
    border-radius: 18px;
    padding: 20px 24px;
    margin-bottom: 14px;
    box-shadow: 0 8px 25px rgba(15, 23, 42, 0.12);
}

.fo-header-title {
    color: #ffffff;
    font-size: 27px;
    font-weight: 800;
    line-height: 1.15;
}

.fo-header-sub {
    color: #b9c7df;
    font-size: 12px;
    font-weight: 600;
    margin-top: 5px;
    letter-spacing: 0.08em;
}

/* =========================================================
   STATUS
   ========================================================= */

.status-live {
    background: #ecfdf3;
    border: 1px solid #a7f3d0;
    color: #047857;
    border-radius: 14px;
    padding: 13px 16px;
    margin-bottom: 14px;
}

.status-closed {
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    color: #475569;
    border-radius: 14px;
    padding: 13px 16px;
    margin-bottom: 14px;
}

.status-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.status-value {
    font-size: 17px;
    font-weight: 800;
    margin-top: 2px;
}

/* =========================================================
   CARDS
   ========================================================= */

.section-card {
    background: #ffffff;
    border: 1px solid #e5eaf1;
    border-radius: 16px;
    padding: 16px;
    margin-bottom: 14px;
    box-shadow: 0 3px 12px rgba(15, 23, 42, 0.045);
}

.card-title {
    font-size: 14px;
    font-weight: 800;
    color: #172033;
    margin-bottom: 10px;
}

.card-subtitle {
    font-size: 12px;
    color: #64748b;
}

/* =========================================================
   DECISION
   ========================================================= */

.decision-call {
    background: #ecfdf3;
    border: 2px solid #86efac;
    border-radius: 18px;
    padding: 18px;
}

.decision-put {
    background: #fff1f2;
    border: 2px solid #fda4af;
    border-radius: 18px;
    padding: 18px;
}

.decision-neutral {
    background: #f8fafc;
    border: 2px solid #cbd5e1;
    border-radius: 18px;
    padding: 18px;
}

.decision-value {
    font-size: 27px;
    font-weight: 900;
    color: #111827;
}

.decision-sub {
    color: #64748b;
    font-size: 13px;
    margin-top: 4px;
}

/* =========================================================
   METRICS
   ========================================================= */

.metric-card {
    background: #ffffff;
    border: 1px solid #e5eaf1;
    border-radius: 14px;
    padding: 12px 13px;
    min-height: 76px;
}

.metric-label {
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
}

.metric-value {
    color: #111827;
    font-size: 19px;
    font-weight: 800;
    margin-top: 4px;
}

/* =========================================================
   TRADE PLAN
   ========================================================= */

.plan-approved {
    background: #ffffff;
    border: 2px solid #86efac;
    border-radius: 16px;
    padding: 15px;
}

.plan-reference {
    background: #ffffff;
    border: 1px solid #d7dee8;
    border-radius: 16px;
    padding: 15px;
}

.plan-warning {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    color: #9a3412;
    border-radius: 10px;
    padding: 9px 11px;
    margin-top: 10px;
    font-size: 12px;
}

.plan-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
}

.plan-title {
    font-weight: 800;
    color: #172033;
}

.badge {
    border-radius: 999px;
    padding: 4px 9px;
    font-size: 10px;
    font-weight: 800;
}

.badge-green {
    background: #dcfce7;
    color: #166534;
}

.badge-red {
    background: #fee2e2;
    color: #991b1b;
}

.badge-gray {
    background: #e2e8f0;
    color: #475569;
}

/* =========================================================
   OI / CHECKLIST
   ========================================================= */

.check-row {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 7px 0;
    border-bottom: 1px solid #eef2f7;
}

.check-row:last-child {
    border-bottom: 0;
}

.check-good {
    color: #059669;
    font-weight: 900;
}

.check-bad {
    color: #dc2626;
    font-weight: 900;
}

.helper {
    color: #64748b;
    font-size: 12px;
    line-height: 1.45;
}

.oi-row {
    display: flex;
    justify-content: space-between;
    padding: 7px 0;
    border-bottom: 1px solid #eef2f7;
    font-size: 13px;
}

.oi-row:last-child {
    border-bottom: 0;
}

.oi-support {
    color: #059669;
    font-weight: 700;
}

.oi-resistance {
    color: #dc2626;
    font-weight: 700;
}

/* =========================================================
   MOBILE
   ========================================================= */

@media (max-width: 768px) {
    .block-container {
        padding: 0.45rem 0.55rem 1.5rem 0.55rem;
    }

    .fo-header {
        padding: 15px 16px;
        border-radius: 14px;
    }

    .fo-header-title {
        font-size: 22px;
    }

    .fo-header-sub {
        font-size: 9px;
    }

    .decision-value {
        font-size: 23px;
    }
}

/* Remove excessive Streamlit gaps */
div[data-testid="stVerticalBlock"] > div {
    gap: 0.45rem;
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
    """
    Central HTML renderer.
    Every custom HTML block goes through unsafe_allow_html=True.
    """
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
        raise UpstoxError(
            "UPSTOX_ACCESS_TOKEN is missing from Streamlit Secrets."
        )

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
            raise UpstoxError(
                "Upstox request timed out. Please try again shortly."
            )
        except requests.exceptions.RequestException as exc:
            raise UpstoxError(
                f"Network error while contacting Upstox: {exc}"
            )
        finally:
            _LAST_API_REQUEST = time.time()

    if response.status_code == 429:
        raise UpstoxRateLimitError(
            "Upstox rate limit reached. Please wait before refreshing."
        )

    if response.status_code != 200:
        body = response.text[:700]

        raise UpstoxError(
            f"Upstox API {response.status_code}: {body}"
        )

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
        {
            "query": symbol,
            "exchanges": "NSE",
            "segments": "EQ",
        },
        {
            "query": symbol,
            "exchanges": "NSE",
            "segments": "INDEX",
        },
    ]

    candidates = []

    for params in attempts:
        try:
            result = api_get(
                "/v2/instruments/search",
                params=params,
                timeout=15,
            )

            data = result.get("data", [])

            if isinstance(data, list):
                candidates.extend(data)

        except UpstoxError:
            continue

    if not candidates:
        raise UpstoxError(
            f"Could not find NSE instrument for {symbol}."
        )

    exact = [
        x
        for x in candidates
        if str(x.get("trading_symbol", "")).upper() == symbol
    ]

    if exact:
        return exact[0]

    # Prefer NSE index instruments for indices
    index_candidates = [
        x
        for x in candidates
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
    result = api_get(
        "/v2/option/contract",
        params={"instrument_key": underlying_key},
        timeout=20,
    )

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
        params={
            "instrument_key": underlying_key,
            "expiry_date": expiry,
        },
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
    """
    Handles several possible locations used by different
    Upstox response versions.
    """
    candidates = []

    market = extract_market(option)
    greeks = extract_greeks(option)

    for source in (
        option,
        market,
        greeks,
    ):
        for key in (
            "pop",
            "probability_of_profit",
            "probabilityOfProfit",
            "probability",
        ):
            if key in source:
                candidates.append(source.get(key))

    for value in candidates:
        x = safe_float(value)

        if np.isnan(x):
            continue

        # Some APIs return 0-1 instead of 0-100
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

        strike = safe_float(
            row.get("strike_price", row.get("strike"))
        )

        if np.isnan(strike):
            continue

        ce = (
            row.get("call_options")
            or row.get("ce")
            or row.get("call")
            or {}
        )

        pe = (
            row.get("put_options")
            or row.get("pe")
            or row.get("put")
            or {}
        )

        ce_market = extract_market(ce)
        pe_market = extract_market(pe)

        ce_greek = extract_greeks(ce)
        pe_greek = extract_greeks(pe)

        records.append(
            {
                "Strike": strike,

                "CE Key": ce.get(
                    "instrument_key",
                    ce.get("instrument_token", ""),
                ),
                "CE LTP": safe_float(
                    ce_market.get("ltp", ce.get("ltp"))
                ),
                "CE Bid": safe_float(
                    ce_market.get("bid_price", ce.get("bid_price"))
                ),
                "CE Ask": safe_float(
                    ce_market.get("ask_price", ce.get("ask_price"))
                ),
                "CE OI": safe_float(
                    ce_market.get("oi", ce.get("oi"))
                ),
                "CE Prev OI": safe_float(
                    ce_market.get("prev_oi", ce.get("prev_oi"))
                ),
                "CE Chg OI": safe_float(
                    ce_market.get(
                        "change_in_oi",
                        ce_market.get(
                            "chg_oi",
                            ce.get("change_in_oi"),
                        ),
                    )
                ),
                "CE Volume": safe_float(
                    ce_market.get("volume", ce.get("volume"))
                ),
                "CE IV": safe_float(
                    ce_greek.get(
                        "iv",
                        ce_market.get("iv", ce.get("iv")),
                    )
                ),
                "CE Delta": safe_float(
                    ce_greek.get(
                        "delta",
                        ce.get("delta"),
                    )
                ),
                "CE PoP": extract_pop(ce),

                "PE Key": pe.get(
                    "instrument_key",
                    pe.get("instrument_token", ""),
                ),
                "PE LTP": safe_float(
                    pe_market.get("ltp", pe.get("ltp"))
                ),
                "PE Bid": safe_float(
                    pe_market.get("bid_price", pe.get("bid_price"))
                ),
                "PE Ask": safe_float(
                    pe_market.get("ask_price", pe.get("ask_price"))
                ),
                "PE OI": safe_float(
                    pe_market.get("oi", pe.get("oi"))
                ),
                "PE Prev OI": safe_float(
                    pe_market.get("prev_oi", pe.get("prev_oi"))
                ),
                "PE Chg OI": safe_float(
                    pe_market.get(
                        "change_in_oi",
                        pe_market.get(
                            "chg_oi",
                            pe.get("change_in_oi"),
                        ),
                    )
                ),
                "PE Volume": safe_float(
                    pe_market.get("volume", pe.get("volume"))
                ),
                "PE IV": safe_float(
                    pe_greek.get(
                        "iv",
                        pe_market.get("iv", pe.get("iv")),
                    )
                ),
                "PE Delta": safe_float(
                    pe_greek.get(
                        "delta",
                        pe.get("delta"),
                    )
                ),
                "PE PoP": extract_pop(pe),
            }
        )

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
    result = api_get(
        "/v3/market-quote/quotes",
        params={
            "instrument_key": instrument_key,
        },
        timeout=15,
    )

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

    for key in (
        "last_price",
        "last_traded_price",
        "ltp",
    ):
        x = safe_float(quote.get(key))

        if not np.isnan(x):
            return x

    return np.nan


def quote_previous_close(quote):
    if not quote:
        return np.nan

    ohlc = quote.get("ohlc", {})

    if isinstance(ohlc, dict):
        for key in (
            "close",
            "previous_close",
        ):
            x = safe_float(ohlc.get(key))

            if not np.isnan(x):
                return x

    for key in (
        "prev_close",
        "previous_close",
        "close_price",
    ):
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

        records.append(
            {
                "timestamp": c[0],
                "open": safe_float(c[1]),
                "high": safe_float(c[2]),
                "low": safe_float(c[3]),
                "close": safe_float(c[4]),
                "volume": safe_float(c[5]),
                "oi": safe_float(c[6])
                if len(c) > 6
                else np.nan,
            }
        )

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    df = df.dropna(subset=["timestamp", "close"])

    return df.sort_values("timestamp").reset_index(drop=True)


@st.cache_data(ttl=90, show_spinner=False)
def get_5m_candles(instrument_key):
    end = now_ist().date()
    start = end - timedelta(days=15)

    result = api_get(
        f"/v3/historical-candle/{instrument_key}/5minute/"
        f"{end.isoformat()}/{start.isoformat()}",
        timeout=20,
    )

    return candle_to_df(result)


@st.cache_data(ttl=600, show_spinner=False)
def get_30m_candles(instrument_key):
    end = now_ist().date()
    start = end - timedelta(days=90)

    result = api_get(
        f"/v3/historical-candle/{instrument_key}/30minute/"
        f"{end.isoformat()}/{start.isoformat()}",
        timeout=20,
    )

    return candle_to_df(result)


@st.cache_data(ttl=1800, show_spinner=False)
def get_daily_candles(instrument_key):
    end = now_ist().date()
    start = end - timedelta(days=220)

    result = api_get(
        f"/v3/historical-candle/{instrument_key}/day/"
        f"{end.isoformat()}/{start.isoformat()}",
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

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return safe_float(
        tr.rolling(period).mean().iloc[-1]
    )


def calculate_adx(df, period=14):
    if len(df) < period * 2:
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
        100
        * pd.Series(plus_dm, index=df.index)
        .rolling(period)
        .mean()
        / atr
    )

    minus_di = (
        100
        * pd.Series(minus_dm, index=df.index)
        .rolling(period)
        .mean()
        / atr
    )

    denominator = (plus_di + minus_di).replace(0, np.nan)

    dx = (
        100
        * (plus_di - minus_di).abs()
        / denominator
    )

    adx = dx.rolling(period).mean()

    return safe_float(adx.iloc[-1])


def calculate_vwap(df):
    if df.empty:
        return np.nan

    work = df.copy()

    typical = (
        work["high"]
        + work["low"]
        + work["close"]
    ) / 3

    volume = work["volume"].fillna(0)

    denominator = volume.cumsum()

    if denominator.iloc[-1] <= 0:
        return np.nan

    return safe_float(
        (typical * volume).cumsum().iloc[-1]
        / denominator.iloc[-1]
    )


def technicals(df, spot):
    if df.empty or len(df) < 5:
        return {
            "rsi": np.nan,
            "ema20": np.nan,
            "ema50": np.nan,
            "atr": np.nan,
            "trend": "Unknown",
            "adx": np.nan,
            "momentum": np.nan,
            "volume_ratio": np.nan,
            "vwap": np.nan,
        }

    close = df["close"].astype(float)

    ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]

    rsi_series = _rsi(close)

    rsi = (
        safe_float(rsi_series.iloc[-1])
        if len(rsi_series)
        else np.nan
    )

    atr = calculate_atr(df)
    adx = calculate_adx(df)
    vwap = calculate_vwap(df)

    recent = close.tail(min(5, len(close)))

    if len(recent) >= 2:
        momentum = (
            (recent.iloc[-1] - recent.iloc[0])
            / recent.iloc[0]
            * 100
        )
    else:
        momentum = 0

    volume_ratio = np.nan

    if "volume" in df.columns:
        vol = df["volume"].replace(0, np.nan)

        if len(vol) >= 20:
            avg_volume = vol.rolling(20).mean().iloc[-1]

            if safe_float(avg_volume, 0) > 0:
                volume_ratio = (
                    safe_float(vol.iloc[-1])
                    / avg_volume
                )

    spot = safe_float(spot)

    if (
        not np.isnan(spot)
        and not np.isnan(ema20)
        and not np.isnan(ema50)
    ):
        if spot > ema20 > ema50:
            trend = "Bullish"
        elif spot < ema20 < ema50:
            trend = "Bearish"
        else:
            trend = "Sideways"
    else:
        trend = "Unknown"

    return {
        "rsi": rsi,
        "ema20": safe_float(ema20),
        "ema50": safe_float(ema50),
        "atr": safe_float(atr),
        "trend": trend,
        "adx": safe_float(adx),
        "momentum": safe_float(momentum),
        "volume_ratio": safe_float(volume_ratio),
        "vwap": safe_float(vwap),
    }


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
    if chain.empty:
        return None

    if "Strike" not in chain.columns:
        return None

    spot = safe_float(spot)

    if np.isnan(spot):
        return chain.iloc[len(chain) // 2]

    idx = (
        chain["Strike"] - spot
    ).abs().idxmin()

    return chain.loc[idx]


def oi_levels(chain, spot):
    result = {
        "support": np.nan,
        "resistance": np.nan,
        "pcr": np.nan,
        "put_walls": [],
        "call_walls": [],
    }

    if chain.empty:
        return result

    spot = safe_float(spot)

    if np.isnan(spot):
        return result

    local = chain[
        (chain["Strike"] >= spot * 0.90)
        & (chain["Strike"] <= spot * 1.10)
    ].copy()

    if local.empty:
        local = chain.copy()

    # Major support:
    # highest PE OI at/below spot
    support_candidates = local[
        local["Strike"] <= spot
    ].copy()

    support_candidates = support_candidates.dropna(
        subset=["PE OI"]
    )

    if not support_candidates.empty:
        support_candidates = support_candidates.sort_values(
            ["PE OI", "Strike"],
            ascending=[False, True],
        )

        result["support"] = safe_float(
            support_candidates.iloc[0]["Strike"]
        )

    # Major resistance:
    # highest CE OI at/above spot
    resistance_candidates = local[
        local["Strike"] >= spot
    ].copy()

    resistance_candidates = resistance_candidates.dropna(
        subset=["CE OI"]
    )

    if not resistance_candidates.empty:
        resistance_candidates = resistance_candidates.sort_values(
            ["CE OI", "Strike"],
            ascending=[False, True],
        )

        result["resistance"] = safe_float(
            resistance_candidates.iloc[0]["Strike"]
        )

    total_pe = safe_float(
        chain["PE OI"].sum(),
        0,
    )

    total_ce = safe_float(
        chain["CE OI"].sum(),
        0,
    )

    if total_ce > 0:
        result["pcr"] = total_pe / total_ce

    put_walls = (
        chain[
            ["Strike", "PE OI"]
        ]
        .dropna()
        .sort_values(
            "PE OI",
            ascending=False,
        )
        .head(3)
    )

    for _, row in put_walls.iterrows():
        result["put_walls"].append(
            (
                safe_float(row["Strike"]),
                safe_float(row["PE OI"]),
            )
        )

    call_walls = (
        chain[
            ["Strike", "CE OI"]
        ]
        .dropna()
        .sort_values(
            "CE OI",
            ascending=False,
        )
        .head(3)
    )

    for _, row in call_walls.iterrows():
        result["call_walls"].append(
            (
                safe_float(row["Strike"]),
                safe_float(row["CE OI"]),
            )
        )

    return result


# ============================================================
# OPTION SCORING
# ============================================================


def score_option(
    side,
    row,
    tf5,
    tf30,
    daily,
    overall_direction,
    pcr,
    spot,
    support,
    resistance,
):
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

    alignment = timeframe_score(
        side,
        tf5,
        tf30,
        daily,
    )

    score = float(alignment)

    # Momentum / trend strength
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

    # VWAP
    vwap = safe_float(tf5.get("vwap"))

    vwap_gap_pct = np.nan

    if not np.isnan(vwap) and vwap != 0:
        vwap_gap_pct = (
            (spot - vwap)
            / vwap
            * 100
        )

        if side == "CE":
            if spot >= vwap:
                score += 10
        else:
            if spot <= vwap:
                score += 10

    # PCR
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

    # OI change
    if not np.isnan(chg_oi):
        if chg_oi > 0:
            score += 5
        elif chg_oi < 0:
            score += 1

    # Liquidity / quality
    quality = 0

    if oi > 0:
        quality += 5

    if volume >= 1000:
        quality += 5

    spread_pct = np.nan

    if (
        not np.isnan(bid)
        and not np.isnan(ask)
        and ask > 0
        and bid >= 0
    ):
        mid = (bid + ask) / 2

        if mid > 0:
            spread_pct = (
                (ask - bid)
                / mid
                * 100
            )

            if spread_pct <= 1:
                quality += 5
            elif spread_pct <= 2:
                quality += 4
            elif spread_pct <= 3:
                quality += 2

    if not np.isnan(premium) and premium > 0:
        quality += 5

    score += quality

    # Strike placement
    strike_quality = 0
    distance_pct = np.nan

    if not np.isnan(strike) and spot > 0:
        distance_pct = (
            abs(strike - spot)
            / spot
            * 100
        )

        if distance_pct <= 1:
            strike_quality = 10
        elif distance_pct <= 2:
            strike_quality = 8
        elif distance_pct <= 3:
            strike_quality = 5
        elif distance_pct <= 5:
            strike_quality = 2

    score += strike_quality

    # PoP
    if not np.isnan(pop):
        score += min(10, max(0, pop / 10))

    score = int(np.clip(score / 1.10, 0, 100))

    # Room to OI wall
    room_pct = np.nan

    if side == "CE":
        if (
            not np.isnan(resistance)
            and resistance > spot
        ):
            room_pct = (
                (resistance - spot)
                / spot
                * 100
            )
    else:
        if (
            not np.isnan(support)
            and support < spot
        ):
            room_pct = (
                (spot - support)
                / spot
                * 100
            )

    return {
        "score": score,
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
    side,
    strike,
    option_data,
    score_data,
    tf5,
    support,
    resistance,
    atr,
    risk_profile,
):
    risk_profiles = {
        "Conservative": (0.72, 1.25, 1.55),
        "Balanced": (0.70, 1.35, 1.75),
        "Aggressive": (0.65, 1.50, 2.00),
    }

    sl_factor, t1_factor, t2_factor = risk_profiles.get(
        risk_profile,
        risk_profiles["Balanced"],
    )

    premium = safe_float(score_data.get("premium"))

    ask = safe_float(
        option_data.get(
            "CE Ask" if side == "CE" else "PE Ask"
        )
    )

    entry = ask if not np.isnan(ask) and ask > 0 else premium

    if np.isnan(entry) or entry <= 0:
        return None

    sl = entry * sl_factor
    target1 = entry * t1_factor
    target2 = entry * t2_factor

    risk = entry - sl

    rr1 = (
        (target1 - entry) / risk
        if risk > 0
        else np.nan
    )

    rr2 = (
        (target2 - entry) / risk
        if risk > 0
        else np.nan
    )

    spot = safe_float(
        tf5.get("last_spot", np.nan)
    )

    atr = safe_float(atr)

    if np.isnan(atr) or atr <= 0:
        atr = max(
            abs(spot) * 0.0015
            if not np.isnan(spot)
            else 1,
            0.05,
        )

    trigger_buffer = max(
        atr * 0.15,
        abs(spot) * 0.0015
        if not np.isnan(spot)
        else 0.05,
    )

    if side == "CE":
        trigger_level = (
            resistance + trigger_buffer
            if not np.isnan(resistance)
            else spot + trigger_buffer
        )

        trigger = (
            f"Break & hold above {fmt_price(trigger_level)}"
        )

        direction_ok = (
            safe_float(tf5.get("momentum"), 0) > 0
            and tf5.get("trend") != "Bearish"
        )

    else:
        trigger_level = (
            support - trigger_buffer
            if not np.isnan(support)
            else spot - trigger_buffer
        )

        trigger = (
            f"Break & hold below {fmt_price(trigger_level)}"
        )

        direction_ok = (
            safe_float(tf5.get("momentum"), 0) < 0
            and tf5.get("trend") != "Bullish"
        )

    score = safe_float(
        score_data.get("score"),
        0,
    )

    alignment = safe_float(
        score_data.get("alignment"),
        0,
    )

    spread_pct = safe_float(
        score_data.get("spread_pct")
    )

    delta = safe_float(
        score_data.get("delta")
    )

    pop = safe_float(
        score_data.get("pop")
    )

    volume = safe_float(
        score_data.get("volume"),
        0,
    )

    oi = safe_float(
        score_data.get("oi"),
        0,
    )

    vwap = safe_float(
        score_data.get("vwap")
    )

    fail_reasons = []

    if score < 72:
        fail_reasons.append(
            f"Score below 72 ({int(score)}/100)"
        )

    if alignment < 2:
        fail_reasons.append(
            "Insufficient timeframe alignment"
        )

    if not direction_ok:
        fail_reasons.append(
            f"5-minute trend conflicts with "
            f"{'CALL' if side == 'CE' else 'PUT'}"
        )

    if not np.isnan(spread_pct) and spread_pct > 3:
        fail_reasons.append(
            "Option spread above 3%"
        )

    if not np.isnan(delta):
        if not 0.35 <= abs(delta) <= 0.80:
            fail_reasons.append(
                "Delta outside preferred range"
            )

    if np.isnan(pop):
        fail_reasons.append(
            "PoP unavailable from option data"
        )
    elif pop < 55:
        fail_reasons.append(
            f"PoP below 55% ({pop:.1f}%)"
        )

    if volume < 1000:
        fail_reasons.append(
            "Option volume below 1,000"
        )

    if oi <= 0:
        fail_reasons.append(
            "Option OI unavailable"
        )

    if not np.isnan(vwap):
        if side == "CE" and spot < vwap:
            fail_reasons.append(
                "Price below VWAP"
            )

        if side == "PE" and spot > vwap:
            fail_reasons.append(
                "Price above VWAP"
            )

    room_pct = safe_float(
        score_data.get("room_pct")
    )

    if not np.isnan(room_pct) and room_pct < 0.5:
        fail_reasons.append(
            "OI wall too close"
        )

    # Trigger confirmation
    trigger_hit = False

    if not np.isnan(spot):
        if side == "CE":
            trigger_hit = spot >= trigger_level
        else:
            trigger_hit = spot <= trigger_level

    volume_ratio = safe_float(
        tf5.get("volume_ratio")
    )

    volume_confirmed = (
        not np.isnan(volume_ratio)
        and volume_ratio >= 1.10
    )

    rsi = safe_float(
        tf5.get("rsi")
    )

    candle_confirmed = direction_ok

    if side == "CE" and not np.isnan(rsi):
        candle_confirmed = (
            candle_confirmed
            and rsi >= 50
        )

    if side == "PE" and not np.isnan(rsi):
        candle_confirmed = (
            candle_confirmed
            and rsi <= 50
        )

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
            f"Exit if price closes below "
            f"{fmt_price(vwap)} VWAP or SL is hit"
            if not np.isnan(vwap)
            else "Exit if price closes below trigger structure or SL is hit"
        )
    else:
        exit_rule = (
            f"Exit if price closes above "
            f"{fmt_price(vwap)} VWAP or SL is hit"
            if not np.isnan(vwap)
            else "Exit if price closes above trigger structure or SL is hit"
        )

    return {
        "side": side,
        "strike": strike,
        "entry": entry,
        "sl": sl,
        "target1": target1,
        "target2": target2,
        "pop": pop,
        "delta": delta,
        "iv": safe_float(score_data.get("iv")),
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
        "chg_oi": safe_float(score_data.get("chg_oi")),
        "volume": volume,
        "spread_pct": spread_pct,
        "alignment": alignment,
        "vwap": vwap,
        "room_pct": room_pct,
    }


# ============================================================
# F&O MASTER
# ============================================================


@st.cache_data(ttl=3600, show_spinner=False)
def get_fno_underlyings():
    try:
        response = requests.get(
            FNO_MASTER_URL,
            timeout=30,
        )

        if response.status_code != 200:
            raise UpstoxError(
                f"Could not download NSE F&O master file "
                f"(HTTP {response.status_code})."
            )

        raw = gzip.decompress(response.content)

        data = json.loads(raw.decode("utf-8"))

    except UpstoxError:
        raise
    except Exception as exc:
        raise UpstoxError(
            f"Unable to read NSE F&O master file: {exc}"
        )

    if isinstance(data, dict):
        data = data.get("data", data)

    if not isinstance(data, list):
        raise UpstoxError(
            "Invalid NSE F&O master data."
        )

    today = now_ist().date()

    result = {}

    for item in data:
        if not isinstance(item, dict):
            continue

        segment = str(
            item.get("segment", "")
        ).upper()

        instrument_type = str(
            item.get("instrument_type", "")
        ).upper()

        if segment != "NSE_FO":
            continue

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

        symbol = (
            item.get("underlying_symbol")
            or item.get("trading_symbol")
        )

        underlying_key = (
            item.get("underlying_key")
        )

        expiry = item.get("expiry")

        if not symbol or not underlying_key:
            continue

        if expiry:
            try:
                expiry_date = date.fromisoformat(
                    str(expiry)[:10]
                )

                if expiry_date < today:
                    continue
            except Exception:
                pass

        result[str(symbol).upper()] = {
            "symbol": str(symbol).upper(),
            "underlying_key": underlying_key,
            "expiry": str(expiry)[:10]
            if expiry
            else "",
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

        status.caption(
            f"Scanning {i + 1}/{total}: {symbol}"
        )

        try:
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

            # Spot from chain if quote isn't available
            valid_strikes = chain["Strike"].dropna()

            if valid_strikes.empty:
                continue

            spot = safe_float(
                valid_strikes.median()
            )

            levels = oi_levels(
                chain,
                spot,
            )

            # Scanner primarily looks for actual PoP > threshold.
            candidates = []

            for _, row in chain.iterrows():

                for side in ("CE", "PE"):
                    prefix = side

                    pop = safe_float(
                        row.get(
                            f"{prefix} PoP"
                        )
                    )

                    if np.isnan(pop):
                        continue

                    if pop < min_pop:
                        continue

                    volume = safe_float(
                        row.get(
                            f"{prefix} Volume"
                        ),
                        0,
                    )

                    oi = safe_float(
                        row.get(
                            f"{prefix} OI"
                        ),
                        0,
                    )

                    if volume < 1000 or oi <= 0:
                        continue

                    premium = safe_float(
                        row.get(
                            f"{prefix} LTP"
                        )
                    )

                    if np.isnan(premium) or premium <= 0:
                        continue

                    delta = safe_float(
                        row.get(
                            f"{prefix} Delta"
                        )
                    )

                    score = (
                        pop * 0.65
                        + min(volume / 100000, 10)
                        + (
                            min(abs(delta) * 10, 10)
                            if not np.isnan(delta)
                            else 0
                        )
                    )

                    candidates.append(
                        {
                            "Symbol": symbol,
                            "Side": (
                                "CALL BUY"
                                if side == "CE"
                                else "PUT BUY"
                            ),
                            "Strike": safe_float(
                                row["Strike"]
                            ),
                            "Expiry": expiry,
                            "PoP": pop,
                            "Delta": delta,
                            "Premium": premium,
                            "Volume": volume,
                            "OI": oi,
                            "_score": score,
                        }
                    )

            if candidates:
                best = sorted(
                    candidates,
                    key=lambda x: (
                        x["PoP"],
                        x["Volume"],
                        -abs(
                            x["Strike"] - spot
                        ),
                    ),
                    reverse=True,
                )[0]

                results.append(best)

        except (
            UpstoxError,
            UpstoxRateLimitError,
            requests.RequestException,
        ):
            pass

        progress.progress(
            min(
                1.0,
                (i + 1) / max(total, 1),
            )
        )

        # Scanner pacing
        time.sleep(0.80)

    progress.empty()
    status.empty()

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    # One best opportunity per symbol
    df = (
        df.sort_values(
            ["PoP", "Volume"],
            ascending=[False, False],
        )
        .drop_duplicates(
            subset=["Symbol"]
        )
        .head(5)
        .reset_index(drop=True)
    )

    display_cols = [
        "Symbol",
        "Side",
        "Strike",
        "Expiry",
        "PoP",
        "Delta",
        "Premium",
        "Volume",
        "OI",
    ]

    return df[display_cols]


# ============================================================
# UI HELPERS
# ============================================================


def metric_card(label, value):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_plan(plan, approved=False):
    if not plan:
        return

    side_name = (
        "CALL BUY"
        if plan["side"] == "CE"
        else "PUT BUY"
    )

    title = (
        "CALL CANDIDATE"
        if plan["side"] == "CE"
        else "PUT CANDIDATE"
    )

    if approved:
        st.markdown(
            '<div class="plan-approved">',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="plan-reference">',
            unsafe_allow_html=True,
        )

    badge_class = (
        "badge-green"
        if approved
        else "badge-gray"
    )

    badge_text = (
        "APPROVED"
        if approved
        else "NO TRADE"
    )

    st.markdown(
        f"""
        <div class="plan-header">
            <div class="plan-title">
                {title}
            </div>
            <span class="badge {badge_class}">
                {badge_text}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="helper" style="margin-top:8px;">
            {side_name} • Strike
            <b>{fmt_num(plan["strike"], 0)}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        metric_card(
            "Entry",
            fmt_price(plan["entry"]),
        )

    with c2:
        metric_card(
            "Stop Loss",
            fmt_price(plan["sl"]),
        )

    with c3:
        metric_card(
            "Target 1",
            fmt_price(plan["target1"]),
        )

    with c4:
        metric_card(
            "Target 2",
            fmt_price(plan["target2"]),
        )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        metric_card(
            "PoP",
            fmt_pct(plan["pop"]),
        )

    with c2:
        metric_card(
            "Delta",
            fmt_num(plan["delta"], 2),
        )

    with c3:
        metric_card(
            "IV",
            fmt_pct(plan["iv"]),
        )

    with c4:
        metric_card(
            "Risk / Reward",
            (
                f"{fmt_num(plan['rr1'], 2)}R"
                if not np.isnan(
                    safe_float(plan["rr1"])
                )
                else "N/A"
            ),
        )

    st.markdown(
        f"""
        <div class="helper" style="margin-top:10px;">
            <b>Entry Trigger:</b>
            {plan["trigger"]}
        </div>

        <div class="helper" style="margin-top:6px;">
            <b>Exit Rule:</b>
            {plan["exit"]}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if plan["fail_reasons"]:
        reason_text = " • ".join(
            plan["fail_reasons"]
        )

        st.markdown(
            f"""
            <div class="plan-warning">
                <b>Engine checks:</b>
                {reason_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not approved:
        st.caption(
            "REFERENCE ONLY — This candidate does not "
            "represent an approved trade. Follow the "
            "main Trade Decision and trigger conditions."
        )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )


def show_checklist(plan):
    if not plan:
        return

    score = safe_float(
        plan.get("score"),
        0,
    )

    alignment = safe_float(
        plan.get("alignment"),
        0,
    )

    pop = safe_float(
        plan.get("pop")
    )

    spread = safe_float(
        plan.get("spread_pct")
    )

    volume = safe_float(
        plan.get("volume"),
        0,
    )

    items = [
        (
            score >= 72,
            f"Score ≥ 72 ({int(score)}/100)",
        ),
        (
            alignment >= 2,
            f"Timeframe alignment ({int(alignment)}/3)",
        ),
        (
            not np.isnan(pop) and pop >= 55,
            (
                f"PoP ≥ 55% ({pop:.1f}%)"
                if not np.isnan(pop)
                else "PoP ≥ 55% (N/A)"
            ),
        ),
        (
            np.isnan(spread) or spread <= 3,
            (
                f"Spread {spread:.2f}%"
                if not np.isnan(spread)
                else "Spread unavailable"
            ),
        ),
        (
            volume >= 1000,
            f"Volume ≥ 1,000 ({fmt_integer(volume)})",
        ),
        (
            plan.get("trigger_hit", False),
            (
                "Trigger confirmed"
                if plan.get("trigger_hit")
                else "Waiting for trigger"
            ),
        ),
        (
            plan.get("candle_confirmed", False),
            (
                "5-minute confirmation"
                if plan.get("candle_confirmed")
                else "5-minute confirmation pending"
            ),
        ),
        (
            plan.get("volume_confirmed", False),
            (
                "Volume confirmation"
                if plan.get("volume_confirmed")
                else "Volume confirmation pending"
            ),
        ),
    ]

    for ok, text in items:
        icon = "✓" if ok else "!"

        cls = (
            "check-good"
            if ok
            else "check-bad"
        )

        st.markdown(
            f"""
            <div class="check-row">
                <span class="{cls}">
                    {icon}
                </span>
                <span>
                    {text}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )


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

    if st.button(
        "🔎 Scan Full F&O Market",
        use_container_width=True,
    ):
        try:
            with st.spinner(
                "Scanning NSE equity F&O market..."
            ):
                st.session_state[
                    "scanner_results"
                ] = scan_full_fno_pop_market(
                    min_pop=75.0
                )

        except UpstoxRateLimitError as exc:
            st.error(str(exc))

        except UpstoxError as exc:
            st.error(str(exc))

        except Exception as exc:
            st.error(
                f"Scanner error: {exc}"
            )

    scanner_results = st.session_state.get(
        "scanner_results"
    )

    if (
        isinstance(scanner_results, pd.DataFrame)
        and not scanner_results.empty
    ):
        st.dataframe(
            scanner_results,
            use_container_width=True,
            hide_index=True,
            column_config={
                "PoP": st.column_config.NumberColumn(
                    "PoP %",
                    format="%.1f%%",
                ),
                "Delta": st.column_config.NumberColumn(
                    "Delta",
                    format="%.2f",
                ),
                "Premium": st.column_config.NumberColumn(
                    "Premium",
                    format="₹%.2f",
                ),
                "Volume": st.column_config.NumberColumn(
                    "Volume",
                    format="%d",
                ),
                "OI": st.column_config.NumberColumn(
                    "OI",
                    format="%d",
                ),
            },
        )

    st.markdown("---")

    st.markdown(
        "### 🔍 Analyze Instrument"
    )

    default_symbol = st.session_state.get(
        "selected_symbol",
        "KOTAKBANK",
    )

    symbol = st.text_input(
        "Instrument",
        value=default_symbol,
        placeholder="KOTAKBANK / RELIANCE / NIFTY",
    ).upper().strip()

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
        "🚀 Analyze",
        use_container_width=True,
    )

    if analyze_clicked:
        st.session_state[
            "selected_symbol"
        ] = symbol

        st.session_state[
            "run_analysis"
        ] = True

    refresh_clicked = st.button(
        "🔄 Refresh Analysis",
        use_container_width=True,
    )

    if refresh_clicked:
        st.cache_data.clear()
        st.session_state[
            "run_analysis"
        ] = True

    st.checkbox(
        "Auto refresh every 60 seconds",
        key="auto_refresh",
    )

    st.caption(
        "Analysis uses live Upstox REST data. "
        "No simulated market prices are used."
    )


# ============================================================
# OPTIONAL AUTO REFRESH
# ============================================================

if st.session_state.get("auto_refresh"):

    try:
        from streamlit_autorefresh import (
            st_autorefresh,
        )

        st_autorefresh(
            interval=60000,
            key="fo_pro_auto_refresh",
        )

    except Exception:
        # Do not allow optional refresh component
        # to break the trading dashboard.
        pass


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
# DEFAULT ANALYSIS
# ============================================================


if "run_analysis" not in st.session_state:
    st.session_state["run_analysis"] = True


if not st.session_state["run_analysis"]:
    st.info(
        "Enter an instrument in the sidebar and click Analyze."
    )
    st.stop()


symbol = st.session_state.get(
    "selected_symbol",
    "KOTAKBANK",
)

# ============================================================
# MAIN ANALYSIS
# ============================================================


try:

    with st.spinner(
        f"Analyzing {symbol} using live Upstox data..."
    ):

        underlying = search_underlying(
            symbol
        )

        underlying_key = underlying.get(
            "instrument_key"
        )

        if not underlying_key:
            raise UpstoxError(
                "Upstox did not return an instrument key."
            )

        contracts = get_contracts(
            underlying_key
        )

        expiries = available_expiries(
            contracts
        )

        if not expiries:
            raise UpstoxError(
                f"No active option expiry found for {symbol}."
            )

        expiry = expiries[0]

        raw_chain = get_option_chain(
            underlying_key,
            expiry,
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

        # ----------------------------------------------------
        # SPOT
        # ----------------------------------------------------

        quote = get_quote(
            underlying_key
        )

        spot = quote_price(
            quote
        )

        previous_close = quote_previous_close(
            quote
        )

        if np.isnan(spot):

            # Fallback: use underlying midpoint from
            # available strike structure only if quote missing.
            # This is NOT a simulated price.
            spot = safe_float(
                underlying.get(
                    "last_price"
                )
            )

        if np.isnan(spot):
            raise UpstoxError(
                "Live underlying price was not available from Upstox."
            )

        if np.isnan(previous_close):
            previous_close = spot

        change = spot - previous_close

        change_pct = (
            change / previous_close * 100
            if previous_close != 0
            else np.nan
        )

        # ----------------------------------------------------
        # CANDLES
        # ----------------------------------------------------

        try:
            candles_5m = get_5m_candles(
                underlying_key
            )
        except Exception:
            candles_5m = pd.DataFrame()

        try:
            candles_30m = get_30m_candles(
                underlying_key
            )
        except Exception:
            candles_30m = pd.DataFrame()

        try:
            candles_daily = get_daily_candles(
                underlying_key
            )
        except Exception:
            candles_daily = pd.DataFrame()

        if candles_5m.empty:
            tf5 = technicals(
                pd.DataFrame(),
                spot,
            )
        else:
            tf5 = technicals(
                candles_5m,
                spot,
            )

        if candles_30m.empty:
            tf30 = technicals(
                pd.DataFrame(),
                spot,
            )
        else:
            tf30 = technicals(
                candles_30m,
                spot,
            )

        if candles_daily.empty:
            daily = technicals(
                pd.DataFrame(),
                spot,
            )
        else:
            daily = technicals(
                candles_daily,
                spot,
            )

        tf5["last_spot"] = spot

        overall_direction = overall_trend(
            tf5,
            tf30,
            daily,
        )

        levels = oi_levels(
            chain,
            spot,
        )

        support = safe_float(
            levels.get("support")
        )

        resistance = safe_float(
            levels.get("resistance")
        )

        pcr = safe_float(
            levels.get("pcr")
        )

        # ----------------------------------------------------
        # ATM
        # ----------------------------------------------------

        atm_row = nearest_row(
            chain,
            spot,
        )

        if atm_row is None:
            raise UpstoxError(
                "Could not determine ATM option."
            )

        atm_strike = safe_float(
            atm_row["Strike"]
        )

        # ----------------------------------------------------
        # CANDIDATE STRIKES
        # ----------------------------------------------------

        candidate_chain = chain[
            (
                chain["Strike"]
                >= atm_strike
                - (
                    abs(
                        chain["Strike"]
                        .diff()
                        .dropna()
                        .median()
                    )
                    * 5
                    if len(chain) > 2
                    else 50
                )
            )
            & (
                chain["Strike"]
                <= atm_strike
                + (
                    abs(
                        chain["Strike"]
                        .diff()
                        .dropna()
                        .median()
                    )
                    * 5
                    if len(chain) > 2
                    else 50
                )
            )
        ].copy()

        if candidate_chain.empty:
            candidate_chain = chain.copy()

        # ----------------------------------------------------
        # FIND BEST CE / PE
        # ----------------------------------------------------

        ce_best = None
        pe_best = None

        ce_score = -1
        pe_score = -1

        for _, row in candidate_chain.iterrows():

            ce_data = score_option(
                "CE",
                row,
                tf5,
                tf30,
                daily,
                overall_direction,
                pcr,
                spot,
                support,
                resistance,
            )

            pe_data = score_option(
                "PE",
                row,
                tf5,
                tf30,
                daily,
                overall_direction,
                pcr,
                spot,
                support,
                resistance,
            )

            if (
                ce_data["score"] > ce_score
            ):
                ce_score = ce_data["score"]
                ce_best = (
                    row.copy(),
                    ce_data,
                )

            if (
                pe_data["score"] > pe_score
            ):
                pe_score = pe_data["score"]
                pe_best = (
                    row.copy(),
                    pe_data,
                )

        # ----------------------------------------------------
        # PLANS
        # ----------------------------------------------------

        ce_plan = None
        pe_plan = None

        atr = safe_float(
            tf5.get("atr")
        )

        if ce_best is not None:
            ce_row, ce_data = ce_best

            ce_plan = build_plan(
                "CE",
                safe_float(
                    ce_row["Strike"]
                ),
                ce_row,
                ce_data,
                tf5,
                support,
                resistance,
                atr,
                risk_profile,
            )

        if pe_best is not None:
            pe_row, pe_data = pe_best

            pe_plan = build_plan(
                "PE",
                safe_float(
                    pe_row["Strike"]
                ),
                pe_row,
                pe_data,
                tf5,
                support,
                resistance,
                atr,
                risk_profile,
            )

        # ----------------------------------------------------
        # TRADE DECISION
        # ----------------------------------------------------

        best_plan = None

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

            decision_class = (
                "decision-call"
                if decision == "CALL BUY"
                else "decision-neutral"
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

            decision_class = (
                "decision-put"
                if decision == "PUT BUY"
                else "decision-neutral"
            )

            best_plan = pe_plan

        else:
            decision = "NO TRADE"
            decision_class = "decision-neutral"

            if (
                ce_plan
                and pe_plan
            ):
                best_plan = (
                    ce_plan
                    if ce_score >= pe_score
                    else pe_plan
                )
            else:
                best_plan = (
                    ce_plan
                    or pe_plan
                )

        # ----------------------------------------------------
        # CONFIDENCE
        # ----------------------------------------------------

        if best_plan:
            best_score = safe_float(
                best_plan.get("score"),
                0,
            )

            align = safe_float(
                best_plan.get("alignment"),
                0,
            )

            confidence = (
                best_score * 0.70
                + (align / 3.0) * 20
            )

            if overall_direction in {
                "Bullish",
                "Bearish",
            }:
                confidence += 5

            # A NO TRADE signal should never display
            # artificial 100% confidence.
            if decision == "NO TRADE":
                confidence = min(
                    confidence,
                    best_score,
                )

            confidence = int(
                np.clip(
                    confidence,
                    0,
                    100,
                )
            )

        else:
            confidence = 0

        # ====================================================
        # HEADER / SYMBOL
        # ====================================================

        st.markdown(
            f"## {symbol}"
        )

        st.caption(
            f"Expiry: {expiry} • "
            f"Risk Profile: {risk_profile} • "
            f"Updated: "
            f"{now_ist().strftime('%d %b %Y, %I:%M:%S %p IST')}"
        )

        # ====================================================
        # TOP METRICS
        # ====================================================

        c1, c2, c3, c4, c5, c6 = st.columns(6)

        with c1:
            metric_card(
                "Spot",
                fmt_price(spot),
            )

        with c2:
            metric_card(
                "Change",
                fmt_price(change),
            )

        with c3:
            metric_card(
                "Change %",
                fmt_pct(change_pct),
            )

        with c4:
            metric_card(
                "PCR",
                fmt_num(pcr, 2),
            )

        with c5:
            metric_card(
                "Support",
                fmt_price(support),
            )

        with c6:
            metric_card(
                "Resistance",
                fmt_price(resistance),
            )

        # ====================================================
        # TRADE DECISION
        # ====================================================

        st.markdown(
            "### Trade Decision"
        )

        st.markdown(
            f"""
            <div class="{decision_class}">
                <div class="decision-value">
                    {decision}
                </div>

                <div class="decision-sub">
                    {
                        "Conditions are aligned for the current setup."
                        if decision in {"CALL BUY", "PUT BUY"}
                        else
                        "Conditions are not sufficiently aligned for a valid setup."
                    }
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")

        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)

        candidate_strike = (
            best_plan["strike"]
            if best_plan
            else np.nan
        )

        candidate_pop = (
            best_plan["pop"]
            if best_plan
            else np.nan
        )

        candidate_score = (
            best_plan["score"]
            if best_plan
            else 0
        )

        with c1:
            metric_card(
                "Market Bias",
                overall_direction,
            )

        with c2:
            metric_card(
                "Confidence",
                f"{confidence}%",
            )

        with c3:
            metric_card(
                "Candidate Strike",
                fmt_num(
                    candidate_strike,
                    0,
                ),
            )

        with c4:
            metric_card(
                "PoP",
                fmt_pct(candidate_pop),
            )

        with c5:
            metric_card(
                "Score",
                f"{int(candidate_score)}/100",
            )

        with c6:
            metric_card(
                "CALL Score",
                f"{max(0, int(ce_score))}/100",
            )

        with c7:
            metric_card(
                "PUT Score",
                f"{max(0, int(pe_score))}/100",
            )

        # ====================================================
        # TRADE STATUS
        # ====================================================

        st.markdown(
            "### Trade Status"
        )

        status_text = (
            decision
        )

        st.info(
            status_text
        )

        if best_plan:

            st.markdown(
                f"""
                <div class="helper">
                    <b>Entry condition:</b>
                    {best_plan["trigger"]}
                </div>

                <div class="helper" style="margin-top:6px;">
                    <b>Engine state:</b>
                    {best_plan["readiness"]}
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ====================================================
        # CHECKLIST
        # ====================================================

        st.markdown(
            "### Trade Checklist"
        )

        if best_plan:
            show_checklist(
                best_plan
            )
        else:
            st.info(
                "No valid option candidate available."
            )

        # ====================================================
        # TRADE PLAN
        # ====================================================

        st.markdown(
            "### 🎯 Trade Plan"
        )

        if decision in {
            "CALL BUY",
            "PUT BUY",
        } and best_plan:
            show_plan(
                best_plan,
                approved=True,
            )
        else:
            # Still show both candidates when available,
            # but clearly label them reference-only.
            if ce_plan:
                show_plan(
                    ce_plan,
                    approved=False,
                )

            st.write("")

            if pe_plan:
                show_plan(
                    pe_plan,
                    approved=False,
                )

        # ====================================================
        # OI STRUCTURE
        # ====================================================

        st.markdown(
            "### 📍 OI Structure"
        )

        with st.container(border=True):

            st.markdown(
                "#### Support / Resistance OI Map"
            )

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                metric_card(
                    "Current Spot",
                    fmt_price(spot),
                )

            with c2:
                metric_card(
                    "Major Support",
                    fmt_price(support),
                )

            with c3:
                metric_card(
                    "Major Resistance",
                    fmt_price(resistance),
                )

            with c4:
                metric_card(
                    "PCR",
                    fmt_num(pcr, 2),
                )

            st.markdown(
                "##### Top Put OI Walls"
            )

            for strike, oi in levels[
                "put_walls"
            ]:
                st.markdown(
                    f"""
                    <div class="oi-row">
                        <span>
                            {fmt_num(strike, 0)} PE
                        </span>
                        <b class="oi-support">
                            {fmt_integer(oi)}
                        </b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown(
                "##### Top Call OI Walls"
            )

            for strike, oi in levels[
                "call_walls"
            ]:
                st.markdown(
                    f"""
                    <div class="oi-row">
                        <span>
                            {fmt_num(strike, 0)} CE
                        </span>
                        <b class="oi-resistance">
                            {fmt_integer(oi)}
                        </b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ====================================================
        # ENGINE SUMMARY
        # ====================================================

        st.markdown(
            "### 🧠 Engine Summary"
        )

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            metric_card(
                "5M Trend",
                tf5.get(
                    "trend",
                    "Unknown",
                ),
            )

        with c2:
            metric_card(
                "30M Trend",
                tf30.get(
                    "trend",
                    "Unknown",
                ),
            )

        with c3:
            metric_card(
                "Daily Trend",
                daily.get(
                    "trend",
                    "Unknown",
                ),
            )

        with c4:
            metric_card(
                "RSI",
                fmt_num(
                    tf5.get("rsi"),
                    1,
                ),
            )

        # ====================================================
        # TECHNICAL SNAPSHOT
        # ====================================================

        with st.container(border=True):

            st.markdown(
                "#### Technical Snapshot"
            )

            technical_rows = [
                (
                    "5M EMA20",
                    fmt_price(
                        tf5.get("ema20")
                    ),
                ),
                (
                    "5M EMA50",
                    fmt_price(
                        tf5.get("ema50")
                    ),
                ),
                (
                    "5M VWAP",
                    fmt_price(
                        tf5.get("vwap")
                    ),
                ),
                (
                    "5M ATR",
                    fmt_price(
                        tf5.get("atr")
                    ),
                ),
                (
                    "ADX",
                    fmt_num(
                        tf5.get("adx"),
                        1,
                    ),
                ),
                (
                    "Volume Ratio",
                    (
                        f"{fmt_num(tf5.get('volume_ratio'), 2)}x"
                        if not np.isnan(
                            safe_float(
                                tf5.get(
                                    "volume_ratio"
                                )
                            )
                        )
                        else "N/A"
                    ),
                ),
            ]

            for label, value in technical_rows:
                st.markdown(
                    f"""
                    <div class="oi-row">
                        <span>{label}</span>
                        <b>{value}</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ====================================================
        # OPTION QUALITY
        # ====================================================

        with st.container(border=True):

            st.markdown(
                "#### Option Quality"
            )

            option_rows = [
                (
                    "CALL Score",
                    f"{max(0, int(ce_score))}/100",
                ),
                (
                    "CALL PoP",
                    (
                        fmt_pct(
                            ce_plan["pop"]
                        )
                        if ce_plan
                        else "N/A"
                    ),
                ),
                (
                    "PUT Score",
                    f"{max(0, int(pe_score))}/100",
                ),
                (
                    "PUT PoP",
                    (
                        fmt_pct(
                            pe_plan["pop"]
                        )
                        if pe_plan
                        else "N/A"
                    ),
                ),
                (
                    "CALL Delta",
                    (
                        fmt_num(
                            ce_plan["delta"],
                            2,
                        )
                        if ce_plan
                        else "N/A"
                    ),
                ),
                (
                    "PUT Delta",
                    (
                        fmt_num(
                            pe_plan["delta"],
                            2,
                        )
                        if pe_plan
                        else "N/A"
                    ),
                ),
            ]

            for label, value in option_rows:
                st.markdown(
                    f"""
                    <div class="oi-row">
                        <span>{label}</span>
                        <b>{value}</b>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ====================================================
        # LIVE OPTION CHAIN
        # ====================================================

        st.markdown(
            "### 📋 Live Option Chain"
        )

        # Approximately ±5 strikes around ATM
        strikes = (
            chain["Strike"]
            .dropna()
            .unique()
        )

        strikes = sorted(
            strikes,
            key=lambda x: abs(x - spot),
        )[:11]

        display_chain = chain[
            chain["Strike"].isin(strikes)
        ].copy()

        display_chain = display_chain.sort_values(
            "Strike"
        )

        if display_chain.empty:
            st.warning(
                "No option-chain rows are currently available."
            )

        else:

            # Only columns that are useful to the user.
            table = display_chain[
                [
                    "CE OI",
                    "CE Chg OI",
                    "CE Volume",
                    "CE IV",
                    "CE Delta",
                    "CE PoP",
                    "CE LTP",
                    "Strike",
                    "PE LTP",
                    "PE PoP",
                    "PE Delta",
                    "PE IV",
                    "PE Volume",
                    "PE Chg OI",
                    "PE OI",
                ]
            ].copy()

            # Keep nullable values safe.
            integer_columns = [
                "CE OI",
                "CE Chg OI",
                "CE Volume",
                "PE OI",
                "PE Chg OI",
                "PE Volume",
            ]

            for col in integer_columns:
                if col in table.columns:
                    table[col] = pd.to_numeric(
                        table[col],
                        errors="coerce",
                    ).round().astype(
                        "Int64"
                    )

            numeric_columns = [
                "CE IV",
                "CE Delta",
                "CE PoP",
                "CE LTP",
                "Strike",
                "PE LTP",
                "PE PoP",
                "PE Delta",
                "PE IV",
            ]

            for col in numeric_columns:
                if col in table.columns:
                    table[col] = pd.to_numeric(
                        table[col],
                        errors="coerce",
                    )

            st.dataframe(
                table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "CE OI": st.column_config.NumberColumn(
                        "CE OI",
                        format="%d",
                    ),
                    "CE Chg OI": st.column_config.NumberColumn(
                        "CE Chg OI",
                        format="%d",
                    ),
                    "CE Volume": st.column_config.NumberColumn(
                        "CE Volume",
                        format="%d",
                    ),
                    "CE IV": st.column_config.NumberColumn(
                        "CE IV",
                        format="%.1f%%",
                    ),
                    "CE Delta": st.column_config.NumberColumn(
                        "CE Delta",
                        format="%.2f",
                    ),
                    "CE PoP": st.column_config.NumberColumn(
                        "CE PoP",
                        format="%.1f%%",
                    ),
                    "CE LTP": st.column_config.NumberColumn(
                        "CE LTP",
                        format="₹%.2f",
                    ),
                    "Strike": st.column_config.NumberColumn(
                        "Strike",
                        format="%.0f",
                    ),
                    "PE LTP": st.column_config.NumberColumn(
                        "PE LTP",
                        format="₹%.2f",
                    ),
                    "PE PoP": st.column_config.NumberColumn(
                        "PE PoP",
                        format="%.1f%%",
                    ),
                    "PE Delta": st.column_config.NumberColumn(
                        "PE Delta",
                        format="%.2f",
                    ),
                    "PE IV": st.column_config.NumberColumn(
                        "PE IV",
                        format="%.1f%%",
                    ),
                    "PE Volume": st.column_config.NumberColumn(
                        "PE Volume",
                        format="%d",
                    ),
                    "PE Chg OI": st.column_config.NumberColumn(
                        "PE Chg OI",
                        format="%d",
                    ),
                    "PE OI": st.column_config.NumberColumn(
                        "PE OI",
                        format="%d",
                    ),
                },
            )

            st.caption(
                "Option chain is centered around the current "
                "spot and shows approximately ±5 strikes."
            )

        # ====================================================
        # ENGINE NOTES
        # ====================================================

        st.markdown(
            "### ℹ️ Engine Notes"
        )

        st.caption(
            "The engine combines multi-timeframe trend, "
            "RSI, EMA structure, VWAP, OI, PCR, option "
            "liquidity, spread, Delta, PoP and trigger "
            "confirmation. A candidate is shown as "
            "REFERENCE ONLY unless the main Trade Decision "
            "approves it."
        )

        st.caption(
            "PoP is displayed only when supplied by the "
            "live option-chain response. Missing PoP is "
            "treated as unavailable rather than being "
            "artificially set to 99%."
        )

except UpstoxRateLimitError as exc:

    st.error(
        f"⏳ {exc}"
    )

    st.info(
        "The app has stopped making additional requests. "
        "Wait briefly and use Refresh Analysis."
    )

except UpstoxError as exc:

    st.error(
        f"⚠️ {exc}"
    )

except Exception as exc:

    st.error(
        "⚠️ Unexpected application error"
    )

    st.caption(
        f"Technical detail: {type(exc).__name__}: {exc}"
    )
