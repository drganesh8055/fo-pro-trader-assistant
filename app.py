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
    st.markdown("### 🔥 Top 5 F&O PoP Scanner")
    st.caption("Scans the full NSE equity F&O market for trades with PoP > 75%.")

    scan_market = st.button(
        "🔎 Scan Full F&O Market",
        use_container_width=True,
        type="primary",
    )

    if scan_market:
        try:
            with st.spinner("Scanning the full F&O market..."):
                results, total, scanned, failed = scan_full_fno_pop_market(75.0)
            st.session_state["fno_pop_results"] = results
            st.session_state["fno_pop_scan_info"] = (total, scanned, failed)
            st.session_state["fno_pop_scan_time"] = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")
        except UpstoxRateLimitError as exc:
            st.session_state["fno_pop_results"] = []
            st.error(
                f"⏳ Upstox rate limit reached. Wait about {exc.retry_after} seconds, "
                "then scan again. The scanner stopped immediately to avoid making the block worse."
            )
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
            st.caption(f"Scanned {scanned}/{total} F&O stocks • {failed} unavailable")
        if scan_time:
            st.caption(f"Last scan: {scan_time} IST")

        scanner_display = pd.DataFrame([
            {
                "Stock": row["Stock"],
                "Trade": row["Trade"],
                "Strike": int(row["Strike"]),
                "PoP": f"{row['PoP']:.1f}%",
                "Entry": fmt_price(row["Entry"]),
                "SL": fmt_price(row["SL"]),
                "Target1": fmt_price(row["Target1"]),
                "Target2": fmt_price(row["Target2"]),
                "Exit": row["Exit"],
            }
            for row in pop_results
        ])
        st.dataframe(
            scanner_display,
            use_container_width=True,
            hide_index=True,
            height=min(360, 58 + len(scanner_display) * 52),
        )
    elif "fno_pop_results" in st.session_state:
        st.info("No F&O stock currently has an option trade with PoP > 75%.")

    st.divider()
    st.markdown("### 🔎 Analyze Instrument")

    symbol_label = "Stock / Index"
    symbol_default = st.session_state.get("symbol", "KOTAKBANK")
    symbol_placeholder = "e.g. KOTAKBANK, HDFCBANK, NIFTY"

    symbol_input = st.text_input(
        symbol_label,
        value=symbol_default,
        placeholder=symbol_placeholder,
        label_visibility="collapsed",
    )

    risk_profile = st.selectbox(
        "Risk Profile",
        ["Conservative", "Balanced", "Aggressive"],
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
            "Auto refresh every 60 seconds",
            value=False,
        )
        if auto_refresh:
            st_autorefresh(interval=60_000, key="upstox_live_refresh")

    st.divider()
    st.caption("LIVE DATA • Powered by Upstox")
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


# ---------- Header ----------
st.markdown(
    f"""
<div class=\"topbar topbar-dashboard\">
    <div>
        <div class=\"topbar-title\">📊 FO PRO Trader Assistant</div>
        <div class=\"topbar-sub\">Options Analysis • Powered by Upstox • Live market data</div>
    </div>
    <div class=\"header-live\">{'● LIVE DATA' if market_open else '● MARKET CLOSED'}</div>
</div>
""",
    unsafe_allow_html=True,
)

h1, h2, h3 = st.columns([2.3, 1.15, 1.05])
with h1:
    st.markdown(f"## {symbol} — F&O Options Analysis")
    st.caption("Live underlying • Option-chain analysis • Multi-timeframe confirmation")
with h2:
    st.markdown("**Last Traded**")
    st.markdown(f"<div class='hero-price'>{fmt_price(spot)}</div>", unsafe_allow_html=True)
    st.caption(f"{net_change:+.2f} ({change_pct:+.2f}%)")
with h3:
    st.markdown("**Data Status**")
    status_text = "● LIVE DATA" if market_open else "● MARKET CLOSED"
    status_css = "live-block" if market_open else "closed-block"
    st.markdown(f"<div class='{status_css}'>{status_text}</div>", unsafe_allow_html=True)
    st.caption(f"Expiry: {selected_expiry}")

