import gzip
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests
import streamlit as st
import threading
import time

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# ============================================================
# FO PRO TRADER ASSISTANT — LIVE UPSTOX VERSION
# UI redesigned to match the provided professional dashboard
# All analysis / scoring / decision logic is untouched
# ============================================================

st.set_page_config(
    page_title="FO PRO Trader Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "https://api.upstox.com"

# ============================================================
# CSS — Matches the uploaded professional dashboard design
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: #f0f4f8 !important;
}

.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    max-width: 1480px !important;
}

/* ---------- SIDEBAR ---------- */
section[data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: none !important;
}
section[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: #1e293b !important;
    color: #e2e8f0 !important;
    border: 1px solid #334155 !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #334155 !important;
    border-color: #475569 !important;
}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: 0.4rem;
}

/* ---------- TOP BAR ---------- */
.top-bar {
    background: white;
    border-radius: 14px;
    padding: 14px 22px;
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
}
.top-bar-left {
    display: flex;
    align-items: center;
    gap: 18px;
}
.top-bar-price {
    font-size: 22px;
    font-weight: 800;
    color: #0f172a;
}
.top-bar-change {
    font-size: 14px;
    font-weight: 600;
}
.live-dot {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: #16a34a;
}
.live-dot::before {
    content: "";
    width: 8px;
    height: 8px;
    background: #16a34a;
    border-radius: 50%;
}

/* ---------- CARDS ---------- */
.card {
    background: white;
    border-radius: 14px;
    padding: 18px 20px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    margin-bottom: 16px;
}
.card-title {
    font-size: 13px;
    font-weight: 700;
    color: #64748b;
    letter-spacing: 0.4px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* ---------- MASTER DECISION ---------- */
.master-decision {
    background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
    border: 1px solid #bbf7d0;
    border-radius: 16px;
    padding: 22px 24px;
    margin-bottom: 18px;
}
.master-decision-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 16px;
}
.call-buy-btn {
    background: linear-gradient(135deg, #16a34a, #15803d);
    color: white;
    font-size: 22px;
    font-weight: 800;
    padding: 12px 28px;
    border-radius: 50px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    box-shadow: 0 4px 14px rgba(22, 163, 74, 0.35);
}
.put-buy-btn {
    background: linear-gradient(135deg, #dc2626, #b91c1c);
    color: white;
    font-size: 22px;
    font-weight: 800;
    padding: 12px 28px;
    border-radius: 50px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
}
.no-trade-btn {
    background: #64748b;
    color: white;
    font-size: 20px;
    font-weight: 800;
    padding: 12px 28px;
    border-radius: 50px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
}
.decision-meta {
    display: flex;
    gap: 28px;
    margin-top: 14px;
    flex-wrap: wrap;
}
.decision-meta-item span {
    display: block;
    font-size: 11px;
    color: #64748b;
    font-weight: 600;
}
.decision-meta-item b {
    font-size: 18px;
    color: #0f172a;
    font-weight: 800;
}
.ready-badge {
    background: #dcfce7;
    color: #15803d;
    font-size: 12px;
    font-weight: 700;
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid #86efac;
}

/* ---------- TRADE PLAN ---------- */
.plan-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin: 12px 0;
}
.plan-item {
    background: #f8fafc;
    border-radius: 10px;
    padding: 10px 8px;
    text-align: center;
}
.plan-item span {
    display: block;
    font-size: 11px;
    color: #64748b;
    font-weight: 600;
}
.plan-item b {
    display: block;
    font-size: 15px;
    color: #0f172a;
    margin-top: 3px;
    font-weight: 700;
}

/* ---------- CHECKLIST ---------- */
.check-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}
.check-table th {
    text-align: left;
    color: #64748b;
    font-weight: 600;
    padding: 6px 8px;
    border-bottom: 1px solid #e2e8f0;
}
.check-table td {
    padding: 8px;
    border-bottom: 1px solid #f1f5f9;
    color: #334155;
}
.pass-badge {
    background: #dcfce7;
    color: #15803d;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 12px;
}
.wait-badge {
    background: #fef9c3;
    color: #a16207;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 12px;
}
.fail-badge {
    background: #fee2e2;
    color: #b91c1c;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 12px;
}

