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
# Restored fuller trade-plan design:
# PoP, Entry, SL, Target 1, Target 2, Exit, Delta, IV,
# PCR, OI support/resistance, live option chain and analysis.
# ============================================================

st.set_page_config(
    page_title="FO PRO Trader Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "https://api.upstox.com"

st.markdown(
    """
<style>
/* ============================================================
   FO PRO — REFERENCE UI (UI ONLY)
   ============================================================ */
:root{
 --navy:#0b1f36; --navy2:#102b49; --blue:#1264d8; --blue2:#2f80ed;
 --ink:#102a43; --muted:#667085; --line:#dfe8f2; --bg:#f5f9fd;
 --green:#079455; --greenbg:#ecfbf3; --red:#e5484d; --redbg:#fff2f2;
 --yellow:#b7791f; --yellowbg:#fff9e8; --cyan:#eaf4ff;
}
.stApp{background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
.block-container{padding:0.55rem 1.05rem 1.2rem;max-width:1450px;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0a1d33 0%,#102b49 100%);border-right:1px solid #173a5f;}
[data-testid="stSidebar"]>div:first-child{padding-top:0.7rem;}
[data-testid="stSidebar"] *{color:#dbe9f8;}
[data-testid="stSidebar"] .stButton>button{border-radius:9px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.06);color:#eef6ff;font-weight:700;}
[data-testid="stSidebar"] .stButton>button:hover{background:#1769c8;border-color:#1769c8;color:white;}
[data-testid="stSidebar"] input,[data-testid="stSidebar"] select{background:#132f4e!important;color:white!important;}
[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,.1);}
.sidebar-brand{padding:8px 6px 22px;display:flex;align-items:center;gap:10px;}
.sidebar-logo{font-size:34px;line-height:1;}
.sidebar-brand b{font-size:24px;letter-spacing:-.6px;color:#fff;display:block;line-height:1.05;}
.sidebar-brand span{font-size:12px;color:#a9c3dd;display:block;margin-top:4px;}
.sidebar-nav{margin:4px 0 20px;}
.sidebar-nav div{padding:10px 12px;margin:3px 0;border-radius:8px;color:#c5d7e9;font-size:13px;font-weight:650;}
.sidebar-nav .active{background:#1769c8;color:white;box-shadow:0 3px 12px rgba(0,0,0,.18);}
.sidebar-status{border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.055);border-radius:9px;padding:10px 11px;margin-top:18px;font-size:11px;color:#a9c3dd;}
.sidebar-status b{color:white;font-size:12px;display:block;margin-bottom:3px;}
.sidebar-dot{color:#24d47a;font-size:13px;}
.topline{height:54px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;}
.topline-left{display:flex;align-items:center;gap:16px;min-width:0;}
.symbol-chip{background:#fff;border:1px solid #dbe5f0;border-radius:8px;padding:8px 12px;font-weight:800;color:#102a43;box-shadow:0 1px 3px rgba(16,42,67,.05);}
.top-price{font-size:22px;font-weight:850;color:#102a43;}
.top-change{font-size:13px;font-weight:800;color:#079455;}
.topline-right{display:flex;align-items:center;gap:14px;font-size:11px;color:#667085;white-space:nowrap;}
.live-dot{color:#079455;font-weight:800;}
.master{background:linear-gradient(105deg,#f5fffa,#fff);border:1px solid #bfe9d3;border-radius:8px;padding:16px 18px;margin-bottom:12px;box-shadow:0 2px 9px rgba(16,42,67,.035);}
.master-title{font-size:17px;font-weight:850;color:#087f49;margin-bottom:9px;}
.master-grid{display:grid;grid-template-columns:1.15fr 1fr .65fr .65fr .75fr 1fr;gap:12px;align-items:center;}
.decision-pill{display:inline-flex;align-items:center;justify-content:center;min-height:45px;border-radius:28px;padding:5px 22px;font-size:25px;font-weight:900;letter-spacing:.2px;white-space:nowrap;}
.call-pill{background:#11a566;color:#fff}.put-pill{background:#e5484d;color:#fff}.wait-pill{background:#f3c969;color:#553b00}.no-pill{background:#e9edf2;color:#344054}
.master-symbol{font-size:15px;font-weight:850;color:#102a43;}.master-sub{font-size:11px;color:#667085;margin-top:4px;}
.master-stat{border-left:1px solid #dbe8e1;padding-left:14px;}.master-stat span{display:block;font-size:10px;color:#667085;margin-bottom:5px}.master-stat b{font-size:18px;color:#087f49}.master-ready{background:#d9f8e8;color:#087f49;border-radius:8px;padding:9px 11px;font-size:11px;font-weight:800;text-align:center;}
.card{background:#fff;border:1px solid #dce6f0;border-radius:8px;padding:12px 14px;box-shadow:0 2px 8px rgba(16,42,67,.035);margin-bottom:12px;}
.card-title{font-size:14px;font-weight:850;color:#102a43;margin-bottom:9px;display:flex;align-items:center;gap:7px;}
.card-title .ico{width:24px;height:24px;border-radius:6px;background:#eaf3ff;color:#1769c8;display:inline-flex;align-items:center;justify-content:center;font-size:14px;}
.trade-header{background:linear-gradient(90deg,#ecfbf4,#fff);border-radius:7px;padding:10px 12px;font-weight:850;color:#102a43;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;}
.selected{background:#d8f7e7;color:#087f49;border-radius:12px;padding:4px 8px;font-size:9px;font-weight:800;}
.metrics4{display:grid;grid-template-columns:repeat(4,1fr);}.metrics4>div{padding:8px 10px;border-right:1px solid #e4ebf2;}.metrics4>div:last-child{border-right:0}.metrics4 span,.small-label{display:block;font-size:9px;color:#667085;margin-bottom:5px}.metrics4 b{font-size:15px;color:#102a43}.submetrics{margin-top:7px;border-top:1px solid #e8eef4;padding-top:7px;}
.check-table{width:100%;border-collapse:collapse;font-size:10px}.check-table th{text-align:left;background:#f7fafc;color:#344054;padding:7px;border:1px solid #e4ebf2}.check-table td{padding:7px;border:1px solid #e4ebf2;color:#243b53}.pass{color:#087f49;background:#d9f8e8;border-radius:10px;padding:3px 7px;font-weight:800;display:inline-block}.fail{color:#b4232f;background:#ffe3e5;border-radius:10px;padding:3px 7px;font-weight:800;display:inline-block}.wait{color:#8a5b00;background:#fff0c7;border-radius:10px;padding:3px 7px;font-weight:800;display:inline-block}
.entry-copy{font-size:11px;line-height:1.55;color:#243b53;margin-bottom:8px}.entry-metrics{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #e8eef4;padding-top:8px}.entry-metrics>div{padding:4px 10px;border-right:1px solid #e4ebf2}.entry-metrics>div:last-child{border:0}.entry-metrics b{font-size:16px}.waiting{margin-top:9px;background:#dff8eb;color:#087f49;border-radius:7px;padding:8px 10px;font-size:10px;font-weight:700}.market-level{position:relative;padding:8px 2px 3px}.level-row{display:flex;align-items:center;justify-content:space-between;font-size:10px;margin:8px 0}.level-line{height:2px;flex:1;margin:0 8px;background:#dce5ef;position:relative}.level-line.red{background:#ef4444}.level-line.green{background:#16a34a}.level-line.blue{background:#3182ce}.level-dot{width:9px;height:9px;border-radius:50%;background:#3182ce;box-shadow:0 0 0 3px #dcecff;}
.bias-big{font-size:18px;font-weight:900;color:#087f49;padding:7px 0 10px}.bias-row{display:flex;justify-content:space-between;padding:7px 0;border-top:1px solid #edf1f5;font-size:10px}.bias-row b{color:#243b53}.why-list{font-size:11px;color:#243b53}.why-item{padding:5px 0;display:flex;gap:7px}.why-item i{color:#079455;font-style:normal;font-weight:900}.chart-box{height:220px;overflow:hidden}.tabs-shell{background:#fff;border:1px solid #dce6f0;border-radius:8px;padding:0 10px 10px;margin-top:2px}.footnote{background:#eaf4ff;color:#1769c8;border-radius:7px;padding:9px 11px;font-size:9px;margin-top:9px;}
[data-testid="stMetric"]{padding:0!important}.stMetric label{font-size:9px!important;color:#667085!important}.stMetric [data-testid="stMetricValue"]{font-size:17px!important;color:#102a43!important}.stButton>button{border-radius:8px!important;font-weight:750!important}.stTabs [data-baseweb="tab-list"]{gap:5px;border-bottom:1px solid #dce6f0}.stTabs [data-baseweb="tab"]{font-size:11px;color:#52657a}.stTabs [aria-selected="true"]{color:#1264d8!important;border-bottom:2px solid #1264d8!important}.stDataFrame{border:1px solid #dce6f0;border-radius:7px;overflow:hidden}.stAlert{border-radius:8px!important}.stCaption{font-size:10px!important}
@media(max-width:1050px){.master-grid{grid-template-columns:1fr 1fr 1fr}.master-ready{grid-column:1/-1}.topline-right{display:none}}
@media(max-width:750px){.block-container{padding:.4rem .55rem}.master-grid{grid-template-columns:1fr 1fr}.decision-pill{font-size:20px}.metrics4,.entry-metrics{grid-template-columns:1fr 1fr}.metrics4>div:nth-child(2){border-right:0}.metrics4>div:nth-child(n+3){border-top:1px solid #e4ebf2}.sidebar-nav{display:none}}
</style>
""",
    unsafe_allow_html=True,
)


class UpstoxError(RuntimeError):
    pass


class UpstoxRateLimitError(UpstoxError):
    def __init__(self, message, retry_after=30):
        super().__init__(message)
        self.retry_after = int(retry_after or 30)


# Global pacing is intentionally conservative because Streamlit can rerun the
# script very quickly (manual refresh, auto-refresh, reconnects, etc.).
# This prevents request bursts from multiple app reruns/sessions.
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
    "User-Agent": "FO-PRO-Trader-Assistant/1.0",
}