# ---------- Market snapshot ----------
st.markdown("<div class='section-heading'>📊 MARKET SNAPSHOT</div>", unsafe_allow_html=True)
m1, m2, m3, m4, m5, m6 = st.columns(6)
with m1:
    st.markdown(f"<div class='metric-card'><span>LAST PRICE</span><b>{fmt_price(spot)}</b><small>LIVE PRICE</small></div>", unsafe_allow_html=True)
with m2:
    bias_cls = "metric-positive" if tech["trend"] == "Bullish" else "metric-negative" if tech["trend"] == "Bearish" else "metric-neutral"
    st.markdown(f"<div class='metric-card {bias_cls}'><span>MARKET BIAS</span><b>{tech['trend']}</b><small>HEADLINE TREND</small></div>", unsafe_allow_html=True)
with m3:
    pcr_display = f"{pcr:.2f}" if np.isfinite(pcr) else "—"
    st.markdown(
        f"<div class='metric-card'><span>PCR</span><b>{pcr_display}</b><small>PUT / CALL OI</small></div>",
        unsafe_allow_html=True,
    )
with m4:
    st.markdown(f"<div class='metric-card metric-support'><span>SUPPORT</span><b>{fmt_price(support)}</b><small>PUT OI WALL</small></div>", unsafe_allow_html=True)
with m5:
    st.markdown(f"<div class='metric-card metric-resistance'><span>RESISTANCE</span><b>{fmt_price(resistance)}</b><small>CALL OI WALL</small></div>", unsafe_allow_html=True)
with m6:
    st.markdown(f"<div class='metric-card'><span>RSI</span><b>{tech['rsi']:.1f}</b><small>DAILY RSI</small></div>", unsafe_allow_html=True)

# ---------- Trade decision ----------
decision_icon = "🟢" if decision == "CALL BUY" else "🔴" if decision == "PUT BUY" else "🟡" if "WAIT" in decision else "⚪"
decision_sub = {
    "CALL BUY": "Bullish conditions aligned — entry confirmation required by the engine.",
    "PUT BUY": "Bearish conditions aligned — entry confirmation required by the engine.",
    "WAIT FOR TRIGGER": "Setup is developing. Do not enter until the trigger is reached.",
    "WAIT FOR CONFIRMATION": "Trigger reached, but confirmation conditions are not complete.",
    "NO TRADE": "Conditions are not sufficiently aligned for a valid setup.",
}.get(decision, "Review the live conditions before taking action.")

st.markdown("<div class='section-heading'>🎯 TRADE DECISION</div>", unsafe_allow_html=True)

# Use native Streamlit layout for this section instead of nested HTML.
# This prevents Streamlit from ever displaying HTML tags as literal text.
with st.container(border=True):
    st.markdown(f"### {decision_icon} {decision}")
    st.caption(decision_sub)

    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.metric("BULL SCORE", f"{ce_score:.0f}/100")
    with d2:
        st.metric("BEAR SCORE", f"{pe_score:.0f}/100")
    with d3:
        st.metric("TREND", overall_direction.upper())
    with d4:
        st.metric("CONFIDENCE", f"{confidence}/100")

