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
.stApp { background:#f6f8fb; }
.block-container { padding-top:1rem; padding-bottom:2rem; max-width:1500px; }
.topbar {
    background:linear-gradient(100deg,#102a43,#1f4b73);
    padding:18px 24px; border-radius:14px; color:white; margin-bottom:18px;
}
.topbar-title {font-size:27px;font-weight:800;}
.topbar-sub {font-size:13px;opacity:.82;margin-top:3px;}
.status-pill {
    display:inline-block;padding:7px 12px;border-radius:20px;
    background:#1f9d55;color:white;font-size:12px;font-weight:700;
}
.card {
    background:white;border:1px solid #e7ebf0;border-radius:14px;
    padding:18px;margin-bottom:16px;box-shadow:0 2px 8px rgba(16,42,67,.04);
}
.section-title {font-size:20px;font-weight:800;color:#182230;margin-bottom:12px;}
.trade-call {
    background:#eaf8ef;border:1px solid #bde5c9;border-radius:12px;
    padding:14px 16px;font-weight:800;color:#147a3d;
}
.trade-put {
    background:#fff0f1;border:1px solid #f2c5c8;border-radius:12px;
    padding:14px 16px;font-weight:800;color:#b4232f;
}
.trade-neutral {
    background:#f2f4f7;border:1px solid #dfe3e8;border-radius:12px;
    padding:14px 16px;font-weight:800;color:#475467;
}

/* ============================================================
   REDESIGNED DASHBOARD VISUAL SYSTEM
   ============================================================ */
.topbar-dashboard {
    display:flex;align-items:center;justify-content:space-between;gap:18px;
}
.header-live,.live-block,.closed-block {
    color:#fff;padding:10px 16px;border-radius:9px;font-size:13px;
    font-weight:800;letter-spacing:.2px;text-align:center;white-space:nowrap;
}
.header-live { background:rgba(255,255,255,.14); }
.live-block { background:#16a34a; }
.closed-block { background:#dc2626; }
.hero-price {font-size:29px;font-weight:850;line-height:1.05;color:#182230;}
.section-heading {
    font-size:19px;font-weight:850;color:#182230;margin:20px 0 10px;
    letter-spacing:.15px;
}
.metric-card,.entry-card {
    background:#fff;border:1px solid #e7ebf0;border-radius:13px;
    padding:15px 14px;min-height:105px;box-shadow:0 2px 8px rgba(16,42,67,.035);
}
.metric-card span,.entry-card span,.decision-stats span,.status-grid span,
.option-grid span,.exit-rule span {
    display:block;font-size:10px;font-weight:800;color:#667085;letter-spacing:.55px;
}
.metric-card b,.entry-card b {display:block;font-size:20px;color:#182230;margin-top:8px;line-height:1.15;}
.metric-card small,.entry-card small {display:block;color:#98a2b3;font-size:10px;margin-top:7px;}
.metric-positive b {color:#147a3d;}.metric-negative b {color:#b4232f;}
.metric-support b {color:#147a3d;}.metric-resistance b {color:#b4232f;}
.metric-neutral b {color:#475467;}
.decision-card {
    border-radius:16px;padding:23px 25px;border:1px solid #dfe5eb;
    background:#fff;box-shadow:0 3px 12px rgba(16,42,67,.055);
}
.decision-call {border-color:#bde5c9;background:linear-gradient(180deg,#f5fcf7,#fff);}
.decision-put {border-color:#f2c5c8;background:linear-gradient(180deg,#fff7f7,#fff);}
.decision-neutral {border-color:#dfe3e8;background:#fbfcfd;}
.decision-main {font-size:32px;font-weight:900;text-align:center;line-height:1.1;}
.decision-call .decision-main {color:#147a3d;}.decision-put .decision-main {color:#b4232f;}.decision-neutral .decision-main {color:#475467;}
.decision-sub {text-align:center;color:#667085;margin:9px 0 20px;font-size:13px;}
.decision-stats {display:grid;grid-template-columns:repeat(4,1fr);gap:10px;}
.decision-stats>div {background:rgba(255,255,255,.78);border:1px solid #edf0f3;border-radius:10px;padding:11px;text-align:center;}
.decision-stats b {display:block;font-size:19px;margin-top:5px;color:#182230;}
.decision-stats .decision-value {display:block;font-size:19px;font-weight:800;margin-top:5px;color:#182230;}
.decision-stats .decision-value span {display:inline;font-size:11px;font-weight:600;color:#98a2b3;margin-left:3px;}
.status-panel {border-radius:14px;padding:18px 20px;border:1px solid #e4e7ec;background:#fff;box-shadow:0 2px 8px rgba(16,42,67,.035);}
.status-green {border-color:#bde5c9;background:#f4fbf6;}.status-yellow {border-color:#f1d79b;background:#fffbf1;}.status-red {border-color:#f2c5c8;background:#fff6f6;}.status-grey {border-color:#dfe3e8;background:#f8fafc;}
.status-title {font-size:22px;font-weight:900;text-align:center;margin-bottom:15px;}
.status-green .status-title{color:#147a3d}.status-yellow .status-title{color:#9a6700}.status-red .status-title{color:#b4232f}.status-grey .status-title{color:#475467}
.status-grid {display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}
.status-grid>div {background:#fff;border:1px solid #e8ebef;border-radius:10px;padding:11px;text-align:center;}
.status-grid b {display:block;font-size:18px;color:#182230;margin-top:5px;}
.status-note {margin-top:12px;text-align:center;color:#667085;font-size:12px;line-height:1.5;}
.check-card {background:#fff;border:1px solid #e7ebf0;border-radius:14px;padding:8px 18px;box-shadow:0 2px 8px rgba(16,42,67,.035);}
.check-row {display:grid;grid-template-columns:1.35fr .8fr 2fr;align-items:center;gap:10px;padding:12px 3px;border-bottom:1px solid #eef0f2;}
.check-row>span {font-weight:750;color:#344054;font-size:13px;}.check-row small {color:#98a2b3;font-size:11px;}.check-pass{color:#147a3d}.check-wait{color:#9a6700}.check-fail{color:#b4232f}
.check-total {display:flex;justify-content:space-between;align-items:center;padding:13px 3px 7px;font-size:12px;font-weight:850;color:#667085;}.check-total b{font-size:18px;color:#182230;}
.option-card {border:1px solid #e5e7eb;border-radius:15px;background:#fff;padding:17px;box-shadow:0 2px 9px rgba(16,42,67,.035);}
.option-call {border-top:4px solid #16a34a;}.option-put {border-top:4px solid #dc2626;}.option-selected{box-shadow:0 4px 16px rgba(16,42,67,.09);}
.option-head {display:flex;justify-content:space-between;align-items:center;font-size:16px;font-weight:900;color:#182230;}.option-call .option-head>span:first-child{color:#147a3d}.option-put .option-head>span:first-child{color:#b4232f}
.selected-tag {font-size:9px;background:#eef7f0;color:#147a3d;padding:5px 8px;border-radius:12px;letter-spacing:.4px;}
.option-strike {font-size:24px;font-weight:900;color:#182230;margin:8px 0 14px;}.option-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;}.option-grid>div{background:#f8fafc;border-radius:9px;padding:9px;}.option-grid b{display:block;font-size:14px;margin-top:5px;color:#182230;}
.option-readiness {margin-top:13px;border-radius:8px;text-align:center;padding:8px;font-size:11px;font-weight:900;letter-spacing:.4px;}.option-readiness.status-green{color:#147a3d}.option-readiness.status-yellow{color:#9a6700}.option-readiness.status-red{color:#b4232f}.option-readiness.status-grey{color:#475467}
.option-empty {padding:28px 5px;color:#98a2b3;text-align:center;font-size:13px;}.option-muted{border-top:4px solid #98a2b3;}
.exit-rule {background:#f8fafc;border:1px solid #e7ebf0;border-radius:11px;padding:13px 15px;margin-top:12px;}.exit-rule b{display:block;color:#344054;font-size:12px;margin-top:5px;line-height:1.5;}
.why-card {background:#fff;border:1px solid #e7ebf0;border-radius:14px;padding:7px 18px;box-shadow:0 2px 8px rgba(16,42,67,.035);}.why-item{padding:10px 3px;border-bottom:1px solid #eef0f2;color:#344054;font-size:12px;}.why-item:last-child{border-bottom:0}.why-warning{color:#9a6700;background:#fffbf1;border-radius:7px;padding-left:9px;padding-right:9px;margin:5px 0;}
.sr-map {display:grid;grid-template-columns:1fr 1.15fr 1fr;align-items:stretch;gap:0;background:#fff;border:1px solid #e7ebf0;border-radius:15px;overflow:hidden;box-shadow:0 2px 8px rgba(16,42,67,.035);min-height:150px;}.sr-side{display:flex;flex-direction:column;justify-content:center;align-items:center;padding:18px;text-align:center;}.sr-side span{font-size:10px;font-weight:900;letter-spacing:.4px}.sr-side b{font-size:25px;margin:7px 0;color:#182230}.sr-side small{color:#667085;font-size:11px}.sr-resistance{background:#fff7f7}.sr-resistance span{color:#b4232f}.sr-support{background:#f4fbf6}.sr-support span{color:#147a3d}.sr-line{display:flex;flex-direction:column;justify-content:center;align-items:center;gap:8px;background:#fff;border-left:1px dashed #dfe3e8;border-right:1px dashed #dfe3e8;}.room-label{font-size:11px;color:#98a2b3;font-weight:700}.current-marker{font-size:17px;font-weight:900;color:#182230;background:#f2f4f7;border:1px solid #e1e5ea;border-radius:20px;padding:8px 14px}.current-marker span{font-size:9px;color:#667085;margin-left:5px;letter-spacing:.4px;}
.tab-alert{border-radius:12px;padding:14px 16px;margin-bottom:16px;line-height:1.55;font-size:12px;}.tab-positive{background:#f4fbf6;border:1px solid #bde5c9;color:#147a3d}.tab-danger{background:#fff6f6;border:1px solid #f2c5c8;color:#b4232f}
@media (max-width:900px){.decision-stats,.status-grid{grid-template-columns:repeat(2,1fr)}.option-grid{grid-template-columns:repeat(2,1fr)}.sr-map{grid-template-columns:1fr}.sr-line{padding:15px;border-top:1px dashed #dfe3e8;border-bottom:1px dashed #dfe3e8}.topbar-dashboard{align-items:flex-start}.header-live{display:none}}
@media (max-width:600px){.block-container{padding-left:.7rem;padding-right:.7rem}.decision-main{font-size:25px}.check-row{grid-template-columns:1fr .9fr}.check-row small{grid-column:1 / -1}.metric-card,.entry-card{min-height:95px}.option-grid{grid-template-columns:repeat(2,1fr)}}
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
}


def api_get(path, params=None, timeout=20):
    """GET from Upstox with pacing and explicit Cloudflare/429 handling.

    Important: a 429 is NOT retried immediately. Upstox/Cloudflare supplies a
    retry_after value, and hammering the endpoint while blocked can prolong the
    rate limit. The caller receives a clear, actionable error instead.
    """
    global _LAST_API_REQUEST

    # Keep requests from arriving in a tight burst after Streamlit reruns.
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
    except requests.RequestException as exc:
        raise UpstoxError(f"Network error while contacting Upstox: {exc}") from exc

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

    # IMPORTANT: Do not use the setup score, timeframe alignment or Upstox PoP
    # as binary hard-fails. Doing so made the previous engine reject almost
    # every developing setup and turned useful information into NO TRADE.
    # These are now quality gates used by the decision engine below.
    hard_fail = []
    if tf5.get("trend") == opposite:
        hard_fail.append("5m trend conflict")
    if scored["spread_pct"] > 3:
        hard_fail.append("wide option spread")
    if not np.isfinite(scored["delta"]) or not (0.35 <= abs(scored["delta"]) <= 0.80):
        hard_fail.append("poor delta")
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

    # Readiness is deliberately separated from the final decision. A setup can
    # be a legitimate developing candidate even when it is not yet actionable.
    # The old logic converted every quality shortfall directly into NO TRADE.
    # That was too restrictive for a live scanner/decision assistant.
    if not trigger_hit:
        trigger_state = "WAIT FOR TRIGGER"
    elif not candle_confirmed or not volume_confirmed:
        trigger_state = "WAIT FOR CONFIRMATION"
    else:
        trigger_state = "READY"

    readiness = trigger_state

    # Descriptive quality flags used by the main decision layer.
    score_gate = scored["score"] >= 65
    watch_score_gate = scored["score"] >= 58
    alignment_gate = scored["alignment"] >= 2
    pop_ok = np.isfinite(scored["pop"]) and scored["pop"] >= 45
    strong_pop = np.isfinite(scored["pop"]) and scored["pop"] >= 55

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
        "score_gate": score_gate,
        "watch_score_gate": watch_score_gate,
        "alignment_gate": alignment_gate,
        "pop_ok": pop_ok,
        "strong_pop": strong_pop,
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
# SIMPLE 5-WAY DECISION ENGINE
# CALL BUY / CALL SELL / PUT BUY / PUT SELL / NO TRADE
# ============================================================

# The existing Upstox option-chain PoP is used directly for option BUYs.
# For option SELLs, the strategy PoP is the complement of the option BUY PoP.
# This is appropriate when the underlying PoP represents the probability that
# the option buyer makes a profit at expiry; transaction costs are not included.
def build_sell_plan(row, side, spot, support, resistance, pcr, tf5, tf30, daily,
                    risk_profile, chain, oi_wall_info=None):
    if row is None:
        return None

    prefix = "CE" if side == "CE" else "PE"
    ltp = safe_float(row[f"{prefix} LTP"])
    bid = safe_float(row[f"{prefix} Bid"])
    ask = safe_float(row[f"{prefix} Ask"])
    oi = safe_float(row[f"{prefix} OI"], 0)
    chg_oi = safe_float(row[f"{prefix} Chg OI"], 0)
    volume = safe_float(row[f"{prefix} Volume"], 0)
    delta = safe_float(row[f"{prefix} Delta"])
    iv = safe_float(row[f"{prefix} IV"])
    long_pop = safe_float(row[f"{prefix} PoP"])

    entry = bid if np.isfinite(bid) and bid > 0 else ltp
    if not np.isfinite(entry) or entry <= 0:
        return None

    short_pop = 100.0 - long_pop if np.isfinite(long_pop) else np.nan

    spread_pct = (
        max(ask - bid, 0) / max((ask + bid) / 2, 0.01) * 100
        if np.isfinite(ask) and np.isfinite(bid) and ask > 0 and bid > 0
        else 999
    )

    desired = "Bearish" if side == "CE" else "Bullish"
    tf_trends = [tf5.get("trend"), tf30.get("trend"), daily.get("trend")]
    alignment = tf_trends.count(desired)
    opposite = "Bullish" if side == "CE" else "Bearish"
    opposite_count = tf_trends.count(opposite)

    score = 0.0
    reasons = []

    # Direction / trend: 30 points.
    score += alignment * 10
    if opposite_count == 0:
        score += 5
    else:
        score -= opposite_count * 5

    # Intraday momentum: 20 points.
    momentum = safe_float(tf5.get("momentum"), 0)
    rsi = safe_float(tf5.get("rsi"), 50)
    if side == "CE":
        if tf5.get("trend") == "Bearish": score += 8
        if momentum < 0: score += 6
        if 32 <= rsi <= 48: score += 6
        elif rsi <= 50: score += 3
    else:
        if tf5.get("trend") == "Bullish": score += 8
        if momentum > 0: score += 6
        if 52 <= rsi <= 68: score += 6
        elif rsi >= 50: score += 3

    # VWAP: 15 points.
    vwap = safe_float(tf5.get("vwap"), spot)
    if np.isfinite(vwap) and vwap > 0:
        if side == "CE":
            if spot < vwap: score += 15
            elif spot <= vwap * 1.003: score += 5
        else:
            if spot > vwap: score += 15
            elif spot >= vwap * 0.997: score += 5

    # OI behaviour: 15 points. Rising OI on the sold side is supportive.
    if chg_oi > 0:
        score += 10
    elif chg_oi == 0:
        score += 4
    if oi >= 3000:
        score += 5
    elif oi > 0:
        score += 2

    # Option quality / liquidity: 20 points.
    abs_delta = abs(delta) if np.isfinite(delta) else np.nan
    if np.isfinite(abs_delta):
        if 0.20 <= abs_delta <= 0.40: score += 7
        elif 0.15 <= abs_delta < 0.20 or 0.40 < abs_delta <= 0.50: score += 4
    if spread_pct <= 1.0: score += 5
    elif spread_pct <= 2.0: score += 3
    if volume >= 10000: score += 5
    elif volume >= 3000: score += 3
    elif volume >= 500: score += 1
    if np.isfinite(iv) and iv >= 15: score += 3

    # Penalize a short position when the underlying is too close to the
    # relevant OI wall in the direction that would hurt the seller.
    wall_room = np.nan
    if side == "CE":
        wall_room = (resistance - spot) / max(spot, 1) * 100
        if wall_room >= 2.0: score += 5
        elif wall_room >= 1.0: score += 2
        elif wall_room < 0.5: score -= 10
    else:
        wall_room = (spot - support) / max(spot, 1) * 100
        if wall_room >= 2.0: score += 5
        elif wall_room >= 1.0: score += 2
        elif wall_room < 0.5: score -= 10

    score = float(np.clip(score, 0, 100))

    hard_fail = []
    if tf5.get("trend") == opposite:
        hard_fail.append("5m trend conflict")
    if spread_pct > 4:
        hard_fail.append("wide option spread")
    if not np.isfinite(abs_delta) or not (0.15 <= abs_delta <= 0.55):
        hard_fail.append("delta unsuitable for selling")
    if volume < 500:
        hard_fail.append("weak option liquidity")
    if oi <= 0:
        hard_fail.append("no option OI")
    if not np.isfinite(short_pop) or short_pop < 50:
        hard_fail.append("low strategy PoP")
    if side == "CE" and spot > resistance:
        hard_fail.append("price above resistance")
    if side == "PE" and spot < support:
        hard_fail.append("price below support")

    # For a short option the simple reference risk levels are premium-based.
    # The SL is deliberately tighter than the profit target because option
    # selling has asymmetric risk. This is a reference plan, not an order.
    sl = round(entry * 1.35, 2)
    target1 = round(entry * 0.60, 2)
    target2 = round(entry * 0.35, 2)

    if side == "CE":
        trigger_level = max(vwap, spot) if np.isfinite(vwap) else spot
        trigger_hit = spot <= resistance and spot < trigger_level * 1.005
        exit_rule = (
            f"Exit if spot sustains above resistance {fmt_price(resistance)} "
            f"or option premium reaches {fmt_price(sl)}. Book profit progressively."
        )
    else:
        trigger_level = min(vwap, spot) if np.isfinite(vwap) else spot
        trigger_hit = spot >= support and spot > trigger_level * 0.995
        exit_rule = (
            f"Exit if spot sustains below support {fmt_price(support)} "
            f"or option premium reaches {fmt_price(sl)}. Book profit progressively."
        )

    return {
        "side": side,
        "strike": float(row["Strike"]),
        "action": "CALL SELL" if side == "CE" else "PUT SELL",
        "entry": entry,
        "sl": sl,
        "target1": target1,
        "target2": target2,
        "pop": short_pop,
        "long_pop": long_pop,
        "delta": delta,
        "iv": iv,
        "score": score,
        "rr1": (entry - target1) / max(sl - entry, 0.01),
        "rr2": (entry - target2) / max(sl - entry, 0.01),
        "trigger": "Sell only while price remains on the safe side of the OI/VWAP structure.",
        "trigger_level": trigger_level,
        "trigger_hit": trigger_hit,
        "fail_reasons": hard_fail,
        "oi": oi,
        "chg_oi": chg_oi,
        "volume": volume,
        "spread_pct": spread_pct,
        "alignment": alignment,
        "vwap": vwap,
        "room_pct": wall_room,
        "readiness": "READY" if not hard_fail and score >= 60 and short_pop >= 55 else "NO TRADE",
        "exit": exit_rule,
    }


# ============================================================
# LIVE ANALYSIS
# ============================================================

with st.sidebar:
    st.markdown("## 🔎 Analyze Instrument")
    symbol_input = st.text_input(
        "NSE Stock / Index",
        value=st.session_state.get("symbol", "KOTAKBANK"),
        placeholder="NIFTY / BANKNIFTY / HDFCBANK",
    )
    risk_profile = st.selectbox("Risk Profile", ["Conservative", "Balanced", "Aggressive"], index=1)
    analyze = st.button("Analyze Live Market", type="primary", use_container_width=True)
    refresh = st.button("↻ Refresh Live Data", use_container_width=True)
    auto_refresh = st.checkbox("Auto refresh every 60 seconds", value=False)
    if auto_refresh and st_autorefresh is not None:
        st_autorefresh(interval=60_000, key="simple_live_refresh")
    st.divider()
    st.caption("LIVE DATA • Powered by Upstox")
    st.caption("No simulated prices are used.")

if analyze:
    st.session_state["symbol"] = alias_symbol(symbol_input)
    st.rerun()
if refresh:
    st.cache_data.clear()
    st.rerun()

symbol = alias_symbol(st.session_state.get("symbol", symbol_input or "KOTAKBANK"))

try:
    with st.spinner(f"Analyzing live {symbol} data..."):
        underlying = search_underlying(symbol)
        underlying_key = underlying["instrument_key"]
        contracts = get_contracts(underlying_key)
        expiries = available_expiries(contracts)
        if not expiries:
            raise UpstoxError("No upcoming F&O expiry was returned by Upstox.")
        selected_expiry = expiries[0]
        raw_chain = get_option_chain(underlying_key, selected_expiry)
        chain = normalize_chain(raw_chain)
        quote_data = get_quote(underlying_key)
        spot = safe_float(quote_data.get("last_price"))
        previous_close = safe_float(quote_data.get("prev_close_price"), spot)
        net_change = safe_float(quote_data.get("net_change"), spot - previous_close)
        change_pct = net_change / previous_close * 100 if previous_close else 0
        candles = get_daily_candles(underlying_key)
        candles_30m = get_30m_candles(underlying_key)
        candles_5m = get_intraday_candles(underlying_key, 5)
        daily_tech = technicals(candles, spot)
        tf30 = technicals(candles_30m, spot)
        tf5 = technicals(candles_5m, spot)
except UpstoxRateLimitError as exc:
    st.error(f"⏳ Upstox rate limit reached. Please wait about {exc.retry_after} seconds before refreshing.")
    st.stop()
except UpstoxError as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:
    st.error(f"Unexpected error while loading live data: {exc}")
    st.stop()

support, resistance, pcr, oi_wall_info = oi_levels(chain, spot)
atm_index = (chain["Strike"] - spot).abs().idxmin()

# For each strategy we select a strike that is close enough to the underlying
# to remain liquid, then score the strategy itself rather than a generic BUY score.
band = chain.iloc[max(0, atm_index - 8):min(len(chain), atm_index + 9)].copy()


def buy_candidate(side):
    candidates = []
    for _, row in band.iterrows():
        scored = score_option(row, side, spot, pcr, tf5, tf30, daily_tech, chain,
                              support=support, resistance=resistance, oi_wall_info=oi_wall_info)
        prefix = "CE" if side == "CE" else "PE"
        pop = safe_float(row[f"{prefix} PoP"])
        volume = safe_float(row[f"{prefix} Volume"], 0)
        spread = scored.get("spread_pct", 999)
        delta = abs(safe_float(row[f"{prefix} Delta"]))
        if np.isfinite(pop) and np.isfinite(row[f"{prefix} LTP"]) and row[f"{prefix} LTP"] > 0:
            candidates.append((scored["score"], pop, volume, -spread, -abs(delta - .55), row))
    if not candidates:
        return None
    row = max(candidates, key=lambda x: x[:-1])[-1]
    return build_plan(row, side, spot, support, resistance, pcr, tf5, tf30, daily_tech,
                      risk_profile, chain, oi_wall_info)


def sell_candidate(side):
    candidates = []
    for _, row in chain.iterrows():
        prefix = "CE" if side == "CE" else "PE"
        strike = safe_float(row["Strike"])
        if not np.isfinite(strike):
            continue
        # Prefer slightly OTM options for selling rather than ATM options.
        if side == "CE" and strike < spot * 1.005:
            continue
        if side == "PE" and strike > spot * 0.995:
            continue
        plan = build_sell_plan(row, side, spot, support, resistance, pcr, tf5, tf30,
                               daily_tech, risk_profile, chain, oi_wall_info)
        if plan is None:
            continue
        candidates.append((plan["score"], plan["pop"], plan["volume"], -plan["spread_pct"], -abs(abs(plan["delta"]) - .30), plan))
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[:-1])[-1]


call_buy = buy_candidate("CE")
put_buy = buy_candidate("PE")
call_sell = sell_candidate("CE")
put_sell = sell_candidate("PE")

# ============================================================
# FINAL 5-WAY DECISION
# ============================================================
MIN_SCORE = 60
MIN_POP = 55

strategy_plans = {
    "CALL BUY": call_buy,
    "CALL SELL": call_sell,
    "PUT BUY": put_buy,
    "PUT SELL": put_sell,
}

eligible = []
for action, plan in strategy_plans.items():
    if not plan:
        continue
    hard_fail = plan.get("fail_reasons") or []
    pop = safe_float(plan.get("pop"))
    score = safe_float(plan.get("score"), 0)
    if action in {"CALL BUY", "PUT BUY"}:
        ready = (
            score >= MIN_SCORE and pop >= MIN_POP and
            not hard_fail and plan.get("readiness") == "READY"
        )
    else:
        ready = score >= MIN_SCORE and pop >= MIN_POP and not hard_fail
    if ready:
        eligible.append((score + pop * 0.25, action, plan))

if eligible:
    _, decision, best_plan = max(eligible, key=lambda x: x[0])
else:
    decision = "NO TRADE"
    # Show the best reference candidate internally for diagnostics, but do not
    # label it as a recommendation.
    available = [(safe_float(p.get("score"), 0), action, p) for action, p in strategy_plans.items() if p]
    best_plan = max(available, key=lambda x: x[0])[2] if available else None

# The decision is intentionally binary at the action level: one of four trades
# or NO TRADE. There are no WAIT/WATCHLIST states in the primary UI.

# ============================================================
# VISUAL DASHBOARD
# ============================================================

now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
market_open = now_ist.weekday() < 5 and (now_ist.hour, now_ist.minute) >= (9, 15) and (now_ist.hour, now_ist.minute) <= (15, 30)
status_text = "● LIVE DATA" if market_open else "● MARKET CLOSED"
status_class = "live-block" if market_open else "closed-block"

st.markdown(
    f"""
<div class="topbar topbar-dashboard">
  <div><div class="topbar-title">📊 FO PRO Trader Assistant</div>
  <div class="topbar-sub">Simple 5-way F&O decision engine • Live Upstox market data</div></div>
  <div class="{status_class}">{status_text}</div>
</div>
""",
    unsafe_allow_html=True,
)

# Stock / index name — displayed once, directly above the market snapshot
st.markdown(
    f"""<div style="font-size:24px;font-weight:900;color:#182230;margin:4px 0 10px 2px;">{symbol}</div>""",
    unsafe_allow_html=True,
)

# Instrument snapshot
st.markdown("<div class='section-heading'>MARKET SNAPSHOT</div>", unsafe_allow_html=True)
cols = st.columns(6)
snapshot = [
    ("SPOT", fmt_price(spot), f"{net_change:+.2f} ({change_pct:+.2f}%)"),
    ("EXPIRY", selected_expiry, "Nearest F&O expiry"),
    ("PCR", f"{pcr:.2f}" if np.isfinite(pcr) else "—", "Put / Call OI"),
    ("SUPPORT", fmt_price(support), "Put OI zone"),
    ("RESISTANCE", fmt_price(resistance), "Call OI zone"),
    ("VWAP", fmt_price(tf5.get("vwap")), "5m VWAP"),
]
for col, (title, value, note) in zip(cols, snapshot):
    with col:
        st.markdown(f"<div class='metric-card'><span>{title}</span><b>{value}</b><small>{note}</small></div>", unsafe_allow_html=True)

# Main decision card — this is the answer the user should look at first.
st.markdown("<div class='section-heading'>🎯 TRADE DECISION</div>", unsafe_allow_html=True)
decision_meta = {
    "CALL BUY": ("🟢", "decision-call", "Buy a Call option when the displayed entry conditions are satisfied."),
    "CALL SELL": ("🔵", "decision-call", "Sell a Call option; understand the higher risk of option selling before entering."),
    "PUT BUY": ("🔴", "decision-put", "Buy a Put option when the displayed entry conditions are satisfied."),
    "PUT SELL": ("🟣", "decision-put", "Sell a Put option; understand the higher risk of option selling before entering."),
    "NO TRADE": ("⚪", "decision-neutral", "No strategy currently meets all minimum quality and PoP conditions."),
}
icon, card_class, subtitle = decision_meta[decision]

if decision != "NO TRADE" and best_plan:
    action_pop = safe_float(best_plan.get("pop"))
    action_score = safe_float(best_plan.get("score"), 0)
    contract = f"{best_plan['strike']:.0f} {'CE' if best_plan['side'] == 'CE' else 'PE'}"
    action_label = decision
else:
    action_pop = np.nan
    action_score = max([safe_float(p.get("score"), 0) for p in strategy_plans.values() if p] or [0])
    contract = "—"
    action_label = "NO TRADE"

st.markdown(
    f"""
<div class="decision-card {card_class}">
  <div class="decision-main">{icon} {action_label}</div>
  <div class="decision-sub">{subtitle}</div>
  <div class="decision-stats">
    <div><span>OPTION</span><div class="decision-value">{contract}</div></div>
    <div><span>PoP</span><div class="decision-value">{f'{action_pop:.1f}%' if np.isfinite(action_pop) else '—'}</div></div>
    <div><span>QUALITY</span><div class="decision-value">{action_score:.0f}<span>/100</span></div></div>
    <div><span>MARKET</span><div class="decision-value">{overall_trend(tf5, tf30, daily_tech)[0].upper()}</div></div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# Compact strategy comparison: one row per possible action. This is useful when
# NO TRADE is returned because it shows that the engine actually evaluated all four sides.
st.markdown("<div class='section-heading'>ENGINE RESULT</div>", unsafe_allow_html=True)
engine_rows = []
for action in ["CALL BUY", "CALL SELL", "PUT BUY", "PUT SELL"]:
    plan = strategy_plans[action]
    if plan:
        fails = ", ".join(plan.get("fail_reasons") or []) or "All minimum checks passed"
        engine_rows.append({
            "Strategy": action,
            "Strike": int(round(plan["strike"])),
            "PoP": f"{safe_float(plan.get('pop')):.1f}%" if np.isfinite(safe_float(plan.get("pop"))) else "—",
            "Quality": f"{safe_float(plan.get('score'), 0):.0f}/100",
            "Status": "SELECTED" if action == decision else ("ELIGIBLE" if not plan.get("fail_reasons") and safe_float(plan.get("score"), 0) >= MIN_SCORE and safe_float(plan.get("pop"), 0) >= MIN_POP else "REJECTED"),
            "Reason": fails,
        })
if engine_rows:
    st.dataframe(pd.DataFrame(engine_rows), use_container_width=True, hide_index=True)

# Selected trade plan — shown prominently only when one of the four
# strategies is actually selected. NO TRADE never displays executable levels.
if decision != "NO TRADE" and best_plan:
    st.markdown("<div class='section-heading'>📌 SELECTED TRADE PLAN</div>", unsafe_allow_html=True)

    selected_contract = f"{best_plan['strike']:.0f} {'CE' if best_plan['side'] == 'CE' else 'PE'}"
    st.markdown(
        f"""
        <div class="card" style="padding:18px 20px; margin-bottom:14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;">
            <div>
              <div style="font-size:11px;font-weight:800;color:#667085;letter-spacing:.6px;">SELECTED STRATEGY</div>
              <div style="font-size:25px;font-weight:900;color:#182230;margin-top:5px;">{decision} • {selected_contract}</div>
            </div>
            <div style="font-size:20px;font-weight:900;color:#147a3d;">PoP {safe_float(best_plan.get('pop')):.1f}%</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    levels = st.columns(5)
    level_items = [
        ("ENTRY", fmt_price(best_plan.get("entry")), "Option premium"),
        ("STOP LOSS", fmt_price(best_plan.get("sl")), "Option premium"),
        ("TARGET 1", fmt_price(best_plan.get("target1")), "First profit level"),
        ("TARGET 2", fmt_price(best_plan.get("target2")), "Second profit level"),
        ("DELTA / IV", f"{safe_float(best_plan.get('delta')):.2f} / {safe_float(best_plan.get('iv')):.1f}%", "Option quality"),
    ]
    for col, (title, value, note) in zip(levels, level_items):
        with col:
            st.markdown(
                f"<div class='entry-card'><span>{title}</span><b>{value}</b><small>{note}</small></div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        f"<div class='exit-rule'><span>🚪 EXIT RULE</span><b>{best_plan.get('exit','Follow stop-loss and targets.')}</b></div>",
        unsafe_allow_html=True,
    )
else:
    st.info("NO TRADE means none of CALL BUY, CALL SELL, PUT BUY or PUT SELL passed the backend quality + PoP gates.")

# Minimal supporting information — no checklist, wait states, watchlist or score dashboard.
with st.expander("Why this decision?", expanded=False):
    if decision != "NO TRADE" and best_plan:
        st.write(
            f"Selected {decision} on {best_plan['strike']:.0f} {'CE' if best_plan['side']=='CE' else 'PE'} "
            f"with strategy PoP {best_plan['pop']:.1f}% and quality score {best_plan['score']:.0f}/100."
        )
        st.write(f"Trend: {overall_trend(tf5, tf30, daily_tech)[0]}. 5m: {tf5['trend']} • 30m: {tf30['trend']} • Daily: {daily_tech['trend']}.")
        st.write(f"Support: {fmt_price(support)} • Resistance: {fmt_price(resistance)} • VWAP: {fmt_price(tf5.get('vwap'))}.")
    else:
        for action in ["CALL BUY", "CALL SELL", "PUT BUY", "PUT SELL"]:
            plan = strategy_plans[action]
            if plan:
                reason = ", ".join(plan.get("fail_reasons") or []) or "quality/confirmation gate not met"
                st.write(f"**{action}:** {reason} • PoP {safe_float(plan.get('pop')):.1f}% • Score {safe_float(plan.get('score'),0):.0f}/100")

st.markdown("<div class='section-heading'>OPTION DETAILS</div>", unsafe_allow_html=True)
if decision != "NO TRADE" and best_plan:
    st.write(
        f"**{decision}** • {best_plan['strike']:.0f} {'CE' if best_plan['side']=='CE' else 'PE'} • "
        f"PoP {best_plan['pop']:.1f}% • Delta {safe_float(best_plan['delta']):.2f} • "
        f"IV {safe_float(best_plan['iv']):.1f}% • OI {fmt_num(best_plan['oi'])} • Volume {fmt_num(best_plan['volume'])}"
    )
else:
    st.write("No option is currently selected for execution.")

st.caption(
    f"Live Upstox snapshot • Expiry {selected_expiry} • Updated {now_ist.strftime('%d-%b-%Y %H:%M:%S IST')}. "
    "PoP is a model input from the Upstox option chain; it is not a guaranteed win probability. Option selling can carry substantial risk."
)