/* ---------- ENTRY / LEVELS ---------- */
.entry-box {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 12px;
    padding: 14px 16px;
    font-size: 13px;
    color: #166534;
    margin-top: 10px;
}
.levels-visual {
    margin: 12px 0;
}
.level-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 8px 0;
    font-size: 13px;
}
.level-line {
    flex: 1;
    height: 3px;
    border-radius: 2px;
}
.level-resistance { background: #f87171; }
.level-support { background: #4ade80; }
.level-current { background: #3b82f6; }

/* ---------- WHY ---------- */
.why-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    font-size: 13px;
    color: #334155;
}
.why-item::before {
    content: "✓";
    color: #16a34a;
    font-weight: 800;
    font-size: 14px;
}

/* ---------- OPTION CHAIN ---------- */
.chain-header {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 10px;
}

/* ---------- MISC ---------- */
.section-label {
    font-size: 12px;
    font-weight: 700;
    color: #64748b;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}
.metric-value {
    font-size: 18px;
    font-weight: 800;
    color: #0f172a;
}
.positive { color: #16a34a !important; }
.negative { color: #dc2626 !important; }

div[data-testid="stMetricValue"] {
    font-size: 18px !important;
    font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)


class UpstoxError(RuntimeError):
    pass


class UpstoxRateLimitError(UpstoxError):
    def __init__(self, message, retry_after=30):
        super().__init__(message)
        self.retry_after = int(retry_after or 30)


_API_REQUEST_LOCK = threading.Lock()
_LAST_API_REQUEST = 0.0
_MIN_API_GAP = 0.50


def get_token():
    try:
        return str(st.secrets.get("UPSTOX_ACCESS_TOKEN", "")).strip()
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


def api_get(path, params=None, timeout=40, max_retries=3):
    """GET from Upstox with pacing, retries on network/timeout, and explicit 429 handling."""
    global _LAST_API_REQUEST
    last_exception = None

    for attempt in range(1, max_retries + 1):
        with _API_REQUEST_LOCK:
            now = time.monotonic()
            wait_for = _MIN_API_GAP - (now - _LAST_API_REQUEST)
            if wait_for > 0:
                time.sleep(wait_for)
            _LAST_API_REQUEST = time.monotonic()

        try:
            response = requests.get(
                f"{API_BASE}{path}",
                headers=HEADERS,
                params=params,
                timeout=timeout,
            )
        except requests.exceptions.Timeout as exc:
            last_exception = exc
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
                continue
            raise UpstoxError(
                f"Network timeout while contacting Upstox after {max_retries} attempts "
                f"(timeout={timeout}s). Please try again in a few seconds."
            ) from exc
        except requests.RequestException as exc:
            last_exception = exc
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
                continue
            raise UpstoxError(f"Network error while contacting Upstox: {exc}") from exc

        if response.status_code == 429:
            retry_after = 30
            try:
                body = response.json()
                if isinstance(body, dict):
                    retry_after = int(body.get("retry_after") or 30)
            except Exception:
                pass
            raise UpstoxRateLimitError(
                f"Upstox is rate-limiting this app (HTTP 429). "
                f"Please wait at least {retry_after} seconds before trying again.",
                retry_after=retry_after,
            )

        if response.status_code != 200:
            try:
                body = response.json()
                message = body.get("errors") or body.get("message") or body
            except Exception:
                message = response.text[:500]
            raise UpstoxError(f"Upstox API {response.status_code}: {message}")

        try:
            return response.json()
        except Exception as exc:
            raise UpstoxError("Upstox returned invalid JSON.") from exc

    raise UpstoxError(f"Network error while contacting Upstox: {last_exception}")


def fmt_price(value):
    try:
        x = float(value)
    except Exception:
        return "—"
    if np.isnan(x):
        return "—"
    return f"₹{x:,.2f}" if abs(x) < 1000 else f"₹{x:,.0f}"


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


@st.cache_data(ttl=60, show_spinner=False)
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
            "Enter an NSE F&O stock symbol such as HDFCBANK or an index such as NIFTY."
        )

    exact = [item for item in results if str(item.get("trading_symbol", "")).upper() == symbol]
    if exact:
        return exact[0]

    if symbol in {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}:
        indexes = [x for x in results if x.get("segment") == "NSE_INDEX"]
        if indexes:
            return indexes[0]

    equities = [x for x in results if x.get("segment") == "NSE_EQ"]
    return equities[0] if equities else results[0]


@st.cache_data(ttl=300, show_spinner=False)
def get_contracts(underlying_key):
    payload = api_get("/v2/option/contract", params={"instrument_key": underlying_key}, timeout=45)
    contracts = payload.get("data", [])
    if not contracts:
        raise UpstoxError("Upstox returned no option contracts for this instrument.")
    return contracts


def available_expiries(contracts):
    today = date.today().isoformat()
    return sorted({str(item.get("expiry")) for item in contracts if item.get("expiry") and str(item.get("expiry")) >= today})


@st.cache_data(ttl=45, show_spinner=False)
def get_option_chain(underlying_key, expiry):
    payload = api_get(
        "/v2/option/chain",
        params={"instrument_key": underlying_key, "expiry_date": expiry},
        timeout=45,
    )
    rows = payload.get("data", [])
    if not rows:
        raise UpstoxError(f"No option-chain data returned for expiry {expiry}.")
    return rows


@st.cache_data(ttl=30, show_spinner=False)
def get_quote(instrument_key):
    payload = api_get("/v3/market-quote/quotes", params={"instrument_key": instrument_key}, timeout=30)
    data = payload.get("data", {})
    if not data:
        raise UpstoxError("No live quote returned by Upstox.")
    return next(iter(data.values()))


@st.cache_data(ttl=90, show_spinner=False)
def get_intraday_candles(instrument_key, interval=5):
    path = f"/v3/historical-candle/intraday/{quote(instrument_key, safe='')}/minutes/{interval}"
    payload = api_get(path, timeout=45)
    candles = payload.get("data", {}).get("candles", [])
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
    for column in ["open", "high", "low", "close", "volume", "oi"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def get_30m_candles(instrument_key):
    end_date = date.today()
    start_date = end_date - timedelta(days=90)
    path = f"/v3/historical-candle/{quote(instrument_key, safe='')}/minutes/30/{end_date.isoformat()}/{start_date.isoformat()}"
    payload = api_get(path, timeout=45)
    candles = payload.get("data", {}).get("candles", [])
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
    for column in ["open", "high", "low", "close", "volume", "oi"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True)


@st.cache_data(ttl=1800, show_spinner=False)
def get_daily_candles(instrument_key):
    end_date = date.today()
    start_date = end_date - timedelta(days=220)
    path = f"/v3/historical-candle/{quote(instrument_key, safe='')}/days/1/{end_date.isoformat()}/{start_date.isoformat()}"
    payload = api_get(path, timeout=45)
    candles = payload.get("data", {}).get("candles", [])
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"])
    for column in ["open", "high", "low", "close", "volume", "oi"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True)


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def technicals(df, spot):
    if df.empty or len(df) < 20:
        return {
            "rsi": 50.0, "ema20": spot, "ema50": spot, "atr": spot * 0.01,
            "trend": "Unavailable", "adx": 0.0, "momentum": 0.0,
            "volume_ratio": 1.0, "vwap": spot
        }

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].fillna(0).astype(float)

    rsi = _rsi(close)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    prev_close = close.shift(1)
    tr = pd.concat([(high-low), (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    atr_safe = atr.replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe
    minus_di = 100 * minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/14, adjust=False).mean()

    typical = (high + low + close) / 3
    if volume.sum() > 0:
        vwap = (typical * volume).cumsum() / volume.cumsum().replace(0, np.nan)
        latest_vwap = safe_float(vwap.iloc[-1], spot)
    else:
        latest_vwap = spot

    lookback = min(10, len(close)-1)
    momentum = ((close.iloc[-1] / close.iloc[-1-lookback] - 1) * 100) if lookback > 0 and close.iloc[-1-lookback] else 0.0
    vol_base = volume.rolling(20).median().iloc[-1]
    volume_ratio = volume.iloc[-1] / vol_base if vol_base and np.isfinite(vol_base) else 1.0

    e20 = safe_float(ema20.iloc[-1], spot)
    e50 = safe_float(ema50.iloc[-1], spot)
    r = safe_float(rsi.iloc[-1], 50.0)
    a = safe_float(atr.iloc[-1], spot * 0.01)
    adx_v = safe_float(adx.iloc[-1], 0.0)

    if spot > e20 > e50:
        trend = "Bullish"
    elif spot < e20 < e50:
        trend = "Bearish"
    else:
        trend = "Sideways"

    return {
        "rsi": r, "ema20": e20, "ema50": e50, "atr": max(a, spot*0.001),
        "trend": trend, "adx": adx_v, "momentum": momentum,
        "volume_ratio": volume_ratio, "vwap": latest_vwap
    }


def overall_trend(tf5, tf30, daily):
    trends = [tf5.get("trend"), tf30.get("trend"), daily.get("trend")]
    bullish = trends.count("Bullish")
    bearish = trends.count("Bearish")
    if bullish >= 2 and bearish == 0:
        return "Bullish", bullish
    if bearish >= 2 and bullish == 0:
        return "Bearish", bearish
    return "Mixed", max(bullish, bearish)


def timeframe_score(side, tf5, tf30, daily):
    desired = "Bullish" if side == "CE" else "Bearish"
    opposite = "Bearish" if side == "CE" else "Bullish"
    values = [tf5, tf30, daily]
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
    return float(np.clip(score, 0, 30)), alignment


def oi_levels(chain, spot):
    valid = chain.dropna(subset=["Strike"]).copy()
    if valid.empty or not np.isfinite(spot):
        return spot, spot, np.nan, {"put_walls": [], "call_walls": [],
                                    "major_support": spot, "major_resistance": spot,
                                    "nearest_support": spot, "nearest_resistance": spot}

    band = valid[(valid["Strike"] >= spot * 0.90) & (valid["Strike"] <= spot * 1.10)].copy()
    if band.empty:
        band = valid.copy()

    band["PE OI"] = pd.to_numeric(band["PE OI"], errors="coerce").fillna(0)
    band["CE OI"] = pd.to_numeric(band["CE OI"], errors="coerce").fillna(0)
    band["PE Chg OI"] = pd.to_numeric(band["PE Chg OI"], errors="coerce").fillna(0)
    band["CE Chg OI"] = pd.to_numeric(band["CE Chg OI"], errors="coerce").fillna(0)

    below = band[band["Strike"] <= spot].copy()
    above = band[band["Strike"] >= spot].copy()

    nearest_support = float(below["Strike"].max()) if not below.empty else float(band["Strike"].min())
    nearest_resistance = float(above["Strike"].min()) if not above.empty else float(band["Strike"].max())

    support_row = below.loc[below["PE OI"].idxmax()] if not below.empty else band.loc[band["PE OI"].idxmax()]
    resistance_row = above.loc[above["CE OI"].idxmax()] if not above.empty else band.loc[band["CE OI"].idxmax()]

    major_support = float(support_row["Strike"])
    major_resistance = float(resistance_row["Strike"])

    total_call_oi = float(band["CE OI"].sum())
    total_put_oi = float(band["PE OI"].sum())
    pcr = total_put_oi / total_call_oi if total_call_oi > 0 else np.nan

    put_walls = band.nlargest(3, "PE OI")[["Strike", "PE OI", "PE Chg OI"]].to_dict("records")
    call_walls = band.nlargest(3, "CE OI")[["Strike", "CE OI", "CE Chg OI"]].to_dict("records")

    return (
        major_support, major_resistance, pcr,
        {
            "put_walls": put_walls, "call_walls": call_walls,
            "major_support": major_support, "major_resistance": major_resistance,
            "nearest_support": nearest_support, "nearest_resistance": nearest_resistance,
            "support_room_pct": max((spot - major_support) / max(spot, 1) * 100, 0),
            "resistance_room_pct": max((major_resistance - spot) / max(spot, 1) * 100, 0),
        },
    )


def nearest_row(chain, strike):
    if chain.empty or not np.isfinite(strike):
        return None
    index = (chain["Strike"] - strike).abs().idxmin()
    return chain.loc[index]


def normalize_chain(rows):
    records = []
    for item in rows:
        strike = safe_float(item.get("strike_price"))
        call = item.get("call_options") or {}
        put = item.get("put_options") or {}
        call_market = call.get("market_data") or {}
        call_greeks = call.get("option_greeks") or {}
        put_market = put.get("market_data") or {}
        put_greeks = put.get("option_greeks") or {}

        call_oi = safe_float(call_market.get("oi"), 0)
        put_oi = safe_float(put_market.get("oi"), 0)
        call_prev_oi = safe_float(call_market.get("prev_oi"), 0)
        put_prev_oi = safe_float(put_market.get("prev_oi"), 0)

        records.append({
            "Strike": strike,
            "CE Key": call.get("instrument_key"),
            "CE LTP": safe_float(call_market.get("ltp")),
            "CE Bid": safe_float(call_market.get("bid_price")),
            "CE Ask": safe_float(call_market.get("ask_price")),
            "CE OI": call_oi,
            "CE Chg OI": call_oi - call_prev_oi,
            "CE Volume": safe_float(call_market.get("volume"), 0),
            "CE IV": safe_float(call_greeks.get("iv")),
            "CE Delta": safe_float(call_greeks.get("delta")),
            "CE PoP": safe_float(call_greeks.get("pop")),
            "PE Key": put.get("instrument_key"),
            "PE LTP": safe_float(put_market.get("ltp")),
            "PE Bid": safe_float(put_market.get("bid_price")),
            "PE Ask": safe_float(put_market.get("ask_price")),
            "PE OI": put_oi,
            "PE Chg OI": put_oi - put_prev_oi,
            "PE Volume": safe_float(put_market.get("volume"), 0),
            "PE IV": safe_float(put_greeks.get("iv")),
            "PE Delta": safe_float(put_greeks.get("delta")),
            "PE PoP": safe_float(put_greeks.get("pop")),
        })
    return pd.DataFrame(records).sort_values("Strike").reset_index(drop=True)


def score_option(row, side, spot, pcr, tf5, tf30, daily, chain,
                 support=None, resistance=None, oi_wall_info=None):
    if side == "CE":
        premium = safe_float(row["CE LTP"])
        delta = safe_float(row["CE Delta"])
        iv = safe_float(row["CE IV"])
        pop = safe_float(row["CE PoP"])
        chg_oi = safe_float(row["CE Chg OI"], 0)
        volume = safe_float(row["CE Volume"], 0)
        oi = safe_float(row["CE OI"], 0)
        bid = safe_float(row["CE Bid"])
        ask = safe_float(row["CE Ask"])
    else:
        premium = safe_float(row["PE LTP"])
        delta = safe_float(row["PE Delta"])
        iv = safe_float(row["PE IV"])
        pop = safe_float(row["PE PoP"])
        chg_oi = safe_float(row["PE Chg OI"], 0)
        volume = safe_float(row["PE Volume"], 0)
        oi = safe_float(row["PE OI"], 0)
        bid = safe_float(row["PE Bid"])
        ask = safe_float(row["PE Ask"])

    desired = "Bullish" if side == "CE" else "Bearish"
    opposite = "Bearish" if side == "CE" else "Bullish"

    tf_points, alignment = timeframe_score(side, tf5, tf30, daily)

    tf = tf5
    momentum_points = 0
    if tf.get("trend") == desired:
        momentum_points += 5
    rsi = tf.get("rsi", 50)
    if side == "CE":
        if 52 <= rsi <= 68: momentum_points += 3
        elif 50 <= rsi < 52: momentum_points += 1
        if tf.get("momentum", 0) > 0: momentum_points += 3
    else:
        if 32 <= rsi <= 48: momentum_points += 3
        elif 48 < rsi <= 50: momentum_points += 1
        if tf.get("momentum", 0) < 0: momentum_points += 3
    if tf.get("adx", 0) >= 25: momentum_points += 4
    elif tf.get("adx", 0) >= 20: momentum_points += 2
    momentum_points = min(momentum_points, 15)

    vwap = safe_float(tf5.get("vwap"), spot)
    vwap_points = 0
    if np.isfinite(vwap) and vwap > 0:
        if side == "CE":
            if spot > vwap and tf5.get("momentum", 0) > 0: vwap_points = 10
            elif spot > vwap: vwap_points = 6
            elif spot >= vwap * 0.997: vwap_points = 2
        else:
            if spot < vwap and tf5.get("momentum", 0) < 0: vwap_points = 10
            elif spot < vwap: vwap_points = 6
            elif spot <= vwap * 1.003: vwap_points = 2
    else:
        vwap_gap_pct = 0.0

    pcr_points = 0
    if np.isfinite(pcr):
        if side == "CE":
            pcr_points = 10 if 0.90 <= pcr <= 1.35 else 5 if 0.80 <= pcr < 0.90 else 0
        else:
            pcr_points = 10 if 0.65 <= pcr <= 1.10 else 5 if 1.10 < pcr <= 1.25 else 0

    oi_points = 5 if chg_oi < 0 else 3 if chg_oi == 0 else 1

    quality = 0
    abs_delta = abs(delta) if np.isfinite(delta) else np.nan
    if np.isfinite(abs_delta):
        if 0.45 <= abs_delta <= 0.65: quality += 6
        elif 0.40 <= abs_delta < 0.45 or 0.65 < abs_delta <= 0.75: quality += 4
        elif 0.35 <= abs_delta < 0.40 or 0.75 < abs_delta <= 0.80: quality += 2

    spread_pct = (max(ask - bid, 0) / max((ask + bid) / 2, 0.01) * 100
                  if np.isfinite(ask) and np.isfinite(bid) and ask > 0 and bid > 0 else 999)
    if spread_pct <= 1.0: quality += 5
    elif spread_pct <= 2.0: quality += 4
    elif spread_pct <= 3.0: quality += 2

    if volume >= 10000: quality += 5
    elif volume >= 5000: quality += 4
    elif volume >= 1000: quality += 2

    if oi >= 10000: quality += 4
    elif oi >= 3000: quality += 3
    elif oi > 0: quality += 1

    distance_pct = abs(float(row["Strike"]) - spot) / max(spot, 1) * 100
    if distance_pct <= 1.0: strike_points = 6
    elif distance_pct <= 2.0: strike_points = 5
    elif distance_pct <= 3.0: strike_points = 3
    elif distance_pct <= 5.0: strike_points = 1
    else: strike_points = 0

    room_points = 0
    room_pct = np.nan
    if side == "CE" and np.isfinite(resistance):
        room_pct = max((resistance - spot) / max(spot, 1) * 100, 0)
        if spot >= resistance: room_points = 4
        elif room_pct >= 2.0: room_points = 4
        elif room_pct >= 1.0: room_points = 2
    elif side == "PE" and np.isfinite(support):
        room_pct = max((spot - support) / max(spot, 1) * 100, 0)
        if spot <= support: room_points = 4
        elif room_pct >= 2.0: room_points = 4
        elif room_pct >= 1.0: room_points = 2

    strike_quality = strike_points + room_points
    pop_points = float(np.clip((pop - 55) / 3.0, 0, 10)) if np.isfinite(pop) else 0

    raw_score = (tf_points + momentum_points + vwap_points + pcr_points + oi_points +
                 quality + strike_quality + pop_points)
    score = float(np.clip(raw_score / 110 * 100, 0, 100))

    return {
        "score": score, "premium": premium, "delta": delta, "iv": iv, "pop": pop,
        "chg_oi": chg_oi, "volume": volume, "oi": oi, "spread_pct": spread_pct,
        "alignment": alignment, "distance_pct": distance_pct, "quality": quality,
        "vwap": vwap, "vwap_gap_pct": 0.0, "room_pct": room_pct, "strike_quality": strike_quality,
    }


def build_plan(row, side, spot, support, resistance, pcr, tf5, tf30, daily,
               risk_profile, chain, oi_wall_info=None):
    if row is None:
        return None

    scored = score_option(row, side, spot, pcr, tf5, tf30, daily, chain,
                          support=support, resistance=resistance, oi_wall_info=oi_wall_info)

    ask = safe_float(row[f"{side} Ask"])
    ltp = safe_float(row[f"{side} LTP"])
    entry = ask if np.isfinite(ask) and ask > 0 else ltp
    if not np.isfinite(entry) or entry <= 0:
        return None

    risk_settings = {
        "Conservative": (0.72, 1.25, 1.55),
        "Balanced": (0.70, 1.35, 1.75),
        "Aggressive": (0.65, 1.50, 2.00),
    }
    sl_factor, target1_factor, target2_factor = risk_settings[risk_profile]
    sl = round(entry * sl_factor, 2)
    target1 = round(entry * target1_factor, 2)
    target2 = round(entry * target2_factor, 2)
    rr1 = (target1 - entry) / max(entry - sl, 0.01)
    rr2 = (target2 - entry) / max(entry - sl, 0.01)

    atr = max(tf5.get("atr", spot * 0.01), spot * 0.001)
    trigger_buffer = max(atr * 0.15, spot * 0.0015)

    candle_confirmed = False
    volume_confirmed = False
    if side == "CE":
        trigger_level = resistance + trigger_buffer
        trigger_hit = spot >= trigger_level
        if trigger_hit and isinstance(tf5, dict):
            candle_confirmed = (tf5.get("trend") == "Bullish" and tf5.get("momentum", 0) > 0 and tf5.get("rsi", 50) >= 52)
            volume_confirmed = tf5.get("volume_ratio", 1.0) >= 1.10
        trigger = (f"Enter only after spot breaks and sustains above {fmt_price(trigger_level)} "
                   "with 5m bullish confirmation and preferably above-average volume.")
        exit_rule = (f"Exit if spot loses support {fmt_price(support)} or premium hits "
                     f"{fmt_price(sl)}. After Target 1, book partial profit and trail.")
    else:
        trigger_level = support - trigger_buffer
        trigger_hit = spot <= trigger_level
        if trigger_hit and isinstance(tf5, dict):
            candle_confirmed = (tf5.get("trend") == "Bearish" and tf5.get("momentum", 0) < 0 and tf5.get("rsi", 50) <= 48)
            volume_confirmed = tf5.get("volume_ratio", 1.0) >= 1.10
        trigger = (f"Enter only after spot breaks and sustains below {fmt_price(trigger_level)} "
                   "with 5m bearish confirmation and preferably above-average volume.")
        exit_rule = (f"Exit if spot reclaims resistance {fmt_price(resistance)} or premium "
                     f"hits {fmt_price(sl)}. After Target 1, book partial profit and trail.")

    desired = "Bullish" if side == "CE" else "Bearish"
    opposite = "Bearish" if side == "CE" else "Bullish"

    hard_fail = []
    if scored["score"] < 72: hard_fail.append("setup score below 72")
    if scored["alignment"] < 2: hard_fail.append("fewer than 2 aligned timeframes")
    if tf5.get("trend") == opposite or tf30.get("trend") == opposite: hard_fail.append("short-term trend conflict")
    if scored["spread_pct"] > 3: hard_fail.append("wide option spread")
    if not np.isfinite(scored["delta"]) or not (0.35 <= abs(scored["delta"]) <= 0.80): hard_fail.append("poor delta")
    if not np.isfinite(scored["pop"]) or scored["pop"] < 55: hard_fail.append("low Upstox PoP")
    if scored["volume"] < 1000: hard_fail.append("weak option liquidity")
    if not np.isfinite(scored["oi"]) or scored["oi"] <= 0: hard_fail.append("no option OI")

    vwap = safe_float(tf5.get("vwap"), spot)
    if np.isfinite(vwap) and vwap > 0:
        if side == "CE" and spot < vwap * 0.997: hard_fail.append("price below VWAP")
        if side == "PE" and spot > vwap * 1.003: hard_fail.append("price above VWAP")

    if side == "CE":
        wall_room = (resistance - spot) / max(spot, 1) * 100
        if spot < resistance and wall_room < 0.50: hard_fail.append("resistance too close")
    else:
        wall_room = (spot - support) / max(spot, 1) * 100
        if spot > support and wall_room < 0.50: hard_fail.append("support too close")

    if not trigger_hit:
        trigger_state = "WAIT FOR TRIGGER"
    elif not candle_confirmed or not volume_confirmed:
        trigger_state = "WAIT FOR CONFIRMATION"
    else:
        trigger_state = "READY" if not hard_fail else "NO TRADE"

    readiness = trigger_state if not hard_fail else "NO TRADE"

    return {
        "side": side, "strike": float(row["Strike"]), "entry": float(entry),
        "sl": sl, "target1": target1, "target2": target2,
        "pop": scored["pop"], "delta": scored["delta"], "iv": scored["iv"],
        "score": scored["score"], "rr1": rr1, "rr2": rr2,
        "trigger": trigger, "trigger_level": trigger_level,
        "trigger_hit": trigger_hit, "candle_confirmed": candle_confirmed,
        "volume_confirmed": volume_confirmed, "readiness": readiness,
        "fail_reasons": hard_fail, "exit": exit_rule,
        "oi": row[f"{side} OI"], "chg_oi": scored["chg_oi"],
        "volume": scored["volume"], "spread_pct": scored["spread_pct"],
        "alignment": scored["alignment"], "vwap": scored["vwap"],
        "room_pct": scored["room_pct"],
    }


# ============================================================
# F&O SCANNER
# ============================================================
FNO_MASTER_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"


@st.cache_data(ttl=3600, show_spinner=False)
def get_fno_underlyings():
    try:
        response = requests.get(FNO_MASTER_URL, timeout=40)
        response.raise_for_status()
        raw = gzip.decompress(response.content)
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise UpstoxError(f"Unable to load the Upstox NSE F&O instrument list: {exc}") from exc

    if isinstance(payload, dict):
        records = payload.get("data", payload.get("instruments", []))
    else:
        records = payload

    today = date.today().isoformat()
    universe = {}

    for item in records:
        if not isinstance(item, dict): continue
        if item.get("segment") != "NSE_FO": continue
        if item.get("instrument_type") not in {"CE", "PE", "FUT"}: continue
        if item.get("underlying_type") != "EQUITY": continue

        expiry = str(item.get("expiry", ""))
        if not expiry: continue

        if expiry.isdigit():
            try:
                expiry_date = datetime.fromtimestamp(int(expiry) / 1000, tz=ZoneInfo("Asia/Kolkata")).date().isoformat()
            except Exception:
                continue
        else:
            expiry_date = expiry[:10]

        if expiry_date < today: continue

        underlying_key = item.get("underlying_key")
        symbol = str(item.get("underlying_symbol") or "").strip().upper()
        if not underlying_key or not symbol: continue

        current = universe.get(underlying_key)
        if current is None or expiry_date < current["expiry"]:
            universe[underlying_key] = {
                "symbol": symbol, "underlying_key": underlying_key, "expiry": expiry_date,
            }

    return sorted(universe.values(), key=lambda x: x["symbol"])


def scan_full_fno_pop_market(min_pop=75.0):
    universe = get_fno_underlyings()
    candidates = []
    scanned = 0
    failed = 0
    progress = st.progress(0, text="Starting full F&O market scan...")

    for idx, item in enumerate(universe, start=1):
        try:
            if idx > 1: time.sleep(0.80)
            rows = get_option_chain(item["underlying_key"], item["expiry"])
            if not rows:
                failed += 1
                continue

            spot_values = [safe_float(row.get("underlying_spot_price")) for row in rows if np.isfinite(safe_float(row.get("underlying_spot_price")))]
            spot_value = spot_values[0] if spot_values else np.nan
            best_for_stock = None

            for raw in rows:
                strike = safe_float(raw.get("strike_price"))
                if not np.isfinite(strike): continue

                for side, action in (("CE", "CALL BUY"), ("PE", "PUT BUY")):
                    option = raw.get("call_options" if side == "CE" else "put_options") or {}
                    market = option.get("market_data") or {}
                    greeks = option.get("option_greeks") or {}

                    pop = safe_float(greeks.get("pop"))
                    if not np.isfinite(pop) or pop <= min_pop: continue

                    ltp = safe_float(market.get("ltp"))
                    ask = safe_float(market.get("ask_price"))
                    bid = safe_float(market.get("bid_price"))
                    volume = safe_float(market.get("volume"), 0)
                    oi = safe_float(market.get("oi"), 0)
                    delta = safe_float(greeks.get("delta"))
                    iv = safe_float(greeks.get("iv"))

                    entry = ask if np.isfinite(ask) and ask > 0 else ltp
                    if not np.isfinite(entry) or entry <= 0: continue

                    distance = abs(strike - spot_value) / max(spot_value, 1) if np.isfinite(spot_value) else 999
                    sl = round(entry * 0.70, 2)
                    target1 = round(entry * 1.40, 2)
                    target2 = round(entry * 1.80, 2)

                    candidate = {
                        "Stock": item["symbol"], "Trade": action, "Strike": strike,
                        "Expiry": item["expiry"], "PoP": pop, "Entry": entry,
                        "SL": sl, "Target1": target1, "Target2": target2,
                        "Exit": "Exit at SL or Target 2; trail after Target 1",
                        "LTP": ltp, "Bid": bid, "Ask": ask, "Delta": delta,
                        "IV": iv, "Volume": volume, "OI": oi, "distance": distance,
                    }

                    if best_for_stock is None or (candidate["PoP"], candidate["Volume"], -candidate["distance"]) > (best_for_stock["PoP"], best_for_stock["Volume"], -best_for_stock["distance"]):
                        best_for_stock = candidate

            if best_for_stock is not None:
                candidates.append(best_for_stock)
            scanned += 1
        except UpstoxRateLimitError:
            progress.empty()
            raise
        except Exception:
            failed += 1

        progress.progress(idx / max(len(universe), 1), text=f"Scanning F&O market: {idx}/{len(universe)} stocks")

    progress.empty()
    candidates.sort(key=lambda x: (-x["PoP"], -x["Volume"], x["distance"]))
    return candidates[:5], len(universe), scanned, failed


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("""
    <div style="padding: 12px 8px 20px 8px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:24px;">
            <div style="width:36px;height:36px;background:linear-gradient(135deg,#0ea5e9,#0284c7);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;">📊</div>
            <div>
                <div style="font-size:16px;font-weight:800;color:white;">FO PRO</div>
                <div style="font-size:11px;color:#94a3b8;">Trader Assistant</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🔥 Top 5 F&O PoP Scanner")
    st.caption("Scans full NSE equity F&O for PoP > 75%")

    scan_market = st.button("🔎 Scan Full F&O Market", use_container_width=True, type="primary")

    if scan_market:
        try:
            with st.spinner("Scanning the full F&O market..."):
                results, total, scanned, failed = scan_full_fno_pop_market(75.0)
            st.session_state["fno_pop_results"] = results
            st.session_state["fno_pop_scan_info"] = (total, scanned, failed)
            st.session_state["fno_pop_scan_time"] = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")
        except UpstoxRateLimitError as exc:
            st.session_state["fno_pop_results"] = []
            st.error(f"⏳ Rate limit. Wait ~{exc.retry_after}s then try again.")
        except UpstoxError as exc:
            st.session_state["fno_pop_results"] = []
            st.error(str(exc))
        except Exception as exc:
            st.session_state["fno_pop_results"] = []
            st.error(f"Scan failed: {exc}")

    pop_results = st.session_state.get("fno_pop_results", [])
    if pop_results:
        st.success(f"Top {len(pop_results)} trades with PoP > 75%")
        scanner_display = pd.DataFrame([{
            "Stock": r["Stock"], "Trade": r["Trade"], "Strike": int(r["Strike"]),
            "PoP": f"{r['PoP']:.1f}%", "Entry": fmt_price(r["Entry"]),
            "SL": fmt_price(r["SL"]), "T1": fmt_price(r["Target1"]), "T2": fmt_price(r["Target2"]),
        } for r in pop_results])
        st.dataframe(scanner_display, use_container_width=True, hide_index=True, height=280)

    st.divider()
    st.markdown("### 🔎 Analyze Instrument")

    symbol_input = st.text_input("Symbol", value=st.session_state.get("symbol", "NIFTY"),
                                 placeholder="NIFTY / BANKNIFTY / HDFCBANK")
    risk_profile = st.selectbox("Risk Profile", ["Conservative", "Balanced", "Aggressive"], index=1)

    analyze = st.button("🔍 Analyze", type="primary", use_container_width=True)
    refresh = st.button("↻ Refresh Live Data", use_container_width=True)

    if st_autorefresh is not None:
        auto_refresh = st.checkbox("Auto refresh every 60s", value=False)
        if auto_refresh:
            st_autorefresh(interval=60_000, key="upstox_live_refresh")

    st.divider()
    st.markdown("""
    <div style="padding:10px;background:#1e293b;border-radius:10px;margin-top:10px;">
        <div style="font-size:12px;color:#4ade80;font-weight:600;">● Upstox Connected</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:2px;">Live Market Data</div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("FO PRO Trader Assistant  •  v1.0")

if analyze:
    st.session_state["symbol"] = alias_symbol(symbol_input)
    st.rerun()
if refresh:
    st.cache_data.clear()
    st.rerun()

symbol = alias_symbol(st.session_state.get("symbol", symbol_input or "NIFTY"))

# ============================================================
# LIVE DATA
# ============================================================
try:
    with st.spinner(f"Fetching live Upstox data for {symbol}..."):
        underlying = search_underlying(symbol)
        underlying_key = underlying["instrument_key"]
        contracts = get_contracts(underlying_key)
        expiries = available_expiries(contracts)
        if not expiries:
            raise UpstoxError("No upcoming F&O expiry found.")
        selected_expiry = expiries[0]
        raw_chain = get_option_chain(underlying_key, selected_expiry)
        chain = normalize_chain(raw_chain)
        quote_data = get_quote(underlying_key)
        spot = safe_float(quote_data.get("last_price"))
        previous_close = safe_float(quote_data.get("prev_close_price"), spot)
        net_change = safe_float(quote_data.get("net_change"), spot - previous_close)
        change_pct = (net_change / previous_close * 100) if previous_close else 0
        candles = get_daily_candles(underlying_key)
        candles_30m = get_30m_candles(underlying_key)
        candles_5m = get_intraday_candles(underlying_key, 5)
        daily_tech = technicals(candles, spot)
        tf30 = technicals(candles_30m, spot)
        tf5 = technicals(candles_5m, spot)
        tech = daily_tech
except UpstoxRateLimitError as e:
    st.error(f"⏳ Rate limit. Wait ~{e.retry_after}s then refresh.")
    st.stop()
except UpstoxError as e:
    st.error(str(e))
    st.stop()
except Exception as e:
    st.error(f"Unexpected error: {e}")
    st.stop()

support, resistance, pcr, oi_wall_info = oi_levels(chain, spot)
atm_index = (chain["Strike"] - spot).abs().idxmin()
atm_strike = float(chain.loc[atm_index, "Strike"])

candidate_rows = chain.iloc[max(0, atm_index-5): min(len(chain), atm_index+6)]
ce_candidates, pe_candidates = [], []

for _, row in candidate_rows.iterrows():
    ce_scored = score_option(row, "CE", spot, pcr, tf5, tf30, daily_tech, chain, support=support, resistance=resistance, oi_wall_info=oi_wall_info)
    pe_scored = score_option(row, "PE", spot, pcr, tf5, tf30, daily_tech, chain, support=support, resistance=resistance, oi_wall_info=oi_wall_info)
    ce_candidates.append((ce_scored, row))
    pe_candidates.append((pe_scored, row))

def _candidate_key(item):
    scored, row = item
    abs_delta = abs(safe_float(scored.get("delta"), 0))
    spread = safe_float(scored.get("spread_pct"), 999)
    volume = safe_float(scored.get("volume"), 0)
    distance = safe_float(scored.get("distance_pct"), 999)
    return (scored["score"], -abs(abs_delta-0.55), -spread, np.log1p(max(volume,0)), -distance)

best_ce_scored, best_ce_row = max(ce_candidates, key=_candidate_key, default=({"score":0}, None))
best_pe_scored, best_pe_row = max(pe_candidates, key=_candidate_key, default=({"score":0}, None))

ce_plan = build_plan(best_ce_row, "CE", spot, support, resistance, pcr, tf5, tf30, daily_tech, risk_profile, chain, oi_wall_info)
pe_plan = build_plan(best_pe_row, "PE", spot, support, resistance, pcr, tf5, tf30, daily_tech, risk_profile, chain, oi_wall_info)

ce_score = ce_plan["score"] if ce_plan else 0
pe_score = pe_plan["score"] if pe_plan else 0

overall_direction, overall_alignment = overall_trend(tf5, tf30, daily_tech)

if ce_plan and ce_score >= 72 and ce_score >= pe_score + 8 and overall_direction == "Bullish" and ce_plan["readiness"] in {"READY", "WAIT FOR TRIGGER", "WAIT FOR CONFIRMATION"}:
    decision = "CALL BUY" if ce_plan["readiness"] == "READY" else ce_plan["readiness"]
    best_plan = ce_plan
elif pe_plan and pe_score >= 72 and pe_score >= ce_score + 8 and overall_direction == "Bearish" and pe_plan["readiness"] in {"READY", "WAIT FOR TRIGGER", "WAIT FOR CONFIRMATION"}:
    decision = "PUT BUY" if pe_plan["readiness"] == "READY" else pe_plan["readiness"]
    best_plan = pe_plan
else:
    decision = "NO TRADE"
    best_plan = ce_plan if ce_score >= pe_score else pe_plan

best_score = best_plan["score"] if best_plan else 0
best_alignment = best_plan["alignment"] if best_plan else 0
confidence = int(np.clip(best_score * 0.70 + (best_alignment / 3) * 20 + (5 if overall_direction in {"Bullish", "Bearish"} else 0), 0, 100))

active_plan = None
if decision == "CALL BUY":
    active_plan = ce_plan
elif decision == "PUT BUY":
    active_plan = pe_plan
elif decision in {"WAIT FOR TRIGGER", "WAIT FOR CONFIRMATION"}:
    active_plan = best_plan

# ============================================================
# UI — Matches the uploaded professional dashboard
# ============================================================

market_now = datetime.now(ZoneInfo("Asia/Kolkata"))
market_open = (market_now.weekday() < 5 and (market_now.hour, market_now.minute) >= (9, 15) and (market_now.hour, market_now.minute) < (15, 30))

# ----- Top Bar -----
change_color = "#16a34a" if net_change >= 0 else "#dc2626"
st.markdown(f"""
<div class="top-bar">
    <div class="top-bar-left">
        <div style="font-size:15px;font-weight:700;color:#0f172a;">{symbol}</div>
        <div class="top-bar-price">{fmt_price(spot)}</div>
        <div class="top-bar-change" style="color:{change_color};">{net_change:+.2f} ({change_pct:+.2f}%)</div>
    </div>
    <div class="live-dot">{'Live Data' if market_open else 'Market Closed'} &nbsp;•&nbsp; {market_now.strftime('%b %d, %Y %I:%M %p')} &nbsp;•&nbsp; Expiry {selected_expiry}</div>
</div>
""", unsafe_allow_html=True)

# ----- MASTER TRADE DECISION -----
if decision == "CALL BUY":
    btn_html = '<div class="call-buy-btn">↗ CALL BUY</div>'
    sub = "Bullish setup • Confirmation required"
    ready_html = '<div class="ready-badge">✓ TRADE READY</div>' if active_plan and active_plan.get("readiness") == "READY" else '<div class="ready-badge" style="background:#fef9c3;color:#a16207;border-color:#fde68a;">Waiting for trigger</div>'
elif decision == "PUT BUY":
    btn_html = '<div class="put-buy-btn">↘ PUT BUY</div>'
    sub = "Bearish setup • Confirmation required"
    ready_html = '<div class="ready-badge">✓ TRADE READY</div>' if active_plan and active_plan.get("readiness") == "READY" else '<div class="ready-badge" style="background:#fef9c3;color:#a16207;border-color:#fde68a;">Waiting for trigger</div>'
else:
    btn_html = '<div class="no-trade-btn">○ NO TRADE</div>'
    sub = "Conditions are not sufficiently aligned for a valid setup"
    ready_html = ""

st.markdown(f"""
<div class="master-decision">
    <div class="card-title">🎯 MASTER TRADE DECISION</div>
    <div class="master-decision-header">
        <div>
            {btn_html}
            <div style="margin-top:8px;font-size:13px;color:#64748b;">{sub}</div>
        </div>
        <div style="text-align:right;">
            {ready_html}
            <div class="decision-meta" style="justify-content:flex-end;margin-top:12px;">
                <div class="decision-meta-item"><span>Setup Score</span><b>{best_score:.0f}/100</b></div>
                <div class="decision-meta-item"><span>Confidence</span><b>{confidence}/100</b></div>
                <div class="decision-meta-item"><span>Market Trend</span><b style="color:{'#16a34a' if overall_direction=='Bullish' else '#dc2626' if overall_direction=='Bearish' else '#64748b'}">{overall_direction.upper()}</b></div>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ----- TRADE PLAN + CHECKLIST -----
col_plan, col_check = st.columns([1.15, 1])

with col_plan:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📋 TRADE PLAN</div>', unsafe_allow_html=True)

    if active_plan:
        side_label = "CALL BUY" if active_plan["side"] == "CE" else "PUT BUY"
        st.markdown(f"""
        <div style="font-size:15px;font-weight:700;color:#0f172a;margin-bottom:4px;">
            {symbol} {active_plan['strike']:.0f} {'CE' if active_plan['side']=='CE' else 'PE'}
            <span style="background:#dcfce7;color:#15803d;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:6px;">{side_label}</span>
        </div>
        <div class="plan-grid">
            <div class="plan-item"><span>Entry</span><b>{fmt_price(active_plan.get('entry'))}</b></div>
            <div class="plan-item"><span>Stop Loss</span><b>{fmt_price(active_plan.get('sl'))}</b></div>
            <div class="plan-item"><span>Target 1</span><b>{fmt_price(active_plan.get('target1'))}</b></div>
            <div class="plan-item"><span>Target 2</span><b>{fmt_price(active_plan.get('target2'))}</b></div>
        </div>
        <div class="plan-grid">
            <div class="plan-item"><span>PoP</span><b>{active_plan.get('pop',0):.1f}%</b></div>
            <div class="plan-item"><span>Delta</span><b>{active_plan.get('delta',0):.2f}</b></div>
            <div class="plan-item"><span>IV</span><b>{active_plan.get('iv',0):.1f}%</b></div>
            <div class="plan-item"><span>R:R (T2)</span><b>1 : {active_plan.get('rr2',0):.2f}</b></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No actionable trade plan. Engine currently says NO TRADE.")
    st.markdown('</div>', unsafe_allow_html=True)

with col_check:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">✅ TRADE CHECKLIST</div>', unsafe_allow_html=True)

    direction_pass = overall_direction in {"Bullish", "Bearish"}
    mtf_pass = overall_alignment >= 2
    oi_pass = np.isfinite(support) and np.isfinite(resistance) and support < spot < resistance
    vwap_value = safe_float(tf5.get("vwap"), spot)
    vwap_pass = (spot >= vwap_value * 0.997) if (active_plan and active_plan["side"] == "CE") else (spot <= vwap_value * 1.003) if active_plan else False
    momentum_pass = (tf5.get("trend") == "Bullish" and tf5.get("momentum", 0) > 0) if (active_plan and active_plan["side"] == "CE") else (tf5.get("trend") == "Bearish" and tf5.get("momentum", 0) < 0) if active_plan else False
    option_quality_pass = active_plan and np.isfinite(active_plan.get("delta")) and 0.35 <= abs(active_plan.get("delta", 0)) <= 0.80 and active_plan.get("volume", 0) >= 1000

    checks = [
        ("Market Direction", "PASS" if direction_pass else "FAIL", overall_direction),
        ("Multi-Timeframe", "PASS" if mtf_pass else "FAIL", f"{overall_alignment}/3 aligned"),
        ("OI Structure", "PASS" if oi_pass else "FAIL", f"S {fmt_price(support)} / R {fmt_price(resistance)}"),
        ("VWAP", "PASS" if vwap_pass else "FAIL", f"5m VWAP {fmt_price(vwap_value)}"),
        ("Momentum", "PASS" if momentum_pass else "FAIL", tf5.get("trend", "—")),
        ("Option Quality", "PASS" if option_quality_pass else "FAIL", "Liquidity & Greeks"),
    ]
    passed = sum(1 for _, s, _ in checks if s == "PASS")

    rows_html = ""
    for i, (name, status, obs) in enumerate(checks, 1):
        badge = f'<span class="pass-badge">PASS</span>' if status == "PASS" else f'<span class="fail-badge">FAIL</span>'
        rows_html += f"<tr><td>{i}</td><td>{name}</td><td>{badge}</td><td>{obs}</td></tr>"

    st.markdown(f"""
    <table class="check-table">
        <thead><tr><th>#</th><th>Check</th><th>Status</th><th>Observation</th></tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    <div style="text-align:right;margin-top:10px;font-size:13px;font-weight:700;color:#0f172a;">
        {passed}/6 PASS
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ----- ENTRY CONDITION + MARKET LEVELS + MARKET BIAS -----
c1, c2, c3 = st.columns([1.3, 1, 0.9])

with c1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">⚡ ENTRY CONDITION</div>', unsafe_allow_html=True)
    if active_plan:
        dist = abs(spot - active_plan["trigger_level"])
        st.markdown(f"""
        <div style="font-size:13px;color:#334155;line-height:1.5;margin-bottom:12px;">
            {active_plan['trigger']}
        </div>
        <div class="plan-grid">
            <div class="plan-item"><span>Current Spot</span><b>{fmt_price(spot)}</b></div>
            <div class="plan-item"><span>Trigger</span><b>{fmt_price(active_plan['trigger_level'])}</b></div>
            <div class="plan-item"><span>Distance</span><b>{fmt_price(dist)}</b></div>
        </div>
        <div class="entry-box">⏳ Waiting for entry trigger...</div>
        """, unsafe_allow_html=True)
    else:
        st.info("No entry condition — engine says NO TRADE.")
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📍 MARKET LEVELS</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="levels-visual">
        <div class="level-row">
            <span style="color:#dc2626;font-weight:600;width:70px;">Resistance</span>
            <div class="level-line level-resistance"></div>
            <b>{fmt_price(resistance)}</b>
        </div>
        <div class="level-row">
            <span style="color:#3b82f6;font-weight:600;width:70px;">Current</span>
            <div class="level-line level-current"></div>
            <b>{fmt_price(spot)}</b>
        </div>
        <div class="level-row">
            <span style="color:#16a34a;font-weight:600;width:70px;">Support</span>
            <div class="level-line level-support"></div>
            <b>{fmt_price(support)}</b>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📊 MARKET BIAS</div>', unsafe_allow_html=True)
    bias_color = "#16a34a" if overall_direction == "Bullish" else "#dc2626" if overall_direction == "Bearish" else "#64748b"
    st.markdown(f"""
    <div style="font-size:22px;font-weight:800;color:{bias_color};margin:8px 0 14px 0;">
        {'↗' if overall_direction=='Bullish' else '↘' if overall_direction=='Bearish' else '→'} {overall_direction.upper()}
    </div>
    <div style="font-size:13px;color:#64748b;">
        <div style="display:flex;justify-content:space-between;margin:6px 0;"><span>PCR</span><b style="color:#0f172a;">{pcr:.2f if np.isfinite(pcr) else '—'}</b></div>
        <div style="display:flex;justify-content:space-between;margin:6px 0;"><span>VWAP</span><b style="color:#0f172a;">{fmt_price(tf5.get('vwap'))}</b></div>
        <div style="display:flex;justify-content:space-between;margin:6px 0;"><span>ATR</span><b style="color:#0f172a;">{fmt_price(daily_tech.get('atr'))}</b></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ----- WHY THIS SETUP + CHART -----
w1, w2 = st.columns([1, 1.15])

with w1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">💡 WHY THIS SETUP?</div>', unsafe_allow_html=True)
    if active_plan:
        side_name = "CALL" if active_plan["side"] == "CE" else "PUT"
        why_list = [
            f"{'Bullish' if active_plan['side']=='CE' else 'Bearish'} short-term trend",
            f"Multiple timeframes aligned ({best_alignment}/3)",
            f"Price structure supports {side_name} direction",
            f"VWAP supports {'bullish' if active_plan['side']=='CE' else 'bearish'} bias",
            "Option liquidity and Greeks acceptable",
            "Entry trigger still required" if active_plan.get("readiness") != "READY" else "Entry conditions met",
        ]
        for item in why_list:
            st.markdown(f'<div class="why-item">{item}</div>', unsafe_allow_html=True)
    else:
        st.write("• Market direction not sufficiently aligned")
        st.write(f"• Multi-timeframe alignment: {overall_alignment}/3")
        st.write("• Candidate hidden because master decision is NO TRADE")
    st.markdown('</div>', unsafe_allow_html=True)

with w2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📈 KEY CHART (Daily)</div>', unsafe_allow_html=True)
    if not candles.empty:
        chart_df = candles.set_index("timestamp")[["close"]].tail(60)
        st.line_chart(chart_df, use_container_width=True, height=220)
    else:
        st.info("No daily candle data available.")
    st.markdown('</div>', unsafe_allow_html=True)

# ----- LIVE OPTION CHAIN -----
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(f'<div class="chain-header">Live Option Chain (Around ATM) — Expiry {selected_expiry}</div>', unsafe_allow_html=True)

view = chain.copy()
display = pd.DataFrame({
    "Strike": view["Strike"].round(0).astype(int),
    "CE LTP": view["CE LTP"].round(2),
    "CE OI": view["CE OI"].round(0).astype("Int64"),
    "CE ΔOI": view["CE Chg OI"].round(0).astype("Int64"),
    "CE IV": view["CE IV"].round(1),
    "CE Delta": view["CE Delta"].round(3),
    "PE LTP": view["PE LTP"].round(2),
    "PE OI": view["PE OI"].round(0).astype("Int64"),
    "PE ΔOI": view["PE Chg OI"].round(0).astype("Int64"),
    "PE IV": view["PE IV"].round(1),
    "PE Delta": view["PE Delta"].round(3),
})
display["_dist"] = (display["Strike"] - spot).abs()
display = display.sort_values("_dist").drop(columns="_dist").head(11)

def highlight_atm(row):
    styles = [""] * len(row)
    if row["Strike"] == int(round(atm_strike)):
        styles = ["background-color: #ecfdf5; font-weight: 700;"] * len(row)
    return styles

st.dataframe(display.style.apply(highlight_atm, axis=1), use_container_width=True, hide_index=True, height=380)
st.caption("ATM strike is highlighted. All values are live from Upstox.")
st.markdown('</div>', unsafe_allow_html=True)

# ----- Footer -----
st.markdown("""
<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:12px 16px;margin-top:12px;font-size:12px;color:#1e40af;">
    ℹ️ This is a decision support tool. Always confirm with your own analysis and risk management before placing a trade.
</div>
""", unsafe_allow_html=True)

st.caption(f"Live Upstox data • {symbol} • Expiry {selected_expiry} • Updated {quote_data.get('timestamp', datetime.now().isoformat())}")