# ---------- Trade status ----------
st.markdown("<div class='section-heading'>🚦 TRADE STATUS</div>", unsafe_allow_html=True)
status_plan = best_plan
if status_plan:
    status = status_plan["readiness"]
    if decision == "NO TRADE":
        status = "NO TRADE"
    status_title = {
        "READY": "🟢 READY TO ENTER",
        "WAIT FOR TRIGGER": "🟡 WAIT FOR TRIGGER",
        "WAIT FOR CONFIRMATION": "🟡 WAIT FOR CONFIRMATION",
        "NO TRADE": "🔴 NO TRADE",
    }.get(status, status)
    trigger_distance = abs(spot - status_plan["trigger_level"])
    st.markdown(
        f"""
<div class='status-panel {_status_class(status)}'>
    <div class='status-title'>{status_title}</div>
    <div class='status-grid'>
        <div><span>CURRENT PRICE</span><b>{fmt_price(spot)}</b></div>
        <div><span>TRIGGER</span><b>{fmt_price(status_plan['trigger_level'])}</b></div>
        <div><span>DISTANCE</span><b>{fmt_price(trigger_distance)}</b></div>
    </div>
    <div class='status-note'>{status_plan['trigger']}</div>
</div>
""",
        unsafe_allow_html=True,
    )
else:
    st.markdown("<div class='status-panel status-grey'><div class='status-title'>⚪ NO VALID PLAN</div><div class='status-note'>No usable option contract was returned by the live chain.</div></div>", unsafe_allow_html=True)

# ---------- Checklist ----------
direction_pass = overall_direction in {"Bullish", "Bearish"}
mtf_pass = overall_alignment >= 2
oi_pass = np.isfinite(support) and np.isfinite(resistance) and support < spot < resistance
vwap_value = safe_float(tf5.get("vwap"), spot)
if best_plan:
    if best_plan["side"] == "CE":
        vwap_pass = spot >= vwap_value * 0.997
    else:
        vwap_pass = spot <= vwap_value * 1.003
else:
    vwap_pass = False
breakout_state = "PASS" if best_plan and best_plan.get("trigger_hit") and best_plan.get("candle_confirmed") and best_plan.get("volume_confirmed") else "WAIT"

st.markdown("<div class='section-heading'>🧠 TRADE CHECKLIST</div>", unsafe_allow_html=True)
check_html = (
    _check_row("Market Direction", "PASS" if direction_pass else "FAIL", f"{overall_direction} market bias") +
    _check_row("Multi-Timeframe", "PASS" if mtf_pass else "FAIL", f"{overall_alignment}/3 timeframes aligned") +
    _check_row("OI Structure", "PASS" if oi_pass else "FAIL", f"Support {fmt_price(support)} • Resistance {fmt_price(resistance)}") +
    _check_row("VWAP", "PASS" if vwap_pass else "FAIL", f"5m VWAP {fmt_price(vwap_value)}") +
    _check_row("Breakout Confirmation", breakout_state, "Trigger + 5m momentum + volume confirmation")
)
check_overall = sum([direction_pass, mtf_pass, oi_pass, vwap_pass, breakout_state == "PASS"])
st.markdown(
    f"<div class='check-card'>{check_html}<div class='check-total'><span>OVERALL</span><b>{check_overall}/5</b></div></div>",
    unsafe_allow_html=True,
)

# ---------- Trade plan ----------
st.markdown("<div class='section-heading'>🎯 TRADE PLAN</div>", unsafe_allow_html=True)
selected_side = best_plan["side"] if best_plan else None

def render_plan_native(plan, label, selected=False):
    """Render the trade plan with native Streamlit components.

    This intentionally avoids nested HTML divs because Streamlit's Markdown/HTML
    sanitizer can render portions of complex nested cards as literal code.
    """
    if not plan:
        st.info(f"{label} BUY — No valid option plan returned.")
        return

    side = plan["side"]
    icon = "🟢" if side == "CE" else "🔴"
    contract = "CE" if side == "CE" else "PE"
    status = str(plan.get("readiness", "NO TRADE"))
    status_icon = "🟢" if status == "READY" else "🟡" if "WAIT" in status else "🔴"

    with st.container(border=True):
        header_left, header_right = st.columns([3, 1])
        with header_left:
            st.markdown(f"### {icon} {label} BUY")
        with header_right:
            if selected:
                st.markdown("**★ SELECTED**")

        st.markdown(f"## {plan['strike']:.0f} {contract}")

        values = [
            ("Entry", fmt_price(plan.get("entry"))),
            ("Stop Loss", fmt_price(plan.get("sl"))),
            ("Target 1", fmt_price(plan.get("target1"))),
            ("Target 2", fmt_price(plan.get("target2"))),
            ("PoP", f"{_num_or_dash(plan.get('pop'), 1)}%"),
            ("Delta", _num_or_dash(plan.get("delta"), 2)),
            ("IV", f"{_num_or_dash(plan.get('iv'), 1)}%"),
            ("R:R T2", f"1:{_num_or_dash(plan.get('rr2'), 2)}"),
        ]
        cols = st.columns(4)
        for col, (title, value) in zip(cols, values[:4]):
            with col:
                st.metric(title, value)
        cols = st.columns(4)
        for col, (title, value) in zip(cols, values[4:]):
            with col:
                st.metric(title, value)

        if status == "READY":
            st.success(f"{status_icon} {status}")
        elif "WAIT" in status:
            st.warning(f"{status_icon} {status}")
        else:
            st.error(f"{status_icon} {status}")

