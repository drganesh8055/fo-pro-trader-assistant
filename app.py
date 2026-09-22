import gzip
import json
import threading
import time
from datetime import date, datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

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
# ============================================================

st.set_page_config(
    page_title="FO PRO Trader Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "https://api.upstox.com"
IST = ZoneInfo("Asia/Kolkata")


# ============================================================
# COMPACT 3:4 STYLE / RESPONSIVE UI
# ============================================================

st.markdown(
    """
<style>

.stApp {
    background:#f4f7fa;
}

.block-container {
    max-width:1080px !important;
    padding-top:0.65rem !important;
    padding-bottom:1.8rem !important;
    padding-left:1rem !important;
    padding-right:1rem !important;
}

/* ---------- Sidebar ---------- */

[data-testid="stSidebar"] {
    background:#f8fafc;
    border-right:1px solid #e5e9ef;
}

[data-testid="stSidebar"] .block-container {
    padding-top:1rem !important;
    max-width:none !important;
}

/* ---------- Header ---------- */

.topbar {
    background:linear-gradient(135deg,#0d2742 0%,#173f63 58%,#21577f 100%);
    color:#fff;
    border-radius:16px;
    padding:18px 20px;
    margin-bottom:14px;
    box-shadow:0 5px 18px rgba(13,39,66,.12);
}

.topbar-inner {
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:15px;
}

.topbar-title {
    font-size:25px;
    line-height:1.1;
    font-weight:900;
    letter-spacing:-.4px;
}

.topbar-sub {
    margin-top:5px;
    font-size:11px;
    opacity:.78;
}

.data-status-live,
.data-status-closed {
    min-width:150px;
    text-align:center;
    padding:12px 15px;
    border-radius:11px;
    color:white;
    font-size:11px;
    font-weight:900;
    letter-spacing:.6px;
}

.data-status-live {
    background:#16a34a;
    box-shadow:0 3px 12px rgba(22,163,74,.28);
}

.data-status-closed {
    background:#dc2626;
    box-shadow:0 3px 12px rgba(220,38,38,.22);
}

/* ---------- Instrument Hero ---------- */

.instrument-card {
    background:#fff;
    border:1px solid #e4e9ef;
    border-radius:15px;
    padding:15px 18px;
    margin-bottom:12px;
    box-shadow:0 2px 9px rgba(16,42,67,.035);
}

.instrument-name {
    font-size:21px;
    font-weight:900;
    color:#17212f;
}

.instrument-sub {
    color:#7b8794;
    font-size:11px;
    margin-top:3px;
}

.hero-price {
    font-size:26px;
    font-weight:900;
    color:#17212f;
    line-height:1;
}

.change-positive {
    color:#16803c;
    font-weight:800;
    font-size:11px;
}

.change-negative {
    color:#b4232f;
    font-weight:800;
    font-size:11px;
}

/* ---------- Section ---------- */

.section-heading {
    font-size:16px;
    font-weight:900;
    color:#182230;
    margin:18px 0 8px;
    letter-spacing:.15px;
}

/* ---------- Metric Cards ---------- */

.metric-card {
    background:#fff;
    border:1px solid #e5e9ef;
    border-radius:13px;
    padding:13px 14px;
    min-height:94px;
    box-shadow:0 2px 8px rgba(16,42,67,.035);
}

.metric-card span {
    display:block;
    color:#7b8794;
    font-size:9px;
    font-weight:900;
    letter-spacing:.65px;
}

.metric-card b {
    display:block;
    color:#17212f;
    font-size:18px;
    font-weight:900;
    margin-top:7px;
    line-height:1.1;
}

.metric-card small {
    display:block;
    color:#a0a8b2;
    font-size:9px;
    margin-top:6px;
}

.metric-positive b,
.metric-support b {
    color:#16803c;
}

.metric-negative b,
.metric-resistance b {
    color:#b4232f;
}

/* ---------- Decision ---------- */

.decision-card {
    background:#fff;
    border:1px solid #e2e7ed;
    border-radius:16px;
    padding:20px;
    box-shadow:0 3px 12px rgba(16,42,67,.045);
}

.decision-call {
    border-color:#b9e2c7;
    background:linear-gradient(180deg,#f3fbf6,#fff);
}

.decision-put {
    border-color:#efc1c6;
    background:linear-gradient(180deg,#fff6f7,#fff);
}

.decision-neutral {
    background:#fbfcfd;
}

.decision-main {
    text-align:center;
    font-size:28px;
    font-weight:950;
    line-height:1.1;
}

.decision-call .decision-main {
    color:#147a3d;
}

.decision-put .decision-main {
    color:#b4232f;
}

.decision-neutral .decision-main {
    color:#475467;
}

.decision-sub {
    text-align:center;
    color:#667085;
    font-size:11px;
    margin:7px 0 16px;
}

.decision-stat {
    background:#fff;
    border:1px solid #e8ebef;
    border-radius:10px;
    padding:10px;
    text-align:center;
}

.decision-stat span {
    display:block;
    color:#7b8794;
    font-size:9px;
    font-weight:900;
}

.decision-stat b {
    display:block;
    margin-top:5px;
    color:#17212f;
    font-size:17px;
}

/* ---------- Status ---------- */

.status-panel {
    border-radius:14px;
    padding:16px;
    border:1px solid #e2e7ed;
    background:#fff;
}

.status-green {
    border-color:#b9e2c7;
    background:#f4fbf6;
}

.status-yellow {
    border-color:#f1d79b;
    background:#fffbf1;
}

.status-red {
    border-color:#efc1c6;
    background:#fff6f7;
}

.status-grey {
    border-color:#dfe4ea;
    background:#f8fafc;
}

.status-title {
    text-align:center;
    font-size:19px;
    font-weight:950;
    margin-bottom:13px;
}

.status-green .status-title {
    color:#147a3d;
}

.status-yellow .status-title {
    color:#9a6700;
}

.status-red .status-title {
    color:#b4232f;
}

.status-grey .status-title {
    color:#475467;
}

.status-grid {
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:9px;
}

.status-box {
    background:#fff;
    border:1px solid #e7ebef;
    border-radius:9px;
    padding:10px;
    text-align:center;
}

.status-box span {
    display:block;
    font-size:9px;
    font-weight:900;
    color:#7b8794;
}

.status-box b {
    display:block;
    font-size:16px;
    color:#17212f;
    margin-top:5px;
}

.status-note {
    text-align:center;
    color:#667085;
    font-size:10px;
    line-height:1.5;
    margin-top:10px;
}

/* ---------- Checklist ---------- */

.check-card {
    background:#fff;
    border:1px solid #e5e9ef;
    border-radius:14px;
    padding:7px 15px;
}

.check-row {
    display:grid;
    grid-template-columns:1.35fr .8fr 2fr;
    gap:8px;
    align-items:center;
    padding:10px 2px;
    border-bottom:1px solid #eef1f4;
}

.check-row:last-of-type {
    border-bottom:0;
}

.check-label {
    font-size:11px;
    font-weight:800;
    color:#344054;
}

.check-state {
    font-size:10px;
    font-weight:900;
}

.check-detail {
    color:#98a2b3;
    font-size:9px;
}

.check-pass {
    color:#16803c;
}

.check-wait {
    color:#9a6700;
}

.check-fail {
    color:#b4232f;
}

.check-total {
    display:flex;
    justify-content:space-between;
    padding:11px 2px 5px;
    color:#7b8794;
    font-size:10px;
    font-weight:900;
}

.check-total b {
    color:#17212f;
    font-size:16px;
}

/* ---------- Plan ---------- */

.plan-card {
    background:#fff;
    border:1px solid #e3e8ee;
    border-radius:15px;
    padding:15px;
    box-shadow:0 2px 9px rgba(16,42,67,.035);
}

.plan-call {
    border-top:4px solid #16a34a;
}

.plan-put {
    border-top:4px solid #dc2626;
}

.plan-title {
    font-size:15px;
    font-weight:950;
    color:#17212f;
}

.plan-call .plan-title {
    color:#147a3d;
}

.plan-put .plan-title {
    color:#b4232f;
}

.plan-strike {
    font-size:22px;
    font-weight:950;
    margin:6px 0 12px;
    color:#17212f;
}

.plan-active {
    border:1px solid #b9e2c7;
    background:#f3fbf6;
    border-radius:8px;
    padding:7px;
    text-align:center;
    font-size:9px;
    font-weight:900;
    color:#147a3d;
    margin-bottom:10px;
}

.plan-reference {
    border:1px solid #f1d79b;
    background:#fffbf1;
    border-radius:8px;
    padding:7px;
    text-align:center;
    font-size:9px;
    font-weight:900;
    color:#9a6700;
    margin-bottom:10px;
}

.plan-metric {
    background:#f8fafc;
    border-radius:9px;
    padding:9px;
    min-height:63px;
}

.plan-metric span {
    display:block;
    color:#7b8794;
    font-size:8px;
    font-weight:900;
}

.plan-metric b {
    display:block;
    color:#17212f;
    font-size:14px;
    margin-top:5px;
}

.plan-status {
    margin-top:10px;
    padding:8px;
    text-align:center;
    border-radius:8px;
    font-size:9px;
    font-weight:900;
}

/* ---------- Entry / Exit ---------- */

.entry-card {
    background:#fff;
    border:1px solid #e5e9ef;
    border-radius:12px;
    padding:12px;
    min-height:82px;
}

.entry-card span {
    display:block;
    font-size:8px;
    font-weight:900;
    color:#7b8794;
    letter-spacing:.5px;
}

.entry-card b {
    display:block;
    font-size:16px;
    margin-top:6px;
    color:#17212f;
}

.entry-card small {
    display:block;
    font-size:9px;
    color:#98a2b3;
    margin-top:5px;
}

.exit-rule {
    background:#f8fafc;
    border:1px solid #e5e9ef;
    border-radius:11px;
    padding:11px 13px;
    margin-top:9px;
}

.exit-rule span {
    display:block;
    color:#7b8794;
    font-size:8px;
    font-weight:900;
}

.exit-rule b {
    display:block;
    color:#344054;
    font-size:10px;
    line-height:1.5;
    margin-top:4px;
}

/* ---------- Why ---------- */

.why-card {
    background:#fff;
    border:1px solid #e5e9ef;
    border-radius:14px;
    padding:7px 14px;
}

.why-item {
    padding:9px 2px;
    border-bottom:1px solid #eef1f4;
    color:#344054;
    font-size:10px;
    line-height:1.45;
}

.why-item:last-child {
    border-bottom:0;
}

.why-warning {
    color:#9a6700;
    background:#fffbf1;
    border-radius:7px;
    padding:8px;
    margin:5px 0;
}

/* ---------- OI Map ---------- */

.sr-map {
    display:grid;
    grid-template-columns:1fr 1.1fr 1fr;
    min-height:135px;
    background:#fff;
    border:1px solid #e5e9ef;
    border-radius:15px;
    overflow:hidden;
}

.sr-side {
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;
    text-align:center;
    padding:14px;
}

.sr-side span {
    font-size:8px;
    font-weight:900;
}

.sr-side b {
    font-size:21px;
    color:#17212f;
    margin:5px 0;
}

.sr-side small {
    color:#7b8794;
    font-size:9px;
}

.sr-resistance {
    background:#fff7f7;
}

.sr-resistance span {
    color:#b4232f;
}

.sr-support {
    background:#f4fbf6;
}

.sr-support span {
    color:#147a3d;
}

.sr-center {
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;
    gap:7px;
    border-left:1px dashed #dfe4ea;
    border-right:1px dashed #dfe4ea;
}

.room {
    color:#98a2b3;
    font-size:9px;
    font-weight:800;
}

.current-price {
    background:#f2f4f7;
    border:1px solid #e0e5ea;
    border-radius:18px;
    padding:7px 11px;
    color:#17212f;
    font-size:13px;
    font-weight:950;
}

/* ---------- Tabs ---------- */

.stTabs [data-baseweb="tab-list"] {
    gap:3px;
}

.stTabs [data-baseweb="tab"] {
    font-size:10px;
    font-weight:800;
    padding:7px 9px;
}

/* ---------- Streamlit controls ---------- */

.stButton > button {
    border-radius:9px;
    font-weight:800;
}

div[data-testid="stMetric"] {
    background:#fff;
    border:1px solid #e5e9ef;
    border-radius:10px;
    padding:8px;
}

div[data-testid="stMetricLabel"] {
    font-size:9px !important;
}

div[data-testid="stMetricValue"] {
    font-size:18px !important;
}

.stDataFrame {
    border-radius:10px;
    overflow:hidden;
}

/* ---------- Mobile ---------- */

@media (max-width:900px) {

    .block-container {
        max-width:760px !important;
        padding-left:.7rem !important;
        padding-right:.7rem !important;
    }

    .topbar-inner {
        align-items:flex-start;
    }

    .data-status-live,
    .data-status-closed {
        min-width:125px;
        font-size:9px;
        padding:9px;
    }

    .status-grid {
        grid-template-columns:repeat(2,1fr);
    }

    .check-row {
        grid-template-columns:1fr .9fr;
    }

    .check-detail {
        grid-column:1 / -1;
    }
}

@media (max-width:600px) {

    .block-container {
        padding-left:.55rem !important;
        padding-right:.55rem !important;
    }

    .topbar {
        padding:14px;
    }

    .topbar-title {
        font-size:19px;
    }

    .topbar-sub {
        font-size:9px;
    }

    .data-status-live,
    .data-status-closed {
        min-width:105px;
        font-size:8px;
        padding:8px;
    }

    .instrument-name {
        font-size:17px;
    }

    .hero-price {
        font-size:22px;
    }

    .decision-main {
        font-size:23px;
    }

    .sr-map {
        grid-template-columns:1fr;
    }

    .sr-center {
        min-height:75px;
        border-left:0;
        border-right:0;
        border-top:1px dashed #dfe4ea;
        border-bottom:1px dashed #dfe4ea;
    }

    .section-heading {
        font-size:14px;
    }
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# ERRORS
# ============================================================

class UpstoxError(RuntimeError):
    pass


class UpstoxRateLimitError(UpstoxError):

    def __init__(self, message, retry_after=30):
        super().__init__(message)
        self.retry_after = int(retry_after or 30)


# ============================================================
# API
# ============================================================

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
        "Upstox access token is not configured. Add "
        "UPSTOX_ACCESS_TOKEN under Streamlit → App settings → Secrets."
    )
    st.stop()


HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}


def api_get(path, params=None, timeout=20):

    global _LAST_API_REQUEST

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

        raise UpstoxError(
            f"Network error while contacting Upstox: {exc}"
        ) from exc

    if response.status_code == 429:

        retry_after = 30

        try:
            body = response.json()

            if isinstance(body, dict):
                retry_after = int(
                    body.get("retry_after") or 30
                )

        except Exception:
            pass

        raise UpstoxRateLimitError(
            f"Upstox rate limit reached. Please wait "
            f"about {retry_after} seconds before refreshing.",
            retry_after,
        )

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


# ============================================================
# FORMATTERS
# ============================================================

def safe_float(value, default=np.nan):

    try:
        return float(value)
    except Exception:
        return default


def fmt_price(value):

    x = safe_float(value)

    if not np.isfinite(x):
        return "—"

    if abs(x) < 1000:
        return f"₹{x:,.2f}"

    return f"₹{x:,.0f}"


def fmt_num(value):

    x = safe_float(value)

    if not np.isfinite(x):
        return "—"

    return f"{x:,.0f}"


def fmt_pct(value, decimals=1):

    x = safe_float(value)

    if not np.isfinite(x):
        return "—"

    return f"{x:.{decimals}f}%"


def alias_symbol(symbol):

    s = str(symbol).strip().upper().replace(" ", "")

    aliases = {
        "NIFTY50": "NIFTY",
        "NIFTYBANK": "BANKNIFTY",
        "NIFTYFIN": "FINNIFTY",
        "MIDCAPNIFTY": "MIDCPNIFTY",
    }

    return aliases.get(s, s)


# ============================================================
# SEARCH / CONTRACTS
# ============================================================

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
            f"No NSE instrument found for '{symbol}'."
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


@st.cache_data(ttl=300, show_spinner=False)
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
            "Upstox returned no option contracts."
        )

    return contracts


def available_expiries(contracts):

    today = datetime.now(IST).date().isoformat()

    return sorted(
        {
            str(item.get("expiry"))
            for item in contracts
            if item.get("expiry")
            and str(item.get("expiry")) >= today
        }
    )


# ============================================================
# OPTION CHAIN / QUOTE
# ============================================================

@st.cache_data(ttl=45, show_spinner=False)
def get_option_chain(
    underlying_key,
    expiry,
):

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
            f"No option-chain data returned for {expiry}."
        )

    return rows


@st.cache_data(ttl=30, show_spinner=False)
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


# ============================================================
# CANDLES
# ============================================================

def _candle_dataframe(candles):

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

    for col in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "oi",
    ]:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    return (
        df
        .dropna(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


@st.cache_data(ttl=90, show_spinner=False)
def get_intraday_candles(
    instrument_key,
    interval=5,
):

    path = (
        f"/v3/historical-candle/intraday/"
        f"{quote(instrument_key, safe='')}/minutes/{interval}"
    )

    payload = api_get(
        path,
        timeout=30,
    )

    return _candle_dataframe(
        payload.get("data", {}).get("candles", [])
    )


@st.cache_data(ttl=600, show_spinner=False)
def get_30m_candles(instrument_key):

    end_date = datetime.now(IST).date()
    start_date = end_date - timedelta(days=90)

    path = (
        f"/v3/historical-candle/"
        f"{quote(instrument_key, safe='')}/minutes/30/"
        f"{end_date.isoformat()}/{start_date.isoformat()}"
    )

    payload = api_get(
        path,
        timeout=30,
    )

    return _candle_dataframe(
        payload.get("data", {}).get("candles", [])
    )


@st.cache_data(ttl=1800, show_spinner=False)
def get_daily_candles(instrument_key):

    end_date = datetime.now(IST).date()
    start_date = end_date - timedelta(days=220)

    path = (
        f"/v3/historical-candle/"
        f"{quote(instrument_key, safe='')}/days/1/"
        f"{end_date.isoformat()}/{start_date.isoformat()}"
    )

    payload = api_get(
        path,
        timeout=30,
    )

    return _candle_dataframe(
        payload.get("data", {}).get("candles", [])
    )


# ============================================================
# TECHNICAL ENGINE
# ============================================================

def _rsi(close, period=14):

    delta = close.diff()

    gain = (
        delta.clip(lower=0)
        .ewm(alpha=1 / period, adjust=False)
        .mean()
    )

    loss = (
        (-delta.clip(upper=0))
        .ewm(alpha=1 / period, adjust=False)
        .mean()
    )

    rs = gain / loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


def technicals(df, spot):

    if df.empty or len(df) < 20:

        return {
            "rsi": 50.0,
            "ema20": spot,
            "ema50": spot,
            "atr": max(spot * .01, .01),
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

    ema20 = close.ewm(
        span=20,
        adjust=False,
    ).mean()

    ema50 = close.ewm(
        span=50,
        adjust=False,
    ).mean()

    previous_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(
        alpha=1 / 14,
        adjust=False,
    ).mean()

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where(
            (up_move > down_move) & (up_move > 0),
            up_move,
            0.0,
        ),
        index=df.index,
    )

    minus_dm = pd.Series(
        np.where(
            (down_move > up_move) & (down_move > 0),
            down_move,
            0.0,
        ),
        index=df.index,
    )

    atr_safe = atr.replace(0, np.nan)

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
        / (plus_di + minus_di).replace(0, np.nan)
    )

    adx = dx.ewm(
        alpha=1 / 14,
        adjust=False,
    ).mean()

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

    lookback = min(10, len(close) - 1)

    if lookback > 0 and close.iloc[-1 - lookback] != 0:

        momentum = (
            close.iloc[-1]
            / close.iloc[-1 - lookback]
            - 1
        ) * 100

    else:
        momentum = 0.0

    vol_base = (
        volume
        .rolling(20)
        .median()
        .iloc[-1]
    )

    volume_ratio = (
        volume.iloc[-1] / vol_base
        if vol_base and np.isfinite(vol_base)
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
        50,
    )

    a = safe_float(
        atr.iloc[-1],
        spot * .01,
    )

    adx_value = safe_float(
        adx.iloc[-1],
        0,
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
        "atr": max(a, spot * .001),
        "trend": trend,
        "adx": adx_value,
        "momentum": momentum,
        "volume_ratio": volume_ratio,
        "vwap": latest_vwap,
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
        return "Bullish", bullish

    if bearish >= 2 and bullish == 0:
        return "Bearish", bearish

    return "Mixed", max(bullish, bearish)


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

    score = 0
    alignment = 0

    for tf in [tf5, tf30, daily]:

        if tf.get("trend") == desired:

            score += 10
            alignment += 1

        elif tf.get("trend") == "Sideways":

            score += 3

        elif tf.get("trend") == opposite:

            score -= 8

    return float(
        np.clip(score, 0, 30)
    ), alignment


# ============================================================
# OI
# ============================================================

def oi_levels(chain, spot):

    valid = chain.dropna(
        subset=["Strike"]
    ).copy()

    if valid.empty or not np.isfinite(spot):

        return (
            spot,
            spot,
            np.nan,
            {
                "put_walls": [],
                "call_walls": [],
                "major_support": spot,
                "major_resistance": spot,
                "nearest_support": spot,
                "nearest_resistance": spot,
            },
        )

    band = valid[
        (valid["Strike"] >= spot * .90)
        & (valid["Strike"] <= spot * 1.10)
    ].copy()

    if band.empty:
        band = valid.copy()

    for col in [
        "PE OI",
        "CE OI",
        "PE Chg OI",
        "CE Chg OI",
    ]:

        band[col] = pd.to_numeric(
            band[col],
            errors="coerce",
        ).fillna(0)

    below = band[
        band["Strike"] <= spot
    ]

    above = band[
        band["Strike"] >= spot
    ]

    nearest_support = (
        float(below["Strike"].max())
        if not below.empty
        else float(band["Strike"].min())
    )

    nearest_resistance = (
        float(above["Strike"].min())
        if not above.empty
        else float(band["Strike"].max())
    )

    support_row = (
        below.loc[below["PE OI"].idxmax()]
        if not below.empty
        else band.loc[band["PE OI"].idxmax()]
    )

    resistance_row = (
        above.loc[above["CE OI"].idxmax()]
        if not above.empty
        else band.loc[band["CE OI"].idxmax()]
    )

    major_support = float(
        support_row["Strike"]
    )

    major_resistance = float(
        resistance_row["Strike"]
    )

    call_oi = float(
        band["CE OI"].sum()
    )

    put_oi = float(
        band["PE OI"].sum()
    )

    pcr = (
        put_oi / call_oi
        if call_oi > 0
        else np.nan
    )

    return (
        major_support,
        major_resistance,
        pcr,
        {
            "put_walls": band.nlargest(
                3,
                "PE OI",
            )[
                ["Strike", "PE OI", "PE Chg OI"]
            ].to_dict("records"),

            "call_walls": band.nlargest(
                3,
                "CE OI",
            )[
                ["Strike", "CE OI", "CE Chg OI"]
            ].to_dict("records"),

            "major_support": major_support,
            "major_resistance": major_resistance,
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,

            "support_room_pct":
                max(
                    (spot - major_support)
                    / max(spot, 1)
                    * 100,
                    0,
                ),

            "resistance_room_pct":
                max(
                    (major_resistance - spot)
                    / max(spot, 1)
                    * 100,
                    0,
                ),
        },
    )


# ============================================================
# NORMALIZE CHAIN
# ============================================================

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

                "CE Key":
                    call.get("instrument_key"),

                "CE LTP":
                    safe_float(
                        call_market.get("ltp")
                    ),

                "CE Bid":
                    safe_float(
                        call_market.get("bid_price")
                    ),

                "CE Ask":
                    safe_float(
                        call_market.get("ask_price")
                    ),

                "CE OI": call_oi,

                "CE Chg OI":
                    call_oi - call_prev_oi,

                "CE Volume":
                    safe_float(
                        call_market.get("volume"),
                        0,
                    ),

                "CE IV":
                    safe_float(
                        call_greeks.get("iv")
                    ),

                "CE Delta":
                    safe_float(
                        call_greeks.get("delta")
                    ),

                "CE PoP":
                    safe_float(
                        call_greeks.get("pop")
                    ),

                "PE Key":
                    put.get("instrument_key"),

                "PE LTP":
                    safe_float(
                        put_market.get("ltp")
                    ),

                "PE Bid":
                    safe_float(
                        put_market.get("bid_price")
                    ),

                "PE Ask":
                    safe_float(
                        put_market.get("ask_price")
                    ),

                "PE OI": put_oi,

                "PE Chg OI":
                    put_oi - put_prev_oi,

                "PE Volume":
                    safe_float(
                        put_market.get("volume"),
                        0,
                    ),

                "PE IV":
                    safe_float(
                        put_greeks.get("iv")
                    ),

                "PE Delta":
                    safe_float(
                        put_greeks.get("delta")
                    ),

                "PE PoP":
                    safe_float(
                        put_greeks.get("pop")
                    ),
            }
        )

    df = pd.DataFrame(records)

    if df.empty:
        return df

    return (
        df
        .dropna(subset=["Strike"])
        .sort_values("Strike")
        .reset_index(drop=True)
    )


def nearest_row(chain, strike):

    if (
        chain.empty
        or not np.isfinite(strike)
    ):
        return None

    idx = (
        chain["Strike"] - strike
    ).abs().idxmin()

    return chain.loc[idx]


# ============================================================
# OPTION SCORE
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
    support=None,
    resistance=None,
    oi_wall_info=None,
):

    if side == "CE":

        premium = safe_float(row["CE LTP"])
        delta = safe_float(row["CE Delta"])
        iv = safe_float(row["CE IV"])
        pop = safe_float(row["CE PoP"])
        chg_oi = safe_float(
            row["CE Chg OI"],
            0,
        )
        volume = safe_float(
            row["CE Volume"],
            0,
        )
        oi = safe_float(
            row["CE OI"],
            0,
        )
        bid = safe_float(row["CE Bid"])
        ask = safe_float(row["CE Ask"])

    else:

        premium = safe_float(row["PE LTP"])
        delta = safe_float(row["PE Delta"])
        iv = safe_float(row["PE IV"])
        pop = safe_float(row["PE PoP"])
        chg_oi = safe_float(
            row["PE Chg OI"],
            0,
        )
        volume = safe_float(
            row["PE Volume"],
            0,
        )
        oi = safe_float(
            row["PE OI"],
            0,
        )
        bid = safe_float(row["PE Bid"])
        ask = safe_float(row["PE Ask"])

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

    if tf5.get("trend") == desired:
        momentum_points += 5

    rsi = tf5.get("rsi", 50)

    if side == "CE":

        if 52 <= rsi <= 68:
            momentum_points += 3

        elif 50 <= rsi < 52:
            momentum_points += 1

        if tf5.get("momentum", 0) > 0:
            momentum_points += 3

    else:

        if 32 <= rsi <= 48:
            momentum_points += 3

        elif 48 < rsi <= 50:
            momentum_points += 1

        if tf5.get("momentum", 0) < 0:
            momentum_points += 3

    if tf5.get("adx", 0) >= 25:
        momentum_points += 4

    elif tf5.get("adx", 0) >= 20:
        momentum_points += 2

    momentum_points = min(
        momentum_points,
        15,
    )

    vwap = safe_float(
        tf5.get("vwap"),
        spot,
    )

    vwap_points = 0

    if np.isfinite(vwap) and vwap > 0:

        vwap_gap_pct = (
            (spot - vwap)
            / spot
            * 100
        )

        if side == "CE":

            if (
                spot > vwap
                and tf5.get("momentum", 0) > 0
            ):
                vwap_points = 10

            elif spot > vwap:
                vwap_points = 6

            elif spot >= vwap * .997:
                vwap_points = 2

        else:

            if (
                spot < vwap
                and tf5.get("momentum", 0) < 0
            ):
                vwap_points = 10

            elif spot < vwap:
                vwap_points = 6

            elif spot <= vwap * 1.003:
                vwap_points = 2

    else:
        vwap_gap_pct = 0

    pcr_points = 0

    if np.isfinite(pcr):

        if side == "CE":

            if .90 <= pcr <= 1.35:
                pcr_points = 10

            elif .80 <= pcr < .90:
                pcr_points = 5

        else:

            if .65 <= pcr <= 1.10:
                pcr_points = 10

            elif 1.10 < pcr <= 1.25:
                pcr_points = 5

    oi_points = 5 if chg_oi < 0 else 3 if chg_oi == 0 else 1

    quality = 0

    abs_delta = (
        abs(delta)
        if np.isfinite(delta)
        else np.nan
    )

    if np.isfinite(abs_delta):

        if .45 <= abs_delta <= .65:
            quality += 6

        elif (
            .40 <= abs_delta < .45
            or .65 < abs_delta <= .75
        ):
            quality += 4

        elif (
            .35 <= abs_delta < .40
            or .75 < abs_delta <= .80
        ):
            quality += 2

    spread_pct = (
        max(ask - bid, 0)
        / max((ask + bid) / 2, .01)
        * 100
        if (
            np.isfinite(ask)
            and np.isfinite(bid)
            and ask > 0
            and bid > 0
        )
        else 999
    )

    if spread_pct <= 1:
        quality += 5

    elif spread_pct <= 2:
        quality += 4

    elif spread_pct <= 3:
        quality += 2

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

    distance_pct = (
        abs(float(row["Strike"]) - spot)
        / max(spot, 1)
        * 100
    )

    if distance_pct <= 1:
        strike_points = 6

    elif distance_pct <= 2:
        strike_points = 5

    elif distance_pct <= 3:
        strike_points = 3

    elif distance_pct <= 5:
        strike_points = 1

    else:
        strike_points = 0

    room_points = 0
    room_pct = np.nan

    if (
        side == "CE"
        and np.isfinite(resistance)
    ):

        room_pct = max(
            (resistance - spot)
            / max(spot, 1)
            * 100,
            0,
        )

        if spot >= resistance:
            room_points = 4

        elif room_pct >= 2:
            room_points = 4

        elif room_pct >= 1:
            room_points = 2

    elif (
        side == "PE"
        and np.isfinite(support)
    ):

        room_pct = max(
            (spot - support)
            / max(spot, 1)
            * 100,
            0,
        )

        if spot <= support:
            room_points = 4

        elif room_pct >= 2:
            room_points = 4

        elif room_pct >= 1:
            room_points = 2

    strike_quality = (
        strike_points + room_points
    )

    pop_points = (
        float(
            np.clip(
                (pop - 55) / 3,
                0,
                10,
            )
        )
        if np.isfinite(pop)
        else 0
    )

    raw_score = (
        tf_points
        + momentum_points
        + vwap_points
        + pcr_points
        + oi_points
        + quality
        + strike_quality
        + pop_points
    )

    score = float(
        np.clip(
            raw_score / 110 * 100,
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
    oi_wall_info=None,
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
        support=support,
        resistance=resistance,
        oi_wall_info=oi_wall_info,
    )

    ask = safe_float(
        row[f"{side} Ask"]
    )

    ltp = safe_float(
        row[f"{side} LTP"]
    )

    entry = (
        ask
        if np.isfinite(ask) and ask > 0
        else ltp
    )

    if (
        not np.isfinite(entry)
        or entry <= 0
    ):
        return None

    risk_settings = {
        "Conservative": (
            .72,
            1.25,
            1.55,
        ),
        "Balanced": (
            .70,
            1.35,
            1.75,
        ),
        "Aggressive": (
            .65,
            1.50,
            2.00,
        ),
    }

    (
        sl_factor,
        target1_factor,
        target2_factor,
    ) = risk_settings[risk_profile]

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
        .01,
    )

    rr2 = (
        target2 - entry
    ) / max(
        entry - sl,
        .01,
    )

    atr = max(
        tf5.get("atr", spot * .01),
        spot * .001,
    )

    trigger_buffer = max(
        atr * .15,
        spot * .0015,
    )

    candle_confirmed = False
    volume_confirmed = False

    if side == "CE":

        trigger_level = (
            resistance
            + trigger_buffer
        )

        trigger_hit = (
            spot >= trigger_level
        )

        if trigger_hit:

            candle_confirmed = (
                tf5.get("trend")
                == "Bullish"
                and tf5.get("momentum", 0) > 0
                and tf5.get("rsi", 50) >= 52
            )

            volume_confirmed = (
                tf5.get(
                    "volume_ratio",
                    1,
                ) >= 1.10
            )

        trigger = (
            f"Enter only after spot breaks and sustains "
            f"above {fmt_price(trigger_level)} with 5m "
            "bullish confirmation and preferably above-average volume."
        )

        exit_rule = (
            f"Exit if spot loses support {fmt_price(support)} "
            f"or premium hits {fmt_price(sl)}. After Target 1, "
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

        if trigger_hit:

            candle_confirmed = (
                tf5.get("trend")
                == "Bearish"
                and tf5.get("momentum", 0) < 0
                and tf5.get("rsi", 50) <= 48
            )

            volume_confirmed = (
                tf5.get(
                    "volume_ratio",
                    1,
                ) >= 1.10
            )

        trigger = (
            f"Enter only after spot breaks and sustains "
            f"below {fmt_price(trigger_level)} with 5m "
            "bearish confirmation and preferably above-average volume."
        )

        exit_rule = (
            f"Exit if spot reclaims resistance {fmt_price(resistance)} "
            f"or premium hits {fmt_price(sl)}. After Target 1, "
            "book partial profit and trail."
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

    if scored["spread_pct"] > 3:
        hard_fail.append(
            "wide option spread"
        )

    if (
        not np.isfinite(scored["delta"])
        or not (
            .35
            <= abs(scored["delta"])
            <= .80
        )
    ):
        hard_fail.append(
            "poor delta"
        )

    if (
        not np.isfinite(scored["pop"])
        or scored["pop"] < 55
    ):
        hard_fail.append(
            "low Upstox PoP"
        )

    if scored["volume"] < 1000:
        hard_fail.append(
            "weak option liquidity"
        )

    if (
        not np.isfinite(scored["oi"])
        or scored["oi"] <= 0
    ):
        hard_fail.append(
            "no option OI"
        )

    vwap = safe_float(
        tf5.get("vwap"),
        spot,
    )

    if np.isfinite(vwap) and vwap > 0:

        if (
            side == "CE"
            and spot < vwap * .997
        ):
            hard_fail.append(
                "price below VWAP"
            )

        if (
            side == "PE"
            and spot > vwap * 1.003
        ):
            hard_fail.append(
                "price above VWAP"
            )

    if side == "CE":

        wall_room = (
            resistance - spot
        ) / max(spot, 1) * 100

        if (
            spot < resistance
            and wall_room < .50
        ):
            hard_fail.append(
                "resistance too close"
            )

    else:

        wall_room = (
            spot - support
        ) / max(spot, 1) * 100

        if (
            spot > support
            and wall_room < .50
        ):
            hard_fail.append(
                "support too close"
            )

    if not trigger_hit:

        trigger_state = (
            "WAIT FOR TRIGGER"
        )

    elif (
        not candle_confirmed
        or not volume_confirmed
    ):

        trigger_state = (
            "WAIT FOR CONFIRMATION"
        )

    else:

        trigger_state = (
            "READY"
            if not hard_fail
            else "NO TRADE"
        )

    readiness = (
        trigger_state
        if not hard_fail
        else "NO TRADE"
    )

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
# F&O SCANNER
# ============================================================

FNO_MASTER_URL = (
    "https://assets.upstox.com/"
    "market-quote/instruments/exchange/NSE.json.gz"
)


@st.cache_data(ttl=3600, show_spinner=False)
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
            "Unable to load the Upstox NSE F&O instrument list: "
            f"{exc}"
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

    today = (
        datetime.now(IST)
        .date()
        .isoformat()
    )

    universe = {}

    for item in records:

        if not isinstance(item, dict):
            continue

        if item.get("segment") != "NSE_FO":
            continue

        if item.get("instrument_type") not in {
            "CE",
            "PE",
            "FUT",
        }:
            continue

        if item.get("underlying_type") != "EQUITY":
            continue

        expiry = str(
            item.get("expiry", "")
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
                "underlying_symbol",
                "",
            )
        ).strip().upper()

        if not underlying_key or not symbol:
            continue

        current = universe.get(
            underlying_key
        )

        if (
            current is None
            or expiry_date < current["expiry"]
        ):

            universe[underlying_key] = {
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
    min_pop=75.0
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

            if idx > 1:
                time.sleep(.80)

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
                    raw.get("strike_price")
                )

                if not np.isfinite(strike):
                    continue

                for side, action in [
                    ("CE", "CALL BUY"),
                    ("PE", "PUT BUY"),
                ]:

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
                        market.get("ask_price")
                    )

                    bid = safe_float(
                        market.get("bid_price")
                    )

                    volume = safe_float(
                        market.get("volume"),
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
                        entry * .70,
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
                        "Stock": item["symbol"],
                        "Trade": action,
                        "Strike": strike,
                        "Expiry": item["expiry"],
                        "PoP": pop,
                        "Entry": entry,
                        "SL": sl,
                        "Target1": target1,
                        "Target2": target2,
                        "Exit":
                            "Exit at SL or Target 2; "
                            "trail after Target 1",
                        "LTP": ltp,
                        "Bid": bid,
                        "Ask": ask,
                        "Delta": delta,
                        "IV": iv,
                        "Volume": volume,
                        "OI": oi,
                        "distance": distance,
                    }

                    if (
                        best_for_stock is None
                        or (
                            candidate["PoP"],
                            candidate["Volume"],
                            -candidate["distance"],
                        )
                        >
                        (
                            best_for_stock["PoP"],
                            best_for_stock["Volume"],
                            -best_for_stock["distance"],
                        )
                    ):

                        best_for_stock = candidate

            if best_for_stock:
                candidates.append(
                    best_for_stock
                )

            scanned += 1

        except UpstoxRateLimitError:
            progress.empty()
            raise

        except Exception:
            failed += 1

        progress.progress(
            idx / max(
                len(universe),
                1,
            ),
            text=(
                f"Scanning F&O market: "
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
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "### 🔥 Top 5 F&O PoP Scanner"
    )

    st.caption(
        "Full NSE equity F&O scan • PoP > 75%"
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
            ] = datetime.now(
                IST
            ).strftime("%H:%M:%S")

        except UpstoxRateLimitError as exc:

            st.session_state[
                "fno_pop_results"
            ] = []

            st.error(
                f"⏳ Upstox rate limit reached. "
                f"Wait about {exc.retry_after} seconds."
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
            f"Top {len(pop_results)} trades • PoP > 75%"
        )

        if scan_info:

            total, scanned, failed = scan_info

            st.caption(
                f"Scanned {scanned}/{total} • "
                f"{failed} unavailable"
            )

        if scan_time:

            st.caption(
                f"Last scan: {scan_time} IST"
            )

        scanner_display = pd.DataFrame(
            [
                {
                    "Stock": row["Stock"],
                    "Trade": row["Trade"],
                    "Strike": int(
                        row["Strike"]
                    ),
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
                    "T1":
                        fmt_price(
                            row["Target1"]
                        ),
                    "T2":
                        fmt_price(
                            row["Target2"]
                        ),
                }
                for row in pop_results
            ]
        )

        st.dataframe(
            scanner_display,
            use_container_width=True,
            hide_index=True,
            height=min(
                350,
                58
                + len(scanner_display) * 50,
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

    symbol_default = st.session_state.get(
        "symbol",
        "KOTAKBANK",
    )

    symbol_input = st.text_input(
        "Stock / Index",
        value=symbol_default,
        placeholder=(
            "KOTAKBANK, HDFCBANK, NIFTY"
        ),
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
            "Auto refresh every 60 seconds",
            value=False,
        )

        if auto_refresh:

            st_autorefresh(
                interval=60_000,
                key="upstox_live_refresh",
            )

    st.divider()

    st.caption(
        "LIVE DATA • Powered by Upstox"
    )

    st.caption(
        "No simulated market values are used."
    )


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
        symbol_input or "KOTAKBANK",
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
                "Upstox did not return an upcoming "
                "F&O expiry for this instrument."
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
                "Upstox returned an empty or "
                "invalid option chain."
            )

        quote_data = get_quote(
            underlying_key
        )

        spot = safe_float(
            quote_data.get("last_price")
        )

        if not np.isfinite(spot) or spot <= 0:

            raise UpstoxError(
                "Upstox returned an invalid "
                "underlying price."
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

except UpstoxRateLimitError as exc:

    st.error(
        f"⏳ Upstox rate limit reached. "
        f"Please wait about {exc.retry_after} seconds "
        "before refreshing."
    )

    st.stop()

except UpstoxError as exc:

    st.error(str(exc))
    st.stop()

except Exception as exc:

    st.error(
        f"Unexpected error while loading live data: {exc}"
    )

    st.stop()


# ============================================================
# ANALYSIS
# ============================================================

support, resistance, pcr, oi_wall_info = oi_levels(
    chain,
    spot,
)

if chain.empty:

    st.error(
        "No usable option-chain rows are available."
    )

    st.stop()


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
    max(0, atm_index - 5):
    min(len(chain), atm_index + 6)
]


ce_candidates = []
pe_candidates = []


for _, row in candidate_rows.iterrows():

    ce_scored = score_option(
        row,
        "CE",
        spot,
        pcr,
        tf5,
        tf30,
        daily_tech,
        chain,
        support=support,
        resistance=resistance,
        oi_wall_info=oi_wall_info,
    )

    pe_scored = score_option(
        row,
        "PE",
        spot,
        pcr,
        tf5,
        tf30,
        daily_tech,
        chain,
        support=support,
        resistance=resistance,
        oi_wall_info=oi_wall_info,
    )

    ce_candidates.append(
        (ce_scored, row)
    )

    pe_candidates.append(
        (pe_scored, row)
    )


def candidate_key(item):

    scored, _ = item

    abs_delta = abs(
        safe_float(
            scored.get("delta"),
            0,
        )
    )

    spread = safe_float(
        scored.get("spread_pct"),
        999,
    )

    volume = safe_float(
        scored.get("volume"),
        0,
    )

    distance = safe_float(
        scored.get("distance_pct"),
        999,
    )

    delta_fit = -abs(
        abs_delta - .55
    )

    return (
        scored["score"],
        delta_fit,
        -spread,
        np.log1p(
            max(volume, 0)
        ),
        -distance,
    )


best_ce_scored, best_ce_row = max(
    ce_candidates,
    key=candidate_key,
    default=(
        {"score": 0},
        None,
    ),
)

best_pe_scored, best_pe_row = max(
    pe_candidates,
    key=candidate_key,
    default=(
        {"score": 0},
        None,
    ),
)


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
    oi_wall_info,
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
    oi_wall_info,
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


overall_direction, overall_alignment = overall_trend(
    tf5,
    tf30,
    daily_tech,
)


# ============================================================
# DECISION
# ============================================================

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
        best_score * .70
        + (
            best_alignment / 3
        ) * 20
        + (
            5
            if overall_direction
            in {"Bullish", "Bearish"}
            else 0
        ),
        0,
        100,
    )
)


updated = quote_data.get(
    "timestamp",
    datetime.now(IST).isoformat(),
)


# ============================================================
# UI HELPERS
# ============================================================

def num_or_dash(
    value,
    decimals=2,
):

    x = safe_float(value)

    if not np.isfinite(x):
        return "—"

    return f"{x:.{decimals}f}"


def status_class(value):

    value = str(value).upper()

    if (
        "READY" in value
        or "PASS" in value
        or "BUY" in value
    ):
        return "status-green"

    if (
        "WAIT" in value
        or "CAUTION" in value
    ):
        return "status-yellow"

    if (
        "NO TRADE" in value
        or "FAIL" in value
    ):
        return "status-red"

    return "status-grey"


def check_row(
    label,
    state,
    detail,
):

    if state == "PASS":

        icon = "🟢"
        css = "check-pass"

    elif state == "WAIT":

        icon = "🟡"
        css = "check-wait"

    else:

        icon = "🔴"
        css = "check-fail"

    return (
        "<div class='check-row'>"
        f"<span class='check-label'>{label}</span>"
        f"<strong class='check-state {css}'>"
        f"{icon} {state}</strong>"
        f"<small class='check-detail'>{detail}</small>"
        "</div>"
    )


# ============================================================
# MARKET STATUS
# ============================================================

market_now = datetime.now(IST)

market_open = (
    market_now.weekday() < 5
    and (
        market_now.hour,
        market_now.minute,
    ) >= (9, 15)
    and (
        market_now.hour,
        market_now.minute,
    ) < (15, 30)
)


# ============================================================
# HEADER
# ============================================================

status_text = (
    "● LIVE DATA"
    if market_open
    else "● MARKET CLOSED"
)

status_class_name = (
    "data-status-live"
    if market_open
    else "data-status-closed"
)

st.markdown(
    f"""
<div class="topbar">
    <div class="topbar-inner">
        <div>
            <div class="topbar-title">
                📊 FO PRO Trader Assistant
            </div>
            <div class="topbar-sub">
                Options Analysis • Live Upstox Market Data
            </div>
        </div>
        <div class="{status_class_name}">
            {status_text}
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# INSTRUMENT HERO
# ============================================================

h1, h2, h3 = st.columns(
    [2.2, 1, 1]
)

with h1:

    st.markdown(
        f"""
<div class="instrument-card">
    <div class="instrument-name">
        {symbol} — F&O Options Analysis
    </div>
    <div class="instrument-sub">
        Live underlying • Multi-timeframe confirmation • Option-chain analysis
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

with h2:

    change_class = (
        "change-positive"
        if net_change >= 0
        else "change-negative"
    )

    st.markdown(
        f"""
<div class="instrument-card">
    <div class="instrument-sub">
        LAST TRADED
    </div>
    <div class="hero-price">
        {fmt_price(spot)}
    </div>
    <div class="{change_class}">
        {net_change:+.2f} ({change_pct:+.2f}%)
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

with h3:

    st.markdown(
        f"""
<div class="instrument-card">
    <div class="instrument-sub">
        DATA STATUS
    </div>
    <div class="{status_class_name}">
        {status_text}
    </div>
    <div class="instrument-sub">
        Expiry {selected_expiry}
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# MARKET SNAPSHOT
# ============================================================

st.markdown(
    "<div class='section-heading'>📊 MARKET SNAPSHOT</div>",
    unsafe_allow_html=True,
)


def metric_html(
    label,
    value,
    note,
    css="",
):

    return (
        f"<div class='metric-card {css}'>"
        f"<span>{label}</span>"
        f"<b>{value}</b>"
        f"<small>{note}</small>"
        "</div>"
    )


m1, m2, m3 = st.columns(3)

with m1:

    st.markdown(
        metric_html(
            "LAST PRICE",
            fmt_price(spot),
            "LIVE PRICE",
        ),
        unsafe_allow_html=True,
    )

with m2:

    bias_css = (
        "metric-positive"
        if tech["trend"] == "Bullish"
        else "metric-negative"
        if tech["trend"] == "Bearish"
        else ""
    )

    st.markdown(
        metric_html(
            "MARKET BIAS",
            tech["trend"],
            "DAILY TREND",
            bias_css,
        ),
        unsafe_allow_html=True,
    )

with m3:

    pcr_display = (
        f"{pcr:.2f}"
        if np.isfinite(pcr)
        else "—"
    )

    st.markdown(
        metric_html(
            "PCR",
            pcr_display,
            "PUT / CALL OI",
        ),
        unsafe_allow_html=True,
    )


m4, m5, m6 = st.columns(3)

with m4:

    st.markdown(
        metric_html(
            "SUPPORT",
            fmt_price(support),
            "PUT OI WALL",
            "metric-support",
        ),
        unsafe_allow_html=True,
    )

with m5:

    st.markdown(
        metric_html(
            "RESISTANCE",
            fmt_price(resistance),
            "CALL OI WALL",
            "metric-resistance",
        ),
        unsafe_allow_html=True,
    )

with m6:

    st.markdown(
        metric_html(
            "RSI",
            f"{tech['rsi']:.1f}",
            "DAILY RSI",
        ),
        unsafe_allow_html=True,
    )


# ============================================================
# TRADE DECISION
# ============================================================

st.markdown(
    "<div class='section-heading'>🎯 TRADE DECISION</div>",
    unsafe_allow_html=True,
)


if decision == "CALL BUY":
    decision_icon = "🟢"
    decision_class = "decision-call"

elif decision == "PUT BUY":
    decision_icon = "🔴"
    decision_class = "decision-put"

elif "WAIT" in decision:
    decision_icon = "🟡"
    decision_class = "decision-neutral"

else:
    decision_icon = "⚪"
    decision_class = "decision-neutral"


decision_sub = {
    "CALL BUY":
        "Bullish conditions aligned — follow the entry trigger.",
    "PUT BUY":
        "Bearish conditions aligned — follow the entry trigger.",
    "WAIT FOR TRIGGER":
        "Setup is developing. Wait for the trigger before entry.",
    "WAIT FOR CONFIRMATION":
        "Trigger reached. Wait for confirmation before entry.",
    "NO TRADE":
        "Conditions are not sufficiently aligned for a valid setup.",
}.get(
    decision,
    "Review live market conditions before trading.",
)


st.markdown(
    f"""
<div class="decision-card {decision_class}">
    <div class="decision-main">
        {decision_icon} {decision}
    </div>

    <div class="decision-sub">
        {decision_sub}
    </div>

    <div class="decision-stats">
        <div class="decision-stat">
            <span>CALL SCORE</span>
            <b>{ce_score:.0f}/100</b>
        </div>

        <div class="decision-stat">
            <span>PUT SCORE</span>
            <b>{pe_score:.0f}/100</b>
        </div>

        <div class="decision-stat">
            <span>TREND</span>
            <b>{overall_direction.upper()}</b>
        </div>

        <div class="decision-stat">
            <span>CONFIDENCE</span>
            <b>{confidence}/100</b>
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# TRADE STATUS
# ============================================================

st.markdown(
    "<div class='section-heading'>🚦 TRADE STATUS</div>",
    unsafe_allow_html=True,
)


if best_plan:

    if decision in {
        "CALL BUY",
        "PUT BUY",
    }:

        current_status = decision

    elif decision in {
        "WAIT FOR TRIGGER",
        "WAIT FOR CONFIRMATION",
    }:

        current_status = decision

    else:

        current_status = "NO TRADE"

    title_map = {
        "CALL BUY":
            "🟢 CALL BUY — ACTIONABLE",
        "PUT BUY":
            "🔴 PUT BUY — ACTIONABLE",
        "WAIT FOR TRIGGER":
            "🟡 WAIT FOR TRIGGER — DO NOT ENTER",
        "WAIT FOR CONFIRMATION":
            "🟡 WAIT FOR CONFIRMATION — DO NOT ENTER",
        "NO TRADE":
            "🔴 NO TRADE — DO NOT ENTER",
    }

    trigger_distance = abs(
        spot
        - best_plan["trigger_level"]
    )

    if current_status == "NO TRADE":

        status_note = (
            "Do not enter this setup now. "
            "The current candidate is shown for reference only. "
            "Wait for the engine to produce an actionable state."
        )

    else:

        status_note = best_plan[
            "trigger"
        ]

    st.markdown(
        f"""
<div class="status-panel {status_class(current_status)}">

    <div class="status-title">
        {title_map[current_status]}
    </div>

    <div class="status-grid">

        <div class="status-box">
            <span>CURRENT PRICE</span>
            <b>{fmt_price(spot)}</b>
        </div>

        <div class="status-box">
            <span>TRIGGER</span>
            <b>{fmt_price(best_plan["trigger_level"])}</b>
        </div>

        <div class="status-box">
            <span>DISTANCE</span>
            <b>{fmt_price(trigger_distance)}</b>
        </div>

    </div>

    <div class="status-note">
        {status_note}
    </div>

</div>
""",
        unsafe_allow_html=True,
    )

else:

    st.markdown(
        """
<div class="status-panel status-grey">
    <div class="status-title">
        ⚪ NO VALID PLAN
    </div>
    <div class="status-note">
        No usable option contract is currently available.
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# CHECKLIST
# ============================================================

direction_pass = (
    overall_direction
    in {"Bullish", "Bearish"}
)

mtf_pass = (
    overall_alignment >= 2
)

oi_pass = (
    np.isfinite(support)
    and np.isfinite(resistance)
    and support < spot < resistance
)

vwap_value = safe_float(
    tf5.get("vwap"),
    spot,
)

if best_plan:

    if best_plan["side"] == "CE":

        vwap_pass = (
            spot >= vwap_value * .997
        )

    else:

        vwap_pass = (
            spot <= vwap_value * 1.003
        )

else:

    vwap_pass = False


breakout_state = (
    "PASS"
    if (
        best_plan
        and best_plan.get("trigger_hit")
        and best_plan.get("candle_confirmed")
        and best_plan.get("volume_confirmed")
    )
    else "WAIT"
)


st.markdown(
    "<div class='section-heading'>🧠 TRADE CHECKLIST</div>",
    unsafe_allow_html=True,
)


check_html = (
    check_row(
        "Market Direction",
        "PASS"
        if direction_pass
        else "FAIL",
        f"{overall_direction} market bias",
    )

    + check_row(
        "Multi-Timeframe",
        "PASS"
        if mtf_pass
        else "FAIL",
        f"{overall_alignment}/3 timeframes aligned",
    )

    + check_row(
        "OI Structure",
        "PASS"
        if oi_pass
        else "FAIL",
        f"Support {fmt_price(support)} • "
        f"Resistance {fmt_price(resistance)}",
    )

    + check_row(
        "VWAP",
        "PASS"
        if vwap_pass
        else "FAIL",
        f"5m VWAP {fmt_price(vwap_value)}",
    )

    + check_row(
        "Breakout Confirmation",
        breakout_state,
        "Trigger + 5m momentum + volume",
    )
)


check_overall = sum(
    [
        direction_pass,
        mtf_pass,
        oi_pass,
        vwap_pass,
        breakout_state == "PASS",
    ]
)


st.markdown(
    f"""
<div class="check-card">
    {check_html}

    <div class="check-total">
        <span>OVERALL CHECKLIST</span>
        <b>{check_overall}/5</b>
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# PLAN RENDERER
# ============================================================

def render_plan(
    plan,
    label,
    active=False,
    candidate=False,
):

    if not plan:

        st.info(
            f"{label} BUY — No valid option plan."
        )

        return

    side = plan["side"]

    icon = (
        "🟢"
        if side == "CE"
        else "🔴"
    )

    contract = (
        "CE"
        if side == "CE"
        else "PE"
    )

    readiness = str(
        plan.get(
            "readiness",
            "NO TRADE",
        )
    )

    plan_class = (
        "plan-call"
        if side == "CE"
        else "plan-put"
    )

    notice = ""

    if active:

        notice = (
            "<div class='plan-active'>"
            "★ ACTIVE TRADE"
            "</div>"
        )

    elif candidate:

        notice = (
            "<div class='plan-reference'>"
            "◉ CANDIDATE ONLY — DO NOT ENTER"
            "</div>"
        )

    status_css = status_class(
        readiness
    )

    st.markdown(
        f"""
<div class="plan-card {plan_class}">

    <div class="plan-title">
        {icon} {label} BUY
    </div>

    <div class="plan-strike">
        {plan["strike"]:.0f} {contract}
    </div>

    {notice}

</div>
""",
        unsafe_allow_html=True,
    )

    p1, p2, p3, p4 = st.columns(4)

    plan_values = [
        (
            "ENTRY",
            fmt_price(
                plan["entry"]
            ),
        ),
        (
            "STOP LOSS",
            fmt_price(
                plan["sl"]
            ),
        ),
        (
            "TARGET 1",
            fmt_price(
                plan["target1"]
            ),
        ),
        (
            "TARGET 2",
            fmt_price(
                plan["target2"]
            ),
        ),
    ]

    for col, (
        title,
        value,
    ) in zip(
        [p1, p2, p3, p4],
        plan_values,
    ):

        with col:

            st.markdown(
                f"""
<div class="plan-metric">
    <span>{title}</span>
    <b>{value}</b>
</div>
""",
                unsafe_allow_html=True,
            )

    q1, q2, q3, q4 = st.columns(4)

    quality_values = [
        (
            "POP",
            f"{num_or_dash(plan['pop'],1)}%",
        ),
        (
            "DELTA",
            num_or_dash(
                plan["delta"],
                2,
            ),
        ),
        (
            "IV",
            f"{num_or_dash(plan['iv'],1)}%",
        ),
        (
            "R:R T2",
            f"1:{num_or_dash(plan['rr2'],2)}",
        ),
    ]

    for col, (
        title,
        value,
    ) in zip(
        [q1, q2, q3, q4],
        quality_values,
    ):

        with col:

            st.markdown(
                f"""
<div class="plan-metric">
    <span>{title}</span>
    <b>{value}</b>
</div>
""",
                unsafe_allow_html=True,
            )

    if readiness == "READY":

        st.success(
            "🟢 READY"
        )

    elif "WAIT" in readiness:

        st.warning(
            f"🟡 {readiness}"
        )

    else:

        st.error(
            f"🔴 {readiness}"
        )


# ============================================================
# TRADE PLAN
# ============================================================

st.markdown(
    "<div class='section-heading'>🎯 TRADE PLAN</div>",
    unsafe_allow_html=True,
)


active_side = (
    "CE"
    if decision == "CALL BUY"
    else "PE"
    if decision == "PUT BUY"
    else None
)

candidate_side = (
    best_plan["side"]
    if best_plan
    else None
)


p1, p2 = st.columns(2)

with p1:

    render_plan(
        ce_plan,
        "CALL",
        active=active_side == "CE",
        candidate=(
            candidate_side == "CE"
            and active_side is None
        ),
    )

with p2:

    render_plan(
        pe_plan,
        "PUT",
        active=active_side == "PE",
        candidate=(
            candidate_side == "PE"
            and active_side is None
        ),
    )


# ============================================================
# ENTRY / EXIT
# ============================================================

st.markdown(
    "<div class='section-heading'>📍 ENTRY / EXIT</div>",
    unsafe_allow_html=True,
)


if (
    best_plan
    and decision in {
        "CALL BUY",
        "PUT BUY",
    }
):

    entry_distance = abs(
        spot
        - best_plan["trigger_level"]
    )

    entry_values = [
        (
            "CURRENT PRICE",
            fmt_price(spot),
            "Underlying",
        ),
        (
            "ENTRY TRIGGER",
            fmt_price(
                best_plan[
                    "trigger_level"
                ]
            ),
            f"Distance {fmt_price(entry_distance)}",
        ),
        (
            "STOP LOSS",
            fmt_price(
                best_plan["sl"]
            ),
            "Option premium",
        ),
        (
            "TARGET 1",
            fmt_price(
                best_plan["target1"]
            ),
            "Partial exit",
        ),
        (
            "TARGET 2",
            fmt_price(
                best_plan["target2"]
            ),
            "Final target",
        ),
    ]

    e1, e2, e3 = st.columns(3)

    for col, (
        title,
        value,
        note,
    ) in zip(
        [e1, e2, e3],
        entry_values[:3],
    ):

        with col:

            st.markdown(
                f"""
<div class="entry-card">
    <span>{title}</span>
    <b>{value}</b>
    <small>{note}</small>
</div>
""",
                unsafe_allow_html=True,
            )

    e4, e5 = st.columns(2)

    for col, (
        title,
        value,
        note,
    ) in zip(
        [e4, e5],
        entry_values[3:],
    ):

        with col:

            st.markdown(
                f"""
<div class="entry-card">
    <span>{title}</span>
    <b>{value}</b>
    <small>{note}</small>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown(
        f"""
<div class="exit-rule">
    <span>EXIT RULE</span>
    <b>{best_plan["exit"]}</b>
</div>
""",
        unsafe_allow_html=True,
    )

else:

    st.warning(
        "NO TRADE: entry, stop-loss and targets are "
        "reference levels only. Wait for CALL BUY or PUT BUY."
    )


# ============================================================
# WHY TRADE / WHY NO TRADE
# ============================================================

title = (
    "💡 WHY THIS TRADE?"
    if decision in {
        "CALL BUY",
        "PUT BUY",
    }
    else "💡 WHY NO TRADE?"
)

st.markdown(
    f"<div class='section-heading'>{title}</div>",
    unsafe_allow_html=True,
)


why_items = []


if best_plan:

    side_name = (
        "CALL"
        if best_plan["side"] == "CE"
        else "PUT"
    )

    if decision in {
        "CALL BUY",
        "PUT BUY",
    }:

        why_items.extend(
            [
                f"{tf5['trend']} 5m trend supports the {side_name} direction.",

                f"{tf30['trend']} 30m trend and "
                f"{daily_tech['trend']} daily trend are "
                "included in the multi-timeframe confirmation.",

                f"Price is "
                f"{'above' if spot >= vwap_value else 'below'} "
                f"the 5m VWAP at {fmt_price(vwap_value)}.",

                f"OI structure shows support at "
                f"{fmt_price(support)} and resistance at "
                f"{fmt_price(resistance)}.",

                f"Option PoP is "
                f"{num_or_dash(best_plan['pop'],1)}% "
                f"with Delta "
                f"{num_or_dash(best_plan['delta'],2)}.",

                f"Option spread is "
                f"{num_or_dash(best_plan['spread_pct'],1)}% "
                f"with volume "
                f"{fmt_num(best_plan['volume'])}.",
            ]
        )

    else:

        why_items.extend(
            [
                f"The {side_name} is only the strongest "
                "current candidate and is NOT an approved entry.",

                f"Market direction is "
                f"{overall_direction} and "
                f"{overall_alignment}/3 timeframes align.",

                f"5m: {tf5['trend']} • "
                f"30m: {tf30['trend']} • "
                f"Daily: {daily_tech['trend']}.",

                f"Price is "
                f"{'above' if spot >= vwap_value else 'below'} "
                f"the 5m VWAP at {fmt_price(vwap_value)}.",

                f"OI support: {fmt_price(support)} • "
                f"OI resistance: {fmt_price(resistance)}.",

                f"Candidate PoP: "
                f"{num_or_dash(best_plan['pop'],1)}% • "
                f"Delta: "
                f"{num_or_dash(best_plan['delta'],2)}.",
            ]
        )

    if best_plan["fail_reasons"]:

        why_items.append(
            "⚠ "
            + "; ".join(
                best_plan["fail_reasons"]
            )
        )

else:

    why_items.append(
        "No valid option plan is currently available."
    )


why_html = ""

for item in why_items:

    warning = item.startswith("⚠")

    clean = item.lstrip("⚠ ")

    why_html += (
        f"<div class='why-item "
        f"{'why-warning' if warning else ''}'>"
        f"{'⚠' if warning else '✓'} {clean}"
        "</div>"
    )


st.markdown(
    f"""
<div class="why-card">
    {why_html}
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SUPPORT / RESISTANCE OI MAP
# ============================================================

st.markdown(
    "<div class='section-heading'>📍 SUPPORT / RESISTANCE + OI MAP</div>",
    unsafe_allow_html=True,
)


put_row = nearest_row(
    chain,
    support,
)

call_row = nearest_row(
    chain,
    resistance,
)


put_oi = (
    put_row["PE OI"]
    if put_row is not None
    else np.nan
)

call_oi = (
    call_row["CE OI"]
    if call_row is not None
    else np.nan
)


support_room = (
    max(
        (spot - support)
        / max(spot, 1)
        * 100,
        0,
    )
    if np.isfinite(support)
    else np.nan
)

resistance_room = (
    max(
        (resistance - spot)
        / max(spot, 1)
        * 100,
        0,
    )
    if np.isfinite(resistance)
    else np.nan
)


st.markdown(
    f"""
<div class="sr-map">

    <div class="sr-side sr-resistance">
        <span>🔴 CALL OI WALL</span>
        <b>{fmt_price(resistance)}</b>
        <small>OI {fmt_num(call_oi)}</small>
    </div>

    <div class="sr-center">
        <div class="room">
            +{num_or_dash(resistance_room,2)}%
        </div>

        <div class="current-price">
            ● {fmt_price(spot)}
        </div>

        <div class="room">
            -{num_or_dash(support_room,2)}%
        </div>
    </div>

    <div class="sr-side sr-support">
        <span>🟢 PUT OI WALL</span>
        <b>{fmt_price(support)}</b>
        <small>OI {fmt_num(put_oi)}</small>
    </div>

</div>
""",
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
# BEST TRADE
# ============================================================

with tab1:

    if decision == "NO TRADE":

        st.error(
            "⚪ NO TRADE — Current conditions "
            "do not meet the quality gate."
        )

    elif best_plan:

        icon = (
            "🟢"
            if best_plan["side"] == "CE"
            else "🔴"
        )

        st.success(
            f"{icon} {decision} • "
            f"{best_plan['strike']:.0f} "
            f"{'CE' if best_plan['side']=='CE' else 'PE'} • "
            f"Entry {fmt_price(best_plan['entry'])} • "
            f"SL {fmt_price(best_plan['sl'])} • "
            f"T1 {fmt_price(best_plan['target1'])} • "
            f"T2 {fmt_price(best_plan['target2'])}"
        )

    st.markdown(
        "### Engine Summary"
    )

    s1, s2, s3, s4 = st.columns(4)

    s1.metric(
        "CALL SCORE",
        f"{ce_score:.0f}/100",
    )

    s2.metric(
        "PUT SCORE",
        f"{pe_score:.0f}/100",
    )

    s3.metric(
        "ALIGNMENT",
        f"{overall_alignment}/3",
    )

    s4.metric(
        "CHECKLIST",
        f"{check_overall}/5",
    )


# ============================================================
# OPTION CHAIN
# ============================================================

with tab2:

    st.markdown(
        f"### Live Option Chain — {selected_expiry}"
    )

    view = chain.copy()

    display = pd.DataFrame(
        {
            "Strike":
                view["Strike"]
                .round(0)
                .astype("Int64"),

            "CE LTP":
                view["CE LTP"]
                .round(2),

            "CE OI":
                view["CE OI"]
                .round(0)
                .astype("Int64"),

            "CE Chg OI":
                view["CE Chg OI"]
                .round(0)
                .astype("Int64"),

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
                .astype("Int64"),

            "PE Chg OI":
                view["PE Chg OI"]
                .round(0)
                .astype("Int64"),

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
        .astype(float)
        - spot
    ).abs()

    display = (
        display
        .sort_values("_distance")
        .drop(columns="_distance")
        .head(15)
    )

    def style_chain(row):

        styles = [
            ""
            for _ in row.index
        ]

        try:

            strike = float(
                row["Strike"]
            )

            if (
                int(round(strike))
                == int(round(atm_strike))
            ):

                styles = [
                    "font-weight:700;"
                    for _ in row.index
                ]

            if (
                best_plan
                and int(round(strike))
                == int(
                    round(
                        best_plan["strike"]
                    )
                )
            ):

                styles = [
                    "font-weight:900;"
                    for _ in row.index
                ]

        except Exception:
            pass

        return styles

    styled_chain = (
        display.style.apply(
            style_chain,
            axis=1,
        )
    )

    st.dataframe(
        styled_chain,
        use_container_width=True,
        hide_index=True,
        height=500,
    )

    st.caption(
        "ATM and selected strikes are emphasized. "
        "CE/PE LTP, OI, Change OI, IV, Delta and PoP are shown."
    )


# ============================================================
# MARKET ANALYSIS
# ============================================================

with tab3:

    a1, a2, a3, a4 = st.columns(4)

    a1.metric(
        "EMA 20",
        fmt_price(
            daily_tech["ema20"]
        ),
    )

    a2.metric(
        "EMA 50",
        fmt_price(
            daily_tech["ema50"]
        ),
    )

    a3.metric(
        "ATR 14",
        fmt_price(
            daily_tech["atr"]
        ),
    )

    a4.metric(
        "5m VWAP",
        fmt_price(
            tf5["vwap"]
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
                "VWAP":
                    fmt_price(
                        tf5["vwap"]
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
                "VWAP":
                    fmt_price(
                        tf30["vwap"]
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
                "VWAP":
                    fmt_price(
                        daily_tech["vwap"]
                    ),
            },
        ]
    )

    st.dataframe(
        mtf,
        use_container_width=True,
        hide_index=True,
    )

    left, right = st.columns(2)

    with left:

        st.markdown(
            "### 🟢 Support / Put OI"
        )

        st.write(
            f"Major support: **{fmt_price(support)}**"
        )

        if put_row is not None:

            st.write(
                f"Put OI: **{fmt_num(put_row['PE OI'])}**"
            )

            st.write(
                f"Put Chg OI: **{fmt_num(put_row['PE Chg OI'])}**"
            )

    with right:

        st.markdown(
            "### 🔴 Resistance / Call OI"
        )

        st.write(
            f"Major resistance: **{fmt_price(resistance)}**"
        )

        if call_row is not None:

            st.write(
                f"Call OI: **{fmt_num(call_row['CE OI'])}**"
            )

            st.write(
                f"Call Chg OI: **{fmt_num(call_row['CE Chg OI'])}**"
            )

    if not candles.empty:

        chart = (
            candles
            .set_index("timestamp")
            [["close"]]
            .tail(80)
        )

        st.line_chart(
            chart,
            use_container_width=True,
        )


# ============================================================
# HOW ENGINE THINKS
# ============================================================

with tab4:

    st.markdown(
        "### Live-data decision framework"
    )

    st.markdown(
        """
**1. Market direction**

- Live underlying price
- 5-minute trend
- 30-minute trend
- Daily trend
- EMA20 / EMA50
- RSI
- ADX
- Momentum
- Intraday VWAP

**2. Option-chain structure**

- Put OI
- Put Change in OI
- Call OI
- Call Change in OI
- PCR
- OI-derived support
- OI-derived resistance

**3. Option quality**

- LTP
- Bid / Ask
- Volume
- IV
- Delta
- Upstox PoP
- Spread
- Strike distance
- Room to OI wall

**4. Trade plan**

- Entry trigger
- Entry price
- Stop Loss
- Target 1
- Target 2
- Exit / invalidation
- Risk / Reward

**5. Quality gate**

- Minimum setup score: 72/100
- At least 2 of 3 timeframes must agree
- VWAP must support the direction
- Short-term trend conflict blocks the setup
- Delta must be within the acceptable range
- Option liquidity and spread are checked
- OI must be available
- Upstox PoP must be at least 55%
- Close OI walls can block a setup
- Breakout requires 5m confirmation
- The engine can return WAIT FOR TRIGGER
- The engine can return WAIT FOR CONFIRMATION
- The engine can return NO TRADE

The score is a rule-based quality measure. It is not a backtested win rate or guarantee of profit.
"""
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    f"Live Upstox snapshot • {symbol} • "
    f"Expiry {selected_expiry} • "
    f"Updated {updated} • "
    "Educational / decision-support use."
)
