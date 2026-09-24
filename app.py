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
.topbar-title {font-size:30px;font-weight:800;}
.topbar-sub {font-size:16px;opacity:.82;margin-top:3px;}
.status-pill {
    display:inline-block;padding:7px 12px;border-radius:20px;
    background:#1f9d55;color:white;font-size:15px;font-weight:700;
}
.card {
    background:white;border:1px solid #e7ebf0;border-radius:14px;
    padding:18px;margin-bottom:16px;box-shadow:0 2px 8px rgba(16,42,67,.04);
}
.section-title {font-size:23px;font-weight:800;color:#182230;margin-bottom:12px;}
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
    color:#fff;padding:10px 16px;border-radius:9px;font-size:16px;
    font-weight:800;letter-spacing:.2px;text-align:center;white-space:nowrap;
}
.header-live { background:rgba(255,255,255,.14); }
.live-block { background:#16a34a; }
.closed-block { background:#dc2626; }
.hero-price {font-size:32px;font-weight:850;line-height:1.05;color:#182230;}
.section-heading {
    font-size:22px;font-weight:850;color:#182230;margin:20px 0 10px;
    letter-spacing:.15px;
}
.metric-card,.entry-card {
    background:#fff;border:1px solid #e7ebf0;border-radius:13px;
    padding:15px 14px;min-height:105px;box-shadow:0 2px 8px rgba(16,42,67,.035);
}
.metric-card span,.entry-card span,.decision-stats span,.status-grid span,
.option-grid span,.exit-rule span {
    display:block;font-size:13px;font-weight:800;color:#667085;letter-spacing:.55px;
}
.metric-card b,.entry-card b {display:block;font-size:23px;color:#182230;margin-top:8px;line-height:1.15;}
.metric-card small,.entry-card small {display:block;color:#98a2b3;font-size:13px;margin-top:7px;}
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
.decision-main {font-size:35px;font-weight:900;text-align:center;line-height:1.1;}
.decision-call .decision-main {color:#147a3d;}.decision-put .decision-main {color:#b4232f;}.decision-neutral .decision-main {color:#475467;}
.decision-sub {text-align:center;color:#667085;margin:9px 0 20px;font-size:16px;}
.decision-stats {display:grid;grid-template-columns:repeat(4,1fr);gap:10px;}
.decision-stats>div {background:rgba(255,255,255,.78);border:1px solid #edf0f3;border-radius:10px;padding:11px;text-align:center;}
.decision-stats b {display:block;font-size:22px;margin-top:5px;color:#182230;}
.decision-stats .decision-value {display:block;font-size:22px;font-weight:800;margin-top:5px;color:#182230;}
.decision-stats .decision-value span {display:inline;font-size:14px;font-weight:600;color:#98a2b3;margin-left:3px;}
.status-panel {border-radius:14px;padding:18px 20px;border:1px solid #e4e7ec;background:#fff;box-shadow:0 2px 8px rgba(16,42,67,.035);}
.status-green {border-color:#bde5c9;background:#f4fbf6;}.status-yellow {border-color:#f1d79b;background:#fffbf1;}.status-red {border-color:#f2c5c8;background:#fff6f6;}.status-grey {border-color:#dfe3e8;background:#f8fafc;}
.status-title {font-size:25px;font-weight:900;text-align:center;margin-bottom:15px;}
.status-green .status-title{color:#147a3d}.status-yellow .status-title{color:#9a6700}.status-red .status-title{color:#b4232f}.status-grey .status-title{color:#475467}
.status-grid {display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}
.status-grid>div {background:#fff;border:1px solid #e8ebef;border-radius:10px;padding:11px;text-align:center;}
.status-grid b {display:block;font-size:21px;color:#182230;margin-top:5px;}
.status-note {margin-top:12px;text-align:center;color:#667085;font-size:15px;line-height:1.5;}
.check-card {background:#fff;border:1px solid #e7ebf0;border-radius:14px;padding:8px 18px;box-shadow:0 2px 8px rgba(16,42,67,.035);}
.check-row {display:grid;grid-template-columns:1.35fr .8fr 2fr;align-items:center;gap:10px;padding:12px 3px;border-bottom:1px solid #eef0f2;}
.check-row>span {font-weight:750;color:#344054;font-size:16px;}.check-row small {color:#98a2b3;font-size:14px;}.check-pass{color:#147a3d}.check-wait{color:#9a6700}.check-fail{color:#b4232f}
.check-total {display:flex;justify-content:space-between;align-items:center;padding:13px 3px 7px;font-size:15px;font-weight:850;color:#667085;}.check-total b{font-size:21px;color:#182230;}
.option-card {border:1px solid #e5e7eb;border-radius:15px;background:#fff;padding:17px;box-shadow:0 2px 9px rgba(16,42,67,.035);}
.option-call {border-top:4px solid #16a34a;}.option-put {border-top:4px solid #dc2626;}.option-selected{box-shadow:0 4px 16px rgba(16,42,67,.09);}
.option-head {display:flex;justify-content:space-between;align-items:center;font-size:19px;font-weight:900;color:#182230;}.option-call .option-head>span:first-child{color:#147a3d}.option-put .option-head>span:first-child{color:#b4232f}
.selected-tag {font-size:12px;background:#eef7f0;color:#147a3d;padding:5px 8px;border-radius:12px;letter-spacing:.4px;}
.option-strike {font-size:27px;font-weight:900;color:#182230;margin:8px 0 14px;}.option-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;}.option-grid>div{background:#f8fafc;border-radius:9px;padding:9px;}.option-grid b{display:block;font-size:17px;margin-top:5px;color:#182230;}
.option-readiness {margin-top:13px;border-radius:8px;text-align:center;padding:8px;font-size:14px;font-weight:900;letter-spacing:.4px;}.option-readiness.status-green{color:#147a3d}.option-readiness.status-yellow{color:#9a6700}.option-readiness.status-red{color:#b4232f}.option-readiness.status-grey{color:#475467}
.option-empty {padding:28px 5px;color:#98a2b3;text-align:center;font-size:16px;}.option-muted{border-top:4px solid #98a2b3;}
.exit-rule {background:#f8fafc;border:1px solid #e7ebf0;border-radius:11px;padding:13px 15px;margin-top:12px;}.exit-rule b{display:block;color:#344054;font-size:15px;margin-top:5px;line-height:1.5;}
.why-card {background:#fff;border:1px solid #e7ebf0;border-radius:14px;padding:7px 18px;box-shadow:0 2px 8px rgba(16,42,67,.035);}.why-item{padding:10px 3px;border-bottom:1px solid #eef0f2;color:#344054;font-size:15px;}.why-item:last-child{border-bottom:0}.why-warning{color:#9a6700;background:#fffbf1;border-radius:7px;padding-left:9px;padding-right:9px;margin:5px 0;}
.sr-map {display:grid;grid-template-columns:1fr 1.15fr 1fr;align-items:stretch;gap:0;background:#fff;border:1px solid #e7ebf0;border-radius:15px;overflow:hidden;box-shadow:0 2px 8px rgba(16,42,67,.035);min-height:150px;}.sr-side{display:flex;flex-direction:column;justify-content:center;align-items:center;padding:18px;text-align:center;}.sr-side span{font-size:13px;font-weight:900;letter-spacing:.4px}.sr-side b{font-size:28px;margin:7px 0;color:#182230}.sr-side small{color:#667085;font-size:14px}.sr-resistance{background:#fff7f7}.sr-resistance span{color:#b4232f}.sr-support{background:#f4fbf6}.sr-support span{color:#147a3d}.sr-line{display:flex;flex-direction:column;justify-content:center;align-items:center;gap:8px;background:#fff;border-left:1px dashed #dfe3e8;border-right:1px dashed #dfe3e8;}.room-label{font-size:14px;color:#98a2b3;font-weight:700}.current-marker{font-size:20px;font-weight:900;color:#182230;background:#f2f4f7;border:1px solid #e1e5ea;border-radius:20px;padding:8px 14px}.current-marker span{font-size:12px;color:#667085;margin-left:5px;letter-spacing:.4px;}
.tab-alert{border-radius:12px;padding:14px 16px;margin-bottom:16px;line-height:1.55;font-size:15px;}.tab-positive{background:#f4fbf6;border:1px solid #bde5c9;color:#147a3d}.tab-danger{background:#fff6f6;border:1px solid #f2c5c8;color:#b4232f}
@media (max-width:900px){.decision-stats,.status-grid{grid-template-columns:repeat(2,1fr)}.option-grid{grid-template-columns:repeat(2,1fr)}.sr-map{grid-template-columns:1fr}.sr-line{padding:15px;border-top:1px dashed #dfe3e8;border-bottom:1px dashed #dfe3e8}.topbar-dashboard{align-items:flex-start}.header-live{display:none}}
@media (max-width:600px){.block-container{padding-left:.7rem;padding-right:.7rem}.decision-main{font-size:28px}.check-row{grid-template-columns:1fr .9fr}.check-row small{grid-column:1 / -1}.metric-card,.entry-card{min-height:95px}.option-grid{grid-template-columns:repeat(2,1fr)}}

/* ============================================================
   COLOR CLARITY UPGRADE — UI ONLY
   ============================================================ */
.stApp { background:linear-gradient(180deg,#f3f7fb 0%,#eef3f8 100%); }
.topbar-dashboard { background:linear-gradient(105deg,#0b1f3a 0%,#123f67 55%,#176b87 100%); box-shadow:0 8px 24px rgba(11,31,58,.16); }
.section-heading { color:#12395b; border-left:5px solid #1f8a9e; padding-left:10px; }
.metric-card { position:relative; overflow:hidden; border-top:4px solid #5b8def; background:linear-gradient(180deg,#ffffff,#f8fbff); }
.metric-card:nth-child(1) { border-top-color:#2563eb; }
.metric-card:nth-child(2) { border-top-color:#7c3aed; }
.metric-card:nth-child(3) { border-top-color:#0891b2; }
.metric-card:nth-child(4) { border-top-color:#16a34a; }
.metric-card:nth-child(5) { border-top-color:#dc2626; }
.metric-card:nth-child(6) { border-top-color:#f59e0b; }
.metric-card span { color:#52657a; }
.metric-card b { color:#102a43; }
.decision-card { border:2px solid #cbd5e1; box-shadow:0 8px 24px rgba(16,42,67,.08); }
.decision-call { background:linear-gradient(135deg,#ecfdf3,#f8fffb); border-color:#4ade80; }
.decision-call .decision-main { color:#087f3e; }
.decision-put { background:linear-gradient(135deg,#fff1f2,#fffafb); border-color:#fb7185; }
.decision-put .decision-main { color:#c81e3a; }
.decision-neutral { background:linear-gradient(135deg,#f8fafc,#eef2f7); border-color:#94a3b8; }
.decision-neutral .decision-main { color:#475569; }
.decision-stats>div { background:#fff; box-shadow:0 2px 8px rgba(15,23,42,.05); }
.decision-stats>div:nth-child(1) { border-top:3px solid #2563eb; }
.decision-stats>div:nth-child(2) { border-top:3px solid #16a34a; }
.decision-stats>div:nth-child(3) { border-top:3px solid #f59e0b; }
.decision-stats>div:nth-child(4) { border-top:3px solid #8b5cf6; }
.status-panel { box-shadow:0 5px 18px rgba(16,42,67,.06); }
.status-green { background:#ecfdf3; border-color:#4ade80; }
.status-yellow { background:#fffbeb; border-color:#fbbf24; }
.status-red { background:#fff1f2; border-color:#fb7185; }
.status-grey { background:#f1f5f9; border-color:#94a3b8; }
.check-pass { color:#087f3e; font-weight:800; }
.check-wait { color:#b45309; font-weight:800; }
.check-fail { color:#c81e3a; font-weight:800; }
.option-call { border-top:5px solid #16a34a; background:linear-gradient(180deg,#f0fdf4,#ffffff); }
.option-put { border-top:5px solid #dc2626; background:linear-gradient(180deg,#fff1f2,#ffffff); }
.option-selected { box-shadow:0 8px 22px rgba(15,23,42,.10); transform:translateY(-1px); }
.selected-tag { background:#dcfce7; color:#087f3e; border:1px solid #86efac; }
.option-readiness.status-green { background:#dcfce7; border:1px solid #86efac; }
.option-readiness.status-yellow { background:#fef3c7; border:1px solid #fbbf24; }
.option-readiness.status-red { background:#ffe4e6; border:1px solid #fb7185; }
.option-readiness.status-grey { background:#e2e8f0; border:1px solid #94a3b8; }
.option-grid>div { background:#f1f5f9; border:1px solid #e2e8f0; }
.sr-resistance { background:linear-gradient(180deg,#fff1f2,#fff); }
.sr-support { background:linear-gradient(180deg,#ecfdf3,#fff); }
.current-marker { background:#e0f2fe; border-color:#7dd3fc; color:#075985; }
.why-warning { background:#fffbeb; border-left:4px solid #f59e0b; }
.exit-rule { background:#eff6ff; border-color:#bfdbfe; }
.tab-positive { background:#ecfdf3; border-color:#86efac; }
.tab-danger { background:#fff1f2; border-color:#fb7185; }
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


def pct_change_from_entry(price, entry):
    """Return raw percentage change of a trade-plan level versus entry."""
    p = safe_float(price)
    e = safe_float(entry)
    if not np.isfinite(p) or not np.isfinite(e) or e == 0:
        return "—"
    pct = (p - e) / e * 100
    if abs(pct) < 0.005:
        pct = 0.0
    return f"{pct:+.2f}% from Entry" if pct != 0 else "0.00% from Entry"


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
    """Trend, volatility, candle-quality and entry-timing features for one timeframe."""
    if df.empty or len(df) < 20:
        return {
            "rsi": 50.0, "ema20": spot, "ema50": spot, "atr": spot * 0.01,
            "trend": "Unavailable", "adx": 0.0, "momentum": 0.0,
            "volume_ratio": 1.0, "vwap": spot, "recent_high": spot,
            "recent_low": spot, "body_strength": 0.0, "close_location": 0.5,
            "breakout_up": False, "breakout_down": False, "volatility_pct": 1.0,
        }

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    open_ = df["open"].astype(float)
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

    bullish = spot > e20 > e50
    bearish = spot < e20 < e50
    if bullish: trend = "Bullish"
    elif bearish: trend = "Bearish"
    else: trend = "Sideways"

    recent_high = safe_float(high.iloc[-11:-1].max(), spot) if len(high) > 11 else spot
    recent_low = safe_float(low.iloc[-11:-1].min(), spot) if len(low) > 11 else spot
    last_range = max(safe_float(high.iloc[-1]) - safe_float(low.iloc[-1]), 0.0)
    last_body = abs(safe_float(close.iloc[-1]) - safe_float(open_.iloc[-1]))
    body_strength = last_body / max(last_range, a * 0.10, 0.0001)
    close_location = (safe_float(close.iloc[-1]) - safe_float(low.iloc[-1])) / max(last_range, 0.0001)
    breakout_up = bool(close.iloc[-1] > recent_high + max(a * 0.05, spot * 0.0005))
    breakout_down = bool(close.iloc[-1] < recent_low - max(a * 0.05, spot * 0.0005))
    volatility_pct = a / max(spot, 1) * 100

    return {
        "rsi": r, "ema20": e20, "ema50": e50, "atr": max(a, spot*0.001),
        "trend": trend, "adx": adx_v, "momentum": momentum,
        "volume_ratio": volume_ratio, "vwap": latest_vwap,
        "recent_high": recent_high, "recent_low": recent_low,
        "body_strength": float(np.clip(body_strength, 0, 1.5)),
        "close_location": float(np.clip(close_location, 0, 1)),
        "breakout_up": breakout_up, "breakout_down": breakout_down,
        "volatility_pct": volatility_pct,
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
    """Normalize the Upstox option chain while preserving all useful Greeks/depth."""
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
            "CE Bid Qty": safe_float(call_market.get("bid_qty"), 0),
            "CE Ask Qty": safe_float(call_market.get("ask_qty"), 0),
            "CE Prev Close": safe_float(call_market.get("close_price")),
            "CE OI": call_oi,
            "CE Chg OI": call_oi - call_prev_oi,
            "CE Volume": safe_float(call_market.get("volume"), 0),
            "CE IV": safe_float(call_greeks.get("iv")),
            "CE Delta": safe_float(call_greeks.get("delta")),
            "CE Gamma": safe_float(call_greeks.get("gamma")),
            "CE Theta": safe_float(call_greeks.get("theta")),
            "CE Vega": safe_float(call_greeks.get("vega")),
            "CE PoP": safe_float(call_greeks.get("pop")),
            "PE Key": put.get("instrument_key"),
            "PE LTP": safe_float(put_market.get("ltp")),
            "PE Bid": safe_float(put_market.get("bid_price")),
            "PE Ask": safe_float(put_market.get("ask_price")),
            "PE Bid Qty": safe_float(put_market.get("bid_qty"), 0),
            "PE Ask Qty": safe_float(put_market.get("ask_qty"), 0),
            "PE Prev Close": safe_float(put_market.get("close_price")),
            "PE OI": put_oi,
            "PE Chg OI": put_oi - put_prev_oi,
            "PE Volume": safe_float(put_market.get("volume"), 0),
            "PE IV": safe_float(put_greeks.get("iv")),
            "PE Delta": safe_float(put_greeks.get("delta")),
            "PE Gamma": safe_float(put_greeks.get("gamma")),
            "PE Theta": safe_float(put_greeks.get("theta")),
            "PE Vega": safe_float(put_greeks.get("vega")),
            "PE PoP": safe_float(put_greeks.get("pop")),
        })
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values("Strike").reset_index(drop=True)


def _pct_distance(a, b):
    a, b = safe_float(a), safe_float(b)
    if not np.isfinite(a) or not np.isfinite(b) or b == 0:
        return np.nan
    return abs(a - b) / abs(b) * 100


def market_regime(tf5, tf30, daily, spot):
    """Classify the current environment without changing the visible UI."""
    trends = [tf5.get("trend"), tf30.get("trend"), daily.get("trend")]
    adx5 = safe_float(tf5.get("adx"), 0)
    adx30 = safe_float(tf30.get("adx"), 0)
    atr_pct = safe_float(tf5.get("atr"), spot * 0.01) / max(spot, 1) * 100
    momentum = safe_float(tf5.get("momentum"), 0)
    breakout_up = bool(tf5.get("breakout_up"))
    breakout_down = bool(tf5.get("breakout_down"))

    if breakout_up and momentum > 0:
        regime = "BREAKOUT"
    elif breakout_down and momentum < 0:
        regime = "BREAKDOWN"
    elif atr_pct >= 1.5 or adx5 >= 32:
        regime = "HIGH VOLATILITY"
    elif adx5 < 17 and adx30 < 20 and len(set([t for t in trends if t])) <= 2:
        regime = "RANGE"
    elif trends.count("Bullish") >= 2:
        regime = "TRENDING UP"
    elif trends.count("Bearish") >= 2:
        regime = "TRENDING DOWN"
    else:
        regime = "MIXED"
    return regime


def oi_levels(chain, spot):
    """Build support/resistance plus OI behaviour and wall strength."""
    valid = chain.dropna(subset=["Strike"]).copy()
    if valid.empty or not np.isfinite(spot):
        return spot, spot, np.nan, {
            "put_walls": [], "call_walls": [], "major_support": spot,
            "major_resistance": spot, "nearest_support": spot,
            "nearest_resistance": spot, "support_strength": 0,
            "resistance_strength": 0, "ce_behavior": "Unknown", "pe_behavior": "Unknown",
        }

    band = valid[(valid["Strike"] >= spot * 0.90) & (valid["Strike"] <= spot * 1.10)].copy()
    if band.empty:
        band = valid.copy()
    for c in ["PE OI", "CE OI", "PE Chg OI", "CE Chg OI", "PE LTP", "CE LTP"]:
        band[c] = pd.to_numeric(band[c], errors="coerce").fillna(0)

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

    # Relative wall strength prevents a tiny OI spike from being treated as a major barrier.
    put_max = max(float(band["PE OI"].max()), 1.0)
    call_max = max(float(band["CE OI"].max()), 1.0)
    support_strength = float(np.clip(support_row["PE OI"] / put_max * 100, 0, 100))
    resistance_strength = float(np.clip(resistance_row["CE OI"] / call_max * 100, 0, 100))

    # OI behaviour is directional context, not proof of writing/unwinding.
    def behaviour(oi, chg, ltp, prev_oi):
        if chg > 0 and ltp <= 0:
            return "OI BUILDUP"
        if chg > 0:
            return "OI BUILDUP"
        if chg < 0:
            return "OI UNWINDING"
        return "NEUTRAL"

    ce_behavior = behaviour(resistance_row["CE OI"], resistance_row["CE Chg OI"], resistance_row.get("CE LTP", 0), 0)
    pe_behavior = behaviour(support_row["PE OI"], support_row["PE Chg OI"], support_row.get("PE LTP", 0), 0)

    return major_support, major_resistance, pcr, {
        "put_walls": put_walls, "call_walls": call_walls,
        "major_support": major_support, "major_resistance": major_resistance,
        "nearest_support": nearest_support, "nearest_resistance": nearest_resistance,
        "support_room_pct": max((spot - major_support) / max(spot, 1) * 100, 0),
        "resistance_room_pct": max((major_resistance - spot) / max(spot, 1) * 100, 0),
        "support_strength": support_strength, "resistance_strength": resistance_strength,
        "ce_behavior": ce_behavior, "pe_behavior": pe_behavior,
        "support_chg_oi": safe_float(support_row.get("PE Chg OI"), 0),
        "resistance_chg_oi": safe_float(resistance_row.get("CE Chg OI"), 0),
    }


def nearest_row(chain, strike):
    if chain.empty or not np.isfinite(strike):
        return None
    index = (chain["Strike"] - strike).abs().idxmin()
    return chain.loc[index]



def oi_price_behavior(row, prefix):
    """Classify price/OI interaction using the current option snapshot.

    The labels are context only. Because prev_oi/close_price are session-reference
    fields, they are not treated as proof of intraday institutional activity.
    """
    ltp = safe_float(row.get(f"{prefix} LTP"))
    prev_close = safe_float(row.get(f"{prefix} Prev Close"))
    chg_oi = safe_float(row.get(f"{prefix} Chg OI"), 0)
    if not np.isfinite(ltp) or not np.isfinite(prev_close) or prev_close <= 0:
        return "UNKNOWN"
    price_up = ltp > prev_close * 1.002
    price_down = ltp < prev_close * 0.998
    if price_up and chg_oi > 0: return "LONG BUILDUP"
    if price_down and chg_oi > 0: return "SHORT BUILDUP"
    if price_up and chg_oi < 0: return "SHORT COVERING"
    if price_down and chg_oi < 0: return "LONG UNWINDING"
    return "NEUTRAL"

def score_option(row, side, spot, pcr, tf5, tf30, daily, chain,
                 support=None, resistance=None, oi_wall_info=None, regime="MIXED",
                 mode="BUY"):
    """Realistic 0-100 setup-quality score.

    The score is deliberately calibrated as a quality grade, not a probability.
    It uses bounded component scores and explicit conflict penalties so a setup
    cannot reach the high 90s merely because several indicators agree.
    """
    prefix = "CE" if side == "CE" else "PE"
    premium = safe_float(row[f"{prefix} LTP"])
    delta = safe_float(row[f"{prefix} Delta"])
    iv = safe_float(row[f"{prefix} IV"])
    gamma = safe_float(row[f"{prefix} Gamma"])
    theta = safe_float(row[f"{prefix} Theta"])
    vega = safe_float(row[f"{prefix} Vega"])
    pop = safe_float(row[f"{prefix} PoP"])
    chg_oi = safe_float(row[f"{prefix} Chg OI"], 0)
    oi_behavior = oi_price_behavior(row, prefix)
    volume = safe_float(row[f"{prefix} Volume"], 0)
    oi = safe_float(row[f"{prefix} OI"], 0)
    bid = safe_float(row[f"{prefix} Bid"])
    ask = safe_float(row[f"{prefix} Ask"])
    bid_qty = safe_float(row[f"{prefix} Bid Qty"], 0)
    ask_qty = safe_float(row[f"{prefix} Ask Qty"], 0)

    is_sell = mode == "SELL"
    desired = ("Bearish" if side == "CE" else "Bullish") if is_sell else ("Bullish" if side == "CE" else "Bearish")
    opposite = "Bullish" if desired == "Bearish" else "Bearish"
    tf_points_raw, alignment = timeframe_score("PE" if is_sell and side == "CE" else "CE" if is_sell and side == "PE" else side, tf5, tf30, daily)
    trends = [tf5.get("trend"), tf30.get("trend"), daily.get("trend")]

    # 1) Multi-timeframe structure.
    trend_points = 0.0
    for trend in trends:
        if trend == desired:
            trend_points += 8.0
        elif trend == "Sideways":
            trend_points += 3.0
        elif trend == opposite:
            trend_points -= 7.0
    trend_points = float(np.clip(trend_points, 0, 24))

    # 2) Intraday momentum / RSI.
    momentum = safe_float(tf5.get("momentum"), 0)
    rsi = safe_float(tf5.get("rsi"), 50)
    momentum_points = 0.0
    if tf5.get("trend") == desired:
        momentum_points += 5
    if (not is_sell and side == "CE") or (is_sell and side == "PE"):
        if 52 <= rsi <= 68: momentum_points += 4
        elif 68 < rsi <= 72: momentum_points += 2
        if momentum > 0: momentum_points += 4
    else:
        if 32 <= rsi <= 48: momentum_points += 4
        elif 28 <= rsi < 32: momentum_points += 2
        if momentum < 0: momentum_points += 4
    if safe_float(tf5.get("adx"), 0) >= 25:
        momentum_points += 2
    momentum_points = float(np.clip(momentum_points, 0, 15))

    # 3) VWAP alignment.
    vwap = safe_float(tf5.get("vwap"), spot)
    vwap_gap_pct = (spot - vwap) / max(spot, 1) * 100 if np.isfinite(vwap) else 0
    vwap_points = 0.0
    if (not is_sell and side == "CE") or (is_sell and side == "PE"):
        if spot > vwap and momentum > 0: vwap_points = 10
        elif spot > vwap: vwap_points = 7
        elif spot >= vwap * 0.998: vwap_points = 3
    else:
        if spot < vwap and momentum < 0: vwap_points = 10
        elif spot < vwap: vwap_points = 7
        elif spot <= vwap * 1.002: vwap_points = 3

    # 4) Regime fit. A breakout is good for directional BUYs but risky for
    # short-premium SELLs, even when the underlying direction is favorable.
    regime_points = 0.0
    if is_sell:
        if regime == "RANGE": regime_points = 12
        elif side == "CE" and regime in {"TRENDING DOWN", "BREAKDOWN"}: regime_points = 12
        elif side == "PE" and regime in {"TRENDING UP", "BREAKOUT"}: regime_points = 8
        elif regime in {"TRENDING UP", "TRENDING DOWN"}: regime_points = 6
        elif regime in {"BREAKOUT", "BREAKDOWN"}: regime_points = 0
        elif regime == "HIGH VOLATILITY": regime_points = 2
    else:
        if side == "CE" and regime in {"TRENDING UP", "BREAKOUT"}: regime_points = 10
        elif side == "PE" and regime in {"TRENDING DOWN", "BREAKDOWN"}: regime_points = 10
        elif regime == "HIGH VOLATILITY": regime_points = 5
        elif regime == "RANGE": regime_points = 2

    # 5) OI structure.
    oi_points = 0.0
    wall_room = np.nan
    if oi_wall_info:
        if side == "CE":
            wall_room = (resistance - spot) / max(spot, 1) * 100
            wall_strength = safe_float(oi_wall_info.get("resistance_strength"), 0)
            wall_chg = safe_float(oi_wall_info.get("resistance_chg_oi"), 0)
        else:
            wall_room = (spot - support) / max(spot, 1) * 100
            wall_strength = safe_float(oi_wall_info.get("support_strength"), 0)
            wall_chg = safe_float(oi_wall_info.get("support_chg_oi"), 0)
        if wall_strength >= 70: oi_points += 6
        elif wall_strength >= 40: oi_points += 4
        elif wall_strength >= 20: oi_points += 2
        if is_sell:
            if wall_chg > 0: oi_points += 5
            elif wall_chg == 0: oi_points += 2
        else:
            if wall_chg > 0: oi_points += 4
            elif wall_chg < 0: oi_points += 2
    if oi_behavior in {"LONG BUILDUP", "SHORT BUILDUP"}:
        oi_points += 2
    elif oi_behavior in {"SHORT COVERING", "LONG UNWINDING"}:
        oi_points -= 1
    oi_points = float(np.clip(oi_points, 0, 15))

    # 6) Option liquidity / execution quality.
    abs_delta = abs(delta) if np.isfinite(delta) else np.nan
    spread_pct = (
        max(ask - bid, 0) / max((ask + bid) / 2, 0.01) * 100
        if np.isfinite(ask) and np.isfinite(bid) and ask > 0 and bid > 0 else 999
    )
    depth_ratio = min(bid_qty, ask_qty) / max(max(bid_qty, ask_qty), 1)
    liquidity_points = 0.0
    if spread_pct <= 1: liquidity_points += 5
    elif spread_pct <= 2: liquidity_points += 4
    elif spread_pct <= 3: liquidity_points += 2
    elif spread_pct <= 4: liquidity_points += 1
    if volume >= 10000: liquidity_points += 4
    elif volume >= 3000: liquidity_points += 3
    elif volume >= 1000: liquidity_points += 2
    elif volume >= 500: liquidity_points += 1
    if oi >= 10000: liquidity_points += 3
    elif oi >= 3000: liquidity_points += 2
    elif oi > 0: liquidity_points += 1
    if depth_ratio >= 0.50: liquidity_points += 3
    elif depth_ratio >= 0.25: liquidity_points += 2
    elif depth_ratio > 0: liquidity_points += 1
    liquidity_points = float(np.clip(liquidity_points, 0, 15))

    # 7) Strike location and room to the relevant OI wall.
    distance_pct = abs(float(row["Strike"]) - spot) / max(spot, 1) * 100
    strike_points = 5 if distance_pct <= 1 else 4 if distance_pct <= 2 else 2 if distance_pct <= 3 else 0
    room_points = 0
    if np.isfinite(wall_room):
        if wall_room >= 2.0: room_points = 6
        elif wall_room >= 1.25: room_points = 4
        elif wall_room >= 0.75: room_points = 2
        elif wall_room >= 0.50: room_points = 1
    room_quality = float(np.clip(strike_points + room_points, 0, 11))

    # 8) Greeks / IV context. This is deliberately small so Greeks cannot
    # manufacture a high score without underlying confirmation.
    greek_points = 0.0
    if np.isfinite(abs_delta):
        if is_sell:
            if 0.18 <= abs_delta <= 0.35: greek_points += 3
            elif 0.15 <= abs_delta <= 0.45: greek_points += 2
            elif 0.10 <= abs_delta <= 0.50: greek_points += 1
        else:
            if 0.45 <= abs_delta <= 0.65: greek_points += 3
            elif 0.35 <= abs_delta <= 0.75: greek_points += 2
            elif 0.30 <= abs_delta <= 0.80: greek_points += 1
    if np.isfinite(iv):
        if is_sell:
            if 20 <= iv <= 45: greek_points += 2
            elif 45 < iv <= 60: greek_points += 1
            elif iv < 12: greek_points -= 1
        else:
            if 20 <= iv <= 50: greek_points += 1
            elif iv >= 80: greek_points -= 2
    if np.isfinite(theta) and np.isfinite(premium) and premium > 0:
        theta_pct = abs(theta) / premium
        if is_sell and theta_pct > 0.02: greek_points += 1
        elif not is_sell and theta_pct > 0.15: greek_points -= 2
    greek_points = float(np.clip(greek_points, 0, 6))

    # PoP is intentionally capped at 4 points and never acts as a proxy for
    # strategy win probability.
    pop_points = float(np.clip((pop - 55) / 4.0, 0, 4)) if np.isfinite(pop) else 0

    # Explicit conflicts. These are applied after component scoring so one
    # strong feature cannot hide a structural contradiction.
    conflict_penalty = 0.0
    if tf5.get("trend") == opposite: conflict_penalty += 8
    if tf30.get("trend") == opposite and daily.get("trend") == opposite: conflict_penalty += 6
    if (not is_sell and side == "CE" and spot < vwap * 0.997) or (not is_sell and side == "PE" and spot > vwap * 1.003):
        conflict_penalty += 5
    if is_sell and regime in {"BREAKOUT", "BREAKDOWN"}: conflict_penalty += 8
    if spread_pct > 4: conflict_penalty += 8
    if not np.isfinite(abs_delta): conflict_penalty += 6

    # Base maximum before penalties is 100. The score is intentionally harder
    # to push above 90: 90+ means very strong confluence, not merely a good setup.
    raw = (trend_points + momentum_points + vwap_points + regime_points +
           oi_points + liquidity_points + room_quality + greek_points + pop_points)
    # Normalize against the theoretical component maximum instead of simply
    # clipping the raw sum. This prevents a setup from reaching 95-100 merely
    # because several components can each award points above the intended
    # 100-point scale.
    theoretical_max = 110.0 if not is_sell else 112.0
    score = float(np.clip((raw / theoretical_max) * 100.0 - conflict_penalty, 0, 100))

    return {
        "score": score, "premium": premium, "delta": delta, "iv": iv,
        "gamma": gamma, "theta": theta, "vega": vega, "pop": pop,
        "chg_oi": chg_oi, "oi_behavior": oi_behavior, "volume": volume, "oi": oi,
        "bid_qty": bid_qty, "ask_qty": ask_qty, "depth_ratio": depth_ratio,
        "spread_pct": spread_pct, "alignment": alignment, "distance_pct": distance_pct,
        "quality": liquidity_points, "vwap": vwap, "vwap_gap_pct": vwap_gap_pct,
        "room_pct": wall_room, "regime_points": regime_points,
        "greek_adjust": greek_points, "conflict_penalty": conflict_penalty,
        "trend_points": trend_points, "momentum_points": momentum_points,
        "vwap_points": vwap_points, "oi_points": oi_points,
        "liquidity_points": liquidity_points, "room_quality": room_quality,
        "greek_points": greek_points, "pop_points": pop_points,
    }

def adaptive_buy_levels(entry, side, spot, support, resistance, tf5, delta, iv, risk_profile):
    """Derive option levels from underlying ATR + Delta instead of fixed premium multiples."""
    atr = max(safe_float(tf5.get("atr"), spot * 0.01), spot * 0.001)
    abs_delta = max(abs(safe_float(delta, 0.50)), 0.25)
    risk_mult = {"Conservative": 0.55, "Balanced": 0.70, "Aggressive": 0.85}.get(risk_profile, 0.70)
    underlying_risk = atr * risk_mult
    # First-order premium sensitivity. Add a modest volatility cushion when IV is high.
    iv_factor = 1.0 + max(min((safe_float(iv, 20) - 25) / 200, 0.25), -0.05)
    premium_risk = max(entry * 0.12, underlying_risk * abs_delta * iv_factor)
    sl = max(entry - premium_risk, entry * 0.55)

    t1_risk = premium_risk * {"Conservative": 1.15, "Balanced": 1.30, "Aggressive": 1.45}.get(risk_profile, 1.30)
    t2_risk = premium_risk * {"Conservative": 1.70, "Balanced": 2.00, "Aggressive": 2.30}.get(risk_profile, 2.00)
    target1 = entry + t1_risk
    target2 = entry + t2_risk

    # Do not advertise an impossible target if the underlying barrier is extremely close.
    barrier = resistance if side == "CE" else support
    room = max((barrier - spot) if side == "CE" else (spot - barrier), 0)
    if room > 0 and room < atr * 0.80:
        target2 = min(target2, entry + premium_risk * 1.55)
    if target2 <= target1:
        target2 = target1 + max(entry * 0.08, premium_risk * 0.35)

    return round(sl, 2), round(target1, 2), round(target2, 2)


def build_plan(row, side, spot, support, resistance, pcr, tf5, tf30, daily,
               risk_profile, chain, oi_wall_info=None, regime="MIXED"):
    if row is None:
        return None
    scored = score_option(row, side, spot, pcr, tf5, tf30, daily, chain,
                          support=support, resistance=resistance,
                          oi_wall_info=oi_wall_info, regime=regime, mode="BUY")
    ask = safe_float(row[f"{side} Ask"])
    ltp = safe_float(row[f"{side} LTP"])
    entry = ask if np.isfinite(ask) and ask > 0 else ltp
    if not np.isfinite(entry) or entry <= 0:
        return None

    sl, target1, target2 = adaptive_buy_levels(entry, side, spot, support, resistance,
                                                tf5, scored["delta"], scored["iv"], risk_profile)
    rr1 = (target1 - entry) / max(entry - sl, 0.01)
    rr2 = (target2 - entry) / max(entry - sl, 0.01)

    atr = max(tf5.get("atr", spot * 0.01), spot * 0.001)
    trigger_buffer = max(atr * 0.12, spot * 0.001)
    recent_high = safe_float(tf5.get("recent_high"), resistance)
    recent_low = safe_float(tf5.get("recent_low"), support)
    body_strength = safe_float(tf5.get("body_strength"), 0)
    close_location = safe_float(tf5.get("close_location"), 0.5)
    volume_ratio = safe_float(tf5.get("volume_ratio"), 1.0)

    if side == "CE":
        trigger_level = max(resistance, recent_high) + trigger_buffer
        trigger_hit = spot >= trigger_level
        candle_confirmed = (
            tf5.get("trend") == "Bullish" and momentum_positive(tf5) and
            rsi_ok_for_breakout(tf5, "CE") and close_location >= 0.60 and body_strength >= 0.35
        )
        volume_confirmed = volume_ratio >= 1.05
        extension_pct = (spot - vwap_value(tf5, spot)) / max(spot, 1) * 100
        late_entry = extension_pct > max(1.8, atr / max(spot, 1) * 100 * 1.8)
        trigger = f"Enter only after spot breaks {fmt_price(trigger_level)} with a strong 5m close and volume confirmation."
        exit_rule = f"Exit if spot loses support {fmt_price(support)} or premium hits {fmt_price(sl)}. After Target 1, trail below the latest 5m swing low."
    else:
        trigger_level = min(support, recent_low) - trigger_buffer
        trigger_hit = spot <= trigger_level
        candle_confirmed = (
            tf5.get("trend") == "Bearish" and momentum_negative(tf5) and
            rsi_ok_for_breakout(tf5, "PE") and close_location <= 0.40 and body_strength >= 0.35
        )
        volume_confirmed = volume_ratio >= 1.05
        extension_pct = (vwap_value(tf5, spot) - spot) / max(spot, 1) * 100
        late_entry = extension_pct > max(1.8, atr / max(spot, 1) * 100 * 1.8)
        trigger = f"Enter only after spot breaks {fmt_price(trigger_level)} with a strong 5m close and volume confirmation."
        exit_rule = f"Exit if spot reclaims resistance {fmt_price(resistance)} or premium hits {fmt_price(sl)}. After Target 1, trail above the latest 5m swing high."

    hard_fail = []
    if tf5.get("trend") in {"Bearish" if side == "CE" else "Bullish"}:
        hard_fail.append("5m trend conflict")
    if scored["spread_pct"] > 3:
        hard_fail.append("wide option spread")
    if not np.isfinite(scored["delta"]) or not (0.30 <= abs(scored["delta"]) <= 0.80):
        hard_fail.append("poor delta")
    if scored["volume"] < 1000:
        hard_fail.append("weak option liquidity")
    if scored["oi"] <= 0:
        hard_fail.append("no option OI")
    vwap = vwap_value(tf5, spot)
    if side == "CE" and spot < vwap * 0.997:
        hard_fail.append("price below VWAP")
    if side == "PE" and spot > vwap * 1.003:
        hard_fail.append("price above VWAP")
    wall_room = (resistance - spot) / max(spot, 1) * 100 if side == "CE" else (spot - support) / max(spot, 1) * 100
    if wall_room < 0.50 and not trigger_hit:
        hard_fail.append("OI wall too close")
    if late_entry:
        hard_fail.append("late entry / overextended")
    if scored["conflict_penalty"] >= 12:
        hard_fail.append("multi-factor conflict")

    if not trigger_hit:
        readiness = "WAIT FOR TRIGGER"
    elif not candle_confirmed or not volume_confirmed:
        readiness = "WAIT FOR CONFIRMATION"
    elif late_entry:
        readiness = "LATE ENTRY"
    else:
        readiness = "READY"

    # A BUY quality score must also reflect entry risk. These penalties stop
    # strong directional indicators from producing an unrealistically high
    # score when the option is late, trapped near a wall, or has poor payoff.
    buy_risk_penalty = 0.0
    if late_entry:
        buy_risk_penalty += 8
    if wall_room < 0.75:
        buy_risk_penalty += 8
    elif wall_room < 1.00:
        buy_risk_penalty += 4
    if rr1 < 0.80:
        buy_risk_penalty += 5
    elif rr1 < 1.00:
        buy_risk_penalty += 2
    adjusted_score = float(np.clip(scored["score"] - buy_risk_penalty, 0, 100))

    return {
        "side": side, "strike": float(row["Strike"]), "entry": float(entry),
        "sl": sl, "target1": target1, "target2": target2,
        "pop": scored["pop"], "delta": scored["delta"], "iv": scored["iv"],
        "score": adjusted_score, "rr1": rr1, "rr2": rr2,
        "trigger": trigger, "trigger_level": trigger_level, "trigger_hit": trigger_hit,
        "candle_confirmed": candle_confirmed, "volume_confirmed": volume_confirmed,
        "readiness": readiness, "fail_reasons": hard_fail,
        "score_gate": scored["score"] >= 65, "watch_score_gate": scored["score"] >= 58,
        "alignment_gate": scored["alignment"] >= 2,
        "pop_ok": np.isfinite(scored["pop"]) and scored["pop"] >= 45,
        "strong_pop": np.isfinite(scored["pop"]) and scored["pop"] >= 55,
        "exit": exit_rule, "oi": scored["oi"], "chg_oi": scored["chg_oi"], "oi_behavior": scored["oi_behavior"],
        "volume": scored["volume"], "spread_pct": scored["spread_pct"],
        "alignment": scored["alignment"], "vwap": scored["vwap"],
        "room_pct": scored["room_pct"], "gamma": scored["gamma"],
        "theta": scored["theta"], "vega": scored["vega"],
        "regime": regime, "late_entry": late_entry, "risk_penalty": buy_risk_penalty,
    }


def vwap_value(tf, spot):
    return safe_float(tf.get("vwap"), spot)


def momentum_positive(tf):
    return safe_float(tf.get("momentum"), 0) > 0


def momentum_negative(tf):
    return safe_float(tf.get("momentum"), 0) < 0


def rsi_ok_for_breakout(tf, side):
    r = safe_float(tf.get("rsi"), 50)
    return 52 <= r <= 72 if side == "CE" else 28 <= r <= 48


def build_sell_plan(row, side, spot, support, resistance, pcr, tf5, tf30, daily,
                    risk_profile, chain, oi_wall_info=None, regime="MIXED"):
    """Build a premium-selling plan using the same calibrated quality framework.

    SELL scores are intentionally stricter than BUY scores. A high option PoP
    cannot compensate for a poor market regime, weak liquidity, close wall or
    unattractive risk/reward.
    """
    if row is None:
        return None
    prefix = "CE" if side == "CE" else "PE"
    ltp = safe_float(row[f"{prefix} LTP"])
    bid = safe_float(row[f"{prefix} Bid"])
    ask = safe_float(row[f"{prefix} Ask"])
    entry = bid if np.isfinite(bid) and bid > 0 else ltp
    if not np.isfinite(entry) or entry <= 0:
        return None

    scored = score_option(row, side, spot, pcr, tf5, tf30, daily, chain,
                          support=support, resistance=resistance,
                          oi_wall_info=oi_wall_info, regime=regime, mode="SELL")
    delta = scored["delta"]
    iv = scored["iv"]
    gamma = scored["gamma"]
    theta = scored["theta"]
    vega = scored["vega"]
    oi = scored["oi"]
    chg_oi = scored["chg_oi"]
    volume = scored["volume"]
    spread_pct = scored["spread_pct"]
    depth_ratio = scored["depth_ratio"]
    long_pop = safe_float(row[f"{prefix} PoP"])
    # Keep the legacy display meaning, but do not treat it as a measured win rate.
    short_pop = 100.0 - long_pop if np.isfinite(long_pop) else np.nan
    abs_delta = abs(delta) if np.isfinite(delta) else np.nan
    oi_behavior = scored["oi_behavior"]

    wall_room = ((resistance - spot) / max(spot, 1) * 100
                 if side == "CE" else
                 (spot - support) / max(spot, 1) * 100)

    # Adaptive seller risk.
    atr = max(safe_float(tf5.get("atr"), spot * 0.01), spot * 0.001)
    underlying_risk = atr * {"Conservative": 0.50, "Balanced": 0.65, "Aggressive": 0.80}.get(risk_profile, 0.65)
    premium_risk = max(
        entry * 0.18,
        underlying_risk * max(abs_delta if np.isfinite(abs_delta) else 0.20, 0.20)
        * (1 + max((safe_float(iv, 20) - 30) / 200, 0))
    )
    sl = round(entry + premium_risk, 2)
    target1 = round(max(entry - premium_risk * 0.90, entry * 0.45), 2)
    target2 = round(max(entry - premium_risk * 1.35, entry * 0.25), 2)
    if target2 >= target1:
        target2 = round(max(entry * 0.30, target1 - entry * 0.10), 2)

    rr1 = (entry - target1) / max(sl - entry, 0.01)
    rr2 = (entry - target2) / max(sl - entry, 0.01)

    # Seller-specific quality penalties. These are the main calibration change:
    # a setup with a near wall or poor T1 reward cannot remain in the 90s.
    risk_penalty = 0.0
    if wall_room < 0.75:
        risk_penalty += 18
    elif wall_room < 1.00:
        risk_penalty += 10
    elif wall_room < 1.50:
        risk_penalty += 5

    if rr1 < 0.75:
        risk_penalty += 8
    elif rr1 < 1.00:
        risk_penalty += 5
    if rr2 < 1.20:
        risk_penalty += 3

    if regime in {"BREAKOUT", "BREAKDOWN"}:
        risk_penalty += 8
    if spread_pct > 3:
        risk_penalty += 7
    if depth_ratio < 0.20:
        risk_penalty += 4
    if np.isfinite(abs_delta) and abs_delta > 0.45:
        risk_penalty += 5
    if np.isfinite(gamma) and gamma > 0 and np.isfinite(abs_delta) and abs_delta > 0.35:
        risk_penalty += 3

    score = float(np.clip(scored["score"] - risk_penalty, 0, 100))

    hard_fail = []
    if tf5.get("trend") == ("Bullish" if side == "CE" else "Bearish"):
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
    if side == "CE" and spot >= resistance:
        hard_fail.append("resistance breached")
    if side == "PE" and spot <= support:
        hard_fail.append("support breached")
    if wall_room < 0.75:
        hard_fail.append("insufficient room to wall")
    if regime in {"BREAKOUT", "BREAKDOWN"}:
        hard_fail.append("breakout regime unsuitable for short premium")
    if rr1 < 0.75:
        hard_fail.append("poor target 1 risk/reward")
    if score < 60:
        hard_fail.append("quality score below threshold")

    if side == "CE":
        trigger = f"Sell only while spot remains below {fmt_price(resistance)} and 5m shows rejection/weakness; avoid fresh shorts after a breakout."
        exit_rule = f"Exit if spot sustains above resistance {fmt_price(resistance)} or premium reaches {fmt_price(sl)}. Book profit progressively."
    else:
        trigger = f"Sell only while spot remains above {fmt_price(support)} and 5m shows rejection/strength; avoid fresh shorts after a breakdown."
        exit_rule = f"Exit if spot sustains below support {fmt_price(support)} or premium reaches {fmt_price(sl)}. Book profit progressively."

    readiness = "READY" if not hard_fail and score >= 65 and np.isfinite(short_pop) and short_pop >= 55 else "NO TRADE"
    return {
        "side": side, "strike": float(row["Strike"]),
        "action": "CALL SELL" if side == "CE" else "PUT SELL",
        "entry": entry, "sl": sl, "target1": target1, "target2": target2,
        "pop": short_pop, "long_pop": long_pop, "delta": delta, "iv": iv,
        "oi_behavior": oi_behavior, "gamma": gamma, "theta": theta, "vega": vega,
        "score": score, "rr1": rr1, "rr2": rr2,
        "trigger": trigger, "trigger_level": resistance if side == "CE" else support,
        "trigger_hit": not hard_fail, "fail_reasons": hard_fail,
        "oi": oi, "chg_oi": chg_oi, "volume": volume, "spread_pct": spread_pct,
        "alignment": scored["alignment"], "vwap": scored["vwap"], "room_pct": wall_room,
        "readiness": readiness, "exit": exit_rule, "regime": regime,
        "depth_ratio": depth_ratio, "risk_penalty": risk_penalty,
    }


# ============================================================
# BACKEND QUALITY / LOGGING HELPERS — NO UI CHANGES
# ============================================================
def _signal_log_path():
    return "/tmp/fo_pro_trader_signal_log.csv"


def log_signal(symbol, expiry, decision, plan, spot, pcr, support, resistance, tf5, tf30, daily, regime):
    """Append selected signals for objective forward testing. No UI is changed."""
    if not plan or decision == "NO TRADE":
        return
    try:
        row = {
            "timestamp": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(),
            "symbol": symbol, "expiry": expiry, "decision": decision,
            "spot": spot, "strike": plan.get("strike"), "pop": plan.get("pop"),
            "score": plan.get("score"), "entry": plan.get("entry"), "sl": plan.get("sl"),
            "target1": plan.get("target1"), "target2": plan.get("target2"),
            "delta": plan.get("delta"), "iv": plan.get("iv"),
            "gamma": plan.get("gamma"), "theta": plan.get("theta"), "vega": plan.get("vega"),
            "pcr": pcr, "support": support, "resistance": resistance,
            "vwap": tf5.get("vwap"), "trend5": tf5.get("trend"),
            "trend30": tf30.get("trend"), "trend_daily": daily.get("trend"),
            "regime": regime,
        }
        df = pd.DataFrame([row])
        path = _signal_log_path()
        if __import__("os").path.exists(path):
            df.to_csv(path, mode="a", header=False, index=False)
        else:
            df.to_csv(path, index=False)
    except Exception:
        pass


# ============================================================
# FULL F&O TRADE ALERT SCANNER — USES THIS FILE'S EXISTING ENGINE
# ============================================================

FNO_MASTER_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"


@st.cache_data(ttl=3600, show_spinner=False)
def get_fno_underlyings():
    """Build current NSE equity F&O universe from Upstox BOD master."""
    try:
        response = requests.get(FNO_MASTER_URL, timeout=30)
        response.raise_for_status()
        raw = gzip.decompress(response.content)
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise UpstoxError(
            f"Unable to load the Upstox NSE F&O instrument list: {exc}"
        ) from exc

    records = payload.get("data", payload.get("instruments", [])) if isinstance(payload, dict) else payload
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

        expiry_raw = str(item.get("expiry", "")).strip()
        underlying_key = item.get("underlying_key")
        symbol = str(item.get("underlying_symbol") or "").strip().upper()
        if not expiry_raw or not underlying_key or not symbol:
            continue

        if expiry_raw.isdigit():
            try:
                expiry_date = datetime.fromtimestamp(
                    int(expiry_raw) / 1000,
                    tz=ZoneInfo("Asia/Kolkata")
                ).date().isoformat()
            except Exception:
                continue
        else:
            expiry_date = expiry_raw[:10]

        if expiry_date < today:
            continue

        current = universe.get(underlying_key)
        if current is None or expiry_date < current["expiry"]:
            universe[underlying_key] = {
                "symbol": symbol,
                "underlying_key": underlying_key,
                "expiry": expiry_date,
            }

    return sorted(universe.values(), key=lambda x: x["symbol"])


@st.cache_data(ttl=45, show_spinner=False)
def get_scanner_chain(underlying_key, expiry):
    return get_option_chain(underlying_key, expiry)


def _scanner_spot_from_rows(rows):
    for row in rows:
        value = safe_float(row.get("underlying_spot_price"))
        if np.isfinite(value) and value > 0:
            return value
    return np.nan


def _scanner_spread_pct(market):
    bid = safe_float(market.get("bid_price"))
    ask = safe_float(market.get("ask_price"))
    if np.isfinite(bid) and np.isfinite(ask) and bid > 0 and ask > 0:
        return max(ask - bid, 0) / max((ask + bid) / 2, 0.01) * 100
    return 999.0


def _scanner_stage1_candidates(rows, spot, max_candidates=8):
    """
    Cheap option-chain-only filter. It deliberately does not create a trade
    signal. Its purpose is to reduce the number of stocks needing 5m/30m/daily
    technical requests in Stage 2.
    """
    candidates = []

    if not np.isfinite(spot) or spot <= 0:
        return candidates

    for raw in rows:
        strike = safe_float(raw.get("strike_price"))
        if not np.isfinite(strike):
            continue

        # Keep the scan practical and liquid around the underlying.
        if abs(strike - spot) / spot > 0.05:
            continue

        for side, action in (
            ("CE", "CALL BUY"),
            ("CE", "CALL SELL"),
            ("PE", "PUT BUY"),
            ("PE", "PUT SELL"),
        ):
            option = raw.get("call_options" if side == "CE" else "put_options") or {}
            market = option.get("market_data") or {}
            greeks = option.get("option_greeks") or {}

            ltp = safe_float(market.get("ltp"))
            oi = safe_float(market.get("oi"), 0)
            volume = safe_float(market.get("volume"), 0)
            pop = safe_float(greeks.get("pop"))
            delta = abs(safe_float(greeks.get("delta")))
            spread = _scanner_spread_pct(market)

            if not np.isfinite(ltp) or ltp <= 0 or oi <= 0:
                continue
            if not np.isfinite(pop) or pop < 55:
                continue

            # Stage 1 only rejects obviously unusable contracts.
            if volume < 300 or spread > 5:
                continue
            if not np.isfinite(delta) or delta < 0.10 or delta > 0.85:
                continue

            candidates.append({
                "raw": raw,
                "side": side,
                "action": action,
                "strike": strike,
                "pop": pop,
                "volume": volume,
                "oi": oi,
                "spread": spread,
                "distance": abs(strike - spot) / spot * 100,
            })

    # Diversify the shortlist across action/strike rather than allowing one
    # highly liquid underlying to dominate Stage 2.
    candidates.sort(
        key=lambda x: (
            -x["pop"],
            -x["volume"],
            x["spread"],
            x["distance"],
        )
    )

    selected = []
    seen = set()
    for item in candidates:
        key = (item["action"], round(item["strike"], 4))
        if key in seen:
            continue
        seen.add(key)
        selected.append(item)
        if len(selected) >= max_candidates:
            break

    return selected


def _scanner_actionable(plan, action):
    """Apply the same final action gates used by the main dashboard."""
    if not plan:
        return False

    score = safe_float(plan.get("score"), 0)
    pop = safe_float(plan.get("pop"))
    alignment = int(plan.get("alignment", 0) or 0)
    hard_fail = plan.get("fail_reasons") or []

    if score < 65 or not np.isfinite(pop) or pop < 55 or alignment < 2:
        return False
    if hard_fail or plan.get("readiness") != "READY":
        return False

    if action in {"CALL BUY", "PUT BUY"}:
        return bool(plan.get("candle_confirmed") and plan.get("volume_confirmed"))

    return safe_float(plan.get("rr1"), 0) >= 0.75


def _scanner_plan_for_candidate(candidate, symbol, expiry, risk_profile):
    """Run this file's existing scoring/build-plan logic on one shortlisted option."""
    rows = [candidate["raw"]]
    chain = normalize_chain(rows)
    if chain.empty:
        return None

    spot = _scanner_spot_from_rows(rows)
    if not np.isfinite(spot) or spot <= 0:
        return None

    support, resistance, pcr, oi_wall_info = oi_levels(chain, spot)

    # Technical data is the expensive part, so it is only requested for Stage-2
    # candidates. Cache decorators on these functions prevent repeated requests
    # for the same underlying during one scan.
    underlying_key = candidate["underlying_key"]
    daily = get_daily_candles(underlying_key)
    tf30 = get_30m_candles(underlying_key)
    tf5 = get_intraday_candles(underlying_key, 5)

    daily_tech = technicals(daily, spot)
    tf30_tech = technicals(tf30, spot)
    tf5_tech = technicals(tf5, spot)
    regime = market_regime(tf5_tech, tf30_tech, daily_tech, spot)

    # oi_levels needs the complete option chain for meaningful OI walls.
    # The full chain is already cached from Stage 1, so this is normally one
    # additional cached read rather than another network request.
    full_rows = get_scanner_chain(underlying_key, expiry)
    full_chain = normalize_chain(full_rows)
    if full_chain.empty:
        return None
    support, resistance, pcr, oi_wall_info = oi_levels(full_chain, spot)

    row = nearest_row(full_chain, candidate["strike"])
    if row is None:
        return None

    side = candidate["side"]
    action = candidate["action"]

    if action in {"CALL BUY", "PUT BUY"}:
        plan = build_plan(
            row, side, spot, support, resistance, pcr,
            tf5_tech, tf30_tech, daily_tech, risk_profile,
            full_chain, oi_wall_info, regime
        )
    else:
        plan = build_sell_plan(
            row, side, spot, support, resistance, pcr,
            tf5_tech, tf30_tech, daily_tech, risk_profile,
            full_chain, oi_wall_info, regime
        )

    if not plan or plan.get("action", action) != action and action in {"CALL SELL", "PUT SELL"}:
        return None

    if not _scanner_actionable(plan, action):
        return None

    return {
        "Stock": symbol,
        "Trade": action,
        "Strike": float(plan["strike"]),
        "Expiry": expiry,
        "PoP": safe_float(plan.get("pop")),
        "Quality": safe_float(plan.get("score"), 0),
        "Entry": safe_float(plan.get("entry")),
        "SL": safe_float(plan.get("sl")),
        "Target1": safe_float(plan.get("target1")),
        "Target2": safe_float(plan.get("target2")),
        "Exit": plan.get("exit", ""),
        "Delta": safe_float(plan.get("delta")),
        "IV": safe_float(plan.get("iv")),
        "Volume": safe_float(plan.get("volume"), 0),
        "OI": safe_float(plan.get("oi"), 0),
        "Alignment": int(plan.get("alignment", 0) or 0),
        "Regime": regime,
        "reason": (
            f"{regime} · {plan.get('readiness','')} · "
            f"{int(plan.get('alignment',0) or 0)}/3 timeframe alignment"
        ),
    }


def scan_fno_trade_alerts(risk_profile, top_alerts=5):
    """
    Full NSE equity F&O scan using the same strategy engine as the main page.

    Stage 1: option-chain filter only.
    Stage 2: existing technical + OI + quality + readiness gates.

    Only final actionable 4-way strategies are returned.
    """
    universe = get_fno_underlyings()
    stage1 = []
    scanned = 0
    failed = 0

    for idx, item in enumerate(universe, start=1):
        try:
            rows = get_scanner_chain(item["underlying_key"], item["expiry"])
            spot = _scanner_spot_from_rows(rows)
            candidates = _scanner_stage1_candidates(
                rows, spot, max_candidates=8
            )

            for candidate in candidates:
                candidate["symbol"] = item["symbol"]
                candidate["underlying_key"] = item["underlying_key"]
                candidate["expiry"] = item["expiry"]
                stage1.append(candidate)

            scanned += 1
        except UpstoxRateLimitError:
            raise
        except Exception:
            failed += 1


    # Do not run expensive technical analysis on hundreds of candidates.
    # Keep the strongest chain candidates, with a per-stock cap.
    stage1.sort(
        key=lambda x: (
            -x["pop"],
            -x["volume"],
            x["spread"],
            x["distance"],
        )
    )

    shortlist = []
    per_stock = {}
    max_stage2 = max(24, top_alerts * 5)

    for item in stage1:
        count = per_stock.get(item["symbol"], 0)
        if count >= 2:
            continue
        shortlist.append(item)
        per_stock[item["symbol"]] = count + 1
        if len(shortlist) >= max_stage2:
            break

    alerts = []
    for idx, candidate in enumerate(shortlist, start=1):
        try:
            plan = _scanner_plan_for_candidate(
                candidate,
                candidate["symbol"],
                candidate["expiry"],
                risk_profile,
            )
            if plan:
                alerts.append(plan)
        except UpstoxRateLimitError:
            raise
        except Exception:
            pass


    # One alert per stock/action combination; prefer quality first.
    unique = {}
    for alert in alerts:
        key = (alert["Stock"], alert["Trade"])
        old = unique.get(key)
        if old is None or (
            alert["Quality"],
            alert["PoP"],
            alert["Alignment"],
            alert["Volume"],
        ) > (
            old["Quality"],
            old["PoP"],
            old["Alignment"],
            old["Volume"],
        ):
            unique[key] = alert

    alerts = list(unique.values())
    alerts.sort(
        key=lambda x: (
            -x["Quality"],
            -x["PoP"],
            -x["Alignment"],
            -x["Volume"],
        )
    )

    return alerts[:top_alerts], len(universe), scanned, failed, len(shortlist)


# ============================================================
# BACKGROUND SCANNER MANAGER
# The F&O scan NEVER runs in the Streamlit request/rerun path.
# It runs in a persistent background worker and the UI only reads
# the last completed result. This keeps the main dashboard responsive.
# ============================================================

SCANNER_REFRESH_SECONDS = 300  # backend refresh: every 5 minutes


class _FNOScannerManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.running = False
        self.results = []
        self.info = None
        self.scan_time = None
        self.error = None
        self.profile = None
        self.next_allowed = 0.0
        self.started_at = 0.0
        self.finished_at = 0.0

    def start_if_needed(self, risk_profile):
        now = time.time()
        with self.lock:
            if self.running:
                return
            if self.profile != risk_profile:
                # A profile change should trigger a fresh scan, but only after
                # the current worker has finished. Do not start duplicate workers.
                self.profile = risk_profile
                self.next_allowed = 0.0
            if now < self.next_allowed and self.results:
                return
            self.running = True
            self.error = None
            self.started_at = now

        worker = threading.Thread(
            target=self._worker,
            args=(risk_profile,),
            daemon=True,
            name="fno-background-scanner",
        )
        worker.start()

    def _worker(self, risk_profile):
        try:
            results, total, scanned, failed, stage2_count = scan_fno_trade_alerts(
                risk_profile, top_alerts=5
            )
            now = time.time()
            with self.lock:
                self.results = results
                self.info = (total, scanned, failed, stage2_count)
                self.scan_time = datetime.now(
                    ZoneInfo("Asia/Kolkata")
                ).strftime("%H:%M:%S")
                self.error = None
                self.running = False
                self.finished_at = now
                self.next_allowed = now + SCANNER_REFRESH_SECONDS
        except UpstoxRateLimitError as exc:
            with self.lock:
                self.error = (
                    f"Upstox rate limit reached. Background scanner will retry after "
                    f"about {exc.retry_after} seconds."
                )
                self.running = False
                self.finished_at = time.time()
                self.next_allowed = time.time() + max(60, int(exc.retry_after or 60))
        except Exception as exc:
            with self.lock:
                self.error = f"Background F&O scanner unavailable: {exc}"
                self.running = False
                self.finished_at = time.time()
                self.next_allowed = time.time() + 120

    def snapshot(self):
        with self.lock:
            return (
                list(self.results),
                self.info,
                self.scan_time,
                self.error,
                self.running,
                self.started_at,
                self.finished_at,
            )


@st.cache_resource(show_spinner=False)
def get_fno_scanner_manager():
    return _FNOScannerManager()


# ============================================================
# SCANNER STYLING — ALERTS ONLY
# ============================================================
st.markdown("""
<style>
.scanner-wrap{margin:4px 0 14px;}
.scanner-title{font-size:18px;font-weight:900;color:#182230;margin-bottom:3px;}
.scanner-sub{font-size:12px;color:#667085;line-height:1.45;margin-bottom:10px;}
.scanner-alert{border:1px solid #dfe5eb;border-radius:12px;padding:10px 11px;margin:8px 0;background:#fff;box-shadow:0 2px 7px rgba(16,42,67,.04);}
.scanner-alert-call{border-left:5px solid #16a34a;background:linear-gradient(180deg,#f0fdf4,#fff);}
.scanner-alert-put{border-left:5px solid #dc2626;background:linear-gradient(180deg,#fff1f2,#fff);}
.scanner-alert-sell{border-left:5px solid #7c3aed;}
.scanner-rank{font-size:11px;font-weight:900;color:#98a2b3;letter-spacing:.7px;}
.scanner-main{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-top:3px;}
.scanner-main b{font-size:15px;color:#182230;}
.scanner-action{font-size:11px;font-weight:900;padding:4px 7px;border-radius:9px;}
.scanner-call-action{background:#dcfce7;color:#087f3e;}
.scanner-put-action{background:#ffe4e6;color:#c81e3a;}
.scanner-sell-action{background:#ede9fe;color:#6d28d9;}
.scanner-stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;margin-top:8px;}
.scanner-stat{background:#f8fafc;border-radius:7px;padding:6px;text-align:center;}
.scanner-stat span{display:block;font-size:9px;color:#98a2b3;font-weight:900;}
.scanner-stat b{display:block;font-size:12px;color:#182230;margin-top:2px;}
.scanner-note{font-size:10px;color:#667085;line-height:1.35;margin-top:7px;}
.scanner-off{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:10px;color:#667085;font-size:12px;}
.scanner-status{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 10px;border-radius:10px;margin:5px 0 10px;font-size:11px;font-weight:800;}
.scanner-status-active{background:#ecfdf3;border:1px solid #b7ebca;color:#087f3e;}
.scanner-status-running{background:#eff8ff;border:1px solid #b9ddf7;color:#175cd3;}
.scanner-status-closed{background:#f8fafc;border:1px solid #e2e8f0;color:#667085;}
.scanner-status-error{background:#fff7ed;border:1px solid #fed7aa;color:#c2410c;}
.scanner-status-main{display:flex;align-items:center;gap:6px;}
.scanner-dot{font-size:13px;line-height:1;}
.scanner-updated{font-weight:700;opacity:.8;}
</style>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================

def _render_fno_scanner_panel():
    """Render only the scanner panel; the actual scan runs in the manager thread."""
    with st.sidebar:
        risk_for_scanner = st.session_state.get("risk_profile", "Balanced")
        scanner_manager = get_fno_scanner_manager()

        scanner_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        scanner_market_open = (
            scanner_now.weekday() < 5
            and (scanner_now.hour, scanner_now.minute) >= (9, 15)
            and (scanner_now.hour, scanner_now.minute) <= (15, 30)
        )

        if scanner_market_open:
            scanner_manager.start_if_needed(risk_for_scanner)

        # Be tolerant of an older cached scanner-manager instance during
        # Streamlit hot reloads. Older versions returned 5 values; newer
        # versions return 7. This prevents a tuple-unpacking ValueError after
        # deploying a new app.py without requiring a manual process reset.
        snapshot = scanner_manager.snapshot()
        if isinstance(snapshot, (tuple, list)) and len(snapshot) >= 7:
            (
                alert_results,
                alert_info,
                alert_time,
                alert_error,
                alert_running,
                started_at,
                finished_at,
            ) = snapshot[:7]
        elif isinstance(snapshot, (tuple, list)) and len(snapshot) == 5:
            (
                alert_results,
                alert_info,
                alert_time,
                alert_error,
                alert_running,
            ) = snapshot
            started_at = 0.0
            finished_at = 0.0
        else:
            raise ValueError(
                f"Unexpected scanner manager snapshot format: {type(snapshot).__name__}"
            )
        alert_results = alert_results[:5]

        st.markdown("### 🔔 F&O TRADE ALERTS")

        if not scanner_market_open:
            scanner_status_cls = "scanner-status-closed"
            scanner_status_text = "● MARKET CLOSED"
            scanner_status_detail = (
                f"Last update: {alert_time + ' IST' if alert_time else 'No completed scan yet'}"
            )
        elif alert_error:
            scanner_status_cls = "scanner-status-error"
            scanner_status_text = "● SCANNER TEMPORARILY PAUSED"
            scanner_status_detail = "Will retry automatically"
        elif alert_running:
            scanner_status_cls = "scanner-status-running"
            scanner_status_text = "● UPDATING OPPORTUNITIES"
            elapsed = int(max(0, time.time() - started_at)) if started_at else 0
            scanner_status_detail = (
                f"Background scan in progress · {elapsed}s"
                if elapsed else "Background scan in progress"
            )
        elif alert_time:
            scanner_status_cls = "scanner-status-active"
            scanner_status_text = "● BACKGROUND SCANNER ACTIVE"
            scanner_status_detail = f"Updated {alert_time} IST"
        else:
            scanner_status_cls = "scanner-status-running"
            scanner_status_text = "● STARTING BACKGROUND SCANNER"
            scanner_status_detail = "First result will appear automatically"

        st.markdown(
            f"""<div class=\"scanner-status {scanner_status_cls}\">
                <div class=\"scanner-status-main\"><span class=\"scanner-dot\">{scanner_status_text[:1]}</span><span>{scanner_status_text[2:]}</span></div>
                <span class=\"scanner-updated\">{scanner_status_detail}</span>
            </div>""",
            unsafe_allow_html=True,
        )

        if alert_results:
            for rank, alert in enumerate(alert_results, start=1):
                action = alert["Trade"]
                is_call = "CALL" in action
                action_class = (
                    "scanner-call-action" if is_call else "scanner-put-action"
                )
                if "SELL" in action:
                    action_class = "scanner-sell-action"

                card_class = (
                    "scanner-alert-call" if is_call else "scanner-alert-put"
                )
                if "SELL" in action:
                    card_class += " scanner-alert-sell"

                st.markdown(
                    f"""
                    <div class=\"scanner-alert {card_class}\">
                      <div class=\"scanner-rank\">#{rank} · {alert['Stock']}</div>
                      <div class=\"scanner-main\">
                        <b>{alert['Trade']} · {alert['Strike']:.0f}</b>
                        <span class=\"scanner-action {action_class}\">{action}</span>
                      </div>
                      <div class=\"scanner-stats\">
                        <div class=\"scanner-stat\"><span>PoP</span><b>{alert['PoP']:.1f}%</b></div>
                        <div class=\"scanner-stat\"><span>QUALITY</span><b>{alert['Quality']:.0f}/100</b></div>
                        <div class=\"scanner-stat\"><span>ALIGN</span><b>{alert['Alignment']}/3</b></div>
                      </div>
                      <div class=\"scanner-note\">
                        Entry {fmt_price(alert['Entry'])} · SL {fmt_price(alert['SL'])} ·
                        T1 {fmt_price(alert['Target1'])}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(
                    f"Analyze {alert['Stock']}",
                    key=f"scanner_analyze_{rank}_{alert['Stock']}_{alert['Trade']}",
                    use_container_width=True,
                ):
                    st.session_state["symbol"] = alias_symbol(alert["Stock"])
                    st.rerun()

        if alert_error and not alert_results:
            st.caption(f"Scanner note: {alert_error}")
        elif not alert_results:
            if scanner_market_open and not alert_running:
                st.info("No qualifying F&O opportunities currently.")
            elif alert_running:
                st.caption(
                    "The scanner is working in the background. Results will appear after the current scan completes."
                )
            elif not scanner_market_open:
                st.caption("No live scan is required while the market is closed.")


# Streamlit fragments are preferable to the external autorefresh component because
# they refresh only this small sidebar panel and do not rerun the heavy dashboard.
# The fallback keeps compatibility with older Streamlit versions.
if hasattr(st, "fragment"):
    @st.fragment(run_every="5s")
    def _fno_scanner_fragment():
        _render_fno_scanner_panel()

    _fno_scanner_fragment()
else:
    with st.sidebar:
        _render_fno_scanner_panel()
        if st_autorefresh is not None:
            st_autorefresh(interval=5_000, key="fno_backend_scanner_status_refresh")

    st.divider()
    st.markdown("## 🔎 Analyze Instrument")

    symbol_input = st.text_input(
        "NSE Stock / Index",
        value=st.session_state.get("symbol", "KOTAKBANK"),
        placeholder="NIFTY / BANKNIFTY / HDFCBANK",
    )

    risk_profile = st.selectbox(
        "Risk Profile",
        ["Conservative", "Balanced", "Aggressive"],
        index=1,
        key="risk_profile",
    )

    analyze = st.button(
        "Analyze Live Market",
        type="primary",
        use_container_width=True,
    )

    refresh = st.button(
        "↻ Refresh Live Data",
        use_container_width=True,
    )

    auto_refresh = st.checkbox(
        "Auto refresh every 60 seconds",
        value=False,
    )

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

# ============================================================
# LIVE ANALYSIS
# ============================================================

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
        # Upstox provides lot_size at the option-contract level. Use the
        # selected nearest expiry so the displayed lot size always matches
        # the contracts being analyzed.
        expiry_contracts = [
            c for c in contracts
            if str(c.get("expiry", "")) == selected_expiry
            and str(c.get("instrument_type", "")).upper() in {"CE", "PE"}
        ]
        lot_sizes = [
            safe_float(c.get("lot_size"))
            for c in expiry_contracts
            if np.isfinite(safe_float(c.get("lot_size"))) and safe_float(c.get("lot_size")) > 0
        ]
        lot_size = int(round(lot_sizes[0])) if lot_sizes else np.nan
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
regime = market_regime(tf5, tf30, daily_tech, spot)
atm_index = (chain["Strike"] - spot).abs().idxmin()

# For each strategy we select a strike that is close enough to the underlying
# to remain liquid, then score the strategy itself rather than a generic BUY score.
band = chain.iloc[max(0, atm_index - 8):min(len(chain), atm_index + 9)].copy()


def buy_candidate(side):
    candidates = []
    for _, row in band.iterrows():
        scored = score_option(row, side, spot, pcr, tf5, tf30, daily_tech, chain,
                              support=support, resistance=resistance, oi_wall_info=oi_wall_info, regime=regime)
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
                      risk_profile, chain, oi_wall_info, regime)


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
                               daily_tech, risk_profile, chain, oi_wall_info, regime)
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
MIN_SCORE = 65
MIN_POP = 55
MIN_ALIGNMENT = 2

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
    alignment = int(plan.get("alignment", 0) or 0)
    if action in {"CALL BUY", "PUT BUY"}:
        # BUYs need actual trigger + confirmation, alignment and enough quality.
        ready = (
            score >= MIN_SCORE and pop >= MIN_POP and alignment >= MIN_ALIGNMENT and
            not hard_fail and plan.get("readiness") == "READY" and
            plan.get("candle_confirmed") and plan.get("volume_confirmed")
        )
    else:
        # SELLs need stronger structure and are never selected during a breakout regime.
        ready = (
            score >= MIN_SCORE and pop >= MIN_POP and alignment >= 2 and
            not hard_fail and plan.get("readiness") == "READY" and
            safe_float(plan.get("rr1"), 0) >= 0.75
        )
    if ready:
        # Small tie-breaker for score, then PoP, then option liquidity.
        eligible.append((score + pop * 0.20 + min(safe_float(plan.get("volume"), 0) / 100000, 3), action, plan))

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

# Forward-test logging is intentionally backend-only. It does not change the UI.
if decision != "NO TRADE" and best_plan:
    log_signal(symbol, selected_expiry, decision, best_plan, spot, pcr, support, resistance, tf5, tf30, daily_tech, regime)


# ENGINE RESULT: 4 strategy cards in a fixed 2x2 grid.
st.markdown("""<style>
.fo-engine-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;width:100%;align-items:stretch;}
.fo-engine-grid .fo-engine-card{min-width:0!important;margin:0!important;height:100%;box-sizing:border-box;}
@media (max-width:760px){.fo-engine-grid{grid-template-columns:1fr;}}
</style>""",unsafe_allow_html=True)

# ============================================================
# VISUAL DASHBOARD — UI ONLY
# ============================================================
# The trading engine above is intentionally untouched. Everything below this
# point is presentation-only: hierarchy, cards, spacing, typography and
# responsive layout.
st.markdown("""
<style>
/* Premium dashboard layer */
.fo-shell {max-width:1500px;margin:0 auto;}
.fo-hero{background:linear-gradient(135deg,#0b1f33 0%,#123b5d 55%,#155e75 100%);border-radius:20px;padding:24px 28px;color:#fff;box-shadow:0 10px 30px rgba(15,45,70,.14);margin:2px 0 18px;position:relative;overflow:hidden;}
.fo-hero:after{content:"";position:absolute;right:-90px;top:-120px;width:300px;height:300px;border-radius:50%;background:rgba(255,255,255,.055);}
.fo-hero-top{display:flex;align-items:center;justify-content:space-between;gap:18px;position:relative;z-index:1;}
.fo-brand{font-size:32px;font-weight:900;letter-spacing:-.6px;line-height:1.1;}
.fo-tagline{font-size:15px;color:rgba(255,255,255,.72);margin-top:6px;letter-spacing:.15px;}
.fo-live{padding:10px 14px;border-radius:12px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.15);text-align:right;min-width:150px;}
.fo-live b{display:block;font-size:15px;letter-spacing:.4px;}.fo-live small{display:block;margin-top:4px;font-size:13px;color:rgba(255,255,255,.68);}
.fo-section{font-size:15px;font-weight:900;letter-spacing:1px;color:#667085;margin:22px 2px 9px;display:flex;align-items:center;gap:9px;}
.fo-section:after{content:"";height:1px;background:#e7ebf0;flex:1;}
.fo-instrument{display:flex;align-items:end;justify-content:space-between;gap:14px;background:#fff;border:1px solid #e7ebf0;border-radius:15px;padding:15px 18px;margin-bottom:14px;box-shadow:0 3px 12px rgba(16,42,67,.035);}
.fo-symbol{font-size:27px;font-weight:900;color:#182230;letter-spacing:-.3px;}.fo-symbol-note{font-size:14px;color:#98a2b3;margin-top:3px;}
.fo-regime{font-size:14px;font-weight:850;color:#475467;background:#f3f5f7;border:1px solid #e5e7eb;padding:7px 10px;border-radius:20px;}
.fo-metrics{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:10px;}
.fo-metric{background:#fff;border:1px solid #e7ebf0;border-radius:14px;padding:14px 13px;min-height:94px;box-shadow:0 3px 12px rgba(16,42,67,.03);}
.fo-metric-label{font-size:12px;font-weight:900;color:#98a2b3;letter-spacing:.8px;}.fo-metric-value{font-size:22px;font-weight:900;color:#182230;margin-top:8px;line-height:1.1;white-space:nowrap;}.fo-metric-note{font-size:12px;color:#98a2b3;margin-top:7px;}
.fo-metric.spot{background:linear-gradient(180deg,#f7fbff,#fff);border-color:#d9e8f2;}.fo-metric.spot .fo-metric-value{font-size:25px;}
.fo-metric.support{border-left:4px solid #16a34a;}.fo-metric.support .fo-metric-value{color:#147a3d;}.fo-metric.resistance{border-left:4px solid #dc2626;}.fo-metric.resistance .fo-metric-value{color:#b4232f;}
.fo-decision{border-radius:19px;padding:22px;border:1px solid #e3e7eb;box-shadow:0 7px 22px rgba(16,42,67,.055);background:#fff;}
.fo-decision.call{background:linear-gradient(135deg,#f3fcf6,#fff);border-color:#bfe4c9;}.fo-decision.put{background:linear-gradient(135deg,#fff5f5,#fff);border-color:#f0c5c8;}.fo-decision.neutral{background:linear-gradient(135deg,#f7f8fa,#fff);}
.fo-decision-row{display:flex;justify-content:space-between;align-items:center;gap:15px;}.fo-decision-label{font-size:13px;font-weight:900;color:#98a2b3;letter-spacing:1px;}.fo-decision-title{font-size:37px;font-weight:950;letter-spacing:-1px;margin-top:4px;}.fo-decision.call .fo-decision-title{color:#147a3d}.fo-decision.put .fo-decision-title{color:#b4232f}.fo-decision.neutral .fo-decision-title{color:#475467;}
.fo-decision-note{font-size:14px;color:#667085;margin-top:6px;}.fo-score-ring{min-width:100px;text-align:center;border-radius:15px;background:rgba(255,255,255,.72);border:1px solid rgba(0,0,0,.06);padding:11px 13px;}.fo-score-ring b{display:block;font-size:28px;color:#182230;line-height:1;}.fo-score-ring span{font-size:12px;color:#98a2b3;font-weight:800;letter-spacing:.6px;}
.fo-decision-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin-top:17px;}.fo-decision-cell{background:rgba(255,255,255,.72);border:1px solid rgba(16,42,67,.07);border-radius:11px;padding:11px;text-align:center;}.fo-decision-cell span{display:block;font-size:12px;font-weight:900;color:#98a2b3;letter-spacing:.7px;}.fo-decision-cell b{display:block;font-size:18px;color:#182230;margin-top:5px;}
.fo-engine{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;}.fo-engine-card{background:#fff;border:1px solid #e7ebf0;border-radius:14px;padding:14px;box-shadow:0 3px 12px rgba(16,42,67,.03);position:relative;overflow:hidden;}.fo-engine-card.selected{border-color:#8fcfa1;box-shadow:0 5px 18px rgba(20,122,61,.09);}.fo-engine-card.rejected{opacity:.82;}.fo-engine-top{display:flex;justify-content:space-between;gap:8px;align-items:center;}.fo-engine-action{font-size:15px;font-weight:900;color:#182230;}.fo-engine-status{font-size:11px;font-weight:900;padding:5px 7px;border-radius:10px;letter-spacing:.5px;background:#f2f4f7;color:#667085;}.fo-engine-card.selected{background:#eaf8ef;border-color:#8fcfa1;box-shadow:0 5px 18px rgba(20,122,61,.12);}.fo-engine-card.selected .fo-engine-status{background:#16a34a;color:#fff;}.fo-engine-card.rejected{background:#fff0f1;border-color:#f2c5c8;opacity:1;}.fo-engine-card.rejected .fo-engine-status{background:#dc2626;color:#fff;}.fo-engine-contract{font-size:25px;font-weight:900;margin:10px 0 12px;color:#182230;}.fo-engine-stats{display:grid;grid-template-columns:1fr 1fr;gap:7px;}.fo-engine-stats div{background:#f8fafc;border-radius:9px;padding:8px;}.fo-engine-stats span{display:block;font-size:11px;color:#98a2b3;font-weight:900;}.fo-engine-stats b{display:block;font-size:16px;margin-top:3px;color:#182230;}.fo-engine-reason{font-size:12px;color:#98a2b3;line-height:1.45;margin-top:10px;min-height:26px;}
.fo-plan-head{display:flex;align-items:center;justify-content:space-between;gap:14px;background:#fff;border:1px solid #e7ebf0;border-radius:16px 16px 0 0;padding:17px 19px;}.fo-plan-action{font-size:13px;font-weight:900;color:#98a2b3;letter-spacing:.8px;}.fo-plan-contract{font-size:25px;font-weight:900;color:#182230;margin-top:3px;}.fo-plan-pop{font-size:24px;font-weight:900;color:#147a3d;white-space:nowrap;}.fo-levels{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-top:9px;}.fo-level{background:#fff;border:1px solid #e7ebf0;border-radius:13px;padding:14px;min-height:86px;}.fo-level span{display:block;font-size:12px;color:#98a2b3;font-weight:900;letter-spacing:.6px;}.fo-level b{display:block;font-size:21px;color:#182230;margin-top:7px;}.fo-level small{display:block;font-size:12px;color:#98a2b3;margin-top:4px;}.fo-level.entry{border-top:3px solid #3b82f6;}.fo-level.sl{border-top:3px solid #dc2626;}.fo-level.t1{border-top:3px solid #16a34a;}.fo-level.t2{border-top:3px solid #0f766e;}.fo-level.greeks{border-top:3px solid #7c3aed;}
.fo-exit{background:#fff;border:1px solid #e7ebf0;border-radius:13px;padding:13px 16px;margin-top:9px;display:flex;gap:12px;align-items:flex-start;}.fo-exit-icon{font-size:21px;}.fo-exit span{display:block;font-size:12px;color:#98a2b3;font-weight:900;letter-spacing:.6px;}.fo-exit b{display:block;font-size:14px;color:#344054;line-height:1.5;margin-top:3px;}
.fo-sr{display:grid;grid-template-columns:1fr 1.2fr 1fr;border:1px solid #e7ebf0;border-radius:16px;overflow:hidden;background:#fff;box-shadow:0 3px 12px rgba(16,42,67,.03);}.fo-sr-side{padding:20px;text-align:center;display:flex;flex-direction:column;justify-content:center;}.fo-sr-side.support{background:#f4fbf6;}.fo-sr-side.resistance{background:#fff6f6;}.fo-sr-side span{font-size:12px;font-weight:900;letter-spacing:.7px;}.fo-sr-side.support span{color:#147a3d;}.fo-sr-side.resistance span{color:#b4232f;}.fo-sr-side b{font-size:28px;margin-top:7px;color:#182230;}.fo-sr-side small{font-size:13px;color:#98a2b3;margin-top:4px;}.fo-sr-mid{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px;border-left:1px dashed #dfe3e8;border-right:1px dashed #dfe3e8;padding:15px;}.fo-sr-mid span{font-size:12px;color:#98a2b3;font-weight:800;}.fo-current{font-size:21px;font-weight:900;background:#f5f7f9;border:1px solid #e5e7eb;border-radius:22px;padding:8px 15px;color:#182230;}
.fo-why{background:#fff;border:1px solid #e7ebf0;border-radius:15px;padding:6px 17px;box-shadow:0 3px 12px rgba(16,42,67,.03);}.fo-why-line{padding:10px 2px;border-bottom:1px solid #eef0f2;font-size:14px;color:#344054;line-height:1.5;}.fo-why-line:last-child{border-bottom:0;}
.fo-footer{margin-top:22px;padding:13px 15px;border-radius:12px;background:#f3f5f7;color:#98a2b3;font-size:12px;line-height:1.6;text-align:center;}
/* Hide Streamlit's dataframe chrome when we no longer use it for the engine panel. */
.fo-hide{display:none;}
@media(max-width:1100px){.fo-metrics{grid-template-columns:repeat(4,1fr)}.fo-engine{grid-template-columns:repeat(2,1fr)}.fo-levels{grid-template-columns:repeat(3,1fr)}}
@media(max-width:720px){.fo-hero-top,.fo-instrument,.fo-decision-row{align-items:flex-start;flex-direction:column}.fo-live{width:100%;text-align:left}.fo-metrics{grid-template-columns:repeat(2,1fr)}.fo-engine{grid-template-columns:1fr}.fo-decision-grid{grid-template-columns:repeat(2,1fr)}.fo-levels{grid-template-columns:repeat(2,1fr)}.fo-sr{grid-template-columns:1fr}.fo-sr-mid{border-left:0;border-right:0;border-top:1px dashed #dfe3e8;border-bottom:1px dashed #dfe3e8}.fo-brand{font-size:27px}}
</style>
""", unsafe_allow_html=True)

now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
market_open = now_ist.weekday() < 5 and (now_ist.hour, now_ist.minute) >= (9, 15) and (now_ist.hour, now_ist.minute) <= (15, 30)
status_text = "● LIVE DATA" if market_open else "● MARKET CLOSED"
status_bg = "#16a34a" if market_open else "#dc2626"

st.markdown(f"""
<div class="fo-hero">
  <div class="fo-hero-top">
    <div>
      <div class="fo-brand">📊 FO PRO Trader Assistant</div>
      <div class="fo-tagline">Live Upstox data · 5-way F&O decision engine · Quality-focused trade selection</div>
    </div>
    <div class="fo-live" style="background:{status_bg};border-color:transparent;">
      <b>{status_text}</b>
      <small>{now_ist.strftime('%d %b %Y · %H:%M:%S IST')}</small>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="fo-instrument">
  <div><div class="fo-symbol">{symbol}</div><div class="fo-symbol-note">NSE F&O · Nearest expiry {selected_expiry}</div></div>
  <div class="fo-regime">MARKET REGIME · {regime}</div>
</div>
<div class="fo-section">MARKET SNAPSHOT</div>
""", unsafe_allow_html=True)

spot_note = f"{net_change:+.2f} ({change_pct:+.2f}%)"
metric_html = [
    ("SPOT", fmt_price(spot), spot_note, "spot"),
    ("EXPIRY", selected_expiry, "Nearest F&O expiry", ""),
    ("PCR", f"{pcr:.2f}" if np.isfinite(pcr) else "—", "Put / Call OI", ""),
    ("SUPPORT", fmt_price(support), "Put OI zone", "support"),
    ("RESISTANCE", fmt_price(resistance), "Call OI zone", "resistance"),
    ("VWAP", fmt_price(tf5.get("vwap")), "5m VWAP", ""),
    ("LOT SIZE", fmt_num(lot_size), "1 F&O lot", ""),
]
metrics = "<div class='fo-metrics'>"
for title, value, note, cls in metric_html:
    metrics += f"<div class='fo-metric {cls}'><div class='fo-metric-label'>{title}</div><div class='fo-metric-value'>{value}</div><div class='fo-metric-note'>{note}</div></div>"
metrics += "</div>"
st.markdown(metrics, unsafe_allow_html=True)

st.markdown("<div class='fo-section'>TRADE DECISION</div>", unsafe_allow_html=True)
trend_name = overall_trend(tf5, tf30, daily_tech)[0].upper()
decision_class = "call" if "CALL" in decision else "put" if "PUT" in decision else "neutral"
if decision != "NO TRADE" and best_plan:
    action_pop = safe_float(best_plan.get("pop")); action_score = safe_float(best_plan.get("score"), 0)
    contract = f"{best_plan['strike']:.0f} {'CE' if best_plan['side']=='CE' else 'PE'}"
else:
    action_pop = np.nan; action_score = max([safe_float(p.get("score"),0) for p in strategy_plans.values() if p] or [0]); contract = "No executable setup"

decision_note = {
    "CALL BUY":"Directional upside setup — execute only when the displayed confirmation conditions are satisfied.",
    "CALL SELL":"Premium-selling setup — requires price to remain below resistance and pass the seller risk gates.",
    "PUT BUY":"Directional downside setup — execute only when the displayed confirmation conditions are satisfied.",
    "PUT SELL":"Premium-selling setup — requires price to remain above support and pass the seller risk gates.",
    "NO TRADE":"No strategy currently meets the minimum quality, alignment, liquidity and PoP gates."
}[decision]

st.markdown(f"""
<div class="fo-decision {decision_class}">
  <div class="fo-decision-row">
    <div><div class="fo-decision-label">ENGINE OUTPUT</div><div class="fo-decision-title">{decision}</div><div class="fo-decision-note">{decision_note}</div></div>
    <div class="fo-score-ring"><b>{action_score:.0f}</b><span>QUALITY / 100</span></div>
  </div>
  <div class="fo-decision-grid">
    <div class="fo-decision-cell"><span>OPTION</span><b>{contract}</b></div>
    <div class="fo-decision-cell"><span>PoP</span><b>{f'{action_pop:.1f}%' if np.isfinite(action_pop) else '—'}</b></div>
    <div class="fo-decision-cell"><span>MARKET</span><b>{trend_name}</b></div>
    <div class="fo-decision-cell"><span>RISK PROFILE</span><b>{risk_profile.upper()}</b></div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div class='fo-section'>ENGINE RESULT · ALL 4 STRATEGIES</div>", unsafe_allow_html=True)

st.markdown("""<style>
/* FORCE ENGINE RESULT 2x2 GRID */
.fo-engine.fo-engine-grid{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-auto-rows:1fr!important;gap:14px!important;width:100%!important;align-items:stretch!important;}
.fo-engine.fo-engine-grid .fo-engine-card{display:flex!important;flex-direction:column!important;min-width:0!important;width:100%!important;height:100%!important;margin:0!important;box-sizing:border-box!important;}
@media(max-width:720px){.fo-engine.fo-engine-grid{grid-template-columns:1fr!important;}}
</style>""", unsafe_allow_html=True)

engine_html = "<div class='fo-engine fo-engine-grid'>"
for action in ["CALL BUY","CALL SELL","PUT BUY","PUT SELL"]:
    plan = strategy_plans[action]
    if not plan:
        engine_html += f"<div class='fo-engine-card rejected'><div class='fo-engine-top'><div class='fo-engine-action'>{action}</div><div class='fo-engine-status'>NO DATA</div></div><div class='fo-engine-contract'>—</div><div class='fo-engine-reason'>No valid candidate was produced.</div></div>"
        continue
    fails = ", ".join(plan.get("fail_reasons") or []) or "All hard checks passed"
    selected = action == decision
    status = "SELECTED" if selected else ("PASS" if not plan.get("fail_reasons") and safe_float(plan.get("score"),0) >= MIN_SCORE and safe_float(plan.get("pop"),0) >= MIN_POP else "REJECTED")
    status_class = "selected" if selected else ("" if status == "PASS" else "rejected")
    engine_html += f"""
    <div class='fo-engine-card {status_class}'>
      <div class='fo-engine-top'><div class='fo-engine-action'>{action}</div><div class='fo-engine-status'>{status}</div></div>
      <div class='fo-engine-contract'>{plan['strike']:.0f} {'CE' if plan['side']=='CE' else 'PE'}</div>
      <div class='fo-engine-stats'><div><span>PoP</span><b>{safe_float(plan.get('pop')):.1f}%</b></div><div><span>QUALITY</span><b>{safe_float(plan.get('score'),0):.0f}/100</b></div></div>
      <div class='fo-engine-reason'>{fails}</div>
    </div>"""
engine_html += "</div>"
st.markdown(engine_html, unsafe_allow_html=True)

# Optional visual support/resistance map. It uses the same values already calculated;
# it does not create or alter a trading signal.
st.markdown("<div class='fo-section'>OI SUPPORT / RESISTANCE MAP</div>", unsafe_allow_html=True)
st.markdown(f"""
<div class="fo-sr">
  <div class="fo-sr-side resistance"><span>RESISTANCE</span><b>{fmt_price(resistance)}</b><small>Call OI wall · {oi_wall_info.get('resistance_strength',0):.0f}% relative strength</small></div>
  <div class="fo-sr-mid"><span>CURRENT SPOT</span><div class="fo-current">{fmt_price(spot)}</div><span>VWAP {fmt_price(tf5.get('vwap'))}</span></div>
  <div class="fo-sr-side support"><span>SUPPORT</span><b>{fmt_price(support)}</b><small>Put OI wall · {oi_wall_info.get('support_strength',0):.0f}% relative strength</small></div>
</div>
""", unsafe_allow_html=True)

if decision != "NO TRADE" and best_plan:
    st.markdown("<div class='fo-section'>SELECTED TRADE PLAN</div>", unsafe_allow_html=True)
    selected_contract = f"{best_plan['strike']:.0f} {'CE' if best_plan['side']=='CE' else 'PE'}"
    st.markdown(f"""
    <div class="fo-plan-head">
      <div><div class="fo-plan-action">SELECTED STRATEGY</div><div class="fo-plan-contract">{decision} · {selected_contract}</div></div>
      <div class="fo-plan-pop">PoP {safe_float(best_plan.get('pop')):.1f}%</div>
    </div>
    """, unsafe_allow_html=True)
    entry_price = safe_float(best_plan.get("entry"))
    level_items = [
        ("ENTRY", fmt_price(entry_price), pct_change_from_entry(entry_price, entry_price), "entry"),
        ("STOP LOSS", fmt_price(best_plan.get("sl")), pct_change_from_entry(best_plan.get("sl"), entry_price), "sl"),
        ("TARGET 1", fmt_price(best_plan.get("target1")), pct_change_from_entry(best_plan.get("target1"), entry_price), "t1"),
        ("TARGET 2", fmt_price(best_plan.get("target2")), pct_change_from_entry(best_plan.get("target2"), entry_price), "t2"),
        ("DELTA / IV", f"{safe_float(best_plan.get('delta')):.2f} / {safe_float(best_plan.get('iv')):.1f}%", "Option characteristics", "greeks"),
    ]
    level_html = "<div class='fo-levels'>"
    for title, value, note, cls in level_items:
        level_html += f"<div class='fo-level {cls}'><span>{title}</span><b>{value}</b><small>{note}</small></div>"
    level_html += "</div>"
    st.markdown(level_html, unsafe_allow_html=True)
    st.markdown(f"<div class='fo-exit'><div class='fo-exit-icon'>🚪</div><div><span>EXIT RULE</span><b>{best_plan.get('exit','Follow stop-loss and targets.')}</b></div></div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='fo-exit' style='margin-top:10px;'><div class='fo-exit-icon'>⛔</div><div><span>NO TRADE</span><b>None of CALL BUY, CALL SELL, PUT BUY or PUT SELL passed the backend quality + PoP gates. No executable entry, SL or target is displayed.</b></div></div>", unsafe_allow_html=True)

with st.expander("Why this decision?", expanded=False):
    why_lines=[]
    if decision != "NO TRADE" and best_plan:
        why_lines += [
            f"Selected {decision} on {best_plan['strike']:.0f} {'CE' if best_plan['side']=='CE' else 'PE'} with strategy PoP {best_plan['pop']:.1f}% and quality score {best_plan['score']:.0f}/100.",
            f"Timeframes: 5m {tf5['trend']} · 30m {tf30['trend']} · Daily {daily_tech['trend']}.",
            f"Market structure: Support {fmt_price(support)} · Resistance {fmt_price(resistance)} · VWAP {fmt_price(tf5.get('vwap'))} · Regime {regime}.",
        ]
    else:
        for action in ["CALL BUY","CALL SELL","PUT BUY","PUT SELL"]:
            plan=strategy_plans[action]
            if plan:
                reason=", ".join(plan.get("fail_reasons") or []) or "quality/confirmation gate not met"
                why_lines.append(f"{action}: {reason} · PoP {safe_float(plan.get('pop')):.1f}% · Score {safe_float(plan.get('score'),0):.0f}/100.")
    st.markdown("<div class='fo-why'>"+"".join(f"<div class='fo-why-line'>{x}</div>" for x in why_lines)+"</div>",unsafe_allow_html=True)

st.markdown("<div class='fo-section'>OPTION DETAILS</div>", unsafe_allow_html=True)
if decision != "NO TRADE" and best_plan:
    st.markdown(f"""
    <div class="fo-why"><div class="fo-why-line"><b>{decision}</b> · {best_plan['strike']:.0f} {'CE' if best_plan['side']=='CE' else 'PE'} · PoP {best_plan['pop']:.1f}% · Delta {safe_float(best_plan['delta']):.2f} · IV {safe_float(best_plan['iv']):.1f}% · OI {fmt_num(best_plan['oi'])} · Volume {fmt_num(best_plan['volume'])}</div></div>
    """,unsafe_allow_html=True)
else:
    st.markdown("<div class='fo-why'><div class='fo-why-line' style='color:#98a2b3;text-align:center;'>No option is currently selected for execution.</div></div>",unsafe_allow_html=True)

st.markdown(f"""
<div class="fo-footer">Live Upstox snapshot · Expiry {selected_expiry} · Updated {now_ist.strftime('%d-%b-%Y %H:%M:%S IST')}<br>PoP is a model input from the Upstox option chain; it is not a guaranteed win probability. Option selling can carry substantial risk.</div>
""",unsafe_allow_html=True)