p1, p2 = st.columns(2)
with p1:
    render_plan_native(ce_plan, "CALL", selected_side == "CE")
with p2:
    render_plan_native(pe_plan, "PUT", selected_side == "PE")

# ---------- Entry / Exit ----------
st.markdown("<div class='section-heading'>📍 ENTRY / EXIT</div>", unsafe_allow_html=True)
if best_plan:
    entry_distance = abs(spot - best_plan["trigger_level"])
    e1, e2, e3, e4, e5 = st.columns(5)
    values = [
        ("CURRENT PRICE", fmt_price(spot), "Underlying"),
        ("ENTRY TRIGGER", fmt_price(best_plan["trigger_level"]), f"Distance {fmt_price(entry_distance)}"),
        ("STOP LOSS", fmt_price(best_plan["sl"]), "Option premium"),
        ("TARGET 1", fmt_price(best_plan["target1"]), "Partial exit"),
        ("TARGET 2", fmt_price(best_plan["target2"]), "Final target"),
    ]
    for col, (title, value, note) in zip([e1,e2,e3,e4,e5], values):
        with col:
            st.markdown(f"<div class='entry-card'><span>{title}</span><b>{value}</b><small>{note}</small></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='exit-rule'><span>EXIT RULE</span><b>{best_plan['exit']}</b></div>", unsafe_allow_html=True)
else:
    st.info("No valid trade plan is available from the current option chain.")

# ---------- Why this trade ----------
st.markdown("<div class='section-heading'>💡 WHY THIS TRADE?</div>", unsafe_allow_html=True)
why_items = []
if best_plan:
    side_name = "CALL" if best_plan["side"] == "CE" else "PUT"
    desired = "Bullish" if best_plan["side"] == "CE" else "Bearish"
    why_items += [
        f"{tf5['trend']} 5m trend supports the {side_name} direction.",
        f"{tf30['trend']} 30m trend and {daily_tech['trend']} daily trend are part of the multi-timeframe check.",
        f"Price is {'above' if spot >= vwap_value else 'below'} the 5m VWAP at {fmt_price(vwap_value)}.",
        f"OI structure shows support at {fmt_price(support)} and resistance at {fmt_price(resistance)}.",
        f"Selected option PoP is {_num_or_dash(best_plan['pop'], 1)}% with Delta {_num_or_dash(best_plan['delta'], 2)}.",
        f"Option spread is {_num_or_dash(best_plan['spread_pct'], 1)}% with volume {fmt_num(best_plan['volume'])}.",
    ]
    if best_plan["fail_reasons"]:
        why_items.append("⚠ " + "; ".join(best_plan["fail_reasons"]))
else:
    why_items = ["No valid option plan is currently available."]

why_html_parts = []
for item in why_items:
    warning_class = "why-warning" if item.startswith("⚠") else ""
    icon = "⚠" if item.startswith("⚠") else "✓"
    clean_item = item.lstrip("⚠ ")
    why_html_parts.append(
        f"<div class='why-item {warning_class}'>{icon} {clean_item}</div>"
    )