def api_get(path, params=None, timeout=20):
    """GET from Upstox with pacing, timeout protection and explicit 429 handling.

    Trading logic is not affected by this function. It only controls how the
    app communicates with Upstox. HTTP 429 responses are never retried
    immediately. Temporary connection/read timeouts are retried a small number
    of times with backoff because Streamlit Cloud can occasionally experience
    a slow connection to the Upstox API.
    """
    global _LAST_API_REQUEST

    url = f"{API_BASE}{path}"
    # A bounded connect/read timeout prevents the whole Streamlit page from
    # hanging for 30 seconds when the upstream connection is unhealthy.
    if isinstance(timeout, (tuple, list)) and len(timeout) == 2:
        request_timeout = (float(timeout[0]), float(timeout[1]))
    else:
        request_timeout = (8.0, float(timeout))

    last_exc = None
    for attempt in range(3):
        # Keep requests from arriving in a tight burst after Streamlit reruns.
        with _API_REQUEST_LOCK:
            now = time.monotonic()
            wait_for = _MIN_API_GAP - (now - _LAST_API_REQUEST)
            if wait_for > 0:
                time.sleep(wait_for)
            _LAST_API_REQUEST = time.monotonic()

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                params=params,
                timeout=request_timeout,
            )
            break
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout) as exc:
            last_exc = exc
            if attempt >= 2:
                raise UpstoxError(
                    "Upstox API timed out after 3 attempts. "
                    "Please refresh after a few seconds. The trading logic was not changed."
                ) from exc
            time.sleep(1.5 * (attempt + 1))
        except requests.RequestException as exc:
            raise UpstoxError(f"Network error while contacting Upstox: {exc}") from exc
    else:
        raise UpstoxError(f"Network error while contacting Upstox: {last_exc}")

    if response.status_code == 429:
        retry_after = 30
        try:
            body = response.json()
            if isinstance(body, dict):
                retry_after = int(body.get("retry_after") or 30)
                detail = body.get("detail") or body.get("message") or body
            else:
                detail = body
        except Exception:
            detail = response.text[:500]

        raise UpstoxRateLimitError(
            f"Upstox is rate-limiting this app (HTTP 429). "
            f"Please wait at least {retry_after} seconds before trying again. "
            f"The app has stopped sending requests while rate-limited.",
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

    exact = [
        item for item in results
        if str(item.get("trading_symbol", "")).upper() == symbol
    ]
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
    payload = api_get(
        "/v2/option/contract",
        params={"instrument_key": underlying_key},
        timeout=30,
    )
    contracts = payload.get("data", [])
    if not contracts:
        raise UpstoxError("Upstox returned no option contracts for this instrument.")
    return contracts


def available_expiries(contracts):
    today = date.today().isoformat()
    return sorted(
        {
            str(item.get("expiry"))
            for item in contracts
            if item.get("expiry") and str(item.get("expiry")) >= today
        }
    )


@st.cache_data(ttl=45, show_spinner=False)
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
        raise UpstoxError(f"No option-chain data returned for expiry {expiry}.")
    return rows


@st.cache_data(ttl=30, show_spinner=False)
def get_quote(instrument_key):
    payload = api_get(
        "/v3/market-quote/quotes",
        params={"instrument_key": instrument_key},
    )
    data = payload.get("data", {})
    if not data:
        raise UpstoxError("No live quote returned by Upstox.")
    return next(iter(data.values()))



@st.cache_data(ttl=90, show_spinner=False)
def get_intraday_candles(instrument_key, interval=5):
    """Current-session intraday candles used for entry timing."""
    path = (
        f"/v3/historical-candle/intraday/{quote(instrument_key, safe='')}"
        f"/minutes/{interval}"
    )
    payload = api_get(path, timeout=30)
    candles = payload.get("data", {}).get("candles", [])
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(
        candles,
        columns=["timestamp", "open", "high", "low", "close", "volume", "oi"],
    )
    for column in ["open", "high", "low", "close", "volume", "oi"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def get_30m_candles(instrument_key):
    end_date = date.today()
    start_date = end_date - timedelta(days=90)
    path = (
        f"/v3/historical-candle/{quote(instrument_key, safe='')}"
        f"/minutes/30/{end_date.isoformat()}/{start_date.isoformat()}"
    )
    payload = api_get(path, timeout=30)
    candles = payload.get("data", {}).get("candles", [])
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(
        candles,
        columns=["timestamp", "open", "high", "low", "close", "volume", "oi"],
    )
    for column in ["open", "high", "low", "close", "volume", "oi"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True)


@st.cache_data(ttl=1800, show_spinner=False)
def get_daily_candles(instrument_key):
    end_date = date.today()
    start_date = end_date - timedelta(days=220)
    path = (
        f"/v3/historical-candle/{quote(instrument_key, safe='')}"
        f"/days/1/{end_date.isoformat()}/{start_date.isoformat()}"
    )
    payload = api_get(path, timeout=30)
    candles = payload.get("data", {}).get("candles", [])
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(
        candles,
        columns=["timestamp", "open", "high", "low", "close", "volume", "oi"],
    )
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
    """Trend/volatility features for one timeframe."""
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
    tr = pd.concat(
        [(high-low), (high-prev_close).abs(), (low-prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index
    )
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
    momentum = (
        (close.iloc[-1] / close.iloc[-1-lookback] - 1) * 100
        if lookback > 0 and close.iloc[-1-lookback] else 0.0
    )
    vol_base = volume.rolling(20).median().iloc[-1]
    volume_ratio = volume.iloc[-1] / vol_base if vol_base and np.isfinite(vol_base) else 1.0

    e20 = safe_float(ema20.iloc[-1], spot)
    e50 = safe_float(ema50.iloc[-1], spot)
    r = safe_float(rsi.iloc[-1], 50.0)
    a = safe_float(atr.iloc[-1], spot * 0.01)
    adx_v = safe_float(adx.iloc[-1], 0.0)

    bullish = spot > e20 > e50
    bearish = spot < e20 < e50

    if bullish:
        trend = "Bullish"
    elif bearish:
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
    """Build practical OI support/resistance and OI-wall context.

    Uses a local strike band, then separates the nearest meaningful wall from
    the largest wall so a very distant strike does not dominate the decision.
    """
    valid = chain.dropna(subset=["Strike"]).copy()
    if valid.empty or not np.isfinite(spot):
        return spot, spot, np.nan, {"put_walls": [], "call_walls": [],
                                    "major_support": spot, "major_resistance": spot,
                                    "nearest_support": spot, "nearest_resistance": spot}

    # Keep OI analysis close enough to the underlying to remain actionable.
    band = valid[(valid["Strike"] >= spot * 0.90) & (valid["Strike"] <= spot * 1.10)].copy()
    if band.empty:
        band = valid.copy()

    band["PE OI"] = pd.to_numeric(band["PE OI"], errors="coerce").fillna(0)
    band["CE OI"] = pd.to_numeric(band["CE OI"], errors="coerce").fillna(0)
    band["PE Chg OI"] = pd.to_numeric(band["PE Chg OI"], errors="coerce").fillna(0)
    band["CE Chg OI"] = pd.to_numeric(band["CE Chg OI"], errors="coerce").fillna(0)

    below = band[band["Strike"] <= spot].copy()
    above = band[band["Strike"] >= spot].copy()

    # Nearest walls provide the immediate decision barrier.
    nearest_support = float(below["Strike"].max()) if not below.empty else float(band["Strike"].min())
    nearest_resistance = float(above["Strike"].min()) if not above.empty else float(band["Strike"].max())

    # Major walls use OI, but only among strikes on the correct side.
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
        major_support,
        major_resistance,
        pcr,
        {
            "put_walls": put_walls,
            "call_walls": call_walls,
            "major_support": major_support,
            "major_resistance": major_resistance,
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
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

        records.append(
            {
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
            }
        )

    return pd.DataFrame(records).sort_values("Strike").reset_index(drop=True)


def score_option(row, side, spot, pcr, tf5, tf30, daily, chain,
                 support=None, resistance=None, oi_wall_info=None):
    """100-point trade-quality engine.

    This is a rule-based setup score, not a historical win probability.
    It deliberately rewards confluence and penalizes poor liquidity, weak room,
    VWAP conflict and expensive/poorly placed strikes.
    """
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

    # 30 points: multi-timeframe agreement.
    tf_points, alignment = timeframe_score(side, tf5, tf30, daily)

    # 15 points: momentum + trend strength.
    tf = tf5
    momentum_points = 0
    if tf.get("trend") == desired:
        momentum_points += 5
    rsi = tf.get("rsi", 50)
    if side == "CE":
        if 52 <= rsi <= 68:
            momentum_points += 3
        elif 50 <= rsi < 52:
            momentum_points += 1
        if tf.get("momentum", 0) > 0:
            momentum_points += 3
    else:
        if 32 <= rsi <= 48:
            momentum_points += 3
        elif 48 < rsi <= 50:
            momentum_points += 1
        if tf.get("momentum", 0) < 0:
            momentum_points += 3
    if tf.get("adx", 0) >= 25:
        momentum_points += 4
    elif tf.get("adx", 0) >= 20:
        momentum_points += 2
    momentum_points = min(momentum_points, 15)

    # 10 points: VWAP confirmation. This was previously calculated but not
    # actually used in the trade score.
    vwap = safe_float(tf5.get("vwap"), spot)
    vwap_points = 0
    if np.isfinite(vwap) and vwap > 0:
        vwap_gap_pct = (spot - vwap) / spot * 100
        if side == "CE":
            if spot > vwap and tf5.get("momentum", 0) > 0:
                vwap_points = 10
            elif spot > vwap:
                vwap_points = 6
            elif spot >= vwap * 0.997:
                vwap_points = 2
        else:
            if spot < vwap and tf5.get("momentum", 0) < 0:
                vwap_points = 10
            elif spot < vwap:
                vwap_points = 6
            elif spot <= vwap * 1.003:
                vwap_points = 2
    else:
        vwap_gap_pct = 0.0

    # 10 points: PCR as secondary confirmation.
    pcr_points = 0
    if np.isfinite(pcr):
        if side == "CE":
            pcr_points = 10 if 0.90 <= pcr <= 1.35 else 5 if 0.80 <= pcr < 0.90 else 0
        else:
            pcr_points = 10 if 0.65 <= pcr <= 1.10 else 5 if 1.10 < pcr <= 1.25 else 0

    # 5 points: option OI change direction. Small weight because the endpoint
    # gives current-vs-previous OI, not a full intraday OI sequence.
    oi_points = 0
    if chg_oi < 0:
        oi_points = 5
    elif chg_oi == 0:
        oi_points = 3
    else:
        oi_points = 1

    # 20 points: option quality and liquidity.
    quality = 0
    abs_delta = abs(delta) if np.isfinite(delta) else np.nan
    if np.isfinite(abs_delta):
        if 0.45 <= abs_delta <= 0.65:
            quality += 6
        elif 0.40 <= abs_delta < 0.45 or 0.65 < abs_delta <= 0.75:
            quality += 4
        elif 0.35 <= abs_delta < 0.40 or 0.75 < abs_delta <= 0.80:
            quality += 2

    spread_pct = (
        max(ask - bid, 0) / max((ask + bid) / 2, 0.01) * 100
        if np.isfinite(ask) and np.isfinite(bid) and ask > 0 and bid > 0
        else 999
    )
    if spread_pct <= 1.0:
        quality += 5
    elif spread_pct <= 2.0:
        quality += 4
    elif spread_pct <= 3.0:
        quality += 2

    # Liquidity is tiered rather than treating any volume > 0 as equal.
    if volume >= 10000:
        quality += 5
    elif volume >= 5000:
        quality += 4
    elif volume >= 1000:
        quality += 2

    if oi >= 10000:
        quality += 4
    elif oi >= 3000:
        quality += 3
    elif oi > 0:
        quality += 1

    # 10 points: strike placement + room to the OI barrier.
    distance_pct = abs(float(row["Strike"]) - spot) / max(spot, 1) * 100
    if distance_pct <= 1.0:
        strike_points = 6
    elif distance_pct <= 2.0:
        strike_points = 5
    elif distance_pct <= 3.0:
        strike_points = 3
    elif distance_pct <= 5.0:
        strike_points = 1
    else:
        strike_points = 0

    room_points = 0
    room_pct = np.nan
    if side == "CE" and np.isfinite(resistance):
        room_pct = max((resistance - spot) / max(spot, 1) * 100, 0)
        if spot >= resistance:
            room_points = 4
        elif room_pct >= 2.0:
            room_points = 4
        elif room_pct >= 1.0:
            room_points = 2
    elif side == "PE" and np.isfinite(support):
        room_pct = max((spot - support) / max(spot, 1) * 100, 0)
        if spot <= support:
            room_points = 4
        elif room_pct >= 2.0:
            room_points = 4
        elif room_pct >= 1.0:
            room_points = 2

    strike_quality = strike_points + room_points

    # 10 points: PoP is useful but capped so it cannot dominate direction.
    pop_points = float(np.clip((pop - 55) / 3.0, 0, 10)) if np.isfinite(pop) else 0

    # Total: 30 + 15 + 10 + 10 + 5 + 20 + 10 + 10 = 110.
    raw_score = (
        tf_points + momentum_points + vwap_points + pcr_points + oi_points +
        quality + strike_quality + pop_points
    )
    score = float(np.clip(raw_score / 110 * 100, 0, 100))

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


def build_plan(row, side, spot, support, resistance, pcr, tf5, tf30, daily,
               risk_profile, chain, oi_wall_info=None):
    if row is None:
        return None

    scored = score_option(
        row, side, spot, pcr, tf5, tf30, daily, chain,
        support=support, resistance=resistance, oi_wall_info=oi_wall_info,
    )

    ask = safe_float(row[f"{side} Ask"])
    ltp = safe_float(row[f"{side} LTP"])
    entry = ask if np.isfinite(ask) and ask > 0 else ltp
    if not np.isfinite(entry) or entry <= 0:
        return None

    # Keep the same risk-profile labels and UI, but make the underlying ATR and
    # OI barrier part of the validation rather than relying only on premium %.
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

    # Breakout confirmation is deliberately stricter than a simple spot touch.
    # A BUY requires a live break plus candle/volume confirmation; otherwise WAIT.
    candle_confirmed = False
    volume_confirmed = False
    body_strength = 0.0
    if side == "CE":
        trigger_level = resistance + trigger_buffer
        trigger_hit = spot >= trigger_level
        if trigger_hit and isinstance(tf5, dict):
            candle_confirmed = (
                tf5.get("trend") == "Bullish" and
                tf5.get("momentum", 0) > 0 and
                tf5.get("rsi", 50) >= 52
            )
            volume_confirmed = tf5.get("volume_ratio", 1.0) >= 1.10
        body_strength = max(tf5.get("momentum", 0), 0)
        trigger = (
            f"Enter only after spot breaks and sustains above {fmt_price(trigger_level)} "
            "with 5m bullish confirmation and preferably above-average volume."
        )
        exit_rule = (
            f"Exit if spot loses support {fmt_price(support)} or premium hits "
            f"{fmt_price(sl)}. After Target 1, book partial profit and trail."
        )
    else:
        trigger_level = support - trigger_buffer
        trigger_hit = spot <= trigger_level
        if trigger_hit and isinstance(tf5, dict):
            candle_confirmed = (
                tf5.get("trend") == "Bearish" and
                tf5.get("momentum", 0) < 0 and
                tf5.get("rsi", 50) <= 48
            )
            volume_confirmed = tf5.get("volume_ratio", 1.0) >= 1.10
        body_strength = max(-tf5.get("momentum", 0), 0)
        trigger = (
            f"Enter only after spot breaks and sustains below {fmt_price(trigger_level)} "
            "with 5m bearish confirmation and preferably above-average volume."
        )
        exit_rule = (
            f"Exit if spot reclaims resistance {fmt_price(resistance)} or premium "
            f"hits {fmt_price(sl)}. After Target 1, book partial profit and trail."
        )

    desired = "Bullish" if side == "CE" else "Bearish"
    opposite = "Bearish" if side == "CE" else "Bullish"

    hard_fail = []
    if scored["score"] < 72:
        hard_fail.append("setup score below 72")
    if scored["alignment"] < 2:
        hard_fail.append("fewer than 2 aligned timeframes")
    if tf5.get("trend") == opposite or tf30.get("trend") == opposite:
        hard_fail.append("short-term trend conflict")
    if scored["spread_pct"] > 3:
        hard_fail.append("wide option spread")
    if not np.isfinite(scored["delta"]) or not (0.35 <= abs(scored["delta"]) <= 0.80):
        hard_fail.append("poor delta")
    if not np.isfinite(scored["pop"]) or scored["pop"] < 55:
        hard_fail.append("low Upstox PoP")
    if scored["volume"] < 1000:
        hard_fail.append("weak option liquidity")
    if not np.isfinite(scored["oi"]) or scored["oi"] <= 0:
        hard_fail.append("no option OI")

    # VWAP is now a real gate: do not buy against the active intraday side.
    vwap = safe_float(tf5.get("vwap"), spot)
    if np.isfinite(vwap) and vwap > 0:
        if side == "CE" and spot < vwap * 0.997:
            hard_fail.append("price below VWAP")
        if side == "PE" and spot > vwap * 1.003:
            hard_fail.append("price above VWAP")

    # Avoid buying directly into a very close OI wall.
    if side == "CE":
        wall_room = (resistance - spot) / max(spot, 1) * 100
        if spot < resistance and wall_room < 0.50:
            hard_fail.append("resistance too close")
    else:
        wall_room = (spot - support) / max(spot, 1) * 100
        if spot > support and wall_room < 0.50:
            hard_fail.append("support too close")

    # A breakout can qualify as READY only after candle confirmation. A raw
    # price touch is not enough.
    if not trigger_hit:
        trigger_state = "WAIT FOR TRIGGER"
    elif not candle_confirmed or not volume_confirmed:
        trigger_state = "WAIT FOR CONFIRMATION"
    else:
        trigger_state = "READY" if not hard_fail else "NO TRADE"

    readiness = trigger_state if not hard_fail else "NO TRADE"

    return {
        "side": side,
        "strike": float(row["Strike"]),
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
        "candle_confirmed": candle_confirmed,
        "volume_confirmed": volume_confirmed,
        "readiness": readiness,
        "fail_reasons": hard_fail,
        "exit": exit_rule,
        "oi": row[f"{side} OI"],
        "chg_oi": scored["chg_oi"],
        "volume": scored["volume"],
        "spread_pct": scored["spread_pct"],
        "alignment": scored["alignment"],
        "vwap": scored["vwap"],
        "room_pct": scored["room_pct"],
    }


# ============================================================
# FULL F&O MARKET PoP SCANNER — SIDEBAR ONLY
# ============================================================

FNO_MASTER_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"


@st.cache_data(ttl=3600, show_spinner=False)
def get_fno_underlyings():
    """Build the current NSE equity F&O universe from Upstox's BOD master."""
    try:
        response = requests.get(FNO_MASTER_URL, timeout=30)
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
        if not isinstance(item, dict):
            continue
        if item.get("segment") != "NSE_FO":
            continue
        if item.get("instrument_type") not in {"CE", "PE", "FUT"}:
            continue
        if item.get("underlying_type") != "EQUITY":
            continue

        expiry = str(item.get("expiry", ""))
        if not expiry:
            continue

        # Upstox BOD JSON normally supplies expiry as an epoch-millisecond value
        # for NSE_FO. Handle both epoch and YYYY-MM-DD formats safely.
        if expiry.isdigit():
            try:
                expiry_date = datetime.fromtimestamp(
                    int(expiry) / 1000, tz=ZoneInfo("Asia/Kolkata")
                ).date().isoformat()
            except Exception:
                continue
        else:
            expiry_date = expiry[:10]

        if expiry_date < today:
            continue

        underlying_key = item.get("underlying_key")
        symbol = str(item.get("underlying_symbol") or "").strip().upper()
        if not underlying_key or not symbol:
            continue

        current = universe.get(underlying_key)
        if current is None or expiry_date < current["expiry"]:
            universe[underlying_key] = {
                "symbol": symbol,
                "underlying_key": underlying_key,
                "expiry": expiry_date,
            }

    return sorted(universe.values(), key=lambda x: x["symbol"])


def scan_full_fno_pop_market(min_pop=75.0):
    """Scan the nearest expiry of every NSE equity F&O underlying and return top 5 unique stocks."""
    universe = get_fno_underlyings()
    candidates = []
    scanned = 0
    failed = 0

    progress = st.progress(0, text="Starting full F&O market scan...")

    for idx, item in enumerate(universe, start=1):
        try:
            if idx > 1:
                time.sleep(0.80)
            rows = get_option_chain(item["underlying_key"], item["expiry"])
            if not rows:
                failed += 1
                continue

            # The option-chain response carries the underlying spot in its rows.
            spot_values = [
                safe_float(row.get("underlying_spot_price"))
                for row in rows
                if np.isfinite(safe_float(row.get("underlying_spot_price")))
            ]
            spot_value = spot_values[0] if spot_values else np.nan

            best_for_stock = None

            for raw in rows:
                strike = safe_float(raw.get("strike_price"))
                if not np.isfinite(strike):
                    continue

                for side, action in (("CE", "CALL BUY"), ("PE", "PUT BUY")):
                    option = raw.get("call_options" if side == "CE" else "put_options") or {}
                    market = option.get("market_data") or {}
                    greeks = option.get("option_greeks") or {}

                    pop = safe_float(greeks.get("pop"))
                    if not np.isfinite(pop) or pop <= min_pop:
                        continue

                    ltp = safe_float(market.get("ltp"))
                    ask = safe_float(market.get("ask_price"))
                    bid = safe_float(market.get("bid_price"))
                    volume = safe_float(market.get("volume"), 0)
                    oi = safe_float(market.get("oi"), 0)
                    delta = safe_float(greeks.get("delta"))
                    iv = safe_float(greeks.get("iv"))

                    entry = ask if np.isfinite(ask) and ask > 0 else ltp
                    if not np.isfinite(entry) or entry <= 0:
                        continue

                    distance = (
                        abs(strike - spot_value) / max(spot_value, 1)
                        if np.isfinite(spot_value)
                        else 999
                    )

                    # Use the same Balanced risk levels as the main analyzer
                    # so the scanner's SL/targets are consistent with the app.
                    sl = round(entry * 0.70, 2)
                    target1 = round(entry * 1.40, 2)
                    target2 = round(entry * 1.80, 2)
                    exit_rule = "Exit at SL or Target 2; trail after Target 1"

                    candidate = {
                        "Stock": item["symbol"],
                        "Trade": action,
                        "Strike": strike,
                        "Expiry": item["expiry"],
                        "PoP": pop,
                        "Entry": entry,
                        "SL": sl,
                        "Target1": target1,
                        "Target2": target2,
                        "Exit": exit_rule,
                        "LTP": ltp,
                        "Bid": bid,
                        "Ask": ask,
                        "Delta": delta,
                        "IV": iv,
                        "Volume": volume,
                        "OI": oi,
                        "distance": distance,
                    }

                    # One highest-PoP opportunity per stock keeps the Top 5 diversified.
                    if best_for_stock is None or (
                        candidate["PoP"], candidate["Volume"], -candidate["distance"]
                    ) > (
                        best_for_stock["PoP"], best_for_stock["Volume"], -best_for_stock["distance"]
                    ):
                        best_for_stock = candidate

            if best_for_stock is not None:
                candidates.append(best_for_stock)
            scanned += 1

        except UpstoxRateLimitError:
            progress.empty()
            raise
        except Exception:
            failed += 1

        progress.progress(
            idx / max(len(universe), 1),
            text=f"Scanning F&O market: {idx}/{len(universe)} stocks",
        )

    progress.empty()

    candidates.sort(
        key=lambda x: (-x["PoP"], -x["Volume"], x["distance"])
    )

    return candidates[:5], len(universe), scanned, failed



# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("""
    <div class='sidebar-brand'>
      <div class='sidebar-logo'>📈</div>
      <div><b>FO PRO</b><span>Trader Assistant</span></div>
    </div>
    <div class='sidebar-nav'>
      <div class='active'>⌂ &nbsp; Dashboard</div>
      <div>▦ &nbsp; Option Chain</div>
      <div>◈ &nbsp; Scanner</div>
      <div>▥ &nbsp; Market Analysis</div>
      <div>◫ &nbsp; Trade Plan</div>
      <div>↕ &nbsp; Entry / Exit</div>
      <div>⌁ &nbsp; Support & Resistance</div>
      <div>☑ &nbsp; Check List</div>
      <div>◉ &nbsp; How Engine Thinks</div>
      <div>⚙ &nbsp; Settings</div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("🔎 ANALYZE INSTRUMENT", expanded=True):
        symbol_label = "Stock / Index"
        symbol_default = st.session_state.get("symbol", "KOTAKBANK")
        symbol_placeholder = "e.g. KOTAKBANK, HDFCBANK, NIFTY"
        symbol_input = st.text_input(symbol_label, value=symbol_default, placeholder=symbol_placeholder)
        risk_profile = st.selectbox("Risk Profile", ["Conservative", "Balanced", "Aggressive"], index=1)
        analyze = st.button("🔍 Analyze", type="primary", use_container_width=True)
        refresh = st.button("↻ Refresh Live Data", use_container_width=True)
        if st_autorefresh is not None:
            auto_refresh = st.checkbox("Auto refresh every 60 seconds", value=False)
            if auto_refresh:
                st_autorefresh(interval=60_000, key="upstox_live_refresh")

    with st.expander("🔥 F&O SCANNER", expanded=False):
        st.caption("Scans the full NSE equity F&O market for PoP > 75%.")
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
                st.error(f"⏳ Rate limit reached. Wait about {exc.retry_after} seconds.")
            except UpstoxError as exc:
                st.session_state["fno_pop_results"] = []
                st.error(str(exc))
            except Exception as exc:
                st.session_state["fno_pop_results"] = []
                st.error(f"F&O scan failed: {exc}")
        pop_results = st.session_state.get("fno_pop_results", [])
        scan_info = st.session_state.get("fno_pop_scan_info")
        scan_time = st.session_state.get("fno_pop_scan_time")
        if pop_results:
            st.success(f"Top {len(pop_results)} trades with PoP > 75%")
            if scan_info:
                total, scanned, failed = scan_info
                st.caption(f"Scanned {scanned}/{total} • {failed} unavailable")
            if scan_time:
                st.caption(f"Last scan: {scan_time} IST")
            scanner_display = pd.DataFrame([{
                "Stock": row["Stock"], "Trade": row["Trade"], "Strike": int(row["Strike"]),
                "PoP": f"{row['PoP']:.1f}%", "Entry": fmt_price(row["Entry"]),
                "SL": fmt_price(row["SL"]), "Target1": fmt_price(row["Target1"]),
                "Target2": fmt_price(row["Target2"]), "Exit": row["Exit"],
            } for row in pop_results])
            st.dataframe(scanner_display, use_container_width=True, hide_index=True, height=min(360,58+len(scanner_display)*52))
        elif "fno_pop_results" in st.session_state:
            st.info("No F&O stock currently has an option trade with PoP > 75%.")

    st.markdown("<div class='sidebar-status'><b><span class='sidebar-dot'>●</span> Upstox Connected</b>Live Market Data</div>", unsafe_allow_html=True)
    st.caption("No simulated market values are used.")


if analyze:
    st.session_state["symbol"] = alias_symbol(symbol_input)
    st.rerun()

if refresh:
    st.cache_data.clear()
    st.rerun()

symbol = alias_symbol(
    st.session_state.get("symbol", symbol_input or "KOTAKBANK")
)

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
            raise UpstoxError(
                "Upstox did not return an upcoming F&O expiry for this instrument."
            )

        selected_expiry = expiries[0]

        raw_chain = get_option_chain(
            underlying_key,
            selected_expiry,
        )

        chain = normalize_chain(raw_chain)

        quote_data = get_quote(underlying_key)

        spot = safe_float(quote_data.get("last_price"))
        previous_close = safe_float(
            quote_data.get("prev_close_price"),
            spot,
        )

        net_change = safe_float(
            quote_data.get("net_change"),
            spot - previous_close,
        )

        change_pct = (
            net_change / previous_close * 100
            if previous_close
            else 0
        )

        candles = get_daily_candles(underlying_key)
        candles_30m = get_30m_candles(underlying_key)
        candles_5m = get_intraday_candles(underlying_key, 5)

        daily_tech = technicals(candles, spot)
        tf30 = technicals(candles_30m, spot)
        tf5 = technicals(candles_5m, spot)

        # Keep the existing UI terminology while using the stronger daily trend
        # as the headline bias.
        tech = daily_tech

except UpstoxRateLimitError as exc:
    st.error(
        f"⏳ Upstox rate limit reached. Please wait about {exc.retry_after} seconds "
        "before refreshing. The app has stopped sending requests while the limit is active."
    )
    st.stop()
except UpstoxError as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:
    st.error(f"Unexpected error while loading live data: {exc}")
    st.stop()

support, resistance, pcr, oi_wall_info = oi_levels(chain, spot)

atm_index = (chain["Strike"] - spot).abs().idxmin()
atm_strike = float(chain.loc[atm_index, "Strike"])

# Evaluate a wider ATM band, then select the strike using the full quality engine.
candidate_rows = chain.iloc[
    max(0, atm_index - 5): min(len(chain), atm_index + 6)
]

ce_candidates = []
pe_candidates = []

for _, row in candidate_rows.iterrows():
    ce_scored = score_option(
        row, "CE", spot, pcr, tf5, tf30, daily_tech, chain,
        support=support, resistance=resistance, oi_wall_info=oi_wall_info,
    )
    pe_scored = score_option(
        row, "PE", spot, pcr, tf5, tf30, daily_tech, chain,
        support=support, resistance=resistance, oi_wall_info=oi_wall_info,
    )
    ce_candidates.append((ce_scored, row))
    pe_candidates.append((pe_scored, row))

def _candidate_key(item):
    scored, row = item
    # Score first; then prefer Delta, lower spread, higher volume and closer ATM.
    abs_delta = abs(safe_float(scored.get("delta"), 0))
    spread = safe_float(scored.get("spread_pct"), 999)
    volume = safe_float(scored.get("volume"), 0)
    distance = safe_float(scored.get("distance_pct"), 999)
    delta_fit = -abs(abs_delta - 0.55)
    return (scored["score"], delta_fit, -spread, np.log1p(max(volume, 0)), -distance)

best_ce_scored, best_ce_row = max(ce_candidates, key=_candidate_key, default=({"score": 0}, None))
best_pe_scored, best_pe_row = max(pe_candidates, key=_candidate_key, default=({"score": 0}, None))

ce_plan = build_plan(
    best_ce_row, "CE", spot, support, resistance, pcr,
    tf5, tf30, daily_tech, risk_profile, chain, oi_wall_info
)
pe_plan = build_plan(
    best_pe_row, "PE", spot, support, resistance, pcr,
    tf5, tf30, daily_tech, risk_profile, chain, oi_wall_info
)

ce_score = ce_plan["score"] if ce_plan else 0
pe_score = pe_plan["score"] if pe_plan else 0

# High-accuracy mode: disagreement or an unconfirmed breakout produces
# WAIT/NO TRADE instead of forcing a position.
overall_direction, overall_alignment = overall_trend(tf5, tf30, daily_tech)

if ce_plan and ce_score >= 72 and ce_score >= pe_score + 8 and         overall_direction == "Bullish" and ce_plan["readiness"] in {"READY", "WAIT FOR TRIGGER", "WAIT FOR CONFIRMATION"}:
    decision = "CALL BUY" if ce_plan["readiness"] == "READY" else ce_plan["readiness"]
    decision_class = "trade-call" if decision == "CALL BUY" else "trade-neutral"
    best_plan = ce_plan
elif pe_plan and pe_score >= 72 and pe_score >= ce_score + 8 and         overall_direction == "Bearish" and pe_plan["readiness"] in {"READY", "WAIT FOR TRIGGER", "WAIT FOR CONFIRMATION"}:
    decision = "PUT BUY" if pe_plan["readiness"] == "READY" else pe_plan["readiness"]
    decision_class = "trade-put" if decision == "PUT BUY" else "trade-neutral"
    best_plan = pe_plan
else:
    decision = "NO TRADE"
    decision_class = "trade-neutral"
    best_plan = ce_plan if ce_score >= pe_score else pe_plan

# Confidence is intentionally a separate descriptive measure.
best_score = best_plan["score"] if best_plan else 0
best_alignment = best_plan["alignment"] if best_plan else 0
confidence = int(np.clip(
    best_score * 0.70 + (best_alignment / 3) * 20 +
    (5 if overall_direction in {"Bullish", "Bearish"} else 0), 0, 100
))

updated = quote_data.get(
    "timestamp",
    datetime.now().astimezone().isoformat(),
)

# ============================================================
# DASHBOARD UI — REDESIGNED VISUAL HIERARCHY ONLY
# The analysis engine above is intentionally unchanged.
# ============================================================

market_now = datetime.now(ZoneInfo("Asia/Kolkata"))
market_open = (
    market_now.weekday() < 5
    and (market_now.hour, market_now.minute) >= (9, 15)
    and (market_now.hour, market_now.minute) < (15, 30)
)

# ---------- UI helpers ----------
def _num_or_dash(v, decimals=2):
    try:
        x = float(v)
        if not np.isfinite(x):
            return "—"
        return f"{x:.{decimals}f}"
    except Exception:
        return "—"


def _status_class(value):
    v = str(value).upper()
    if "READY" in v or "PASS" in v or "BUY" in v:
        return "status-green"
    if "WAIT" in v or "CAUTION" in v:
        return "status-yellow"
    if "NO TRADE" in v or "FAIL" in v:
        return "status-red"
    return "status-grey"



def _check_row(label, state, detail):
    icon = "🟢" if state == "PASS" else "🟡" if state == "WAIT" else "🔴"
    css = "check-pass" if state == "PASS" else "check-wait" if state == "WAIT" else "check-fail"
    return f"<div class='check-row'><span>{label}</span><strong class='{css}'>{icon} {state}</strong><small>{detail}</small></div>"


# ============================================================
# MAIN DASHBOARD — REFERENCE IMAGE UI ONLY
# All calculations/logic above are unchanged.
# ============================================================

def _pill_class(dec):
    if dec == "CALL BUY": return "call-pill"
    if dec == "PUT BUY": return "put-pill"
    if "WAIT" in dec: return "wait-pill"
    return "no-pill"

def _status_badge(state):
    return "<span class='pass'>PASS</span>" if state == "PASS" else "<span class='wait'>WAIT</span>" if state == "WAIT" else "<span class='fail'>FAIL</span>"

# ---------- Top ticker ----------
st.markdown(f"""
<div class='topline'>
  <div class='topline-left'>
    <div class='symbol-chip'>{symbol} ▾</div>
    <div class='top-price'>{fmt_price(spot)}</div>
    <div class='top-change'>{net_change:+.2f} ({change_pct:+.2f}%)</div>
  </div>
  <div class='topline-right'>
    <span class='live-dot'>● Live Data</span>
    <span>{datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%b %d, %Y  %I:%M %p')}</span>
    <span>↻</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------- Master decision ----------
decision_sub = {
    "CALL BUY": "Bullish setup  •  Confirmation required",
    "PUT BUY": "Bearish setup  •  Confirmation required",
    "WAIT FOR TRIGGER": "Setup developing  •  Wait for trigger",
    "WAIT FOR CONFIRMATION": "Trigger area reached  •  Confirmation required",
    "NO TRADE": "Conditions are not sufficiently aligned  •  Wait",
}.get(decision, "Review live conditions before acting")
ready_text = "TRADE READY" if decision in {"CALL BUY", "PUT BUY"} else "WAIT / MONITOR" if "WAIT" in decision else "NO TRADE"
master_ready_cls = "master-ready" if decision in {"CALL BUY","PUT BUY"} else "master-ready"
contract_text = f"{best_plan['strike']:.0f} {'CE' if best_plan['side']=='CE' else 'PE'}" if best_plan else "No active contract"

st.markdown(f"""
<div class='master'>
  <div class='master-title'>🎯 MASTER TRADE DECISION</div>
  <div class='master-grid'>
    <div class='decision-pill {_pill_class(decision)}'>{'↗' if decision=='CALL BUY' else '↘' if decision=='PUT BUY' else '•'}&nbsp; {decision}</div>
    <div><div class='master-symbol'>{contract_text}</div><div class='master-sub'>{decision_sub}</div></div>
    <div class='master-stat'><span>SETUP SCORE</span><b>{best_score:.0f}/100</b></div>
    <div class='master-stat'><span>CONFIDENCE</span><b>{confidence}/100</b></div>
    <div class='master-stat'><span>MARKET TREND</span><b>{overall_direction.upper()}</b></div>
    <div class='{master_ready_cls}'>{'●' if decision in {'CALL BUY','PUT BUY'} else '○'} {ready_text}<br><span style='font-weight:600;color:#5b7085'>{'Buy only after entry trigger is confirmed.' if decision in {'CALL BUY','PUT BUY'} else 'No entry until the master decision permits it.'}</span></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------- Active plan ----------
active_plan = ce_plan if decision == "CALL BUY" else pe_plan if decision == "PUT BUY" else best_plan if "WAIT" in decision else None

# ---------- Checklist data ----------
direction_pass = overall_direction in {"Bullish", "Bearish"}
mtf_pass = overall_alignment >= 2
oi_pass = np.isfinite(support) and np.isfinite(resistance) and support < spot < resistance
vwap_value = safe_float(tf5.get("vwap"), spot)
if active_plan:
    vwap_pass = spot >= vwap_value * 0.997 if active_plan["side"] == "CE" else spot <= vwap_value * 1.003
else:
    vwap_pass = False
breakout_state = "PASS" if active_plan and active_plan.get("trigger_hit") and active_plan.get("candle_confirmed") and active_plan.get("volume_confirmed") else "WAIT"
check_items = [
    ("Market Direction", "PASS" if direction_pass else "FAIL", overall_direction),
    ("Multi-Timeframe", "PASS" if mtf_pass else "FAIL", f"{overall_alignment}/3 aligned"),
    ("OI Structure", "PASS" if oi_pass else "FAIL", f"Support {fmt_price(support)}"),
    ("VWAP", "PASS" if vwap_pass else "FAIL", f"Price {'above' if spot >= vwap_value else 'below'} {fmt_price(vwap_value)}"),
    ("Momentum / Entry", breakout_state, "Trigger + 5m confirmation"),
    ("Option Quality", "PASS" if active_plan and active_plan.get("spread_pct",99) <= 3 else "FAIL", "Liquid / healthy" if active_plan else "No active setup"),
]
check_overall=sum(1 for _,s,_ in check_items if s=="PASS")

# ---------- Two-column main cards ----------
left, right = st.columns([1.04, 1.0], gap="small")
with left:
    st.markdown("<div class='card'><div class='card-title'><span class='ico'>✚</span> TRADE PLAN</div>", unsafe_allow_html=True)
    if active_plan:
        side = active_plan["side"]
        contract = "CE" if side == "CE" else "PE"
        side_label = "CALL BUY" if side == "CE" else "PUT BUY"
        selected_tag = "SELECTED" if decision in {"CALL BUY","PUT BUY"} else "MONITORING"
        st.markdown(f"<div class='trade-header'><span>{active_plan['strike']:.0f} {contract}</span><span class='selected'>● {side_label} ({selected_tag})</span></div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class='metrics4'>
          <div><span>Entry</span><b>{fmt_price(active_plan.get('entry'))}</b></div>
          <div><span>Stop Loss</span><b>{fmt_price(active_plan.get('sl'))}</b></div>
          <div><span>Target 1</span><b>{fmt_price(active_plan.get('target1'))}</b></div>
          <div><span>Target 2</span><b>{fmt_price(active_plan.get('target2'))}</b></div>
        </div>
        <div class='metrics4 submetrics'>
          <div><span>PoP</span><b>{_num_or_dash(active_plan.get('pop'),1)}%</b></div>
          <div><span>Delta</span><b>{_num_or_dash(active_plan.get('delta'),2)}</b></div>
          <div><span>IV</span><b>{_num_or_dash(active_plan.get('iv'),1)}%</b></div>
          <div><span>R:R (T2)</span><b>1:{_num_or_dash(active_plan.get('rr2'),2)}</b></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div style='padding:30px 10px;text-align:center;color:#667085;font-size:12px'>🚫 No actionable trade<br><small>The engine currently says NO TRADE.</small></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown(f"<div class='card'><div class='card-title'><span class='ico'>✓</span> TRADE CHECKLIST <span style='margin-left:auto;background:#d9f8e8;color:#087f49;border-radius:10px;padding:4px 8px;font-size:9px'>{check_overall}/{len(check_items)} PASS</span></div>", unsafe_allow_html=True)
    rows="".join(f"<tr><td>{i}</td><td>{label}</td><td>{_status_badge(state)}</td><td>{detail}</td></tr>" for i,(label,state,detail) in enumerate(check_items,1))
    st.markdown(f"<table class='check-table'><thead><tr><th>#</th><th>Check</th><th>Status</th><th>Observation</th></tr></thead><tbody>{rows}</tbody></table></div>", unsafe_allow_html=True)

# ---------- Entry + levels ----------
left2, mid2, right2 = st.columns([1.25, .8, .65], gap="small")
with left2:
    st.markdown("<div class='card'><div class='card-title'><span class='ico'>⚡</span> ENTRY CONDITION</div>", unsafe_allow_html=True)
    if active_plan:
        dist=abs(spot-active_plan["trigger_level"])
        st.markdown(f"<div class='entry-copy'><b>Enter ONLY when</b> {active_plan['trigger']} </div>", unsafe_allow_html=True)
        st.markdown(f"<div class='entry-metrics'><div><span>Current Spot</span><b>{fmt_price(spot)}</b></div><div><span>Trigger</span><b>{fmt_price(active_plan['trigger_level'])}</b></div><div><span>Distance</span><b>{fmt_price(dist)}</b></div></div>", unsafe_allow_html=True)
        st.markdown("<div class='waiting'>◷ &nbsp; Waiting for entry trigger...</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='entry-copy'>No entry condition is active because the master decision is <b>NO TRADE</b>.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
with mid2:
    st.markdown("<div class='card'><div class='card-title'><span class='ico'>▥</span> MARKET LEVELS</div><div class='market-level'>", unsafe_allow_html=True)
    st.markdown(f"<div class='level-row'><span style='color:#e5484d'>Resistance</span><div class='level-line red'></div><b style='color:#e5484d'>{fmt_price(resistance)}</b></div><div class='level-row'><span style='color:#1264d8'>Current</span><div class='level-line blue'><span class='level-dot' style='float:right'></span></div><b style='color:#1264d8'>{fmt_price(spot)}</b></div><div class='level-row'><span style='color:#079455'>Support</span><div class='level-line green'></div><b style='color:#079455'>{fmt_price(support)}</b></div>", unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)
with right2:
    st.markdown("<div class='card'><div class='card-title'><span class='ico'>◉</span> MARKET BIAS</div>", unsafe_allow_html=True)
    bias_color="#079455" if tech["trend"]=="Bullish" else "#e5484d" if tech["trend"]=="Bearish" else "#667085"
    st.markdown(f"<div class='bias-big' style='color:{bias_color}'>↗ {tech['trend'].upper()}</div><div class='bias-row'><span>PCR</span><b>{pcr:.2f}</b></div><div class='bias-row'><span>VWAP</span><b>{fmt_price(vwap_value)}</b></div><div class='bias-row'><span>ATR</span><b>{fmt_price(daily_tech.get('atr'))}</b></div></div>", unsafe_allow_html=True)

# ---------- Why + chart ----------
left3,right3=st.columns([.92,1.08],gap="small")
with left3:
    st.markdown("<div class='card'><div class='card-title'><span class='ico'>💡</span> WHY THIS SETUP?</div><div class='why-list'>", unsafe_allow_html=True)
    if active_plan:
        side_name="CALL" if active_plan["side"]=="CE" else "PUT"
        why_items=[
            f"{tf5['trend']} short-term trend supports {side_name} direction",
            f"{overall_alignment}/3 timeframes aligned",
            f"Price is {'above' if spot>=vwap_value else 'below'} 5m VWAP",
            f"OI structure: support {fmt_price(support)} • resistance {fmt_price(resistance)}",
            "Option liquidity and Greeks are within the engine gate",
            "Entry trigger still required",
        ]
    else:
        why_items=["Market direction is not sufficiently aligned","No actionable CALL/PUT meets the quality gate","Wait for a new setup rather than forcing an entry"]
    for x in why_items: st.markdown(f"<div class='why-item'><i>●</i><span>{x}</span></div>",unsafe_allow_html=True)
    st.markdown("</div></div>",unsafe_allow_html=True)
with right3:
    st.markdown("<div class='card'><div class='card-title'><span class='ico'>♣</span> KEY CHART <span style='font-size:9px;color:#667085'>(NIFTY 5m)</span></div><div class='chart-box'>",unsafe_allow_html=True)
    if not candles.empty:
        chart = candles.set_index("timestamp")[["close"]].tail(70)
        st.line_chart(chart,use_container_width=True,height=190)
    else:
        st.caption("Chart unavailable for the current data window.")
    st.markdown("</div></div>",unsafe_allow_html=True)

# ---------- OI values for the reference cards ----------
put_row = nearest_row(chain, support)
call_row = nearest_row(chain, resistance)
put_oi = put_row["PE OI"] if put_row is not None else np.nan
call_oi = call_row["CE OI"] if call_row is not None else np.nan

# ---------- Tabs ----------
st.markdown("<div class='tabs-shell'>",unsafe_allow_html=True)
tab1,tab2,tab3,tab4=st.tabs(["⚙ Option Chain","⌁ Market Analysis","⌁ Support & Resistance","⌁ How Engine Thinks"])
with tab1:
    st.markdown(f"**Live Option Chain (Around ATM)**  ·  Expiry {selected_expiry}")
    view=chain.copy()
    display=pd.DataFrame({
      "Strike":view["Strike"].round(0).astype(int),"CE LTP":view["CE LTP"].round(2),"CE OI":view["CE OI"].round(0).astype(int),"CE ΔOI":view["CE Chg OI"].round(0).astype(int),
      "PE LTP":view["PE LTP"].round(2),"PE OI":view["PE OI"].round(0).astype(int),"PE ΔOI":view["PE Chg OI"].round(0).astype(int)
    })
    display["_distance"]=(display["Strike"]-spot).abs(); display=display.sort_values("_distance").drop(columns="_distance").head(12)
    st.dataframe(display,use_container_width=True,hide_index=True,height=300)
with tab2:
    a,b,c,d=st.columns(4); a.metric("EMA 20",fmt_price(daily_tech["ema20"])); b.metric("EMA 50",fmt_price(daily_tech["ema50"])); c.metric("ATR 14",fmt_price(daily_tech["atr"])); d.metric("5m VWAP",fmt_price(tf5["vwap"]))
    mtf=pd.DataFrame([
      {"Timeframe":"5 Minute","Trend":tf5["trend"],"RSI":round(tf5["rsi"],1),"ADX":round(tf5["adx"],1),"Momentum %":round(tf5["momentum"],2)},
      {"Timeframe":"30 Minute","Trend":tf30["trend"],"RSI":round(tf30["rsi"],1),"ADX":round(tf30["adx"],1),"Momentum %":round(tf30["momentum"],2)},
      {"Timeframe":"Daily","Trend":daily_tech["trend"],"RSI":round(daily_tech["rsi"],1),"ADX":round(daily_tech["adx"],1),"Momentum %":round(daily_tech["momentum"],2)},
    ])
    st.dataframe(mtf,use_container_width=True,hide_index=True)
with tab3:
    x,y=st.columns(2)
    with x:
        st.markdown(f"**🟢 Support / Put OI**<br>Major support: **{fmt_price(support)}**<br>Put OI: **{fmt_num(put_oi)}**", unsafe_allow_html=True)
    with y:
        st.markdown(f"**🔴 Resistance / Call OI**<br>Major resistance: **{fmt_price(resistance)}**<br>Call OI: **{fmt_num(call_oi)}**", unsafe_allow_html=True)
with tab4:
    st.markdown("""**Live-data decision framework**

- Market direction uses live spot and multi-timeframe trend.
- Option-chain structure uses OI, Change OI and PCR.
- Option quality uses LTP, spread, volume, IV, Delta and Upstox PoP.
- Trade plan uses trigger, entry, stop loss, targets and exit rule.
- Quality gates can return BUY, WAIT or NO TRADE.
- The score is a rule-based quality measure, not a guaranteed win rate.
""")
st.markdown("</div>",unsafe_allow_html=True)

st.markdown(f"<div class='footnote'>ⓘ &nbsp; This is a decision-support tool. Always confirm live market conditions and your own risk management before placing a trade. • Data: Upstox • Expiry: {selected_expiry}</div>",unsafe_allow_html=True)

st.divider()

st.caption(
    f"Live Upstox snapshot • {symbol} • Expiry {selected_expiry} • "
    f"Updated {updated}. "
    "For educational/decision-support use; review live market conditions before trading."
)
