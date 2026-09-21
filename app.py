import gzip
import json
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None


# ============================================================
# FO PRO TRADER ASSISTANT — LIVE UPSTOX VERSION
#
# Existing UI / trading engine preserved.
#
# NEW VALIDATION LAYER:
# - Every decision is journaled
# - CALL / PUT outcomes are monitored
# - T1 / T2 / SL / TIMEOUT are recorded
# - NO TRADE decisions are recorded
# - Historical performance statistics are calculated
# - Engine score remains separate from actual probability
#
# Hidden validation dashboard:
# Add ?validation=1 to the app URL
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

API_BASE = "https://api.upstox.com"

IST = ZoneInfo("Asia/Kolkata")

JOURNAL_FILE = "signal_journal.csv"

JOURNAL_COLUMNS = [
    "signal_id",
    "timestamp",
    "symbol",
    "underlying_key",
    "expiry",
    "decision",
    "side",
    "strike",
    "spot",
    "option_key",
    "option_ltp_at_signal",
    "entry",
    "sl",
    "target1",
    "target2",
    "upstox_pop",
    "engine_score",
    "engine_confidence",
    "delta",
    "iv",
    "pcr",
    "support",
    "resistance",
    "trend_5m",
    "trend_30m",
    "trend_daily",
    "overall_direction",
    "timeframe_alignment",
    "rsi_5m",
    "rsi_30m",
    "rsi_daily",
    "adx_5m",
    "momentum_5m",
    "volume",
    "spread_pct",
    "readiness",
    "trigger_level",
    "trigger_hit",
    "status",
    "outcome",
    "outcome_timestamp",
    "outcome_price",
    "outcome_pnl_pct",
    "holding_minutes",
    "max_favorable_pct",
    "max_adverse_pct",
    "notes",
]


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>
.stApp { background:#f6f8fb; }
.block-container { padding-top:1rem; padding-bottom:2rem; max-width:1500px; }

.topbar {
    background:linear-gradient(100deg,#102a43,#1f4b73);
    padding:18px 24px;
    border-radius:14px;
    color:white;
    margin-bottom:18px;
}

.topbar-title {
    font-size:27px;
    font-weight:800;
}

.topbar-sub {
    font-size:13px;
    opacity:.82;
    margin-top:3px;
}

.card {
    background:white;
    border:1px solid #e7ebf0;
    border-radius:14px;
    padding:18px;
    margin-bottom:16px;
    box-shadow:0 2px 8px rgba(16,42,67,.04);
}

.section-title {
    font-size:20px;
    font-weight:800;
    color:#182230;
    margin-bottom:12px;
}

.trade-call {
    background:#eaf8ef;
    border:1px solid #bde5c9;
    border-radius:12px;
    padding:14px 16px;
    font-weight:800;
    color:#147a3d;
}

.trade-put {
    background:#fff0f1;
    border:1px solid #f2c5c8;
    border-radius:12px;
    padding:14px 16px;
    font-weight:800;
    color:#b4232f;
}

.trade-neutral {
    background:#f2f4f7;
    border:1px solid #dfe3e8;
    border-radius:12px;
    padding:14px 16px;
    font-weight:800;
    color:#475467;
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# ERROR
# ============================================================

class UpstoxError(RuntimeError):
    pass


# ============================================================
# BASIC HELPERS
# ============================================================

def now_ist():
    return datetime.now(IST)


def get_token():
    try:
        return str(
            st.secrets.get("UPSTOX_ACCESS_TOKEN", "")
        ).strip()
    except Exception:
        return ""


TOKEN = get_token()

if not TOKEN:
    st.error(
        "Upstox access token is not configured. Add UPSTOX_ACCESS_TOKEN "
        "under Streamlit → App settings → Secrets, then reload the app."
    )
    st.stop()


HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}


def api_get(path, params=None, timeout=20):
    try:
        response = requests.get(
            f"{API_BASE}{path}",
            headers=HEADERS,
            params=params,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise UpstoxError(
            f"Network error while contacting Upstox: {exc}"
        ) from exc

    if response.status_code != 200:
        try:
            body = response.json()
            message = (
                body.get("errors")
                or body.get("message")
                or body
            )
        except Exception:
            message = response.text[:500]

        raise UpstoxError(
            f"Upstox API {response.status_code}: {message}"
        )

    try:
        return response.json()
    except Exception as exc:
        raise UpstoxError(
            "Upstox returned invalid JSON."
        ) from exc


def fmt_price(value):
    try:
        x = float(value)
    except Exception:
        return "—"

    if np.isnan(x):
        return "—"

    if abs(x) < 1000:
        return f"₹{x:,.2f}"

    return f"₹{x:,.0f}"


def fmt_num(value):
    try:
        x = float(value)
    except Exception:
        return "—"

    if np.isnan(x):
        return "—"

    return f"{x:,.0f}"


def safe_float(value, default=np.nan):
    try:
        return float(value)
    except Exception:
        return default


def alias_symbol(symbol):
    s = symbol.strip().upper().replace(" ", "")

    aliases = {
        "NIFTY50": "NIFTY",
        "NIFTYBANK": "BANKNIFTY",
        "NIFTYFIN": "FINNIFTY",
        "MIDCAPNIFTY": "MIDCPNIFTY",
    }

    return aliases.get(s, s)


# ============================================================
# UPSTOX DATA
# ============================================================

@st.cache_data(ttl=30, show_spinner=False)
def search_underlying(symbol):
    symbol = alias_symbol(symbol)
    results = []

    for segment in ["EQ", "INDEX"]:
        payload = api_get(
            "/v2/instruments/search",
            params={
                "query": symbol,
                "exchanges": "NSE",
                "segments": segment,
                "page_number": 1,
                "records": 30,
            },
        )

        results.extend(payload.get("data", []))

    if not results:
        raise UpstoxError(
            f"No NSE instrument found for '{symbol}'. "
            "Enter an NSE F&O stock symbol such as HDFCBANK "
            "or an index such as NIFTY."
        )

    exact = [
        item
        for item in results
        if str(
            item.get("trading_symbol", "")
        ).upper() == symbol
    ]

    if exact:
        return exact[0]

    if symbol in {
        "NIFTY",
        "BANKNIFTY",
        "FINNIFTY",
        "MIDCPNIFTY",
    }:
        indexes = [
            x
            for x in results
            if x.get("segment") == "NSE_INDEX"
        ]

        if indexes:
            return indexes[0]

    equities = [
        x
        for x in results
        if x.get("segment") == "NSE_EQ"
    ]

    return equities[0] if equities else results[0]


@st.cache_data(ttl=120, show_spinner=False)
def get_contracts(underlying_key):
    payload = api_get(
        "/v2/option/contract",
        params={
            "instrument_key": underlying_key
        },
        timeout=30,
    )

    contracts = payload.get("data", [])

    if not contracts:
        raise UpstoxError(
            "Upstox returned no option contracts for this instrument."
        )

    return contracts


def available_expiries(contracts):
    today = date.today().isoformat()

    return sorted(
        {
            str(item.get("expiry"))
            for item in contracts
            if item.get("expiry")
            and str(item.get("expiry")) >= today
        }
    )


@st.cache_data(ttl=20, show_spinner=False)
def get_option_chain(underlying_key, expiry):
    payload = api_get(
        "/v2/option/chain",
        params={
            "instrument_key": underlying_key,
            "expiry_date": expiry,
        },
        timeout=30,
    )

    rows = payload.get("data", [])

    if not rows:
        raise UpstoxError(
            f"No option-chain data returned for expiry {expiry}."
        )

    return rows


@st.cache_data(ttl=20, show_spinner=False)
def get_quote(instrument_key):
    payload = api_get(
        "/v3/market-quote/quotes",
        params={
            "instrument_key": instrument_key
        },
    )

    data = payload.get("data", {})

    if not data:
        raise UpstoxError(
            "No live quote returned by Upstox."
        )

    return next(iter(data.values()))


@st.cache_data(ttl=60, show_spinner=False)
def get_intraday_candles(
    instrument_key,
    interval=5,
):
    path = (
        f"/v3/historical-candle/intraday/"
        f"{quote(instrument_key, safe='')}"
        f"/minutes/{interval}"
    )

    payload = api_get(
        path,
        timeout=30,
    )

    candles = (
        payload
        .get("data", {})
        .get("candles", [])
    )

    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(
        candles,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "oi",
        ],
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "oi",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    return (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


@st.cache_data(ttl=180, show_spinner=False)
def get_30m_candles(instrument_key):
    end_date = date.today()
    start_date = end_date - timedelta(days=90)

    path = (
        f"/v3/historical-candle/"
        f"{quote(instrument_key, safe='')}"
        f"/minutes/30/"
        f"{end_date.isoformat()}/"
        f"{start_date.isoformat()}"
    )

    payload = api_get(
        path,
        timeout=30,
    )

    candles = (
        payload
        .get("data", {})
        .get("candles", [])
    )

    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(
        candles,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "oi",
        ],
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "oi",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    return (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_daily_candles(instrument_key):
    end_date = date.today()
    start_date = end_date - timedelta(days=220)

    path = (
        f"/v3/historical-candle/"
        f"{quote(instrument_key, safe='')}"
        f"/days/1/"
        f"{end_date.isoformat()}/"
        f"{start_date.isoformat()}"
    )

    payload = api_get(
        path,
        timeout=30,
    )

    candles = (
        payload
        .get("data", {})
        .get("candles", [])
    )

    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(
        candles,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "oi",
        ],
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "oi",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    return (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


# ============================================================
# TECHNICAL ANALYSIS
# ============================================================

def _rsi(close, period=14):
    delta = close.diff()

    gain = (
        delta
        .clip(lower=0)
        .ewm(
            alpha=1 / period,
            adjust=False,
        )
        .mean()
    )

    loss = (
        -delta
        .clip(upper=0)
        .ewm(
            alpha=1 / period,
            adjust=False,
        )
        .mean()
    )

    rs = gain / loss.replace(0, np.nan)

    return 100 - (
        100 / (1 + rs)
    )


def technicals(df, spot):
    if df.empty or len(df) < 20:
        return {
            "rsi": 50.0,
            "ema20": spot,
            "ema50": spot,
            "atr": spot * 0.01,
            "trend": "Unavailable",
            "adx": 0.0,
            "momentum": 0.0,
            "volume_ratio": 1.0,
            "vwap": spot,
        }

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].fillna(0).astype(float)

    rsi = _rsi(close)

    ema20 = (
        close
        .ewm(
            span=20,
            adjust=False,
        )
        .mean()
    )

    ema50 = (
        close
        .ewm(
            span=50,
            adjust=False,
        )
        .mean()
    )

    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = (
        tr
        .ewm(
            alpha=1 / 14,
            adjust=False,
        )
        .mean()
    )

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where(
            (up_move > down_move)
            & (up_move > 0),
            up_move,
            0.0,
        ),
        index=df.index,
    )

    minus_dm = pd.Series(
        np.where(
            (down_move > up_move)
            & (down_move > 0),
            down_move,
            0.0,
        ),
        index=df.index,
    )

    atr_safe = atr.replace(
        0,
        np.nan,
    )

    plus_di = (
        100
        * plus_dm.ewm(
            alpha=1 / 14,
            adjust=False,
        ).mean()
        / atr_safe
    )

    minus_di = (
        100
        * minus_dm.ewm(
            alpha=1 / 14,
            adjust=False,
        ).mean()
        / atr_safe
    )

    dx = (
        100
        * (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(
            0,
            np.nan,
        )
    )

    adx = (
        dx
        .ewm(
            alpha=1 / 14,
            adjust=False,
        )
        .mean()
    )

    typical = (
        high + low + close
    ) / 3

    if volume.sum() > 0:
        vwap = (
            typical * volume
        ).cumsum() / volume.cumsum().replace(
            0,
            np.nan,
        )

        latest_vwap = safe_float(
            vwap.iloc[-1],
            spot,
        )
    else:
        latest_vwap = spot

    lookback = min(
        10,
        len(close) - 1,
    )

    momentum = (
        (
            close.iloc[-1]
            / close.iloc[-1 - lookback]
            - 1
        )
        * 100
        if lookback > 0
        and close.iloc[-1 - lookback]
        else 0.0
    )

    vol_base = (
        volume
        .rolling(20)
        .median()
        .iloc[-1]
    )

    volume_ratio = (
        volume.iloc[-1] / vol_base
        if vol_base
        and np.isfinite(vol_base)
        else 1.0
    )

    e20 = safe_float(
        ema20.iloc[-1],
        spot,
    )

    e50 = safe_float(
        ema50.iloc[-1],
        spot,
    )

    r = safe_float(
        rsi.iloc[-1],
        50.0,
    )

    a = safe_float(
        atr.iloc[-1],
        spot * 0.01,
    )

    adx_v = safe_float(
        adx.iloc[-1],
        0.0,
    )

    bullish = spot > e20 > e50
    bearish = spot < e20 < e50

    if bullish:
        trend = "Bullish"
    elif bearish:
        trend = "Bearish"
    else:
        trend = "Sideways"

    return {
        "rsi": r,
        "ema20": e20,
        "ema50": e50,
        "atr": max(
            a,
            spot * 0.001,
        ),
        "trend": trend,
        "adx": adx_v,
        "momentum": momentum,
        "volume_ratio": volume_ratio,
        "vwap": latest_vwap,
    }


def overall_trend(
    tf5,
    tf30,
    daily,
):
    trends = [
        tf5.get("trend"),
        tf30.get("trend"),
        daily.get("trend"),
    ]

    bullish = trends.count("Bullish")
    bearish = trends.count("Bearish")

    if bullish >= 2 and bearish == 0:
        return "Bullish", bullish

    if bearish >= 2 and bullish == 0:
        return "Bearish", bearish

    return "Mixed", max(
        bullish,
        bearish,
    )


def timeframe_score(
    side,
    tf5,
    tf30,
    daily,
):
    desired = (
        "Bullish"
        if side == "CE"
        else "Bearish"
    )

    opposite = (
        "Bearish"
        if side == "CE"
        else "Bullish"
    )

    values = [
        tf5,
        tf30,
        daily,
    ]

    score = 0
    alignment = 0

    for tf in values:
        if tf.get("trend") == desired:
            score += 10
            alignment += 1

        elif tf.get("trend") == "Sideways":
            score += 3

        elif tf.get("trend") == opposite:
            score -= 8

    return (
        float(
            np.clip(
                score,
                0,
                30,
            )
        ),
        alignment,
    )


# ============================================================
# OPTION CHAIN
# ============================================================

def oi_levels(
    chain,
    spot,
):
    valid = chain.dropna(
        subset=["Strike"]
    ).copy()

    if valid.empty:
        return (
            spot,
            spot,
            np.nan,
            {
                "put_walls": [],
                "call_walls": [],
            },
        )

    band = valid[
        (valid["Strike"] >= spot * 0.90)
        & (valid["Strike"] <= spot * 1.10)
    ].copy()

    if band.empty:
        band = valid

    below = band[
        band["Strike"] <= spot
    ]

    above = band[
        band["Strike"] >= spot
    ]

    support_row = (
        below.loc[
            below["PE OI"]
            .fillna(0)
            .idxmax()
        ]
        if not below.empty
        else band.loc[
            band["PE OI"]
            .fillna(0)
            .idxmax()
        ]
    )

    resistance_row = (
        above.loc[
            above["CE OI"]
            .fillna(0)
            .idxmax()
        ]
        if not above.empty
        else band.loc[
            band["CE OI"]
            .fillna(0)
            .idxmax()
        ]
    )

    total_call_oi = (
        band["CE OI"]
        .fillna(0)
        .sum()
    )

    total_put_oi = (
        band["PE OI"]
        .fillna(0)
        .sum()
    )

    pcr = (
        total_put_oi / total_call_oi
        if total_call_oi
        else np.nan
    )

    put_walls = (
        band
        .nlargest(3, "PE OI")
        [
            [
                "Strike",
                "PE OI",
                "PE Chg OI",
            ]
        ]
        .to_dict("records")
    )

    call_walls = (
        band
        .nlargest(3, "CE OI")
        [
            [
                "Strike",
                "CE OI",
                "CE Chg OI",
            ]
        ]
        .to_dict("records")
    )

    return (
        float(support_row["Strike"]),
        float(resistance_row["Strike"]),
        pcr,
        {
            "put_walls": put_walls,
            "call_walls": call_walls,
        },
    )


def nearest_row(
    chain,
    strike,
):
    if chain.empty:
        return None

    index = (
        chain["Strike"] - strike
    ).abs().idxmin()

    return chain.loc[index]


def normalize_chain(rows):
    records = []

    for item in rows:
        strike = safe_float(
            item.get("strike_price")
        )

        call = (
            item.get("call_options")
            or {}
        )

        put = (
            item.get("put_options")
            or {}
        )

        call_market = (
            call.get("market_data")
            or {}
        )

        call_greeks = (
            call.get("option_greeks")
            or {}
        )

        put_market = (
            put.get("market_data")
            or {}
        )

        put_greeks = (
            put.get("option_greeks")
            or {}
        )

        call_oi = safe_float(
            call_market.get("oi"),
            0,
        )

        put_oi = safe_float(
            put_market.get("oi"),
            0,
        )

        call_prev_oi = safe_float(
            call_market.get("prev_oi"),
            0,
        )

        put_prev_oi = safe_float(
            put_market.get("prev_oi"),
            0,
        )

        records.append(
            {
                "Strike": strike,

                "CE Key": call.get(
                    "instrument_key"
                ),

                "CE LTP": safe_float(
                    call_market.get("ltp")
                ),

                "CE Bid": safe_float(
                    call_market.get("bid_price")
                ),

                "CE Ask": safe_float(
                    call_market.get("ask_price")
                ),

                "CE OI": call_oi,

                "CE Chg OI": (
                    call_oi
                    - call_prev_oi
                ),

                "CE Volume": safe_float(
                    call_market.get(
                        "volume"
                    ),
                    0,
                ),

                "CE IV": safe_float(
                    call_greeks.get("iv")
                ),

                "CE Delta": safe_float(
                    call_greeks.get("delta")
                ),

                "CE PoP": safe_float(
                    call_greeks.get("pop")
                ),

                "PE Key": put.get(
                    "instrument_key"
                ),

                "PE LTP": safe_float(
                    put_market.get("ltp")
                ),

                "PE Bid": safe_float(
                    put_market.get("bid_price")
                ),

                "PE Ask": safe_float(
                    put_market.get("ask_price")
                ),

                "PE OI": put_oi,

                "PE Chg OI": (
                    put_oi
                    - put_prev_oi
                ),

                "PE Volume": safe_float(
                    put_market.get(
                        "volume"
                    ),
                    0,
                ),

                "PE IV": safe_float(
                    put_greeks.get("iv")
                ),

                "PE Delta": safe_float(
                    put_greeks.get("delta")
                ),

                "PE PoP": safe_float(
                    put_greeks.get("pop")
                ),
            }
        )

    if not records:
        return pd.DataFrame()

    return (
        pd.DataFrame(records)
        .sort_values("Strike")
        .reset_index(drop=True)
    )


# ============================================================
# OPTION SCORING
# ============================================================

def score_option(
    row,
    side,
    spot,
    pcr,
    tf5,
    tf30,
    daily,
    chain,
):
    if side == "CE":
        premium = safe_float(
            row["CE LTP"]
        )
        delta = safe_float(
            row["CE Delta"]
        )
        iv = safe_float(
            row["CE IV"]
        )
        pop = safe_float(
            row["CE PoP"]
        )
        chg_oi = safe_float(
            row["CE Chg OI"],
            0,
        )
        volume = safe_float(
            row["CE Volume"],
            0,
        )
        bid = safe_float(
            row["CE Bid"]
        )
        ask = safe_float(
            row["CE Ask"]
        )
    else:
        premium = safe_float(
            row["PE LTP"]
        )
        delta = safe_float(
            row["PE Delta"]
        )
        iv = safe_float(
            row["PE IV"]
        )
        pop = safe_float(
            row["PE PoP"]
        )
        chg_oi = safe_float(
            row["PE Chg OI"],
            0,
        )
        volume = safe_float(
            row["PE Volume"],
            0,
        )
        bid = safe_float(
            row["PE Bid"]
        )
        ask = safe_float(
            row["PE Ask"]
        )

    desired = (
        "Bullish"
        if side == "CE"
        else "Bearish"
    )

    opposite = (
        "Bearish"
        if side == "CE"
        else "Bullish"
    )

    tf_points, alignment = timeframe_score(
        side,
        tf5,
        tf30,
        daily,
    )

    momentum_points = 0

    tf = tf5

    if tf.get("trend") == desired:
        momentum_points += 6

    if (
        tf.get("rsi", 50) >= 52
        and side == "CE"
    ):
        momentum_points += 3

    if (
        tf.get("rsi", 50) <= 48
        and side == "PE"
    ):
        momentum_points += 3

    if (
        side == "CE"
        and tf.get("momentum", 0) > 0
    ):
        momentum_points += 3

    if (
        side == "PE"
        and tf.get("momentum", 0) < 0
    ):
        momentum_points += 3

    if tf.get("adx", 0) >= 20:
        momentum_points += 3

    momentum_points = min(
        momentum_points,
        15,
    )

    pcr_points = 0

    if np.isfinite(pcr):
        if side == "CE":
            pcr_points = (
                7
                if 0.90 <= pcr <= 1.35
                else 3
                if 0.75 <= pcr < 0.90
                else 0
            )
        else:
            pcr_points = (
                7
                if 0.65 <= pcr <= 1.10
                else 3
                if 1.10 < pcr <= 1.30
                else 0
            )

    if side == "CE":
        oi_points = (
            4 if chg_oi <= 0 else 2
        )
    else:
        oi_points = (
            4 if chg_oi <= 0 else 2
        )

    quality = 0

    abs_delta = (
        abs(delta)
        if np.isfinite(delta)
        else np.nan
    )

    if np.isfinite(abs_delta):
        if 0.45 <= abs_delta <= 0.70:
            quality += 8

        elif (
            0.35 <= abs_delta < 0.45
            or 0.70 < abs_delta <= 0.80
        ):
            quality += 5

    spread_pct = (
        max(ask - bid, 0)
        / max(
            (ask + bid) / 2,
            0.01,
        )
        * 100
        if np.isfinite(ask)
        and np.isfinite(bid)
        and ask > 0
        and bid > 0
        else 999
    )

    if spread_pct <= 1.5:
        quality += 6

    elif spread_pct <= 2.5:
        quality += 4

    elif spread_pct <= 4:
        quality += 2

    if volume > 0:
        quality += 4

    if np.isfinite(iv):
        iv_values = (
            chain[f"{side} IV"]
            .replace(
                [np.inf, -np.inf],
                np.nan,
            )
            .dropna()
        )

        if len(iv_values) >= 5:
            iv_rank = float(
                (
                    iv_values <= iv
                ).mean()
            )

            if 0.15 <= iv_rank <= 0.75:
                quality += 4

            elif iv_rank < 0.90:
                quality += 2

        else:
            quality += 2

    distance_pct = (
        abs(
            float(row["Strike"])
            - spot
        )
        / max(spot, 1)
    )

    if distance_pct <= 0.015:
        distance_points = 5

    elif distance_pct <= 0.03:
        distance_points = 3

    else:
        distance_points = 0

    pop_points = (
        float(
            np.clip(
                (pop - 50) / 2.5,
                0,
                10,
            )
        )
        if np.isfinite(pop)
        else 0
    )

    score = float(
        np.clip(
            tf_points
            + momentum_points
            + pcr_points
            + oi_points
            + quality
            + distance_points
            + pop_points,
            0,
            100,
        )
    )

    return {
        "score": score,
        "premium": premium,
        "delta": delta,
        "iv": iv,
        "pop": pop,
        "chg_oi": chg_oi,
        "volume": volume,
        "spread_pct": spread_pct,
        "alignment": alignment,
        "distance_pct": distance_pct,
        "quality": quality,
    }


# ============================================================
# TRADE PLAN
# ============================================================

def build_plan(
    row,
    side,
    spot,
    support,
    resistance,
    pcr,
    tf5,
    tf30,
    daily,
    risk_profile,
    chain,
):
    if row is None:
        return None

    scored = score_option(
        row,
        side,
        spot,
        pcr,
        tf5,
        tf30,
        daily,
        chain,
    )

    ask = safe_float(
        row[f"{side} Ask"]
    )

    ltp = safe_float(
        row[f"{side} LTP"]
    )

    entry = (
        ask
        if np.isfinite(ask)
        and ask > 0
        else ltp
    )

    if (
        not np.isfinite(entry)
        or entry <= 0
    ):
        return None

    risk_settings = {
        "Conservative": (
            0.72,
            1.25,
            1.55,
        ),
        "Balanced": (
            0.70,
            1.35,
            1.75,
        ),
        "Aggressive": (
            0.65,
            1.50,
            2.00,
        ),
    }

    (
        sl_factor,
        target1_factor,
        target2_factor,
    ) = risk_settings[
        risk_profile
    ]

    sl = round(
        entry * sl_factor,
        2,
    )

    target1 = round(
        entry * target1_factor,
        2,
    )

    target2 = round(
        entry * target2_factor,
        2,
    )

    rr1 = (
        target1 - entry
    ) / max(
        entry - sl,
        0.01,
    )

    rr2 = (
        target2 - entry
    ) / max(
        entry - sl,
        0.01,
    )

    atr = max(
        tf5.get(
            "atr",
            spot * 0.01,
        ),
        spot * 0.001,
    )

    trigger_buffer = max(
        atr * 0.15,
        spot * 0.0015,
    )

    if side == "CE":
        trigger_level = (
            resistance
            + trigger_buffer
        )

        trigger_hit = (
            spot >= trigger_level
        )

        trigger = (
            "Enter only after spot "
            "breaks and sustains above "
            f"{fmt_price(trigger_level)}."
        )

        exit_rule = (
            f"Exit if spot loses support "
            f"{fmt_price(support)} or premium "
            f"hits {fmt_price(sl)}. After Target 1, "
            "book partial profit and trail."
        )

    else:
        trigger_level = (
            support
            - trigger_buffer
        )

        trigger_hit = (
            spot <= trigger_level
        )

        trigger = (
            "Enter only after spot "
            "breaks and sustains below "
            f"{fmt_price(trigger_level)}."
        )

        exit_rule = (
            f"Exit if spot reclaims resistance "
            f"{fmt_price(resistance)} or premium "
            f"hits {fmt_price(sl)}. After Target 1, "
            "book partial profit and trail."
        )

    desired = (
        "Bullish"
        if side == "CE"
        else "Bearish"
    )

    opposite = (
        "Bearish"
        if side == "CE"
        else "Bullish"
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

    if (
        tf5.get("trend") == opposite
        or tf30.get("trend") == opposite
    ):
        hard_fail.append(
            "short-term trend conflict"
        )

    if scored["spread_pct"] > 4:
        hard_fail.append(
            "wide option spread"
        )

    if (
        not np.isfinite(
            scored["delta"]
        )
        or not (
            0.35
            <= abs(scored["delta"])
            <= 0.80
        )
    ):
        hard_fail.append(
            "poor delta"
        )

    if (
        not np.isfinite(
            scored["pop"]
        )
        or scored["pop"] < 55
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
        if not hard_fail
        and trigger_hit
        else
        "WAIT FOR TRIGGER"
        if not hard_fail
        else
        "NO TRADE"
    )

    return {
        "side": side,
        "strike": float(
            row["Strike"]
        ),
        "entry": float(entry),
        "sl": sl,
        "target1": target1,
        "target2": target2,
        "pop": scored["pop"],
        "delta": scored["delta"],
        "iv": scored["iv"],
        "score": scored["score"],
        "rr1": rr1,
        "rr2": rr2,
        "trigger": trigger,
        "trigger_level": trigger_level,
        "trigger_hit": trigger_hit,
        "readiness": readiness,
        "fail_reasons": hard_fail,
        "exit": exit_rule,
        "oi": row[
            f"{side} OI"
        ],
        "chg_oi": scored["chg_oi"],
        "volume": scored["volume"],
        "spread_pct": scored[
            "spread_pct"
        ],
        "alignment": scored[
            "alignment"
        ],
        "option_key": row[
            f"{side} Key"
        ],
        "option_ltp": row[
            f"{side} LTP"
        ],
    }


# ============================================================
# F&O SCANNER
# ============================================================

FNO_MASTER_URL = (
    "https://assets.upstox.com/"
    "market-quote/instruments/"
    "exchange/NSE.json.gz"
)


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def get_fno_underlyings():
    try:
        response = requests.get(
            FNO_MASTER_URL,
            timeout=30,
        )

        response.raise_for_status()

        raw = gzip.decompress(
            response.content
        )

        payload = json.loads(
            raw.decode("utf-8")
        )

    except Exception as exc:
        raise UpstoxError(
            "Unable to load the Upstox NSE F&O "
            f"instrument list: {exc}"
        ) from exc

    if isinstance(payload, dict):
        records = payload.get(
            "data",
            payload.get(
                "instruments",
                [],
            ),
        )
    else:
        records = payload

    today = date.today().isoformat()

    universe = {}

    for item in records:
        if not isinstance(item, dict):
            continue

        if item.get("segment") != "NSE_FO":
            continue

        if item.get(
            "instrument_type"
        ) not in {
            "CE",
            "PE",
            "FUT",
        }:
            continue

        if item.get(
            "underlying_type"
        ) != "EQUITY":
            continue

        expiry = str(
            item.get(
                "expiry",
                "",
            )
        )

        if not expiry:
            continue

        if expiry.isdigit():
            try:
                expiry_date = (
                    datetime.fromtimestamp(
                        int(expiry) / 1000,
                        tz=IST,
                    )
                    .date()
                    .isoformat()
                )
            except Exception:
                continue
        else:
            expiry_date = expiry[:10]

        if expiry_date < today:
            continue

        underlying_key = item.get(
            "underlying_key"
        )

        symbol = str(
            item.get(
                "underlying_symbol"
            )
            or ""
        ).strip().upper()

        if not underlying_key or not symbol:
            continue

        current = universe.get(
            underlying_key
        )

        if (
            current is None
            or expiry_date
            < current["expiry"]
        ):
            universe[
                underlying_key
            ] = {
                "symbol": symbol,
                "underlying_key":
                    underlying_key,
                "expiry": expiry_date,
            }

    return sorted(
        universe.values(),
        key=lambda x: x["symbol"],
    )


def scan_full_fno_pop_market(
    min_pop=75.0,
):
    universe = get_fno_underlyings()

    candidates = []

    scanned = 0
    failed = 0

    progress = st.progress(
        0,
        text="Starting full F&O market scan...",
    )

    for idx, item in enumerate(
        universe,
        start=1,
    ):
        try:
            rows = get_option_chain(
                item["underlying_key"],
                item["expiry"],
            )

            if not rows:
                failed += 1
                continue

            spot_values = [
                safe_float(
                    row.get(
                        "underlying_spot_price"
                    )
                )
                for row in rows
                if np.isfinite(
                    safe_float(
                        row.get(
                            "underlying_spot_price"
                        )
                    )
                )
            ]

            spot_value = (
                spot_values[0]
                if spot_values
                else np.nan
            )

            best_for_stock = None

            for raw in rows:
                strike = safe_float(
                    raw.get(
                        "strike_price"
                    )
                )

                if not np.isfinite(strike):
                    continue

                for side, action in (
                    ("CE", "CALL BUY"),
                    ("PE", "PUT BUY"),
                ):
                    option = (
                        raw.get(
                            "call_options"
                            if side == "CE"
                            else "put_options"
                        )
                        or {}
                    )

                    market = (
                        option.get(
                            "market_data"
                        )
                        or {}
                    )

                    greeks = (
                        option.get(
                            "option_greeks"
                        )
                        or {}
                    )

                    pop = safe_float(
                        greeks.get("pop")
                    )

                    if (
                        not np.isfinite(pop)
                        or pop <= min_pop
                    ):
                        continue

                    ltp = safe_float(
                        market.get("ltp")
                    )

                    ask = safe_float(
                        market.get(
                            "ask_price"
                        )
                    )

                    bid = safe_float(
                        market.get(
                            "bid_price"
                        )
                    )

                    volume = safe_float(
                        market.get(
                            "volume"
                        ),
                        0,
                    )

                    oi = safe_float(
                        market.get("oi"),
                        0,
                    )

                    delta = safe_float(
                        greeks.get("delta")
                    )

                    iv = safe_float(
                        greeks.get("iv")
                    )

                    entry = (
                        ask
                        if np.isfinite(ask)
                        and ask > 0
                        else ltp
                    )

                    if (
                        not np.isfinite(entry)
                        or entry <= 0
                    ):
                        continue

                    distance = (
                        abs(
                            strike
                            - spot_value
                        )
                        / max(
                            spot_value,
                            1,
                        )
                        if np.isfinite(
                            spot_value
                        )
                        else 999
                    )

                    sl = round(
                        entry * 0.70,
                        2,
                    )

                    target1 = round(
                        entry * 1.40,
                        2,
                    )

                    target2 = round(
                        entry * 1.80,
                        2,
                    )

                    candidate = {
                        "Stock":
                            item["symbol"],
                        "Trade":
                            action,
                        "Strike":
                            strike,
                        "Expiry":
                            item["expiry"],
                        "PoP":
                            pop,
                        "Entry":
                            entry,
                        "SL":
                            sl,
                        "Target1":
                            target1,
                        "Target2":
                            target2,
                        "Exit":
                            "Exit at SL or Target 2; "
                            "trail after Target 1",
                        "LTP":
                            ltp,
                        "Bid":
                            bid,
                        "Ask":
                            ask,
                        "Delta":
                            delta,
                        "IV":
                            iv,
                        "Volume":
                            volume,
                        "OI":
                            oi,
                        "distance":
                            distance,
                    }

                    if (
                        best_for_stock is None
                        or (
                            candidate["PoP"],
                            candidate["Volume"],
                            -candidate[
                                "distance"
                            ],
                        )
                        >
                        (
                            best_for_stock[
                                "PoP"
                            ],
                            best_for_stock[
                                "Volume"
                            ],
                            -best_for_stock[
                                "distance"
                            ],
                        )
                    ):
                        best_for_stock = candidate

            if best_for_stock is not None:
                candidates.append(
                    best_for_stock
                )

            scanned += 1

        except Exception:
            failed += 1

        progress.progress(
            idx / max(
                len(universe),
                1,
            ),
            text=(
                "Scanning F&O market: "
                f"{idx}/{len(universe)} stocks"
            ),
        )

    progress.empty()

    candidates.sort(
        key=lambda x: (
            -x["PoP"],
            -x["Volume"],
            x["distance"],
        )
    )

    return (
        candidates[:5],
        len(universe),
        scanned,
        failed,
    )


# ============================================================
# VALIDATION JOURNAL
# ============================================================

def empty_journal():
    return pd.DataFrame(
        columns=JOURNAL_COLUMNS
    )


def load_journal():
    if not os.path.exists(
        JOURNAL_FILE
    ):
        return empty_journal()

    try:
        df = pd.read_csv(
            JOURNAL_FILE
        )

        for column in JOURNAL_COLUMNS:
            if column not in df.columns:
                df[column] = np.nan

        return df[
            JOURNAL_COLUMNS
        ].copy()

    except Exception:
        return empty_journal()


def save_journal(df):
    temp_file = (
        JOURNAL_FILE
        + ".tmp"
    )

    try:
        df[
            JOURNAL_COLUMNS
        ].to_csv(
            temp_file,
            index=False,
        )

        os.replace(
            temp_file,
            JOURNAL_FILE,
        )

    except Exception:
        try:
            if os.path.exists(
                temp_file
            ):
                os.remove(
                    temp_file
                )
        except Exception:
            pass


def normalize_signal_value(
    value
):
    if value is None:
        return ""

    if isinstance(
        value,
        (float, np.floating),
    ):
        if np.isnan(value):
            return ""

        return round(
            float(value),
            6,
        )

    return str(value)


def make_signal_signature(
    symbol,
    expiry,
    decision,
    best_plan,
    spot,
):
    if best_plan is None:
        plan_part = "NONE"
    else:
        plan_part = (
            f"{best_plan.get('side')}_"
            f"{best_plan.get('strike')}_"
            f"{best_plan.get('entry')}_"
            f"{best_plan.get('score'):.2f}_"
            f"{best_plan.get('readiness')}"
        )

    return (
        f"{symbol}|"
        f"{expiry}|"
        f"{decision}|"
        f"{plan_part}|"
        f"{round(float(spot), 2)}"
    )


def generate_signal_id(
    signature,
):
    import hashlib

    return hashlib.sha256(
        signature.encode(
            "utf-8"
        )
    ).hexdigest()[:20]


def journal_decision(
    *,
    symbol,
    underlying_key,
    expiry,
    decision,
    best_plan,
    spot,
    pcr,
    support,
    resistance,
    tf5,
    tf30,
    daily,
    overall_direction,
    overall_alignment,
    confidence,
):
    df = load_journal()

    if best_plan:
        side = best_plan.get(
            "side"
        )

        option_ltp = safe_float(
            best_plan.get(
                "option_ltp"
            )
        )

        option_key = best_plan.get(
            "option_key"
        )

        strike = safe_float(
            best_plan.get(
                "strike"
            )
        )

        entry = safe_float(
            best_plan.get(
                "entry"
            )
        )

        sl = safe_float(
            best_plan.get(
                "sl"
            )
        )

        target1 = safe_float(
            best_plan.get(
                "target1"
            )
        )

        target2 = safe_float(
            best_plan.get(
                "target2"
            )
        )

        pop = safe_float(
            best_plan.get(
                "pop"
            )
        )

        score = safe_float(
            best_plan.get(
                "score"
            )
        )

        delta = safe_float(
            best_plan.get(
                "delta"
            )
        )

        iv = safe_float(
            best_plan.get(
                "iv"
            )
        )

        volume = safe_float(
            best_plan.get(
                "volume"
            ),
            0,
        )

        spread_pct = safe_float(
            best_plan.get(
                "spread_pct"
            )
        )

        readiness = best_plan.get(
            "readiness"
        )

        trigger_level = safe_float(
            best_plan.get(
                "trigger_level"
            )
        )

        trigger_hit = bool(
            best_plan.get(
                "trigger_hit"
            )
        )

    else:
        side = ""
        option_ltp = np.nan
        option_key = ""
        strike = np.nan
        entry = np.nan
        sl = np.nan
        target1 = np.nan
        target2 = np.nan
        pop = np.nan
        score = 0
        delta = np.nan
        iv = np.nan
        volume = 0
        spread_pct = np.nan
        readiness = ""
        trigger_level = np.nan
        trigger_hit = False

    signature = make_signal_signature(
        symbol,
        expiry,
        decision,
        best_plan,
        spot,
    )

    signal_id = generate_signal_id(
        signature
    )

    # Same signal already recorded.
    if not df.empty:
        existing = df[
            df["signal_id"].astype(str)
            == str(signal_id)
        ]

        if not existing.empty:
            return False

    timestamp = now_ist()

    row = {
        "signal_id":
            signal_id,

        "timestamp":
            timestamp.isoformat(),

        "symbol":
            symbol,

        "underlying_key":
            underlying_key,

        "expiry":
            expiry,

        "decision":
            decision,

        "side":
            side,

        "strike":
            strike,

        "spot":
            spot,

        "option_key":
            option_key,

        "option_ltp_at_signal":
            option_ltp,

        "entry":
            entry,

        "sl":
            sl,

        "target1":
            target1,

        "target2":
            target2,

        "upstox_pop":
            pop,

        "engine_score":
            score,

        "engine_confidence":
            confidence,

        "delta":
            delta,

        "iv":
            iv,

        "pcr":
            pcr,

        "support":
            support,

        "resistance":
            resistance,

        "trend_5m":
            tf5.get("trend"),

        "trend_30m":
            tf30.get("trend"),

        "trend_daily":
            daily.get("trend"),

        "overall_direction":
            overall_direction,

        "timeframe_alignment":
            overall_alignment,

        "rsi_5m":
            tf5.get("rsi"),

        "rsi_30m":
            tf30.get("rsi"),

        "rsi_daily":
            daily.get("rsi"),

        "adx_5m":
            tf5.get("adx"),

        "momentum_5m":
            tf5.get("momentum"),

        "volume":
            volume,

        "spread_pct":
            spread_pct,

        "readiness":
            readiness,

        "trigger_level":
            trigger_level,

        "trigger_hit":
            trigger_hit,

        "status":
            (
                "OPEN"
                if decision
                in {
                    "CALL BUY",
                    "PUT BUY",
                }
                and np.isfinite(entry)
                else "CLOSED"
            ),

        "outcome":
            "",

        "outcome_timestamp":
            "",

        "outcome_price":
            np.nan,

        "outcome_pnl_pct":
            np.nan,

        "holding_minutes":
            np.nan,

        "max_favorable_pct":
            np.nan,

        "max_adverse_pct":
            np.nan,

        "notes":
            (
                "NO TRADE decision"
                if decision
                == "NO TRADE"
                else ""
            ),
    }

    new_df = pd.DataFrame(
        [row],
        columns=JOURNAL_COLUMNS,
    )

    df = pd.concat(
        [
            df,
            new_df,
        ],
        ignore_index=True,
    )

    save_journal(df)

    return True


def get_option_live_price(
    option_key,
):
    if not option_key:
        return np.nan

    try:
        quote_data = get_quote(
            option_key
        )

        return safe_float(
            quote_data.get(
                "last_price"
            )
        )

    except Exception:
        return np.nan


def update_open_trade_outcomes(
    current_symbol=None,
):
    df = load_journal()

    if df.empty:
        return df

    open_mask = (
        df["status"].astype(str)
        == "OPEN"
    )

    open_df = df[
        open_mask
    ].copy()

    if current_symbol:
        open_df = open_df[
            open_df["symbol"].astype(str)
            == str(current_symbol)
        ]

    if open_df.empty:
        return df

    changed = False

    for idx in open_df.index:
        row = df.loc[idx]

        option_key = str(
            row.get(
                "option_key",
                ""
            )
        )

        if not option_key:
            continue

        current_price = (
            get_option_live_price(
                option_key
            )
        )

        if not np.isfinite(
            current_price
        ):
            continue

        entry = safe_float(
            row.get("entry")
        )

        sl = safe_float(
            row.get("sl")
        )

        t1 = safe_float(
            row.get("target1")
        )

        t2 = safe_float(
            row.get("target2")
        )

        if (
            not np.isfinite(entry)
            or entry <= 0
        ):
            continue

        timestamp = pd.to_datetime(
            row.get("timestamp"),
            errors="coerce",
        )

        if pd.isna(timestamp):
            timestamp = pd.Timestamp(
                now_ist()
            )

        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize(
                IST
            )

        now_ts = pd.Timestamp(
            now_ist()
        )

        holding_minutes = (
            now_ts - timestamp
        ).total_seconds() / 60

        pnl_pct = (
            (
                current_price
                - entry
            )
            / entry
            * 100
        )

        old_favorable = safe_float(
            row.get(
                "max_favorable_pct"
            ),
            0,
        )

        old_adverse = safe_float(
            row.get(
                "max_adverse_pct"
            ),
            0,
        )

        new_favorable = max(
            old_favorable,
            pnl_pct,
        )

        new_adverse = min(
            old_adverse,
            pnl_pct,
        )

        outcome = ""

        if (
            np.isfinite(sl)
            and current_price <= sl
        ):
            outcome = "SL HIT"

        elif (
            np.isfinite(t2)
            and current_price >= t2
        ):
            outcome = "T2 HIT"

        elif (
            np.isfinite(t1)
            and current_price >= t1
        ):
            outcome = "T1 HIT"

        # Prevent trades remaining open forever.
        # Four market hours is deliberately longer than a normal intraday setup.
        elif holding_minutes >= 240:
            outcome = "TIMEOUT"

        df.at[
            idx,
            "max_favorable_pct"
        ] = new_favorable

        df.at[
            idx,
            "max_adverse_pct"
        ] = new_adverse

        if outcome:
            df.at[
                idx,
                "status"
            ] = "CLOSED"

            df.at[
                idx,
                "outcome"
            ] = outcome

            df.at[
                idx,
                "outcome_timestamp"
            ] = now_ist().isoformat()

            df.at[
                idx,
                "outcome_price"
            ] = current_price

            df.at[
                idx,
                "outcome_pnl_pct"
            ] = pnl_pct

            df.at[
                idx,
                "holding_minutes"
            ] = holding_minutes

            changed = True

        else:
            df.at[
                idx,
                "holding_minutes"
            ] = holding_minutes

            changed = True

    if changed:
        save_journal(df)

    return df


# ============================================================
# VALIDATION STATISTICS
# ============================================================

def calculate_validation_stats(
    df,
):
    if df.empty:
        return {
            "actionable": 0,
            "closed": 0,
            "open": 0,
            "wins": 0,
            "losses": 0,
            "timeouts": 0,
            "win_rate": np.nan,
            "avg_win": np.nan,
            "avg_loss": np.nan,
            "expectancy": np.nan,
            "profit_factor": np.nan,
        }

    actionable = df[
        df["decision"].astype(str)
        .isin(
            [
                "CALL BUY",
                "PUT BUY",
            ]
        )
    ].copy()

    closed = actionable[
        actionable["status"].astype(str)
        == "CLOSED"
    ].copy()

    open_trades = actionable[
        actionable["status"].astype(str)
        == "OPEN"
    ].copy()

    wins = closed[
        closed["outcome"].astype(str)
        .isin(
            [
                "T1 HIT",
                "T2 HIT",
            ]
        )
    ]

    losses = closed[
        closed["outcome"].astype(str)
        == "SL HIT"
    ]

    timeouts = closed[
        closed["outcome"].astype(str)
        == "TIMEOUT"
    ]

    decisive = pd.concat(
        [
            wins,
            losses,
        ],
        ignore_index=True,
    )

    if not decisive.empty:
        win_rate = (
            len(wins)
            / len(decisive)
            * 100
        )
    else:
        win_rate = np.nan

    win_values = pd.to_numeric(
        wins["outcome_pnl_pct"],
        errors="coerce",
    ).dropna()

    loss_values = pd.to_numeric(
        losses["outcome_pnl_pct"],
        errors="coerce",
    ).dropna()

    avg_win = (
        win_values.mean()
        if not win_values.empty
        else np.nan
    )

    avg_loss = (
        loss_values.mean()
        if not loss_values.empty
        else np.nan
    )

    if (
        np.isfinite(avg_win)
        and np.isfinite(avg_loss)
    ):
        expectancy = (
            (
                len(wins)
                / max(
                    len(decisive),
                    1,
                )
            )
            * avg_win
            +
            (
                len(losses)
                / max(
                    len(decisive),
                    1,
                )
            )
            * avg_loss
        )
    else:
        expectancy = np.nan

    gross_profit = (
        win_values.sum()
        if not win_values.empty
        else 0
    )

    gross_loss = abs(
        loss_values.sum()
    ) if not loss_values.empty else 0

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else np.nan
    )

    return {
        "actionable":
            len(actionable),

        "closed":
            len(closed),

        "open":
            len(open_trades),

        "wins":
            len(wins),

        "losses":
            len(losses),

        "timeouts":
            len(timeouts),

        "win_rate":
            win_rate,

        "avg_win":
            avg_win,

        "avg_loss":
            avg_loss,

        "expectancy":
            expectancy,

        "profit_factor":
            profit_factor,
    }


def score_bucket_stats(
    df,
):
    if df.empty:
        return pd.DataFrame()

    actionable = df[
        df["decision"].astype(str)
        .isin(
            [
                "CALL BUY",
                "PUT BUY",
            ]
        )
        & (
            df["status"].astype(str)
            == "CLOSED"
        )
    ].copy()

    if actionable.empty:
        return pd.DataFrame()

    actionable[
        "engine_score"
    ] = pd.to_numeric(
        actionable["engine_score"],
        errors="coerce",
    )

    def bucket(score):
        if not np.isfinite(score):
            return "Unknown"

        if score < 60:
            return "<60"

        if score < 70:
            return "60–69"

        if score < 80:
            return "70–79"

        if score < 90:
            return "80–89"

        return "90–100"

    actionable[
        "Score Band"
    ] = actionable[
        "engine_score"
    ].apply(bucket)

    actionable[
        "Win"
    ] = actionable[
        "outcome"
    ].isin(
        [
            "T1 HIT",
            "T2 HIT",
        ]
    )

    result = (
        actionable
        .groupby(
            "Score Band",
            dropna=False,
        )
        .agg(
            Signals=(
                "signal_id",
                "count",
            ),
            Wins=(
                "Win",
                "sum",
            ),
        )
        .reset_index()
    )

    result[
        "Actual Win Rate"
    ] = (
        result["Wins"]
        / result["Signals"]
        * 100
    ).round(1)

    order = [
        "<60",
        "60–69",
        "70–79",
        "80–89",
        "90–100",
        "Unknown",
    ]

    result[
        "order"
    ] = result[
        "Score Band"
    ].map(
        {
            x: i
            for i, x in enumerate(order)
        }
    )

    return (
        result
        .sort_values("order")
        .drop(columns="order")
    )


# ============================================================
# HIDDEN VALIDATION DASHBOARD
# ============================================================

def show_validation_dashboard():
    st.markdown(
        """
        <div class="topbar">
            <div class="topbar-title">
                🧪 F&O Signal Validation
            </div>
            <div class="topbar-sub">
                Measurement layer for actual outcomes — not a prediction guarantee
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df = load_journal()

    st.markdown(
        "### Validation Dataset"
    )

    if df.empty:
        st.info(
            "No decisions have been recorded yet. "
            "Use the normal app during market hours. "
            "The validation layer will automatically build the dataset."
        )
        return

    stats = calculate_validation_stats(
        df
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Actionable Signals",
        stats["actionable"],
    )

    c2.metric(
        "Closed",
        stats["closed"],
    )

    c3.metric(
        "Open",
        stats["open"],
    )

    c4.metric(
        "Actual Win Rate",
        (
            f"{stats['win_rate']:.1f}%"
            if np.isfinite(
                stats["win_rate"]
            )
            else "—"
        ),
    )

    c5.metric(
        "Expectancy",
        (
            f"{stats['expectancy']:.2f}%"
            if np.isfinite(
                stats["expectancy"]
            )
            else "—"
        ),
    )

    st.markdown(
        "### Outcome Summary"
    )

    o1, o2, o3, o4 = st.columns(4)

    o1.metric(
        "T1/T2 Wins",
        stats["wins"],
    )

    o2.metric(
        "SL Losses",
        stats["losses"],
    )

    o3.metric(
        "Timeouts",
        stats["timeouts"],
    )

    o4.metric(
        "Profit Factor",
        (
            f"{stats['profit_factor']:.2f}"
            if np.isfinite(
                stats["profit_factor"]
            )
            else "—"
        ),
    )

    st.markdown(
        "### Score vs Actual Outcome"
    )

    bucket_df = score_bucket_stats(
        df
    )

    if bucket_df.empty:
        st.info(
            "Not enough closed trades to measure "
            "score calibration yet."
        )
    else:
        st.dataframe(
            bucket_df,
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(
        "### Recent Recorded Decisions"
    )

    display = df.copy()

    display = display.sort_values(
        "timestamp",
        ascending=False,
    )

    columns = [
        "timestamp",
        "symbol",
        "decision",
        "strike",
        "spot",
        "entry",
        "sl",
        "target1",
        "target2",
        "upstox_pop",
        "engine_score",
        "engine_confidence",
        "outcome",
        "outcome_pnl_pct",
        "status",
    ]

    display = display[
        [
            c
            for c in columns
            if c in display.columns
        ]
    ].head(100)

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )

    csv_data = df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "Download Signal Journal CSV",
        data=csv_data,
        file_name=(
            "signal_journal.csv"
        ),
        mime="text/csv",
    )

    st.markdown(
        "### Interpretation"
    )

    st.warning(
        "Do not interpret Engine Confidence as a probability. "
        "It is currently a rule-based score. "
        "Only Actual Win Rate calculated from completed observations "
        "is empirical evidence about this engine."
    )


# ============================================================
# VALIDATION MODE
# ============================================================

validation_mode = (
    str(
        st.query_params.get(
            "validation",
            "0",
        )
    ).lower()
    in {
        "1",
        "true",
        "yes",
    }
)

if validation_mode:
    try:
        validation_symbol = alias_symbol(
            st.session_state.get(
                "symbol",
                "",
            )
        )

        if validation_symbol:
            update_open_trade_outcomes(
                validation_symbol
            )

    except Exception:
        pass

    show_validation_dashboard()
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "### 🔥 Top 5 F&O PoP Scanner"
    )

    st.caption(
        "Scans the full NSE equity F&O market "
        "for trades with PoP > 75%."
    )

    scan_market = st.button(
        "🔎 Scan Full F&O Market",
        use_container_width=True,
        type="primary",
    )

    if scan_market:
        try:
            with st.spinner(
                "Scanning the full F&O market..."
            ):
                (
                    results,
                    total,
                    scanned,
                    failed,
                ) = scan_full_fno_pop_market(
                    75.0
                )

            st.session_state[
                "fno_pop_results"
            ] = results

            st.session_state[
                "fno_pop_scan_info"
            ] = (
                total,
                scanned,
                failed,
            )

            st.session_state[
                "fno_pop_scan_time"
            ] = (
                now_ist()
                .strftime("%H:%M:%S")
            )

        except UpstoxError as exc:
            st.session_state[
                "fno_pop_results"
            ] = []

            st.error(
                str(exc)
            )

        except Exception as exc:
            st.session_state[
                "fno_pop_results"
            ] = []

            st.error(
                f"F&O scan failed: {exc}"
            )

    pop_results = st.session_state.get(
        "fno_pop_results",
        [],
    )

    scan_info = st.session_state.get(
        "fno_pop_scan_info"
    )

    scan_time = st.session_state.get(
        "fno_pop_scan_time"
    )

    if pop_results:

        st.success(
            f"Top {len(pop_results)} "
            "trades with PoP > 75%"
        )

        if scan_info:
            (
                total,
                scanned,
                failed,
            ) = scan_info

            st.caption(
                f"Scanned {scanned}/{total} "
                f"F&O stocks • "
                f"{failed} unavailable"
            )

        if scan_time:
            st.caption(
                f"Last scan: {scan_time} IST"
            )

        scanner_display = pd.DataFrame(
            [
                {
                    "Stock":
                        row["Stock"],

                    "Trade":
                        row["Trade"],

                    "Strike":
                        int(row["Strike"]),

                    "PoP":
                        f"{row['PoP']:.1f}%",

                    "Entry":
                        fmt_price(
                            row["Entry"]
                        ),

                    "SL":
                        fmt_price(
                            row["SL"]
                        ),

                    "Target1":
                        fmt_price(
                            row["Target1"]
                        ),

                    "Target2":
                        fmt_price(
                            row["Target2"]
                        ),

                    "Exit":
                        row["Exit"],
                }
                for row in pop_results
            ]
        )

        st.dataframe(
            scanner_display,
            use_container_width=True,
            hide_index=True,
            height=min(
                360,
                58
                + len(
                    scanner_display
                ) * 52,
            ),
        )

    elif (
        "fno_pop_results"
        in st.session_state
    ):
        st.info(
            "No F&O stock currently has "
            "an option trade with PoP > 75%."
        )

    st.divider()

    st.markdown(
        "### 🔎 Analyze Instrument"
    )

    symbol_label = (
        "Stock / Index"
    )

    symbol_default = (
        st.session_state.get(
            "symbol",
            "KOTAKBANK",
        )
    )

    symbol_placeholder = (
        "e.g. KOTAKBANK, "
        "HDFCBANK, NIFTY"
    )

    symbol_input = st.text_input(
        symbol_label,
        value=symbol_default,
        placeholder=symbol_placeholder,
        label_visibility="collapsed",
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

    analyze = st.button(
        "🔍 Analyze",
        type="primary",
        use_container_width=True,
    )

    refresh = st.button(
        "↻ Refresh Live Data",
        use_container_width=True,
    )

    if st_autorefresh is not None:
        auto_refresh = st.checkbox(
            "Auto refresh every 30 seconds",
            value=True,
        )

        if auto_refresh:
            st_autorefresh(
                interval=30_000,
                key="upstox_live_refresh",
            )

    st.divider()

    st.caption(
        "LIVE DATA • Powered by Upstox"
    )

    st.caption(
        "No simulated market values are used."
    )


# ============================================================
# USER ACTIONS
# ============================================================

if analyze:
    st.session_state[
        "symbol"
    ] = alias_symbol(
        symbol_input
    )

    st.rerun()


if refresh:
    st.cache_data.clear()
    st.rerun()


symbol = alias_symbol(
    st.session_state.get(
        "symbol",
        symbol_input
        or "KOTAKBANK",
    )
)


# ============================================================
# LIVE DATA
# ============================================================

try:

    with st.spinner(
        f"Fetching live Upstox data for {symbol}..."
    ):

        underlying = search_underlying(
            symbol
        )

        underlying_key = underlying[
            "instrument_key"
        ]

        contracts = get_contracts(
            underlying_key
        )

        expiries = available_expiries(
            contracts
        )

        if not expiries:
            raise UpstoxError(
                "Upstox did not return an "
                "upcoming F&O expiry for this instrument."
            )

        selected_expiry = expiries[0]

        raw_chain = get_option_chain(
            underlying_key,
            selected_expiry,
        )

        chain = normalize_chain(
            raw_chain
        )

        if chain.empty:
            raise UpstoxError(
                "Option chain was empty "
                "after normalization."
            )

        quote_data = get_quote(
            underlying_key
        )

        spot = safe_float(
            quote_data.get(
                "last_price"
            )
        )

        previous_close = safe_float(
            quote_data.get(
                "prev_close_price"
            ),
            spot,
        )

        net_change = safe_float(
            quote_data.get(
                "net_change"
            ),
            spot - previous_close,
        )

        change_pct = (
            net_change
            / previous_close
            * 100
            if previous_close
            else 0
        )

        candles = get_daily_candles(
            underlying_key
        )

        candles_30m = get_30m_candles(
            underlying_key
        )

        candles_5m = get_intraday_candles(
            underlying_key,
            5,
        )

        daily_tech = technicals(
            candles,
            spot,
        )

        tf30 = technicals(
            candles_30m,
            spot,
        )

        tf5 = technicals(
            candles_5m,
            spot,
        )

        tech = daily_tech

except UpstoxError as exc:
    st.error(
        str(exc)
    )
    st.stop()

except Exception as exc:
    st.error(
        f"Unexpected error while loading live data: {exc}"
    )
    st.stop()


# ============================================================
# OPTION ANALYSIS
# ============================================================

(
    support,
    resistance,
    pcr,
    oi_wall_info,
) = oi_levels(
    chain,
    spot,
)


atm_index = (
    chain["Strike"] - spot
).abs().idxmin()

atm_strike = float(
    chain.loc[
        atm_index,
        "Strike",
    ]
)


candidate_rows = chain.iloc[
    max(
        0,
        atm_index - 5,
    ):
    min(
        len(chain),
        atm_index + 6,
    )
]


ce_candidates = []
pe_candidates = []

for _, row in candidate_rows.iterrows():

    ce_candidates.append(
        (
            score_option(
                row,
                "CE",
                spot,
                pcr,
                tf5,
                tf30,
                daily_tech,
                chain,
            )["score"],
            row,
        )
    )

    pe_candidates.append(
        (
            score_option(
                row,
                "PE",
                spot,
                pcr,
                tf5,
                tf30,
                daily_tech,
                chain,
            )["score"],
            row,
        )
    )


best_ce_row = max(
    ce_candidates,
    key=lambda x: x[0],
    default=(0, None),
)[1]

best_pe_row = max(
    pe_candidates,
    key=lambda x: x[0],
    default=(0, None),
)[1]


ce_plan = build_plan(
    best_ce_row,
    "CE",
    spot,
    support,
    resistance,
    pcr,
    tf5,
    tf30,
    daily_tech,
    risk_profile,
    chain,
)


pe_plan = build_plan(
    best_pe_row,
    "PE",
    spot,
    support,
    resistance,
    pcr,
    tf5,
    tf30,
    daily_tech,
    risk_profile,
    chain,
)


ce_score = (
    ce_plan["score"]
    if ce_plan
    else 0
)

pe_score = (
    pe_plan["score"]
    if pe_plan
    else 0
)


overall_direction, overall_alignment = (
    overall_trend(
        tf5,
        tf30,
        daily_tech,
    )
)


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

    decision_class = (
        "trade-call"
        if decision == "CALL BUY"
        else "trade-neutral"
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
    }
):

    decision = (
        "PUT BUY"
        if pe_plan["readiness"]
        == "READY"
        else "WAIT FOR TRIGGER"
    )

    decision_class = (
        "trade-put"
        if decision == "PUT BUY"
        else "trade-neutral"
    )

    best_plan = pe_plan


else:

    decision = "NO TRADE"

    decision_class = (
        "trade-neutral"
    )

    best_plan = (
        ce_plan
        if ce_score >= pe_score
        else pe_plan
    )


# ============================================================
# CONFIDENCE
#
# IMPORTANT:
# This remains a descriptive engine score.
# It is NOT a calibrated probability.
# ============================================================

best_score = (
    best_plan["score"]
    if best_plan
    else 0
)

best_alignment = (
    best_plan["alignment"]
    if best_plan
    else 0
)

confidence = int(
    np.clip(
        best_score * 0.70
        + (
            best_alignment / 3
        ) * 20
        + (
            5
            if overall_direction
            in {
                "Bullish",
                "Bearish",
            }
            else 0
        ),
        0,
        100,
    )
)


updated = quote_data.get(
    "timestamp",
    now_ist().isoformat(),
)


# ============================================================
# VALIDATION — UPDATE EXISTING OPEN SIGNALS
#
# This happens silently.
# It does NOT alter the normal UI.
# ============================================================

try:
    update_open_trade_outcomes(
        symbol
    )
except Exception:
    pass


# ============================================================
# VALIDATION — RECORD CURRENT DECISION
#
# Every decision is measurable.
# Duplicate identical signals are ignored.
# ============================================================

try:
    journal_decision(
        symbol=symbol,
        underlying_key=underlying_key,
        expiry=selected_expiry,
        decision=decision,
        best_plan=best_plan,
        spot=spot,
        pcr=pcr,
        support=support,
        resistance=resistance,
        tf5=tf5,
        tf30=tf30,
        daily=daily_tech,
        overall_direction=overall_direction,
        overall_alignment=overall_alignment,
        confidence=confidence,
    )
except Exception:
    pass


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
<div class="topbar">
    <div class="topbar-title">
        📊 FO PRO Trader Assistant
    </div>
    <div class="topbar-sub">
        Options Analysis • Powered by Upstox • Live market data
    </div>
</div>
""",
    unsafe_allow_html=True,
)


h1, h2, h3 = st.columns(
    [2.2, 1.2, 1.0]
)


with h1:
    st.markdown(
        f"## {symbol} — F&O Options Analysis"
    )


with h2:

    st.markdown(
        "**Last Traded**"
    )

    st.markdown(
        f"""
        <span style='font-size:25px;
        font-weight:800'>
        {fmt_price(spot)}
        </span>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        f"{net_change:+.2f} "
        f"({change_pct:+.2f}%)"
    )


with h3:

    st.markdown(
        "**Data Status**"
    )

    market_now = now_ist()

    market_open = (
        market_now.weekday() < 5
        and (
            market_now.hour,
            market_now.minute,
        ) >= (
            9,
            15,
        )
        and (
            market_now.hour,
            market_now.minute,
        ) < (
            15,
            30,
        )
    )

    if market_open:

        st.markdown(
            """
            <div style="
                background:#16a34a;
                color:#ffffff;
                padding:10px 16px;
                border-radius:8px;
                font-weight:700;
                font-size:15px;
                text-align:center;
                width:100%;
                box-sizing:border-box;
                margin:6px 0 10px 0;
            ">
                ● LIVE DATA
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        st.markdown(
            """
            <div style="
                background:#dc2626;
                color:#ffffff;
                padding:10px 16px;
                border-radius:8px;
                font-weight:700;
                font-size:15px;
                text-align:center;
                width:100%;
                box-sizing:border-box;
                margin:6px 0 10px 0;
            ">
                ● MARKET CLOSED
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.caption(
        f"Expiry: {selected_expiry}"
    )


# ============================================================
# MARKET SNAPSHOT
# ============================================================

st.markdown(
    '<div class="card">',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-title">'
    '📊 Market Snapshot'
    '</div>',
    unsafe_allow_html=True,
)


m1, m2, m3, m4, m5, m6 = st.columns(
    6
)


m1.metric(
    "Live Price",
    fmt_price(spot),
    f"{net_change:+.2f} "
    f"({change_pct:+.2f}%)",
)

m2.metric(
    "Bias",
    tech["trend"],
)

m3.metric(
    "PCR",
    (
        f"{pcr:.2f}"
        if not np.isnan(pcr)
        else "—"
    ),
)

m4.metric(
    "Support",
    fmt_price(support),
)

m5.metric(
    "Resistance",
    fmt_price(resistance),
)

m6.metric(
    "RSI",
    f"{tech['rsi']:.1f}",
)


st.markdown(
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# TRADE DECISION
# ============================================================

st.markdown(
    '<div class="card">',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-title">'
    '🎯 Trade Decision'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="{decision_class}">'
    f'Decision: {decision}'
    f'</div>',
    unsafe_allow_html=True,
)


d1, d2, d3, d4 = st.columns(
    4
)


d1.metric(
    "Bull Score",
    f"{ce_score:.0f}/100",
)

d2.metric(
    "Bear Score",
    f"{pe_score:.0f}/100",
)

d3.metric(
    "Trend",
    overall_direction,
)

d4.metric(
    "Confidence",
    f"{confidence}/100",
)


st.markdown(
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# TRADE PLAN
# ============================================================

st.markdown(
    '<div class="card">',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-title">'
    '🎯 Trade Plan'
    '</div>',
    unsafe_allow_html=True,
)


plan_rows = []

for label, plan in [
    ("CALL", ce_plan),
    ("PUT", pe_plan),
]:

    if plan:

        plan_rows.append(
            {
                "Side":
                    label,

                "Strike":
                    int(
                        plan["strike"]
                    ),

                "Entry (₹)":
                    round(
                        plan["entry"],
                        2,
                    ),

                "SL (₹)":
                    round(
                        plan["sl"],
                        2,
                    ),

                "Target 1 (₹)":
                    round(
                        plan["target1"],
                        2,
                    ),

                "Target 2 (₹)":
                    round(
                        plan["target2"],
                        2,
                    ),

                "PoP":
                    (
                        f"{plan['pop']:.1f}%"
                        if not np.isnan(
                            plan["pop"]
                        )
                        else "—"
                    ),

                "Delta":
                    (
                        round(
                            plan["delta"],
                            3,
                        )
                        if not np.isnan(
                            plan["delta"]
                        )
                        else "—"
                    ),

                "IV":
                    (
                        f"{plan['iv']:.1f}%"
                        if not np.isnan(
                            plan["iv"]
                        )
                        else "—"
                    ),

                "R:R T1":
                    f"1:{plan['rr1']:.2f}",

                "Readiness":
                    plan["readiness"],
            }
        )


if plan_rows:

    st.dataframe(
        pd.DataFrame(
            plan_rows
        ),
        use_container_width=True,
        hide_index=True,
    )


if best_plan:

    st.markdown(
        "### Entry / Exit Rules"
    )

    e1, e2 = st.columns(
        2
    )

    with e1:

        st.markdown(
            "**Entry Trigger**"
        )

        st.write(
            best_plan[
                "trigger"
            ]
        )

        st.markdown(
            "**Entry**"
        )

        st.write(
            fmt_price(
                best_plan[
                    "entry"
                ]
            )
        )

        st.markdown(
            "**Stop Loss**"
        )

        st.write(
            fmt_price(
                best_plan[
                    "sl"
                ]
            )
        )

        st.markdown(
            "**Target 1 / Target 2**"
        )

        st.write(
            f"{fmt_price(best_plan['target1'])} / "
            f"{fmt_price(best_plan['target2'])}"
        )

    with e2:

        st.markdown(
            "**Exit Rule**"
        )

        st.write(
            best_plan[
                "exit"
            ]
        )

        st.markdown(
            "**PoP**"
        )

        st.write(
            (
                f"{best_plan['pop']:.1f}%"
                if not np.isnan(
                    best_plan["pop"]
                )
                else
                "Not returned by Upstox"
            )
        )

        st.markdown(
            "**Risk / Reward**"
        )

        st.write(
            f"Target 1: "
            f"1:{best_plan['rr1']:.2f} | "
            f"Target 2: "
            f"1:{best_plan['rr2']:.2f}"
        )


st.caption(
    "PoP is the Probability of Profit returned "
    "by Upstox for the option contract; it is "
    "not a guarantee of profit."
)


st.markdown(
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🏆 Best Trade",
        "🔎 Live Option Chain",
        "📊 Market Analysis",
        "🧠 How Engine Thinks",
    ]
)


# ============================================================
# TAB 1
# ============================================================

with tab1:

    if decision == "NO TRADE":

        st.info(
            "NO TRADE: the live conditions do not "
            "currently meet the directional quality gate. "
            "Wait for the entry trigger instead of forcing "
            "an option position."
        )

    elif best_plan:

        st.success(
            f"{decision} | "
            f"Strike {best_plan['strike']:.0f} | "
            f"Entry {fmt_price(best_plan['entry'])} | "
            f"SL {fmt_price(best_plan['sl'])} | "
            f"T1 {fmt_price(best_plan['target1'])} | "
            f"T2 {fmt_price(best_plan['target2'])}"
        )

    st.markdown(
        "### Why the Engine Says This"
    )

    reasons = [
        (
            f"Live spot is {fmt_price(spot)}; "
            f"nearest ATM strike is "
            f"{atm_strike:.0f}."
        ),

        (
            f"5-minute trend: {tf5['trend']} | "
            f"30-minute trend: {tf30['trend']} | "
            f"Daily trend: {daily_tech['trend']}."
        ),

        (
            f"RSI: 5m {tf5['rsi']:.1f} | "
            f"30m {tf30['rsi']:.1f} | "
            f"Daily {daily_tech['rsi']:.1f}."
        ),

        (
            f"PCR is {pcr:.2f}."
        ),

        (
            f"OI support is {fmt_price(support)} "
            f"and resistance is "
            f"{fmt_price(resistance)}."
        ),

        (
            f"Overall direction: "
            f"{overall_direction} with "
            f"{overall_alignment}/3 "
            f"timeframes aligned."
        ),

        (
            f"Engine confidence: "
            f"{confidence}/100. "
            "The score is a rule-based quality "
            "measure, not a historical win probability."
        ),
    ]

    if (
        best_plan
        and not np.isnan(
            best_plan["pop"]
        )
    ):
        reasons.append(
            f"Selected option PoP from "
            f"Upstox is "
            f"{best_plan['pop']:.1f}%."
        )

    for reason in reasons:
        st.write(
            "✓",
            reason,
        )


# ============================================================
# TAB 2
# ============================================================

with tab2:

    st.markdown(
        f"### Live Option Chain — "
        f"{selected_expiry}"
    )

    view = chain.copy()

    display = pd.DataFrame(
        {
            "Strike":
                view["Strike"]
                .round(0)
                .astype(int),

            "CE LTP":
                view["CE LTP"]
                .round(2),

            "CE OI":
                view["CE OI"]
                .round(0)
                .astype("int64"),

            "CE Chg OI":
                view["CE Chg OI"]
                .round(0)
                .astype("int64"),

            "CE IV":
                view["CE IV"]
                .round(1),

            "CE Delta":
                view["CE Delta"]
                .round(3),

            "CE PoP":
                view["CE PoP"]
                .round(1),

            "PE LTP":
                view["PE LTP"]
                .round(2),

            "PE OI":
                view["PE OI"]
                .round(0)
                .astype("int64"),

            "PE Chg OI":
                view["PE Chg OI"]
                .round(0)
                .astype("int64"),

            "PE IV":
                view["PE IV"]
                .round(1),

            "PE Delta":
                view["PE Delta"]
                .round(3),

            "PE PoP":
                view["PE PoP"]
                .round(1),
        }
    )

    display["_distance"] = (
        display["Strike"]
        - spot
    ).abs()

    display = (
        display
        .sort_values(
            "_distance"
        )
        .drop(
            columns="_distance"
        )
        .head(11)
    )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# TAB 3
# ============================================================

with tab3:

    a1, a2, a3 = st.columns(
        3
    )

    a1.metric(
        "EMA 20",
        fmt_price(
            daily_tech[
                "ema20"
            ]
        ),
    )

    a2.metric(
        "EMA 50",
        fmt_price(
            daily_tech[
                "ema50"
            ]
        ),
    )

    a3.metric(
        "ATR 14",
        fmt_price(
            daily_tech[
                "atr"
            ]
        ),
    )

    st.markdown(
        "### Multi-Timeframe Confirmation"
    )

    mtf = pd.DataFrame(
        [
            {
                "Timeframe":
                    "5 Minute",
                "Trend":
                    tf5["trend"],
                "RSI":
                    round(
                        tf5["rsi"],
                        1,
                    ),
                "ADX":
                    round(
                        tf5["adx"],
                        1,
                    ),
                "Momentum %":
                    round(
                        tf5["momentum"],
                        2,
                    ),
            },

            {
                "Timeframe":
                    "30 Minute",
                "Trend":
                    tf30["trend"],
                "RSI":
                    round(
                        tf30["rsi"],
                        1,
                    ),
                "ADX":
                    round(
                        tf30["adx"],
                        1,
                    ),
                "Momentum %":
                    round(
                        tf30["momentum"],
                        2,
                    ),
            },

            {
                "Timeframe":
                    "Daily",
                "Trend":
                    daily_tech["trend"],
                "RSI":
                    round(
                        daily_tech["rsi"],
                        1,
                    ),
                "ADX":
                    round(
                        daily_tech["adx"],
                        1,
                    ),
                "Momentum %":
                    round(
                        daily_tech["momentum"],
                        2,
                    ),
            },
        ]
    )

    st.dataframe(
        mtf,
        use_container_width=True,
        hide_index=True,
    )

    left, right = st.columns(
        2
    )

    with left:

        st.markdown(
            "### 🟢 Support / Put OI"
        )

        st.write(
            f"Major support from Put OI: "
            f"**{fmt_price(support)}**"
        )

        support_row = nearest_row(
            chain,
            support,
        )

        if support_row is not None:

            st.write(
                f"Put OI: "
                f"**{fmt_num(support_row['PE OI'])}**"
            )

            st.write(
                f"Put Chg OI: "
                f"**{fmt_num(support_row['PE Chg OI'])}**"
            )

    with right:

        st.markdown(
            "### 🔴 Resistance / Call OI"
        )

        st.write(
            f"Major resistance from Call OI: "
            f"**{fmt_price(resistance)}**"
        )

        resistance_row = nearest_row(
            chain,
            resistance,
        )

        if resistance_row is not None:

            st.write(
                f"Call OI: "
                f"**{fmt_num(resistance_row['CE OI'])}**"
            )

            st.write(
                f"Call Chg OI: "
                f"**{fmt_num(resistance_row['CE Chg OI'])}**"
            )

    if not candles.empty:

        chart = (
            candles
            .set_index(
                "timestamp"
            )[["close"]]
            .tail(80)
        )

        st.line_chart(
            chart,
            use_container_width=True,
        )


# ============================================================
# TAB 4
# ============================================================

with tab4:

    st.markdown(
        """
### Live-data decision framework

**1. Market direction**
- Live spot
- 5-minute + 30-minute + Daily trend alignment
- EMA20 / EMA50
- RSI
- ADX / momentum
- Intraday VWAP where volume is available

**2. Option-chain structure**
- Put OI / Change in OI
- Call OI / Change in OI
- PCR
- OI-derived support and resistance

**3. Option quality**
- LTP
- Bid / Ask
- Volume
- IV
- Delta
- Upstox PoP

**4. Trade plan**
- Entry trigger
- Entry price
- Stop Loss
- Target 1
- Target 2
- Exit / invalidation rule
- Risk / Reward

**5. High-accuracy quality gate**
- Minimum setup score: 72/100
- At least 2 of 3 timeframes must agree
- Short-term trend conflict blocks the trade
- Delta, liquidity and bid/ask spread are checked
- Upstox PoP must be at least 55%
- The underlying breakout trigger must occur before a BUY signal
- Otherwise the engine returns **WAIT FOR TRIGGER** or **NO TRADE**

**6. Measurement layer**
- Every decision is recorded
- CALL BUY and PUT BUY signals are followed until an outcome occurs
- T1 / T2 / SL / TIMEOUT are measured
- NO TRADE decisions are also retained
- Engine Confidence is not treated as a probability
- Actual historical outcomes are used for eventual calibration

**7. Validation principle**
- A rule is not considered useful merely because it sounds logical
- Thresholds such as 72 score and 55% PoP must eventually be tested
- Historical results must be separated from future/live observations
- Backtesting must avoid look-ahead bias
- Brokerage, slippage and execution assumptions must eventually be included
"""
    )

    st.divider()

    st.caption(
        "Validation dashboard: add "
        "?validation=1 to the app URL "
        "to inspect recorded decisions and outcomes."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    f"Live Upstox snapshot • "
    f"{symbol} • "
    f"Expiry {selected_expiry} • "
    f"Updated {updated}. "
    "For educational/decision-support use; "
    "review live market conditions before trading."
)