why_html = "".join(why_html_parts)
st.markdown(f"<div class='why-card'>{why_html}</div>", unsafe_allow_html=True)

# ---------- OI map ----------
st.markdown("<div class='section-heading'>📍 SUPPORT / RESISTANCE + OI MAP</div>", unsafe_allow_html=True)
put_row = nearest_row(chain, support)
call_row = nearest_row(chain, resistance)
put_oi = put_row["PE OI"] if put_row is not None else np.nan
call_oi = call_row["CE OI"] if call_row is not None else np.nan
support_room = max((spot - support) / max(spot,1) * 100, 0) if np.isfinite(support) else np.nan
resistance_room = max((resistance - spot) / max(spot,1) * 100, 0) if np.isfinite(resistance) else np.nan

st.markdown(
    f"""
<div class='sr-map'>
    <div class='sr-side sr-resistance'>
        <span>🔴 CALL OI WALL</span><b>{fmt_price(resistance)}</b><small>OI {fmt_num(call_oi)}</small>
    </div>
    <div class='sr-line'>
        <div class='room-label'>+{_num_or_dash(resistance_room,2)}%</div>
        <div class='current-marker'>● {fmt_price(spot)} <span>CURRENT</span></div>
        <div class='room-label'>-{_num_or_dash(support_room,2)}%</div>
    </div>
    <div class='sr-side sr-support'>
        <span>🟢 PUT OI WALL</span><b>{fmt_price(support)}</b><small>OI {fmt_num(put_oi)}</small>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------- Tabs ----------
tab1, tab2, tab3, tab4 = st.tabs([
    "🏆 Best Trade", "🔎 Live Option Chain", "📊 Market Analysis", "🧠 How Engine Thinks"
])

with tab1:
    if decision == "NO TRADE":
        st.markdown("<div class='tab-alert tab-danger'><b>⚪ NO TRADE</b><br>Conditions do not currently meet the quality gate. Wait for a new setup rather than forcing an entry.</div>", unsafe_allow_html=True)
    elif best_plan:
        tab_icon = "🟢" if best_plan["side"] == "CE" else "🔴"
        st.markdown(f"<div class='tab-alert tab-positive'><b>{tab_icon} {decision}</b><br>Strike {best_plan['strike']:.0f} • Entry {fmt_price(best_plan['entry'])} • SL {fmt_price(best_plan['sl'])} • T1 {fmt_price(best_plan['target1'])} • T2 {fmt_price(best_plan['target2'])}</div>", unsafe_allow_html=True)

    st.markdown("### Engine Summary")
    summary_cols = st.columns(4)
    summary_cols[0].metric("CALL SCORE", f"{ce_score:.0f}/100")
    summary_cols[1].metric("PUT SCORE", f"{pe_score:.0f}/100")
    summary_cols[2].metric("ALIGNMENT", f"{overall_alignment}/3")
    summary_cols[3].metric("CHECKLIST", f"{check_overall}/5")

with tab2:
    st.markdown(f"### Live Option Chain — {selected_expiry}")
    view = chain.copy()
    display = pd.DataFrame({
        "Strike": view["Strike"].round(0).astype(int),
        "CE LTP": view["CE LTP"].round(2),
        "CE OI": view["CE OI"].round(0).astype("int64"),
        "CE Chg OI": view["CE Chg OI"].round(0).astype("int64"),
        "CE IV": view["CE IV"].round(1),
        "CE Delta": view["CE Delta"].round(3),
        "CE PoP": view["CE PoP"].round(1),
        "PE LTP": view["PE LTP"].round(2),
        "PE OI": view["PE OI"].round(0).astype("int64"),
        "PE Chg OI": view["PE Chg OI"].round(0).astype("int64"),
        "PE IV": view["PE IV"].round(1),
        "PE Delta": view["PE Delta"].round(3),
        "PE PoP": view["PE PoP"].round(1),
    })
    display["_distance"] = (display["Strike"] - spot).abs()
    display = display.sort_values("_distance").drop(columns="_distance").head(15)

    def style_chain(row):
        styles = ["" for _ in row.index]
        strike = row["Strike"]
        if strike == int(round(atm_strike)):
            styles = ["font-weight:700;" for _ in row.index]
        if best_plan and strike == int(round(best_plan["strike"])):
            styles = ["font-weight:800;" for _ in row.index]
        return styles

    styled_chain = display.style.apply(style_chain, axis=1)
    st.dataframe(styled_chain, use_container_width=True, hide_index=True, height=520)
    st.caption("ATM and selected strikes are emphasized. All original CE/PE LTP, OI, Change OI, IV, Delta and PoP fields remain available.")

with tab3:
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("EMA 20", fmt_price(daily_tech["ema20"]))
    a2.metric("EMA 50", fmt_price(daily_tech["ema50"]))
    a3.metric("ATR 14", fmt_price(daily_tech["atr"]))
    a4.metric("5m VWAP", fmt_price(tf5["vwap"]))

    st.markdown("### Multi-Timeframe Confirmation")
    mtf = pd.DataFrame([
        {"Timeframe": "5 Minute", "Trend": tf5["trend"], "RSI": round(tf5["rsi"], 1), "ADX": round(tf5["adx"], 1), "Momentum %": round(tf5["momentum"], 2), "VWAP": fmt_price(tf5["vwap"])},
        {"Timeframe": "30 Minute", "Trend": tf30["trend"], "RSI": round(tf30["rsi"], 1), "ADX": round(tf30["adx"], 1), "Momentum %": round(tf30["momentum"], 2), "VWAP": fmt_price(tf30["vwap"])},
        {"Timeframe": "Daily", "Trend": daily_tech["trend"], "RSI": round(daily_tech["rsi"], 1), "ADX": round(daily_tech["adx"], 1), "Momentum %": round(daily_tech["momentum"], 2), "VWAP": fmt_price(daily_tech["vwap"])},
    ])
    st.dataframe(mtf, use_container_width=True, hide_index=True)

    left, right = st.columns(2)
    with left:
        st.markdown("### 🟢 Support / Put OI")
        st.write(f"Major support from Put OI: **{fmt_price(support)}**")
        if put_row is not None:
            st.write(f"Put OI: **{fmt_num(put_row['PE OI'])}**")
            st.write(f"Put Chg OI: **{fmt_num(put_row['PE Chg OI'])}**")
    with right:
        st.markdown("### 🔴 Resistance / Call OI")
        st.write(f"Major resistance from Call OI: **{fmt_price(resistance)}**")
        if call_row is not None:
            st.write(f"Call OI: **{fmt_num(call_row['CE OI'])}**")
            st.write(f"Call Chg OI: **{fmt_num(call_row['CE Chg OI'])}**")

    if not candles.empty:
        chart = candles.set_index("timestamp")[["close"]].tail(80)
        st.line_chart(chart, use_container_width=True)

with tab4:
    st.markdown("### Live-data decision framework")
    st.markdown("""
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

**5. Quality gate**
- Minimum setup score: 72/100
- At least 2 of 3 timeframes must agree
- VWAP must confirm the intraday direction
- Short-term trend conflict blocks the trade
- Delta, OI, tiered liquidity and bid/ask spread are checked
- Upstox PoP must be at least 55%
- The underlying breakout requires 5m trend/momentum confirmation
- A close OI wall can block a setup even when PoP is high
- The engine can return **WAIT FOR TRIGGER**, **WAIT FOR CONFIRMATION** or **NO TRADE**
- The score is a rule-based quality measure, not a backtested win rate or guarantee of profit.
""")

st.divider()

st.caption(
    f"Live Upstox snapshot • {symbol} • Expiry {selected_expiry} • "
    f"Updated {updated}. "
    "For educational/decision-support use; review live market conditions before trading."
)
