import os
import json
import math
import sqlite3
from datetime import datetime, timedelta
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
# F&O PRO TRADER ASSISTANT — LIVE UPSTOX REST VERSION
# ============================================================
# IMPORTANT:
# - Uses Upstox REST APIs only.
# - No WebSocket status is shown.
# - Keeps the full decision dashboard.
# - Every generated decision can be stored in SQLite for later
#   outcome tracking.
# ============================================================

st.set_page_config(
    page_title="FO PRO Trader Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------
# CSS / UI
# -----------------------------
st.markdown(
    """
<style>
html, body, [class*="css"] {
    font-family: Arial, sans-serif;
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 1rem;
    max-width: 1500px;
}

.topbar {
    padding: 16px 20px;
    border-radius: 14px;
    background: linear-gradient(135deg, #111827, #1f2937);
    color: white;
    margin-bottom: 16px;
}

.topbar-title {
    font-size: 30px;
    font-weight: 800;
    line-height: 1.1;
}

.topbar-sub {
    margin-top: 5px;
    font-size: 14px;
    opacity: 0.85;
}

.status-live, .status-closed {
    padding: 12px 16px;
    border-radius: 10px;
    font-weight: 800;
    margin: 8px 0 16px 0;
}

.status-live {
    background: #dcfce7;
    color: #166534;
    border: 1px solid #86efac;
}

.status-closed {
    background: #fee2e2;
    color: #991b1b;
    border: 1px solid #fca5a5;
}

.metric-card {
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 12px 14px;
    background: white;
    min-height: 88px;
}

.metric-label {
    color: #6b7280;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
}

.metric-value {
    font-size: 21px;
    font-weight: 800;
    margin-top: 5px;
}

.decision-call {
    border: 2px solid #16a34a;
    background: #f0fdf4;
    color: #166534;
    padding: 18px;
    border-radius: 14px;
    font-size: 28px;
    font-weight: 900;
    text-align: center;
}

.decision-put {
    border: 2px solid #dc2626;
    background: #fef2f2;
    color: #991b1b;
    padding: 18px;
    border-radius: 14px;
    font-size: 28px;
    font-weight: 900;
    text-align: center;
}

.decision-wait {
    border: 2px solid #d97706;
    background: #fffbeb;
    color: #92400e;
    padding: 18px;
    border-radius: 14px;
    font-size: 25px;
    font-weight: 900;
    text-align: center;
}

.decision-none {
    border: 2px solid #6b7280;
    background: #f9fafb;
    color: #374151;
    padding: 18px;
    border-radius: 14px;
    font-size: 25px;
    font-weight: 900;
    text-align: center;
}

.section-title {
    font-size: 20px;
    font-weight: 850;
    margin-top: 12px;
    margin-bottom: 8px;
}

.small-note {
    color: #6b7280;
    font-size: 12px;
}

.scanner-card {
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 9px;
    margin-bottom: 8px;
    background: #ffffff;
}
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------
# Constants
# -----------------------------
BASE_URL = "https://api.upstox.com"
V3_BASE_URL = "https://api.upstox.com/v3"
INSTRUMENT_MASTER_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
)

DB_FILE = "fo_trader_journal.sqlite3"

RISK_PROFILES = {
    "Conservative": {"sl": 0.75, "t1": 1.30, "t2": 1.60},
    "Balanced": {"sl": 0.70, "t1": 1.40, "t2": 1.80},
    "Aggressive": {"sl": 0.65, "t1": 1.55, "t2": 2.10},
}

DEFAULT_SYMBOLS = [
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "KOTAKBANK",
    "HDFCBANK",
    "RELIANCE",
    "ICICIBANK",
    "SBIN",
    "AXISBANK",
    "INFY",
    "TCS",
    "BHARTIARTL",
    "INDUSTOWER",
]


# -----------------------------
# Utility functions
# -----------------------------
def safe_float(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        number = float(value)
        return number if np.isfinite(number) else default
    except Exception:
        return default


def fmt_num(value, digits=2):
    value = safe_float(value)
    if not np.isfinite(value):
        return "—"
    return f"{value:,.{digits}f}"


def fmt_pct(value, digits=1):
    value = safe_float(value)
    if not np.isfinite(value):
        return "—"
    return f"{value:.{digits}f}%"


def now_ist():
    # India is UTC+5:30 and does not use DST.
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def is_market_open():
    current = now_ist()
    if current.weekday() >= 5:
        return False
    open_time = current.replace(hour=9, minute=15, second=0, microsecond=0)
    close_time = current.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_time <= current <= close_time


def flatten_dict(obj, prefix=""):
    result = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                result.update(flatten_dict(value, name))
            else:
                result[name] = value
    return result


def first_value(mapping, keys, default=np.nan):
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        if key in mapping:
            value = safe_float(mapping[key], default)
            if np.isfinite(value):
                return value
    return default


# -----------------------------
# Upstox API
# -----------------------------
def get_access_token():
    try:
        token = st.secrets.get("UPSTOX_ACCESS_TOKEN", "")
    except Exception:
        token = os.getenv("UPSTOX_ACCESS_TOKEN", "")
    return str(token).strip()


TOKEN = get_access_token()


def api_headers():
    if not TOKEN:
        return {"Accept": "application/json"}
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {TOKEN}",
    }


def api_get(path, params=None, base=BASE_URL, timeout=15):
    if not TOKEN:
        raise RuntimeError("UPSTOX_ACCESS_TOKEN is missing in Streamlit Secrets.")

    response = requests.get(
        f"{base}{path}",
        headers=api_headers(),
        params=params,
        timeout=timeout,
    )

    if response.status_code >= 400:
        try:
            body = response.json()
        except Exception:
            body = response.text[:500]
        raise RuntimeError(f"Upstox API {response.status_code}: {body}")

    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError("Upstox returned a non-JSON response.") from exc

    return payload.get("data", payload)


@st.cache_data(ttl=86400, show_spinner=False)
def load_instrument_master():
    response = requests.get(INSTRUMENT_MASTER_URL, timeout=30)
    response.raise_for_status()

    import gzip

    raw = gzip.decompress(response.content)
    data = json.loads(raw.decode("utf-8"))
    df = pd.DataFrame(data)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def search_instrument(symbol):
    symbol = symbol.strip().upper()

    # First use the current Upstox search endpoint.
    try:
        data = api_get(
            "/v2/instruments/search",
            params={
                "query": symbol,
                "exchanges": "NSE",
                "segments": "EQ,INDEX",
            },
        )
        if isinstance(data, list):
            for item in data:
                trading_symbol = str(item.get("trading_symbol", "")).upper()
                short_name = str(item.get("short_name", "")).upper()
                if trading_symbol == symbol or short_name == symbol:
                    return item
            if data:
                return data[0]
    except Exception:
        pass

    # Fallback to instrument master.
    df = load_instrument_master()
    if df.empty:
        return None

    columns = {str(c).lower(): c for c in df.columns}
    trading_col = columns.get("trading_symbol")
    segment_col = columns.get("segment")
    instrument_type_col = columns.get("instrument_type")

    if not trading_col:
        return None

    mask = df[trading_col].astype(str).str.upper().eq(symbol)

    if segment_col:
        mask &= df[segment_col].astype(str).str.upper().isin(
            ["NSE_EQ", "NSE_INDEX", "NSE_FO"]
        )

    matches = df.loc[mask]
    if matches.empty:
        return None

    if instrument_type_col:
        index_matches = matches[
            matches[instrument_type_col].astype(str).str.upper().eq("INDEX")
        ]
        if not index_matches.empty:
            matches = index_matches

    return matches.iloc[0].to_dict()


@st.cache_data(ttl=300, show_spinner=False)
def get_option_contracts(instrument_key):
    data = api_get(
        "/v2/option/contract",
        params={"instrument_key": instrument_key},
    )
    if not isinstance(data, list):
        return []
    return data


@st.cache_data(ttl=300, show_spinner=False)
def get_option_chain(instrument_key, expiry):
    data = api_get(
        "/v2/option/chain",
        params={
            "instrument_key": instrument_key,
            "expiry_date": expiry,
        },
    )
    return data if isinstance(data, list) else []


@st.cache_data(ttl=30, show_spinner=False)
def get_quotes(instrument_keys):
    if not instrument_keys:
        return {}

    # Upstox accepts comma-separated instrument keys.
    data = api_get(
        "/v3/market-quote/quotes",
        params={"instrument_key": ",".join(instrument_keys)},
        base=BASE_URL,
    )
    return data if isinstance(data, dict) else {}


@st.cache_data(ttl=300, show_spinner=False)
def get_v3_candles(instrument_key, interval="30", days=80):
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)

    encoded_key = quote(instrument_key, safe="")
    url = (
        f"{V3_BASE_URL}/historical-candle/"
        f"{encoded_key}/minutes/{interval}/{end_date}/{start_date}"
    )

    if not TOKEN:
        raise RuntimeError("UPSTOX_ACCESS_TOKEN is missing in Streamlit Secrets.")

    response = requests.get(url, headers=api_headers(), timeout=20)
    if response.status_code >= 400:
        raise RuntimeError(f"Candle API {response.status_code}: {response.text[:300]}")

    payload = response.json()
    data = payload.get("data", {})
    candles = data.get("candles", []) if isinstance(data, dict) else []

    if not candles:
        return pd.DataFrame()

    rows = []
    for row in candles:
        if len(row) < 6:
            continue
        rows.append(
            {
                "timestamp": row[0],
                "open": safe_float(row[1]),
                "high": safe_float(row[2]),
                "low": safe_float(row[3]),
                "close": safe_float(row[4]),
                "volume": safe_float(row[5], 0),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


# -----------------------------
# Technical analysis
# -----------------------------
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df, period=14):
    if df.empty:
        return pd.Series(dtype=float)
    previous_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - previous_close).abs(),
            (df["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def technical_snapshot(df):
    if df.empty or len(df) < 30:
        return {
            "trend": "Neutral",
            "rsi": np.nan,
            "ema20": np.nan,
            "ema50": np.nan,
            "atr": np.nan,
            "close": np.nan,
        }

    close = df["close"]
    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    rsi14 = rsi(close, 14)
    atr14 = atr(df, 14)

    last_close = safe_float(close.iloc[-1])
    e20 = safe_float(ema20.iloc[-1])
    e50 = safe_float(ema50.iloc[-1])
    rsi_last = safe_float(rsi14.iloc[-1])
    atr_last = safe_float(atr14.iloc[-1])

    if np.isfinite(last_close) and np.isfinite(e20) and np.isfinite(e50):
        if last_close > e20 > e50:
            trend = "Bullish"
        elif last_close < e20 < e50:
            trend = "Bearish"
        else:
            trend = "Neutral"
    else:
        trend = "Neutral"

    return {
        "trend": trend,
        "rsi": rsi_last,
        "ema20": e20,
        "ema50": e50,
        "atr": atr_last,
        "close": last_close,
    }


def get_timeframe_analysis(instrument_key):
    result = {}
    for label, interval, days in [
        ("5m", "5", 15),
        ("30m", "30", 40),
    ]:
        try:
            df = get_v3_candles(instrument_key, interval=interval, days=days)
            result[label] = technical_snapshot(df)
        except Exception:
            result[label] = {
                "trend": "Neutral",
                "rsi": np.nan,
                "ema20": np.nan,
                "ema50": np.nan,
                "atr": np.nan,
                "close": np.nan,
            }

    return result


# -----------------------------
# Option-chain normalization
# -----------------------------
def extract_side(row, side):
    side = side.upper()
    source = row.get("call_options") if side == "CE" else row.get("put_options")
    if source is None:
        source = row.get("CE") if side == "CE" else row.get("PE")
    return source if isinstance(source, dict) else {}


def normalize_option(row, side):
    side = side.upper()
    side_data = extract_side(row, side)
    market = side_data.get("market_data", {})
    greeks = side_data.get("option_greeks", {})

    flat = flatten_dict(side_data)

    def value(keys, default=np.nan):
        candidates = list(keys)
        for key in candidates:
            if key in side_data:
                v = safe_float(side_data[key], default)
                if np.isfinite(v):
                    return v
            if key in market:
                v = safe_float(market[key], default)
                if np.isfinite(v):
                    return v
            if key in greeks:
                v = safe_float(greeks[key], default)
                if np.isfinite(v):
                    return v
            if key in flat:
                v = safe_float(flat[key], default)
                if np.isfinite(v):
                    return v
        return default

    strike = safe_float(
        row.get("strike_price", row.get("strike", side_data.get("strike_price")))
    )

    ltp = value(["ltp", "last_price", "last_traded_price"])
    bid = value(["bid_price", "bid", "best_bid_price"])
    ask = value(["ask_price", "ask", "best_ask_price"])
    volume = value(["volume", "traded_volume"], 0)
    oi = value(["oi", "open_interest", "openInterest"], 0)
    prev_oi = value(["prev_oi", "previous_oi", "previous_open_interest"], np.nan)
    iv = value(["iv", "implied_volatility", "impliedVolatility"])
    delta = value(["delta"])

    pop = value(
        [
            "pop",
            "probability_of_profit",
            "probabilityOfProfit",
            "probability_of_profit_percentage",
        ]
    )

    # Some payloads expose PoP as 0-1 rather than 0-100.
    if np.isfinite(pop) and 0 < pop <= 1:
        pop *= 100

    chg_oi = (
        oi - prev_oi
        if np.isfinite(oi) and np.isfinite(prev_oi)
        else value(["change_in_oi", "chg_oi", "change_oi"], np.nan)
    )

    return {
        "strike": strike,
        "ltp": ltp,
        "bid": bid,
        "ask": ask,
        "volume": volume,
        "oi": oi,
        "prev_oi": prev_oi,
        "chg_oi": chg_oi,
        "iv": iv,
        "delta": delta,
        "pop": pop,
        "side": side,
    }


def normalize_chain(raw_chain):
    rows = []
    for row in raw_chain:
        if not isinstance(row, dict):
            continue

        strike = safe_float(row.get("strike_price", row.get("strike")))
        if not np.isfinite(strike):
            continue

        ce = normalize_option(row, "CE")
        pe = normalize_option(row, "PE")
        ce["strike"] = strike
        pe["strike"] = strike

        rows.append({"strike": strike, "CE": ce, "PE": pe})

    rows.sort(key=lambda x: x["strike"])
    return rows


def nearest_row(chain, spot):
    valid = [r for r in chain if np.isfinite(safe_float(r.get("strike")))]
    if not valid:
        return None
    return min(valid, key=lambda r: abs(r["strike"] - spot))


def oi_levels(chain, spot):
    ce_rows = []
    pe_rows = []

    for row in chain:
        strike = safe_float(row.get("strike"))
        ce_oi = safe_float(row.get("CE", {}).get("oi"), 0)
        pe_oi = safe_float(row.get("PE", {}).get("oi"), 0)
        if np.isfinite(strike):
            ce_rows.append((strike, ce_oi))
            pe_rows.append((strike, pe_oi))

    if not ce_rows and not pe_rows:
        return np.nan, np.nan, np.nan, {}

    below_ce = [(s, oi) for s, oi in ce_rows if s >= spot]
    above_pe = [(s, oi) for s, oi in pe_rows if s <= spot]

    # Resistance = strongest CE OI above/near spot.
    if below_ce:
        resistance = max(below_ce, key=lambda x: x[1])[0]
    elif ce_rows:
        resistance = max(ce_rows, key=lambda x: x[1])[0]
    else:
        resistance = np.nan

    # Support = strongest PE OI below/near spot.
    if above_pe:
        support = max(above_pe, key=lambda x: x[1])[0]
    elif pe_rows:
        support = max(pe_rows, key=lambda x: x[1])[0]
    else:
        support = np.nan

    total_ce = sum(max(0, oi) for _, oi in ce_rows)
    total_pe = sum(max(0, oi) for _, oi in pe_rows)
    pcr = total_pe / total_ce if total_ce > 0 else np.nan

    info = {
        "max_ce_oi": max(ce_rows, key=lambda x: x[1]) if ce_rows else None,
        "max_pe_oi": max(pe_rows, key=lambda x: x[1]) if pe_rows else None,
    }
    return support, resistance, pcr, info


# -----------------------------
# Option selection / scoring
# -----------------------------
def select_option(chain, spot, side):
    candidates = []
    for row in chain:
        strike = safe_float(row.get("strike"))
        option = row.get(side, {})
        ltp = safe_float(option.get("ltp"))
        if not np.isfinite(strike) or not np.isfinite(ltp) or ltp <= 0:
            continue

        # Prefer reasonably liquid contracts near ATM.
        distance_pct = abs(strike - spot) / max(spot, 1) * 100
        volume = safe_float(option.get("volume"), 0)
        oi = safe_float(option.get("oi"), 0)
        delta = safe_float(option.get("delta"))

        score = distance_pct
        if np.isfinite(delta):
            score += abs(abs(delta) - 0.55) * 8
        if volume <= 0:
            score += 100
        if oi <= 0:
            score += 50

        candidates.append((score, row, option))

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[0])
    _, row, option = candidates[0]
    return row, option


def estimate_pop(option, side, spot, strike):
    """Fallback only when Upstox does not expose PoP.

    This is deliberately conservative and is NOT presented as a broker-
    supplied statistical probability. The app still uses the value only as
    a secondary filter.
    """
    ltp = safe_float(option.get("ltp"))
    delta = safe_float(option.get("delta"))
    iv = safe_float(option.get("iv"))

    if np.isfinite(delta):
        base = abs(delta) * 100
    else:
        distance = abs(strike - spot) / max(spot, 1)
        base = max(25, 70 - distance * 1000)

    if np.isfinite(iv):
        # Higher IV creates a wider uncertainty band; reduce the fallback.
        base -= max(0, iv - 25) * 0.20

    if np.isfinite(ltp) and ltp <= 0:
        return np.nan

    return float(max(20, min(75, base)))


def score_option(option, side, spot, support, resistance, tf5, tf30, pcr):
    score = 0.0
    reasons = []
    opposite = "PE" if side == "CE" else "CE"

    ltp = safe_float(option.get("ltp"))
    delta = safe_float(option.get("delta"))
    iv = safe_float(option.get("iv"))
    volume = safe_float(option.get("volume"), 0)
    oi = safe_float(option.get("oi"), 0)
    bid = safe_float(option.get("bid"))
    ask = safe_float(option.get("ask"))
    strike = safe_float(option.get("strike"), spot)

    # Use the short timeframe as the primary technical context.
    tf = tf5
    trend5 = tf5.get("trend", "Neutral")
    trend30 = tf30.get("trend", "Neutral")

    desired_trend = "Bullish" if side == "CE" else "Bearish"
    undesired_trend = "Bearish" if side == "CE" else "Bullish"

    if trend5 == desired_trend:
        score += 20
        reasons.append("5m trend aligned")
    elif trend5 == undesired_trend:
        score -= 15
        reasons.append("5m trend opposed")

    if trend30 == desired_trend:
        score += 18
        reasons.append("30m trend aligned")
    elif trend30 == undesired_trend:
        score -= 15
        reasons.append("30m trend opposed")

    rsi_value = safe_float(tf.get("rsi"))
    if np.isfinite(rsi_value):
        if side == "CE" and 50 <= rsi_value <= 70:
            score += 12
            reasons.append("RSI supports call momentum")
        elif side == "PE" and 30 <= rsi_value <= 50:
            score += 12
            reasons.append("RSI supports put momentum")
        elif (side == "CE" and rsi_value < 40) or (side == "PE" and rsi_value > 60):
            score -= 8
            reasons.append("RSI is not supportive")

    if np.isfinite(pcr):
        if side == "CE" and pcr >= 1.0:
            score += 10
            reasons.append("PCR supports bullish side")
        elif side == "PE" and pcr <= 1.0:
            score += 10
            reasons.append("PCR supports bearish side")

    if np.isfinite(support) and np.isfinite(resistance):
        if side == "CE":
            if spot > support:
                score += 8
                reasons.append("above OI support")
            if spot < resistance:
                score += 7
                reasons.append("below OI resistance")
        else:
            if spot < resistance:
                score += 8
                reasons.append("below OI resistance")
            if spot > support:
                score += 7
                reasons.append("above OI support")

    if np.isfinite(delta):
        if 0.35 <= abs(delta) <= 0.80:
            score += 10
            reasons.append("usable delta")
        else:
            score -= 5
            reasons.append("delta outside preferred range")

    if np.isfinite(iv):
        if iv <= 45:
            score += 5
            reasons.append("IV acceptable")
        else:
            score -= 4
            reasons.append("high IV")

    if volume > 0:
        score += 5
        reasons.append("option has volume")

    if oi > 0:
        score += 5
        reasons.append("option has OI")

    if np.isfinite(bid) and np.isfinite(ask) and ask > 0:
        spread_pct = (ask - bid) / ask * 100
    else:
        spread_pct = np.nan

    if np.isfinite(spread_pct):
        if spread_pct <= 2:
            score += 5
            reasons.append("tight spread")
        elif spread_pct <= 4:
            score += 2
        else:
            score -= 8
            reasons.append("wide spread")

    # Near-ATM preference.
    distance_pct = abs(strike - spot) / max(spot, 1) * 100
    if distance_pct <= 2:
        score += 5
        reasons.append("near ATM")
    elif distance_pct > 5:
        score -= 5
        reasons.append("far from ATM")

    score = max(0, min(100, score))

    return {
        "score": score,
        "reasons": reasons,
        "delta": delta,
        "iv": iv,
        "volume": volume,
        "oi": oi,
        "spread_pct": spread_pct,
        "trend5": trend5,
        "trend30": trend30,
    }


def build_plan(option, side, spot, support, resistance, risk_profile):
    ltp = safe_float(option.get("ltp"))
    if not np.isfinite(ltp) or ltp <= 0:
        return None

    factor = RISK_PROFILES[risk_profile]

    entry = ltp
    sl = entry * factor["sl"]
    t1 = entry * factor["t1"]
    t2 = entry * factor["t2"]

    if side == "CE":
        trigger_level = support if np.isfinite(support) else spot
        trigger_text = f"Spot holds above support ₹{fmt_num(trigger_level)}"
        trigger_hit = spot >= trigger_level
        exit_rule = "Exit if spot breaks OI support or option SL is hit."
    else:
        trigger_level = resistance if np.isfinite(resistance) else spot
        trigger_text = f"Spot stays below resistance ₹{fmt_num(trigger_level)}"
        trigger_hit = spot <= trigger_level
        exit_rule = "Exit if spot breaks OI resistance or option SL is hit."

    risk = entry - sl
    reward = t1 - entry
    rr = reward / risk if risk > 0 else np.nan

    return {
        "side": side,
        "entry": entry,
        "sl": sl,
        "t1": t1,
        "t2": t2,
        "trigger_level": trigger_level,
        "trigger_text": trigger_text,
        "trigger_hit": bool(trigger_hit),
        "exit_rule": exit_rule,
        "rr": rr,
    }


def enrich_option(option, side, spot, support, resistance, tf5, tf30, pcr):
    option = dict(option)
    if not np.isfinite(safe_float(option.get("pop"))):
        option["pop"] = estimate_pop(option, side, spot, safe_float(option.get("strike"), spot))
        option["pop_source"] = "fallback estimate"
    else:
        option["pop_source"] = "Upstox"

    scored = score_option(
        option,
        side,
        spot,
        support,
        resistance,
        tf5,
        tf30,
        pcr,
    )
    option.update(scored)
    return option


def make_plan_for_side(chain, side, spot, support, resistance, tf5, tf30, pcr, risk_profile):
    row, option = select_option(chain, spot, side)
    if option is None:
        return None

    option = dict(option)
    option["strike"] = safe_float(row.get("strike"))
    option = enrich_option(option, side, spot, support, resistance, tf5, tf30, pcr)
    plan = build_plan(option, side, spot, support, resistance, risk_profile)
    if plan is None:
        return None

    # Decision gates. These are deliberately strict: a low setup score,
    # conflicting timeframes, bad delta/spread, or zero volume cannot be
    # rescued simply by one strong indicator.
    hard_fail = []

    if option["score"] < 72:
        hard_fail.append("setup score below 72")

    alignment = 0
    desired = "Bullish" if side == "CE" else "Bearish"
    if tf5.get("trend") == desired:
        alignment += 1
    if tf30.get("trend") == desired:
        alignment += 1

    if alignment < 2:
        hard_fail.append("fewer than 2 aligned timeframes")

    opposite = "Bearish" if side == "CE" else "Bullish"
    if tf5.get("trend") == opposite or tf30.get("trend") == opposite:
        hard_fail.append("short-term trend conflict")

    if np.isfinite(option["spread_pct"]) and option["spread_pct"] > 4:
        hard_fail.append("wide option spread")

    if not np.isfinite(option["delta"]) or not (0.35 <= abs(option["delta"]) <= 0.80):
        hard_fail.append("poor delta")

    if not np.isfinite(option["pop"]) or option["pop"] < 55:
        hard_fail.append("low Upstox/fallback PoP")

    if option["volume"] <= 0:
        hard_fail.append("no option volume")

    readiness = "READY" if not hard_fail and plan["trigger_hit"] else (
        "WAIT FOR TRIGGER" if not hard_fail else "NO TRADE"
    )

    option["alignment"] = alignment
    option["hard_fail"] = hard_fail
    option["readiness"] = readiness
    plan["option"] = option
    return plan


# -----------------------------
# Decision engine
# -----------------------------
def decide(ce_plan, pe_plan, tf5, tf30):
    ce_score = ce_plan["option"]["score"] if ce_plan else -np.inf
    pe_score = pe_plan["option"]["score"] if pe_plan else -np.inf

    if tf5.get("trend") == "Bullish" and tf30.get("trend") == "Bullish":
        overall_direction = "Bullish"
    elif tf5.get("trend") == "Bearish" and tf30.get("trend") == "Bearish":
        overall_direction = "Bearish"
    else:
        overall_direction = "Neutral"

    if (
        ce_plan
        and ce_score >= 72
        and ce_score >= pe_score + 8
        and overall_direction == "Bullish"
        and ce_plan["readiness"] in {"READY", "WAIT FOR TRIGGER"}
    ):
        decision = (
            "CALL BUY"
            if ce_plan["readiness"] == "READY"
            else "WAIT FOR TRIGGER"
        )
        selected = ce_plan
    elif (
        pe_plan
        and pe_score >= 72
        and pe_score >= ce_score + 8
        and overall_direction == "Bearish"
        and pe_plan["readiness"] in {"READY", "WAIT FOR TRIGGER"}
    ):
        decision = (
            "PUT BUY"
            if pe_plan["readiness"] == "READY"
            else "WAIT FOR TRIGGER"
        )
        selected = pe_plan
    else:
        decision = "NO TRADE"
        selected = None

    return decision, selected, overall_direction


# -----------------------------
# Decision journal
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            symbol TEXT NOT NULL,
            expiry TEXT,
            spot REAL,
            decision TEXT,
            strike REAL,
            option_ltp REAL,
            score REAL,
            pop REAL,
            delta REAL,
            iv REAL,
            pcr REAL,
            support REAL,
            resistance REAL,
            entry REAL,
            sl REAL,
            t1 REAL,
            t2 REAL,
            trigger_hit INTEGER,
            outcome TEXT,
            outcome_time TEXT,
            last_price REAL
        )
        """
    )
    conn.commit()
    conn.close()


def log_decision(symbol, expiry, spot, decision, selected, pcr, support, resistance):
    if decision not in {"CALL BUY", "PUT BUY"} or selected is None:
        return

    option = selected["option"]
    created = now_ist().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_FILE)
    try:
        # Prevent repeated identical signals every auto-refresh cycle.
        recent = conn.execute(
            """
            SELECT id FROM decisions
            WHERE symbol = ? AND expiry = ? AND decision = ?
              AND strike = ? AND created_at >= ?
            ORDER BY id DESC LIMIT 1
            """,
            (
                symbol,
                expiry,
                decision,
                safe_float(option.get("strike")),
                (now_ist() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        ).fetchone()

        if recent:
            return

        conn.execute(
            """
            INSERT INTO decisions (
                created_at, symbol, expiry, spot, decision, strike,
                option_ltp, score, pop, delta, iv, pcr, support,
                resistance, entry, sl, t1, t2, trigger_hit,
                outcome, outcome_time, last_price
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created,
                symbol,
                expiry,
                safe_float(spot),
                decision,
                safe_float(option.get("strike")),
                safe_float(option.get("ltp")),
                safe_float(option.get("score")),
                safe_float(option.get("pop")),
                safe_float(option.get("delta")),
                safe_float(option.get("iv")),
                safe_float(pcr),
                safe_float(support),
                safe_float(resistance),
                safe_float(selected.get("entry")),
                safe_float(selected.get("sl")),
                safe_float(selected.get("t1")),
                safe_float(selected.get("t2")),
                1 if selected.get("trigger_hit") else 0,
                "OPEN",
                None,
                safe_float(option.get("ltp")),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_open_outcomes():
    """Update journal records when the stored option reaches T1 or SL.

    This is a simple first-pass outcome tracker. It intentionally does not
    claim that the journal is a full backtest; it only evaluates live logged
    trades after they are recorded.
    """
    if not TOKEN:
        return

    conn = sqlite3.connect(DB_FILE)
    try:
        rows = conn.execute(
            """
            SELECT id, symbol, expiry, decision, strike, entry, sl, t1,
                   created_at, outcome
            FROM decisions
            WHERE outcome = 'OPEN'
            ORDER BY id ASC
            LIMIT 50
            """
        ).fetchall()

        for row in rows:
            (
                record_id,
                symbol,
                expiry,
                decision,
                strike,
                entry,
                sl,
                t1,
                created_at,
                outcome,
            ) = row

            # We need the underlying instrument to locate the current option
            # contract. Failure here simply leaves the trade open.
            try:
                instrument = search_instrument(symbol)
                if not instrument:
                    continue
                instrument_key = instrument.get("instrument_key")
                if not instrument_key:
                    continue

                chain_raw = get_option_chain(instrument_key, expiry)
                chain = normalize_chain(chain_raw)
                target_side = "CE" if decision == "CALL BUY" else "PE"
                current = None
                for chain_row in chain:
                    if abs(safe_float(chain_row.get("strike")) - safe_float(strike)) < 0.01:
                        current = chain_row.get(target_side)
                        break

                if not current:
                    continue

                current_ltp = safe_float(current.get("ltp"))
                if not np.isfinite(current_ltp):
                    continue

                created_dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                age = now_ist() - created_dt

                new_outcome = None
                if current_ltp >= safe_float(t1):
                    new_outcome = "WIN_T1"
                elif current_ltp <= safe_float(sl):
                    new_outcome = "LOSS_SL"
                elif age >= timedelta(hours=4):
                    if current_ltp > safe_float(entry):
                        new_outcome = "TIMEOUT_PROFIT"
                    elif current_ltp < safe_float(entry):
                        new_outcome = "TIMEOUT_LOSS"
                    else:
                        new_outcome = "TIMEOUT_FLAT"

                conn.execute(
                    """
                    UPDATE decisions
                    SET last_price = ?, outcome = COALESCE(?, outcome),
                        outcome_time = CASE WHEN ? IS NOT NULL THEN ? ELSE outcome_time END
                    WHERE id = ?
                    """,
                    (
                        current_ltp,
                        new_outcome,
                        new_outcome,
                        now_ist().strftime("%Y-%m-%d %H:%M:%S"),
                        record_id,
                    ),
                )
            except Exception:
                continue

        conn.commit()
    finally:
        conn.close()


# Initialize storage safely.
try:
    init_db()
except Exception:
    pass


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.markdown("### 🔎 Analyze Instrument")

symbol_input = st.sidebar.text_input(
    "Stock / Index",
    value="HDFCBANK",
    help="Enter an NSE stock or index available in F&O.",
)

risk_profile = st.sidebar.selectbox(
    "Risk Profile",
    list(RISK_PROFILES.keys()),
    index=1,
)

analyze = st.sidebar.button("🚀 Analyze", use_container_width=True)

if analyze:
    st.session_state["selected_symbol"] = symbol_input.strip().upper()

if "selected_symbol" not in st.session_state:
    st.session_state["selected_symbol"] = symbol_input.strip().upper()

scanner_on = st.sidebar.toggle("⚡ F&O Scanner", value=False)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚡ Quick Select")
quick = st.sidebar.selectbox(
    "",
    ["Select"] + DEFAULT_SYMBOLS,
    label_visibility="collapsed",
)
if quick != "Select":
    st.session_state["selected_symbol"] = quick


# -----------------------------
# Auto refresh during market hours
# -----------------------------
if st_autorefresh is not None and is_market_open():
    st_autorefresh(interval=30000, key="fo_refresh")


# -----------------------------
# Header / status
# -----------------------------
st.markdown(
    """
<div class="topbar">
    <div class="topbar-title">📊 FO PRO Trader Assistant</div>
    <div class="topbar-sub">Options Analysis • Upstox REST API • Live market data</div>
</div>
""",
    unsafe_allow_html=True,
)

if is_market_open():
    st.markdown(
        '<div class="status-live">● LIVE DATA</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="status-closed">● MARKET CLOSED</div>',
        unsafe_allow_html=True,
    )


# -----------------------------
# Scanner
# -----------------------------
def scanner_results():
    results = []
    if not TOKEN:
        return results

    for symbol in DEFAULT_SYMBOLS[:12]:
        try:
            instrument = search_instrument(symbol)
            if not instrument:
                continue
            instrument_key = instrument.get("instrument_key")
            if not instrument_key:
                continue

            contracts = get_option_contracts(instrument_key)
            if not contracts:
                continue

            expiries = []
            for contract in contracts:
                expiry = contract.get("expiry") or contract.get("expiry_date")
                if expiry and expiry not in expiries:
                    expiries.append(expiry)

            if not expiries:
                continue

            expiry = sorted(expiries)[0]
            raw_chain = get_option_chain(instrument_key, expiry)
            chain = normalize_chain(raw_chain)
            if not chain:
                continue

            spot = safe_float(instrument.get("last_price"))
            if not np.isfinite(spot):
                near = nearest_row(chain, safe_float(spot, 0))
                spot = safe_float(near.get("strike")) if near else np.nan

            if not np.isfinite(spot):
                continue

            support, resistance, pcr, _ = oi_levels(chain, spot)
            tfs = get_timeframe_analysis(instrument_key)
            tf5 = tfs["5m"]
            tf30 = tfs["30m"]

            ce_plan = make_plan_for_side(
                chain, "CE", spot, support, resistance, tf5, tf30, pcr, risk_profile
            )
            pe_plan = make_plan_for_side(
                chain, "PE", spot, support, resistance, tf5, tf30, pcr, risk_profile
            )
            decision, selected, direction = decide(ce_plan, pe_plan, tf5, tf30)

            if selected and safe_float(selected["option"].get("pop")) >= 75:
                results.append(
                    {
                        "Symbol": symbol,
                        "Side": decision,
                        "Strike": selected["option"].get("strike"),
                        "PoP": selected["option"].get("pop"),
                        "Score": selected["option"].get("score"),
                        "LTP": selected["option"].get("ltp"),
                    }
                )
        except Exception:
            continue

    return results


if scanner_on:
    st.sidebar.markdown("### 📡 High PoP Scanner")
    with st.sidebar:
        with st.spinner("Scanning F&O contracts..."):
            scan = scanner_results()
    if scan:
        for item in sorted(scan, key=lambda x: x["PoP"], reverse=True):
            st.sidebar.markdown(
                f"""
<div class="scanner-card">
<b>{item['Symbol']} — {item['Side']}</b><br>
Strike: {fmt_num(item['Strike'], 0)}<br>
PoP: {fmt_pct(item['PoP'])} &nbsp; Score: {fmt_num(item['Score'], 0)}<br>
LTP: ₹{fmt_num(item['LTP'])}
</div>
""",
                unsafe_allow_html=True,
            )
    else:
        st.sidebar.info("No qualifying PoP > 75% setup found.")


# -----------------------------
# Main analysis
# -----------------------------
symbol = st.session_state["selected_symbol"].strip().upper()

if not TOKEN:
    st.error("UPSTOX_ACCESS_TOKEN is not configured in Streamlit Secrets.")
    st.stop()

try:
    instrument = search_instrument(symbol)
    if not instrument:
        st.error(f"Could not find NSE instrument: {symbol}")
        st.stop()

    instrument_key = instrument.get("instrument_key")
    if not instrument_key:
        st.error(f"No Upstox instrument key found for {symbol}.")
        st.stop()

    spot = safe_float(instrument.get("last_price"))

    contracts = get_option_contracts(instrument_key)
    if not contracts:
        st.error(f"No F&O option contracts found for {symbol}.")
        st.stop()

    expiries = []
    for contract in contracts:
        expiry = contract.get("expiry") or contract.get("expiry_date")
        if expiry and expiry not in expiries:
            expiries.append(expiry)

    expiries = sorted(expiries)
    if not expiries:
        st.error(f"No expiry found for {symbol}.")
        st.stop()

    expiry = expiries[0]

    raw_chain = get_option_chain(instrument_key, expiry)
    chain = normalize_chain(raw_chain)
    if not chain:
        st.error(f"Option chain is empty for {symbol} / {expiry}.")
        st.stop()

    if not np.isfinite(spot):
        # Try the ATM strike as a final display fallback.
        first_row = nearest_row(chain, chain[len(chain) // 2]["strike"])
        spot = safe_float(first_row.get("strike")) if first_row else np.nan

    support, resistance, pcr, oi_wall_info = oi_levels(chain, spot)
    tf_analysis = get_timeframe_analysis(instrument_key)
    tf5 = tf_analysis["5m"]
    tf30 = tf_analysis["30m"]

    ce_plan = make_plan_for_side(
        chain, "CE", spot, support, resistance, tf5, tf30, pcr, risk_profile
    )
    pe_plan = make_plan_for_side(
        chain, "PE", spot, support, resistance, tf5, tf30, pcr, risk_profile
    )

    decision, selected, overall_direction = decide(
        ce_plan, pe_plan, tf5, tf30
    )

    if decision in {"CALL BUY", "PUT BUY"} and selected is not None:
        try:
            log_decision(
                symbol,
                expiry,
                spot,
                decision,
                selected,
                pcr,
                support,
                resistance,
            )
            update_open_outcomes()
        except Exception:
            pass

except Exception as exc:
    st.error(f"Unable to fetch/analyze live Upstox data: {exc}")
    st.stop()


# -----------------------------
# Dashboard
# -----------------------------
st.markdown(
    f'<div class="section-title">📊 {symbol} — F&O Options Analysis</div>',
    unsafe_allow_html=True,
)

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Last Traded</div><div class="metric-value">₹{fmt_num(spot)}</div></div>',
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Expiry</div><div class="metric-value">{expiry}</div></div>',
        unsafe_allow_html=True,
    )
with m3:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Market Bias</div><div class="metric-value">{overall_direction}</div></div>',
        unsafe_allow_html=True,
    )
with m4:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">PCR</div><div class="metric-value">{fmt_num(pcr, 2)}</div></div>',
        unsafe_allow_html=True,
    )
with m5:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Risk Profile</div><div class="metric-value">{risk_profile}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

if decision == "CALL BUY":
    decision_class = "decision-call"
elif decision == "PUT BUY":
    decision_class = "decision-put"
elif decision == "WAIT FOR TRIGGER":
    decision_class = "decision-wait"
else:
    decision_class = "decision-none"

st.markdown(
    f'<div class="{decision_class}">{decision}</div>',
    unsafe_allow_html=True,
)


# -----------------------------
# Key levels
# -----------------------------
k1, k2, k3 = st.columns(3)
with k1:
    st.metric("OI Support", f"₹{fmt_num(support)}")
with k2:
    st.metric("OI Resistance", f"₹{fmt_num(resistance)}")
with k3:
    st.metric("5m / 30m", f"{tf5.get('trend')} / {tf30.get('trend')}")


# -----------------------------
# Selected trade plan
# -----------------------------
if selected is not None:
    option = selected["option"]
    st.markdown(
        f"### {'📈 CALL BUY' if selected['side'] == 'CE' else '📉 PUT BUY'} — {fmt_num(option.get('strike'), 0)}"
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("PoP", fmt_pct(option.get("pop")))
    c2.metric("Score", fmt_num(option.get("score"), 0) + "/100")
    c3.metric("Delta", fmt_num(option.get("delta"), 2))
    c4.metric("IV", fmt_num(option.get("iv"), 2))
    c5.metric("LTP", f"₹{fmt_num(option.get('ltp'))}")

    p1, p2, p3, p4, p5 = st.columns(5)
    p1.metric("Entry", f"₹{fmt_num(selected.get('entry'))}")
    p2.metric("Stop Loss", f"₹{fmt_num(selected.get('sl'))}")
    p3.metric("Target 1", f"₹{fmt_num(selected.get('t1'))}")
    p4.metric("Target 2", f"₹{fmt_num(selected.get('t2'))}")
    p5.metric("Risk / Reward", fmt_num(selected.get("rr"), 2))

    st.markdown(
        f"**Entry Trigger:** {selected.get('trigger_text')}"
    )
    st.markdown(f"**Exit Rule:** {selected.get('exit_rule')}")

    if option.get("readiness") == "WAIT FOR TRIGGER":
        st.warning("Setup conditions are satisfied, but the entry trigger has not fired yet.")
    elif option.get("readiness") == "NO TRADE":
        st.error("This setup failed one or more hard safety gates.")

    with st.expander("Why this setup received this score"):
        reasons = option.get("reasons", [])
        if reasons:
            for reason in reasons:
                st.write(f"• {reason}")
        else:
            st.write("No positive scoring reason was recorded.")

        hard_fail = option.get("hard_fail", [])
        if hard_fail:
            st.write("**Hard filters:**")
            for reason in hard_fail:
                st.write(f"• {reason}")

        st.caption(
            f"PoP source: {option.get('pop_source', 'unknown')}. "
            "Setup Score is a rule-based score and is not the same thing as a statistically calibrated probability."
        )
else:
    st.info("No clear CALL BUY / PUT BUY setup currently satisfies all decision gates.")


# -----------------------------
# CALL / PUT comparison
# -----------------------------
st.markdown("### ⚖️ CALL vs PUT")
comparison_rows = []
for label, plan in [("CALL", ce_plan), ("PUT", pe_plan)]:
    if plan:
        opt = plan["option"]
        comparison_rows.append(
            {
                "Side": label,
                "Strike": safe_float(opt.get("strike")),
                "Score": safe_float(opt.get("score")),
                "PoP": safe_float(opt.get("pop")),
                "Delta": safe_float(opt.get("delta")),
                "IV": safe_float(opt.get("iv")),
                "Alignment": safe_float(opt.get("alignment"), 0),
                "Readiness": opt.get("readiness"),
            }
        )

if comparison_rows:
    comparison_df = pd.DataFrame(comparison_rows)
    st.dataframe(
        comparison_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Strike": st.column_config.NumberColumn(format="%.0f"),
            "Score": st.column_config.NumberColumn(format="%.0f"),
            "PoP": st.column_config.NumberColumn(format="%.1f%%"),
            "Delta": st.column_config.NumberColumn(format="%.2f"),
            "IV": st.column_config.NumberColumn(format="%.2f"),
            "Alignment": st.column_config.NumberColumn(format="%.0f"),
        },
    )


# -----------------------------
# Live option chain
# -----------------------------
st.markdown("### 📋 Live Option Chain")

chain_table = []
for row in chain:
    ce = row["CE"]
    pe = row["PE"]
    chain_table.append(
        {
            "CE OI": safe_float(ce.get("oi"), 0),
            "CE Chg OI": safe_float(ce.get("chg_oi")),
            "CE LTP": safe_float(ce.get("ltp")),
            "Strike": safe_float(row.get("strike")),
            "PE LTP": safe_float(pe.get("ltp")),
            "PE Chg OI": safe_float(pe.get("chg_oi")),
            "PE OI": safe_float(pe.get("oi"), 0),
        }
    )

chain_df = pd.DataFrame(chain_table)

# Show the most relevant strikes around spot without hiding the live chain
# entirely.
if not chain_df.empty and np.isfinite(spot):
    chain_df["distance"] = (chain_df["Strike"] - spot).abs()
    display_df = chain_df.sort_values("distance").head(21).sort_values("Strike")
    display_df = display_df.drop(columns=["distance"])
else:
    display_df = chain_df

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "CE OI": st.column_config.NumberColumn(format="%d"),
        "CE Chg OI": st.column_config.NumberColumn(format="%d"),
        "CE LTP": st.column_config.NumberColumn(format="₹%.2f"),
        "Strike": st.column_config.NumberColumn(format="%.0f"),
        "PE LTP": st.column_config.NumberColumn(format="₹%.2f"),
        "PE Chg OI": st.column_config.NumberColumn(format="%d"),
        "PE OI": st.column_config.NumberColumn(format="%d"),
    },
)


# -----------------------------
# Market analysis
# -----------------------------
st.markdown("### 📈 Market Analysis")
analysis_cols = st.columns(2)
with analysis_cols[0]:
    st.markdown("**5-Minute**")
    st.write(f"Trend: **{tf5.get('trend')}**")
    st.write(f"RSI: **{fmt_num(tf5.get('rsi'), 1)}**")
    st.write(f"EMA20: **₹{fmt_num(tf5.get('ema20'))}**")
    st.write(f"EMA50: **₹{fmt_num(tf5.get('ema50'))}**")
    st.write(f"ATR: **₹{fmt_num(tf5.get('atr'))}**")

with analysis_cols[1]:
    st.markdown("**30-Minute**")
    st.write(f"Trend: **{tf30.get('trend')}**")
    st.write(f"RSI: **{fmt_num(tf30.get('rsi'), 1)}**")
    st.write(f"EMA20: **₹{fmt_num(tf30.get('ema20'))}**")
    st.write(f"EMA50: **₹{fmt_num(tf30.get('ema50'))}**")
    st.write(f"ATR: **₹{fmt_num(tf30.get('atr'))}**")


# -----------------------------
# How engine thinks
# -----------------------------
with st.expander("🧠 How Engine Thinks"):
    st.write(
        "The engine combines trend alignment, RSI, OI support/resistance, PCR, "
        "option liquidity, delta, IV, spread and a rule-based setup score. "
        "It requires multiple conditions to agree before allowing a CALL BUY "
        "or PUT BUY. If conditions conflict, it returns NO TRADE."
    )
    st.write(
        "The PoP field is taken from Upstox when available. If the API does not "
        "provide PoP for a contract, the app uses a capped fallback estimate and "
        "labels the source accordingly; it should not be treated as a calibrated "
        "historical probability."
    )

st.markdown(
    '<div class="small-note">Live Upstox REST data • Decision-support only • No automatic orders are placed</div>',
    unsafe_allow_html=True,
)
