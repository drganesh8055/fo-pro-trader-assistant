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
# FO PRO TRADER ASSISTANT — LIVE UPSTOX REST VERSION
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
# CSS
# ============================================================

st.markdown(
    """
<style>
.stApp {
    background:#f6f8fb;
}

.block-container {
    padding-top:1rem;
    padding-bottom:2rem;
    max-width:1500px;
}

.topbar {
    background:linear-gradient(100deg,#102a43,#1f4b73);
    padding:18px 24px;
    border-radius:14px;
    color:white;
    margin-bottom:18px;
}

.topbar-dashboard {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:18px;
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

.header-live,
.live-block,
.closed-block {
    color:#fff;
    padding:10px 16px;
    border-radius:9px;
    font-size:13px;
    font-weight:800;
    letter-spacing:.2px;
    text-align:center;
    white-space:nowrap;
}

.header-live {
    background:rgba(255,255,255,.14);
}

.live-block {
    background:#16a34a;
}

.closed-block {
    background:#dc2626;
}

.card {
    background:white;
    border:1px solid #e7ebf0;
    border-radius:14px;
    padding:18px;
    margin-bottom:16px;
    box-shadow:0 2px 8px rgba(16,42,67,.04);
}

.section-heading {
    font-size:19px;
    font-weight:850;
    color:#182230;
    margin:20px 0 10px;
}

.hero-price {
    font-size:29px;
    font-weight:850;
    line-height:1.05;
    color:#182230;
}

.metric-card,
.entry-card {
    background:#fff;
    border:1px solid #e7ebf0;
    border-radius:13px;
    padding:15px 14px;
    min-height:105px;
    box-shadow:0 2px 8px rgba(16,42,67,.035);
}

.metric-card span,
.entry-card span,
.decision-stats span,
.status-grid span,
.option-grid span,
.exit-rule span {
    display:block;
    font-size:10px;
    font-weight:800;
    color:#667085;
    letter-spacing:.55px;
}

.metric-card b,
.entry-card b {
    display:block;
    font-size:20px;
    color:#182230;
    margin-top:8px;
    line-height:1.15;
}

.metric-card small,
.entry-card small {
    display:block;
    color:#98a2b3;
    font-size:10px;
    margin-top:7px;
}

.metric-positive b,
.metric-support b {
    color:#147a3d;
}

.metric-negative b,
.metric-resistance b {
    color:#b4232f;
}

.metric-neutral b {
    color:#475467;
}

.decision-card {
    border-radius:16px;
    padding:23px 25px;
    border:1px solid #dfe5eb;
    background:#fff;
    box-shadow:0 3px 12px rgba(16,42,67,.055);
}

.decision-call {
    border-color:#bde5c9;
    background:linear-gradient(180deg,#f5fcf7,#fff);
}

.decision-put {
    border-color:#f2c5c8;
    background:linear-gradient(180deg,#fff7f7,#fff);
}

.decision-neutral {
    border-color:#dfe3e8;
    background:#fbfcfd;
}

.decision-main {
    font-size:32px;
    font-weight:900;
    text-align:center;
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
    margin:9px 0 20px;
    font-size:13px;
}

.decision-stats {
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:10px;
}

.decision-stats > div {
    background:rgba(255,255,255,.78);
    border:1px solid #edf0f3;
    border-radius:10px;
    padding:11px;
    text-align:center;
}

.decision-stats b {
    display:block;
    font-size:19px;
    margin-top:5px;
    color:#182230;
}

.status-panel {
    border-radius:14px;
    padding:18px 20px;
    border:1px solid #e4e7ec;
    background:#fff;
    box-shadow:0 2px 8px rgba(16,42,67,.035);
}

.status-green {
    border-color:#bde5c9;
    background:#f4fbf6;
}

.status-yellow {
    border-color:#f1d79b;
    background:#fffbf1;
}

.status-red {
    border-color:#f2c5c8;
    background:#fff6f6;
}

.status-grey {
    border-color:#dfe3e8;
    background:#f8fafc;
}

.status-title {
    font-size:22px;
    font-weight:900;
    text-align:center;
    margin-bottom:15px;
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
    gap:12px;
}

.status-grid > div {
    background:#fff;
    border:1px solid #e8ebef;
    border-radius:10px;
    padding:11px;
    text-align:center;
}

.status-grid b {
    display:block;
    font-size:18px;
    color:#182230;
    margin-top:5px;
}

.status-note {
    margin-top:12px;
    text-align:center;
    color:#667085;
    font-size:12px;
    line-height:1.5;
}

.check-card {
    background:#fff;
    border:1px solid #e7ebf0;
    border-radius:14px;
    padding:8px 18px;
    box-shadow:0 2px 8px rgba(16,42,67,.035);
}

.check-row {
    display:grid;
    grid-template-columns:1.35fr .8fr 2fr;
    align-items:center;
    gap:10px;
    padding:12px 3px;
    border-bottom:1px solid #eef0f2;
}

.check-row > span {
    font-weight:750;
    color:#344054;
    font-size:13px;
}

.check-row small {
    color:#98a2b3;
    font-size:11px;
}

.check-pass {
    color:#147a3d;
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
    align-items:center;
    padding:13px 3px 7px;
    font-size:12px;
    font-weight:850;
    color:#667085;
}

.check-total b {
    font-size:18px;
    color:#182230;
}

.option-card {
    border:1px solid #e5e7eb;
    border-radius:15px;
    background:#fff;
    padding:17px;
    box-shadow:0 2px 9px rgba(16,42,67,.035);
}

.option-call {
    border-top:4px solid #16a34a;
}

.option-put {
    border-top:4px solid #dc2626;
}

.option-selected {
    box-shadow:0 4px 16px rgba(16,42,67,.09);
}

.option-head {
    display:flex;
    justify-content:space-between;
    align-items:center;
    font-size:16px;
    font-weight:900;
    color:#182230;
}

.option-call .option-head > span:first-child {
    color:#147a3d;
}

.option-put .option-head > span:first-child {
    color:#b4232f;
}

.selected-tag {
    font-size:9px;
    background:#eef7f0;
    color:#147a3d;
    padding:5px 8px;
    border-radius:12px;
    letter-spacing:.4px;
}

.option-strike {
    font-size:24px;
    font-weight:900;
    color:#182230;
    margin:8px 0 14px;
}

.option-grid {
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:10px;
}

.option-grid > div {
    background:#f8fafc;
    border-radius:9px;
    padding:9px;
}

.option-grid b {
    display:block;
    font-size:14px;
    margin-top:5px;
    color:#182230;
}

.option-readiness {
    margin-top:13px;
    border-radius:8px;
    text-align:center;
    padding:8px;
    font-size:11px;
    font-weight:900;
    letter-spacing:.4px;
}

.option-empty {
    padding:28px 5px;
    color:#98a2b3;
    text-align:center;
    font-size:13px;
}

.exit-rule {
    background:#f8fafc;
    border:1px solid #e7ebf0;
    border-radius:11px;
    padding:13px 15px;
    margin-top:12px;
}

.exit-rule b {
    display:block;
    color:#344054;
    font-size:12px;
    margin-top:5px;
    line-height:1.5;
}

.why-card {
    background:#fff;
    border:1px solid #e7ebf0;
    border-radius:14px;
    padding:7px 18px;
    box-shadow:0 2px 8px rgba(16,42,67,.035);
}

.why-item {
    padding:10px 3px;
    border-bottom:1px solid #eef0f2;
    color:#344054;
    font-size:12px;
}

.why-item:last-child {
    border-bottom:0;
}

.why-warning {
    color:#9a6700;
    background:#fffbf1;
    border-radius:7px;
    padding:8px 9px;
    margin:5px 0;
}

.sr-map {
    display:grid;
    grid-template-columns:1fr 1.15fr 1fr;
    align-items:stretch;
    gap:0;
    background:#fff;
    border:1px solid #e7ebf0;
    border-radius:15px;
    overflow:hidden;
    box-shadow:0 2px 8px rgba(16,42,67,.035);
    min-height:150px;
}

.sr-side {
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;
    padding:18px;
    text-align:center;
}

.sr-side span {
    font-size:10px;
    font-weight:900;
    letter-spacing:.4px;
}

.sr-side b {
    font-size:25px;
    margin:7px 0;
    color:#182230;
}

.sr-side small {
    color:#667085;
    font-size:11px;
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

.sr-line {
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;
    gap:8px;
    background:#fff;
    border-left:1px dashed #dfe3e8;
    border-right:1px dashed #dfe3e8;
}

.room-label {
    font-size:11px;
    color:#98a2b3;
    font-weight:700;
}

.current-marker {
    font-size:17px;
    font-weight:900;
    color:#182230;
    background:#f2f4f7;
    border:1px solid #e1e5ea;
    border-radius:20px;
    padding:8px 14px;
}

.current-marker span {
    font-size:9px;
    color:#667085;
    margin-left:5px;
    letter-spacing:.4px;
}

.tab-alert {
    border-radius:12px;
    padding:14px 16px;
    margin-bottom:16px;
    line-height:1.55;
    font-size:12px;
}

.tab-positive {
    background:#f4fbf6;
    border:1px solid #bde5c9;
    color:#147a3d;
}

.tab-danger {
    background:#fff6f6;
    border:1px solid #f2c5c8;
    color:#b4232f;
}

.scanner-card {
    background:#fff;
    border:1px solid #e7ebf0;
    border-radius:13px;
    padding:14px;
    margin-bottom:10px;
}

.scanner-title {
    font-weight:900;
    font-size:14px;
    color:#182230;
}

.scanner-meta {
    color:#667085;
    font-size:11px;
    margin-top:5px;
}

@media (max-width:900px) {
    .decision-stats,
    .status-grid {
        grid-template-columns:repeat(2,1fr);
    }

    .option-grid {
        grid-template-columns:repeat(2,1fr);
    }

    .sr-map {
        grid-template-columns:1fr;
    }

    .sr-line {
        padding:15px;
        border-top:1px dashed #dfe3e8;
        border-bottom:1px dashed #dfe3e8;
    }

    .topbar-dashboard {
        align-items:flex-start;
    }

    .header-live {
        display:none;
    }
}

@media (max-width:600px) {
    .block-container {
        padding-left:.7rem;
        padding-right:.7rem;
    }

    .decision-main {
        font-size:25px;
    }

    .check-row {
        grid-template-columns:1fr .9fr;
    }

    .check-row small {
        grid-column:1 / -1;
    }

    .metric-card,
    .entry-card {
        min-height:95px;
    }

    .option-grid {
        grid-template-columns:repeat(2,1fr);
    }

    .topbar-title {
        font-size:21px;
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
        self.retry_after = int(max(1, retry_after or 30))


# ============================================================
# API STATE / RATE LIMIT PROTECTION
# ============================================================

_API_REQUEST_LOCK = threading.Lock()
_LAST_API_REQUEST = 0.0
_RATE_LIMIT_UNTIL = 0.0

# Deliberately conservative.
_MIN_API_GAP = 0.75


def now_ist():
    return datetime.now(IST)


def market_is_open():
    """
    NSE-style regular session:
    Monday-Friday, 09:15-15:30 IST.

    This is deliberately a clock-based status. It does not pretend that a
    weekday holiday is an active exchange session.
    """
    current = now_ist()

    if current.weekday() >= 5:
        return False

    t = current.time()
    return (
        t >= datetime.strptime("09:15", "%H:%M").time()
        and t <= datetime.strptime("15:30", "%H:%M").time()
    )


def cooldown_remaining():
    global _RATE_LIMIT_UNTIL
    return max(0, int(round(_RATE_LIMIT_UNTIL - time.monotonic())))


def _extract_retry_after(response):
    header = response.headers.get("Retry-After")

    if header:
        try:
            value = float(header)
            if value >= 0:
                return int(max(1, round(value)))
        except Exception:
            pass

    try:
        body = response.json()

        if isinstance(body, dict):
            for key in (
                "retry_after",
                "retryAfter",
                "retry_after_seconds",
            ):
                value = body.get(key)
                if value is not None:
                    return int(max(1, float(value)))

            errors = body.get("errors")
            if isinstance(errors, list) and errors:
                first = errors[0]
                if isinstance(first, dict):
                    for key in (
                        "retry_after",
                        "retryAfter",
                        "retry_after_seconds",
                    ):
                        value = first.get(key)
                        if value is not None:
                            return int(max(1, float(value)))
    except Exception:
        pass

    return 30


def api_get(path, params=None, timeout=20):
    """
    Central Upstox GET wrapper.

    Important protections:
    - global minimum request spacing
    - global 429 cooldown
    - Retry-After support
    - no immediate retry after 429
    - useful errors for 401/403/404/5xx
    """
    global _LAST_API_REQUEST
    global _RATE_LIMIT_UNTIL

    remaining = cooldown_remaining()

    if remaining > 0:
        raise UpstoxRateLimitError(
            f"Upstox rate limit cooldown is active. "
            f"Please wait about {remaining} seconds.",
            retry_after=remaining,
        )

    with _API_REQUEST_LOCK:
        remaining = cooldown_remaining()

        if remaining > 0:
            raise UpstoxRateLimitError(
                f"Upstox rate limit cooldown is active. "
                f"Please wait about {remaining} seconds.",
                retry_after=remaining,
            )

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
        retry_after = _extract_retry_after(response)

        # Add a small safety margin so the next request is not made
        # immediately when the upstream limit expires.
        _RATE_LIMIT_UNTIL = time.monotonic() + retry_after + 2

        raise UpstoxRateLimitError(
            f"Upstox rate limit reached. Please wait about "
            f"{retry_after} seconds before refreshing.",
            retry_after=retry_after,
        )

    if response.status_code in (401, 403):
        raise UpstoxError(
            "Upstox rejected the access token. "
            "Please generate a fresh Upstox access token and update "
            "UPSTOX_ACCESS_TOKEN in Streamlit Secrets."
        )

    if response.status_code == 404:
        raise UpstoxError(
            f"Upstox endpoint/resource was not found: {path}"
        )

    if response.status_code >= 500:
        raise UpstoxError(
            f"Upstox server error HTTP {response.status_code}. "
            "Please try again after a short interval."
        )

    if response.status_code != 200:
        try:
            body = response.json()

            if isinstance(body, dict):
                message = (
                    body.get("message")
                    or body.get("errors")
                    or body
                )
            else:
                message = body

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
# TOKEN
# ============================================================

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
        "Upstox access token is not configured. "
        "Add UPSTOX_ACCESS_TOKEN under Streamlit → App settings → Secrets, "
        "then reload the app."
    )
    st.stop()


HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}


# ============================================================
# FORMATTING
# ============================================================

def finite(value):
    try:
        return bool(np.isfinite(float(value)))
    except Exception:
        return False


def safe_float(value, default=np.nan):
    try:
        result = float(value)

        if not np.isfinite(result):
            return default

        return result

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


def fmt_delta(value):
    x = safe_float(value)

    if not np.isfinite(x):
        return "—"

    return f"{x:.2f}"


def normalize_probability(value):
    """
    Upstox/other APIs can represent probabilities either as:
        0.65
    or:
        65

    Normalize both to 0-100.
    """
    x = safe_float(value)

    if not np.isfinite(x):
        return np.nan

    if 0 <= x <= 1:
        return x * 100

    return x


# ============================================================
# SYMBOL / INSTRUMENT
# ============================================================

def alias_symbol(symbol):
    s = str(symbol).strip().upper().replace(" ", "")

    aliases = {
        "NIFTY50": "NIFTY",
        "NIFTYBANK": "BANKNIFTY",
        "NIFTYFIN": "FINNIFTY",
        "MIDCAPNIFTY": "MIDCPNIFTY",
    }

    return aliases.get(s, s)


INDEX_SYMBOLS = {
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
}


@st.cache_data(ttl=120, show_spinner=False)
def search_underlying(symbol):
    symbol = alias_symbol(symbol)

    if symbol in INDEX_SYMBOLS:
        segments = ["INDEX"]
    else:
        segments = ["EQ"]

    results = []

    for segment in segments:
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
            "Use an NSE F&O stock symbol such as HDFCBANK "
            "or an index such as NIFTY."
        )

    exact = [
        item
        for item in results
        if str(item.get("trading_symbol", "")).upper() == symbol
    ]

    if exact:
        return exact[0]

    if symbol in INDEX_SYMBOLS:
        indexes = [
            item
            for item in results
            if str(item.get("segment", "")).upper() == "NSE_INDEX"
        ]

        if indexes:
            return indexes[0]

    equities = [
        item
        for item in results
        if str(item.get("segment", "")).upper() == "NSE_EQ"
    ]

    if equities:
        return equities[0]

    return results[0]


# ============================================================
# OPTIONS
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def get_contracts(underlying_key):
    payload = api_get(
        "/v2/option/contract",
        params={"instrument_key": underlying_key},
        timeout=30,
    )

    contracts = payload.get("data", [])

    if not contracts:
        raise UpstoxError(
            "Upstox returned no option contracts for this instrument."
        )

    return contracts


def available_expiries(contracts):
    today = now_ist().date()

    expiries = []

    for item in contracts:
        raw = item.get("expiry")

        if not raw:
            continue

        try:
            parsed = date.fromisoformat(str(raw)[:10])

            if parsed >= today:
                expiries.append(parsed.isoformat())

        except Exception:
            continue

    return sorted(set(expiries))


@st.cache_data(ttl=60, show_spinner=False)
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


@st.cache_data(ttl=15, show_spinner=False)
def get_quote(instrument_key):
    payload = api_get(
        "/v3/market-quote/quotes",
        params={
            "instrument_key": instrument_key,
        },
    )

    data = payload.get("data", {})

    if not data:
        raise UpstoxError(
            "No quote returned by Upstox."
        )

    if instrument_key in data:
        return data[instrument_key]

    return next(iter(data.values()))


def extract_last_price(quote_data):
    for key in (
        "last_price",
        "ltp",
        "last_traded_price",
        "close_price",
        "close",
    ):
        value = safe_float(quote_data.get(key))

        if np.isfinite(value):
            return value

    return np.nan


# ============================================================
# CANDLES
# ============================================================

def _candles_to_df(candles):
    if not candles:
        return pd.DataFrame()

    columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "oi",
    ]

    df = pd.DataFrame(candles)

    if df.shape[1] >= len(columns):
        df = df.iloc[:, :len(columns)]
        df.columns = columns
    else:
        return pd.DataFrame()

    for column in columns[1:]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["timestamp", "close"]
    )

    return (
        df.sort_values("timestamp")
        .reset_index(drop=True)
    )


@st.cache_data(ttl=90, show_spinner=False)
def get_intraday_candles(instrument_key, interval=5):
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

    return _candles_to_df(candles)


@st.cache_data(ttl=900, show_spinner=False)
def get_30m_candles(instrument_key):
    end_date = now_ist().date()
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

    return _candles_to_df(candles)


@st.cache_data(ttl=3600, show_spinner=False)
def get_daily_candles(instrument_key):
    end_date = now_ist().date()
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

    return _candles_to_df(candles)


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

def _rsi(close, period=14):
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    result = pd.Series(
        50.0,
        index=close.index,
        dtype=float,
    )

    zero_loss = avg_loss == 0
    normal = avg_loss > 0

    result.loc[normal] = (
        100
        - (
            100
            / (
                1
                + avg_gain.loc[normal]
                / avg_loss.loc[normal]
            )
        )
    )

    result.loc[
        zero_loss & (avg_gain > 0)
    ] = 100.0

    return result


def technicals(df, spot):
    if (
        df is None
        or df.empty
        or len(df) < 20
        or not np.isfinite(spot)
        or spot <= 0
    ):
        return {
            "rsi": 50.0,
            "ema20": spot,
            "ema50": spot,
            "atr": max(spot * 0.01, 0.01),
            "trend": "Unavailable",
            "adx": 0.0,
            "momentum": 0.0,
            "volume_ratio": 1.0,
            "vwap": spot,
        }

    close = pd.to_numeric(
        df["close"],
        errors="coerce",
    )

    high = pd.to_numeric(
        df["high"],
        errors="coerce",
    )

    low = pd.to_numeric(
        df["low"],
        errors="coerce",
    )

    volume = pd.to_numeric(
        df["volume"],
        errors="coerce",
    ).fillna(0)

    valid = pd.concat(
        [close, high, low],
        axis=1,
    ).dropna()

    if len(valid) < 20:
        return {
            "rsi": 50.0,
            "ema20": spot,
            "ema50": spot,
            "atr": max(spot * 0.01, 0.01),
            "trend": "Unavailable",
            "adx": 0.0,
            "momentum": 0.0,
            "volume_ratio": 1.0,
            "vwap": spot,
        }

    close = close.loc[valid.index]
    high = high.loc[valid.index]
    low = low.loc[valid.index]
    volume = volume.loc[valid.index]

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
        index=close.index,
    )

    minus_dm = pd.Series(
        np.where(
            (down_move > up_move) & (down_move > 0),
            down_move,
            0.0,
        ),
        index=close.index,
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

    denominator = (
        plus_di + minus_di
    ).replace(0, np.nan)

    dx = (
        100
        * (plus_di - minus_di).abs()
        / denominator
    )

    adx = dx.ewm(
        alpha=1 / 14,
        adjust=False,
    ).mean()

    typical = (
        high + low + close
    ) / 3

    # Session-style VWAP for intraday data.
    cumulative_volume = volume.cumsum()

    if cumulative_volume.iloc[-1] > 0:
        vwap_series = (
            typical * volume
        ).cumsum() / cumulative_volume

        latest_vwap = safe_float(
            vwap_series.iloc[-1],
            spot,
        )
    else:
        latest_vwap = spot

    lookback = min(10, len(close) - 1)

    if lookback > 0:
        old_close = safe_float(
            close.iloc[-1 - lookback]
        )

        current_close = safe_float(
            close.iloc[-1]
        )

        if (
            np.isfinite(old_close)
            and old_close > 0
            and np.isfinite(current_close)
        ):
            momentum = (
                current_close / old_close - 1
            ) * 100
        else:
            momentum = 0.0
    else:
        momentum = 0.0

    previous_volume = (
        volume.shift(1)
        .rolling(20)
        .median()
        .iloc[-1]
    )

    if (
        np.isfinite(previous_volume)
        and previous_volume > 0
    ):
        volume_ratio = (
            volume.iloc[-1]
            / previous_volume
        )
    else:
        volume_ratio = 1.0

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
        spot * 0.01,
    )

    adx_value = safe_float(
        adx.iloc[-1],
        0,
    )

    bullish = (
        spot > e20
        and e20 > e50
    )

    bearish = (
        spot < e20
        and e20 < e50
    )

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
        "atr": max(a, spot * 0.001),
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


def timeframe_score(side, tf5, tf30, daily):
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
        trend = tf.get("trend")

        if trend == desired:
            score += 10
            alignment += 1

        elif trend == "Sideways":
            score += 3

        elif trend == opposite:
            score -= 8

    return float(
        np.clip(score, 0, 30)
    ), alignment


# ============================================================
# OI ANALYSIS
# ============================================================

def oi_levels(chain, spot):
    valid = chain.copy()

    if "Strike" not in valid.columns:
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

    valid["Strike"] = pd.to_numeric(
        valid["Strike"],
        errors="coerce",
    )

    valid = valid.dropna(
        subset=["Strike"]
    )

    if (
        valid.empty
        or not np.isfinite(spot)
        or spot <= 0
    ):
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

    # Prefer a reasonable local band.
    band = valid[
        (valid["Strike"] >= spot * 0.90)
        & (valid["Strike"] <= spot * 1.10)
    ].copy()

    if len(band) < 5:
        band = valid.copy()

    for col in (
        "PE OI",
        "CE OI",
        "PE Chg OI",
        "CE Chg OI",
    ):
        if col not in band.columns:
            band[col] = 0

        band[col] = pd.to_numeric(
            band[col],
            errors="coerce",
        ).fillna(0)

    below = band[
        band["Strike"] < spot
    ].copy()

    above = band[
        band["Strike"] > spot
    ].copy()

    if below.empty:
        nearest_support = float(
            band["Strike"].min()
        )
    else:
        nearest_support = float(
            below["Strike"].max()
        )

    if above.empty:
        nearest_resistance = float(
            band["Strike"].max()
        )
    else:
        nearest_resistance = float(
            above["Strike"].min()
        )

    # Major support must be BELOW spot.
    if not below.empty:
        support_row = below.loc[
            below["PE OI"].idxmax()
        ]
    else:
        support_row = band.loc[
            band["PE OI"].idxmax()
        ]

    # Major resistance must be ABOVE spot.
    if not above.empty:
        resistance_row = above.loc[
            above["CE OI"].idxmax()
        ]
    else:
        resistance_row = band.loc[
            band["CE OI"].idxmax()
        ]

    major_support = safe_float(
        support_row["Strike"],
        nearest_support,
    )

    major_resistance = safe_float(
        resistance_row["Strike"],
        nearest_resistance,
    )

    if major_support >= spot:
        major_support = nearest_support

    if major_resistance <= spot:
        major_resistance = nearest_resistance

    total_call_oi = float(
        band["CE OI"].sum()
    )

    total_put_oi = float(
        band["PE OI"].sum()
    )

    pcr = (
        total_put_oi / total_call_oi
        if total_call_oi > 0
        else np.nan
    )

    put_walls = (
        band.nlargest(3, "PE OI")
        [
            ["Strike", "PE OI", "PE Chg OI"]
        ]
        .to_dict("records")
    )

    call_walls = (
        band.nlargest(3, "CE OI")
        [
            ["Strike", "CE OI", "CE Chg OI"]
        ]
        .to_dict("records")
    )

    support_room = max(
        (
            spot - major_support
        )
        / max(spot, 1)
        * 100,
        0,
    )

    resistance_room = max(
        (
            major_resistance - spot
        )
        / max(spot, 1)
        * 100,
        0,
    )

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
            "support_room_pct": support_room,
            "resistance_room_pct": resistance_room,
        },
    )


def nearest_row(chain, strike):
    if (
        chain is None
        or chain.empty
        or not np.isfinite(strike)
    ):
        return None

    distance = (
        chain["Strike"] - strike
    ).abs()

    if distance.empty:
        return None

    index = distance.idxmin()

    return chain.loc[index]


# ============================================================
# OPTION CHAIN NORMALIZATION
# ============================================================

def normalize_chain(rows):
    records = []

    for item in rows:
        strike = safe_float(
            item.get("strike_price")
        )

        if not np.isfinite(strike):
            continue

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

        call_change = call_market.get(
            "change_in_oi"
        )

        if call_change is None:
            call_change = call_market.get(
                "oi_change"
            )

        if call_change is None:
            prev = safe_float(
                call_market.get("prev_oi"),
                np.nan,
            )

            call_change = (
                call_oi - prev
                if np.isfinite(prev)
                else 0
            )

        put_change = put_market.get(
            "change_in_oi"
        )

        if put_change is None:
            put_change = put_market.get(
                "oi_change"
            )

        if put_change is None:
            prev = safe_float(
                put_market.get("prev_oi"),
                np.nan,
            )

            put_change = (
                put_oi - prev
                if np.isfinite(prev)
                else 0
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
                "CE Chg OI": safe_float(
                    call_change,
                    0,
                ),
                "CE Volume": safe_float(
                    call_market.get("volume"),
                    0,
                ),
                "CE IV": safe_float(
                    call_greeks.get("iv")
                ),
                "CE Delta": safe_float(
                    call_greeks.get("delta")
                ),
                "CE PoP": normalize_probability(
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
                "PE Chg OI": safe_float(
                    put_change,
                    0,
                ),
                "PE Volume": safe_float(
                    put_market.get("volume"),
                    0,
                ),
                "PE IV": safe_float(
                    put_greeks.get("iv")
                ),
                "PE Delta": safe_float(
                    put_greeks.get("delta")
                ),
                "PE PoP": normalize_probability(
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
# SCORING ENGINE
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
        prefix = "CE"
    else:
        prefix = "PE"

    premium = safe_float(
        row.get(f"{prefix} LTP")
    )

    delta = safe_float(
        row.get(f"{prefix} Delta")
    )

    iv = safe_float(
        row.get(f"{prefix} IV")
    )

    pop = safe_float(
        row.get(f"{prefix} PoP")
    )

    chg_oi = safe_float(
        row.get(f"{prefix} Chg OI"),
        0,
    )

    volume = safe_float(
        row.get(f"{prefix} Volume"),
        0,
    )

    oi = safe_float(
        row.get(f"{prefix} OI"),
        0,
    )

    bid = safe_float(
        row.get(f"{prefix} Bid")
    )

    ask = safe_float(
        row.get(f"{prefix} Ask")
    )

    desired = (
        "Bullish"
        if side == "CE"
        else "Bearish"
    )

    tf_points, alignment = timeframe_score(
        side,
        tf5,
        tf30,
        daily,
    )

    # --------------------------------------------------------
    # Momentum / trend = 15
    # --------------------------------------------------------

    momentum_points = 0

    if tf5.get("trend") == desired:
        momentum_points += 5

    rsi = safe_float(
        tf5.get("rsi"),
        50,
    )

    momentum = safe_float(
        tf5.get("momentum"),
        0,
    )

    if side == "CE":
        if 52 <= rsi <= 68:
            momentum_points += 3
        elif 50 <= rsi < 52:
            momentum_points += 1

        if momentum > 0:
            momentum_points += 3

    else:
        if 32 <= rsi <= 48:
            momentum_points += 3
        elif 48 < rsi <= 50:
            momentum_points += 1

        if momentum < 0:
            momentum_points += 3

    adx = safe_float(
        tf5.get("adx"),
        0,
    )

    if adx >= 25:
        momentum_points += 4
    elif adx >= 20:
        momentum_points += 2

    momentum_points = min(
        momentum_points,
        15,
    )

    # --------------------------------------------------------
    # VWAP = 10
    # --------------------------------------------------------

    vwap = safe_float(
        tf5.get("vwap"),
        spot,
    )

    vwap_points = 0

    if (
        np.isfinite(vwap)
        and vwap > 0
        and spot > 0
    ):
        vwap_gap_pct = (
            (spot - vwap)
            / spot
            * 100
        )

        if side == "CE":
            if (
                spot > vwap
                and momentum > 0
            ):
                vwap_points = 10

            elif spot > vwap:
                vwap_points = 6

            elif spot >= vwap * 0.997:
                vwap_points = 2

        else:
            if (
                spot < vwap
                and momentum < 0
            ):
                vwap_points = 10

            elif spot < vwap:
                vwap_points = 6

            elif spot <= vwap * 1.003:
                vwap_points = 2

    else:
        vwap_gap_pct = 0

    # --------------------------------------------------------
    # PCR = 10
    # --------------------------------------------------------

    pcr_points = 0

    if np.isfinite(pcr):
        if side == "CE":
            if 0.90 <= pcr <= 1.35:
                pcr_points = 10
            elif 0.80 <= pcr < 0.90:
                pcr_points = 5

        else:
            if 0.65 <= pcr <= 1.10:
                pcr_points = 10
            elif 1.10 < pcr <= 1.25:
                pcr_points = 5

    # --------------------------------------------------------
    # OI change = 5
    # --------------------------------------------------------

    if chg_oi < 0:
        oi_points = 5
    elif chg_oi == 0:
        oi_points = 3
    else:
        oi_points = 1

    # --------------------------------------------------------
    # Option quality = 20
    # --------------------------------------------------------

    quality = 0

    abs_delta = (
        abs(delta)
        if np.isfinite(delta)
        else np.nan
    )

    if np.isfinite(abs_delta):
        if 0.45 <= abs_delta <= 0.65:
            quality += 6
        elif (
            0.40 <= abs_delta < 0.45
            or 0.65 < abs_delta <= 0.75
        ):
            quality += 4
        elif (
            0.35 <= abs_delta < 0.40
            or 0.75 < abs_delta <= 0.80
        ):
            quality += 2

    if (
        np.isfinite(ask)
        and np.isfinite(bid)
        and ask > 0
        and bid > 0
    ):
        midpoint = (
            ask + bid
        ) / 2

        spread_pct = (
            max(ask - bid, 0)
            / max(midpoint, 0.01)
            * 100
        )

    else:
        spread_pct = 999

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

    # --------------------------------------------------------
    # Strike quality = 10
    # --------------------------------------------------------

    strike = safe_float(
        row.get("Strike")
    )

    if np.isfinite(strike) and spot > 0:
        distance_pct = (
            abs(strike - spot)
            / spot
            * 100
        )
    else:
        distance_pct = 999

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
        and resistance > spot
    ):
        room_pct = (
            resistance - spot
        ) / max(spot, 1) * 100

        if room_pct >= 2:
            room_points = 4
        elif room_pct >= 1:
            room_points = 2

    elif (
        side == "PE"
        and np.isfinite(support)
        and support < spot
    ):
        room_pct = (
            spot - support
        ) / max(spot, 1) * 100

        if room_pct >= 2:
            room_points = 4
        elif room_pct >= 1:
            room_points = 2

    strike_quality = (
        strike_points
        + room_points
    )

    # --------------------------------------------------------
    # PoP = 10
    # --------------------------------------------------------

    if np.isfinite(pop):
        pop_points = float(
            np.clip(
                (pop - 55) / 3,
                0,
                10,
            )
        )
    else:
        pop_points = 0

    # --------------------------------------------------------
    # Final score
    # --------------------------------------------------------

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

    # Components total 110.
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

    prefix = (
        "CE"
        if side == "CE"
        else "PE"
    )

    ask = safe_float(
        row.get(f"{prefix} Ask")
    )

    ltp = safe_float(
        row.get(f"{prefix} LTP")
    )

    # Ask is the realistic BUY entry when available.
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

    sl_factor, target1_factor, target2_factor = (
        risk_settings.get(
            risk_profile,
            risk_settings["Balanced"],
        )
    )

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

    risk_per_unit = max(
        entry - sl,
        0.01,
    )

    rr1 = (
        target1 - entry
    ) / risk_per_unit

    rr2 = (
        target2 - entry
    ) / risk_per_unit

    atr = safe_float(
        tf5.get("atr"),
        spot * 0.01,
    )

    atr = max(
        atr,
        spot * 0.001,
    )

    trigger_buffer = max(
        atr * 0.15,
        spot * 0.0015,
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
                and safe_float(
                    tf5.get("momentum"),
                    0,
                ) > 0
                and safe_float(
                    tf5.get("rsi"),
                    50,
                ) >= 52
            )

            volume_confirmed = (
                safe_float(
                    tf5.get("volume_ratio"),
                    1,
                ) >= 1.10
            )

        trigger = (
            f"Enter only after spot breaks and sustains "
            f"above {fmt_price(trigger_level)} with 5-minute "
            "bullish confirmation."
        )

        exit_rule = (
            f"Exit if spot loses support "
            f"{fmt_price(support)} or option premium "
            f"falls to {fmt_price(sl)}. "
            "After Target 1, consider partial booking and trail."
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
                and safe_float(
                    tf5.get("momentum"),
                    0,
                ) < 0
                and safe_float(
                    tf5.get("rsi"),
                    50,
                ) <= 48
            )

            volume_confirmed = (
                safe_float(
                    tf5.get("volume_ratio"),
                    1,
                ) >= 1.10
            )

        trigger = (
            f"Enter only after spot breaks and sustains "
            f"below {fmt_price(trigger_level)} with 5-minute "
            "bearish confirmation."
        )

        exit_rule = (
            f"Exit if spot reclaims resistance "
            f"{fmt_price(resistance)} or option premium "
            f"falls to {fmt_price(sl)}. "
            "After Target 1, consider partial booking and trail."
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
            0.35
            <= abs(scored["delta"])
            <= 0.80
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
            "low option PoP"
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

    # --------------------------------------------------------
    # Readiness
    # --------------------------------------------------------

    if hard_fail:
        readiness = "NO TRADE"
        readiness_class = "status-red"
    elif (
        trigger_hit
        and candle_confirmed
        and volume_confirmed
    ):
        readiness = "TRIGGER CONFIRMED"
        readiness_class = "status-green"
    elif trigger_hit:
        readiness = "TRIGGER HIT — CONFIRMATION WAIT"
        readiness_class = "status-yellow"
    else:
        readiness = "WAIT FOR TRIGGER"
        readiness_class = "status-yellow"

    # Actual action is deliberately stricter.
    # A setup is not promoted to CALL BUY / PUT BUY merely because
    # its score is high.
    if (
        not hard_fail
        and trigger_hit
        and candle_confirmed
        and volume_confirmed
    ):
        action = (
            "CALL BUY"
            if side == "CE"
            else "PUT BUY"
        )
    else:
        action = "NO TRADE"

    reasons = []

    if scored["alignment"] >= 2:
        reasons.append(
            f"{scored['alignment']}/3 timeframes aligned"
        )
    else:
        reasons.append(
            "Timeframe alignment is incomplete"
        )

    if scored["score"] >= 72:
        reasons.append(
            f"setup score {scored['score']:.0f}/100"
        )
    else:
        reasons.append(
            f"setup score only {scored['score']:.0f}/100"
        )

    if np.isfinite(scored["pop"]):
        reasons.append(
            f"PoP {scored['pop']:.1f}%"
        )

    if np.isfinite(scored["delta"]):
        reasons.append(
            f"Delta {scored['delta']:.2f}"
        )

    if scored["spread_pct"] <= 3:
        reasons.append(
            f"spread {scored['spread_pct']:.1f}%"
        )

    if candle_confirmed:
        reasons.append(
            "5m candle confirmation passed"
        )
    else:
        reasons.append(
            "5m candle confirmation pending"
        )

    if volume_confirmed:
        reasons.append(
            "volume confirmation passed"
        )
    else:
        reasons.append(
            "volume confirmation pending"
        )

    return {
        "side": side,
        "action": action,
        "readiness": readiness,
        "readiness_class": readiness_class,
        "score": scored["score"],
        "pop": scored["pop"],
        "delta": scored["delta"],
        "iv": scored["iv"],
        "volume": scored["volume"],
        "oi": scored["oi"],
        "chg_oi": scored["chg_oi"],
        "spread_pct": scored["spread_pct"],
        "premium": scored["premium"],
        "entry": entry,
        "sl": sl,
        "target1": target1,
        "target2": target2,
        "rr1": rr1,
        "rr2": rr2,
        "trigger_level": trigger_level,
        "trigger_hit": trigger_hit,
        "candle_confirmed": candle_confirmed,
        "volume_confirmed": volume_confirmed,
        "trigger": trigger,
        "exit_rule": exit_rule,
        "hard_fail": hard_fail,
        "reasons": reasons,
        "strike": safe_float(
            row.get("Strike")
        ),
        "key": row.get(
            f"{prefix} Key"
        ),
    }


# ============================================================
# FIND BEST OPTION
# ============================================================

def candidate_rows(chain, side, spot):
    if chain.empty:
        return pd.DataFrame()

    prefix = (
        "CE"
        if side == "CE"
        else "PE"
    )

    working = chain.copy()

    working["_distance"] = (
        working["Strike"] - spot
    ).abs()

    # Focus on reasonably close strikes.
    working = working[
        working["_distance"]
        <= spot * 0.06
    ]

    working = working[
        pd.to_numeric(
            working[f"{prefix} LTP"],
            errors="coerce",
        ) > 0
    ]

    return (
        working
        .sort_values("_distance")
        .head(15)
        .drop(columns=["_distance"])
    )


def find_best_plan(
    chain,
    side,
    spot,
    support,
    resistance,
    pcr,
    tf5,
    tf30,
    daily,
    risk_profile,
    oi_info,
):
    candidates = candidate_rows(
        chain,
        side,
        spot,
    )

    plans = []

    for _, row in candidates.iterrows():
        plan = build_plan(
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
            oi_wall_info=oi_info,
        )

        if plan is not None:
            plans.append(plan)

    if not plans:
        return None

    plans.sort(
        key=lambda x: (
            x["score"],
            x["pop"] if np.isfinite(x["pop"]) else -1,
            -x["spread_pct"],
        ),
        reverse=True,
    )

    return plans[0]


# ============================================================
# SCANNER
# ============================================================

def scanner_results(
    chain,
    spot,
    support,
    resistance,
    pcr,
    tf5,
    tf30,
    daily,
    risk_profile,
):
    results = []

    for side in ("CE", "PE"):
        candidates = candidate_rows(
            chain,
            side,
            spot,
        )

        for _, row in candidates.iterrows():
            plan = build_plan(
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
            )

            if not plan:
                continue

            # User's requested scanner threshold.
            if (
                not np.isfinite(plan["pop"])
                or plan["pop"] <= 60
            ):
                continue

            # Keep scanner useful: only sufficiently liquid /
            # structurally reasonable contracts.
            if plan["spread_pct"] > 4:
                continue

            if plan["oi"] <= 0:
                continue

            results.append(plan)

    results.sort(
        key=lambda x: (
            x["pop"],
            x["score"],
            x["rr1"],
        ),
        reverse=True,
    )

    return results[:12]


# ============================================================
# UI HELPERS
# ============================================================

def metric_card(label, value, css="metric-neutral", note=""):
    return f"""
    <div class="metric-card {css}">
        <span>{label}</span>
        <b>{value}</b>
        <small>{note}</small>
    </div>
    """


def render_metric_grid(items, columns=4):
    cols = st.columns(columns)

    for index, item in enumerate(items):
        with cols[index % columns]:
            st.markdown(
                metric_card(
                    item[0],
                    item[1],
                    item[2] if len(item) > 2 else "metric-neutral",
                    item[3] if len(item) > 3 else "",
                ),
                unsafe_allow_html=True,
            )


def render_decision(plan, fallback_side=None):
    if plan is None:
        action = "NO TRADE"
        decision_class = "decision-neutral"
        subtitle = "No valid option setup was found."
        score = "—"
        pop = "—"
        entry = "—"
        rr = "—"

    else:
        action = plan["action"]

        if action == "CALL BUY":
            decision_class = "decision-call"
        elif action == "PUT BUY":
            decision_class = "decision-put"
        else:
            decision_class = "decision-neutral"

        if action == "NO TRADE":
            subtitle = plan["readiness"]
        else:
            subtitle = "All entry conditions are currently confirmed."

        score = (
            f'{plan["score"]:.0f}/100'
        )

        pop = (
            fmt_pct(plan["pop"])
            if np.isfinite(plan["pop"])
            else "—"
        )

        entry = fmt_price(
            plan["entry"]
        )

        rr = (
            f'1:{plan["rr1"]:.2f}'
        )

    html = f"""
    <div class="decision-card {decision_class}">
        <div class="decision-main">{action}</div>
        <div class="decision-sub">{subtitle}</div>

        <div class="decision-stats">
            <div>
                <span>SETUP SCORE</span>
                <b>{score}</b>
            </div>

            <div>
                <span>PoP</span>
                <b>{pop}</b>
            </div>

            <div>
                <span>ENTRY</span>
                <b>{entry}</b>
            </div>

            <div>
                <span>R:R</span>
                <b>{rr}</b>
            </div>
        </div>
    </div>
    """

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


def render_plan_card(plan):
    if not plan:
        st.markdown(
            """
            <div class="option-card option-muted">
                <div class="option-empty">
                    No valid option plan available.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    side = plan["side"]

    css = (
        "option-call"
        if side == "CE"
        else "option-put"
    )

    label = (
        "CALL"
        if side == "CE"
        else "PUT"
    )

    readiness = plan["readiness"]

    readiness_class = plan[
        "readiness_class"
    ]

    selected = (
        " option-selected"
        if plan["action"] != "NO TRADE"
        else ""
    )

    html = f"""
    <div class="option-card {css}{selected}">
        <div class="option-head">
            <span>{label} BUY</span>
            <span class="selected-tag">
                {readiness}
            </span>
        </div>

        <div class="option-strike">
            {fmt_price(plan["strike"])}
        </div>

        <div class="option-grid">

            <div>
                <span>ENTRY</span>
                <b>{fmt_price(plan["entry"])}</b>
            </div>

            <div>
                <span>STOP LOSS</span>
                <b>{fmt_price(plan["sl"])}</b>
            </div>

            <div>
                <span>TARGET 1</span>
                <b>{fmt_price(plan["target1"])}</b>
            </div>

            <div>
                <span>TARGET 2</span>
                <b>{fmt_price(plan["target2"])}</b>
            </div>

            <div>
                <span>PoP</span>
                <b>{fmt_pct(plan["pop"])}</b>
            </div>

            <div>
                <span>DELTA</span>
                <b>{fmt_delta(plan["delta"])}</b>
            </div>

            <div>
                <span>IV</span>
                <b>{fmt_pct(plan["iv"])}</b>
            </div>

            <div>
                <span>R:R</span>
                <b>1:{plan["rr1"]:.2f}</b>
            </div>

        </div>

        <div class="option-readiness {readiness_class}">
            {readiness}
        </div>

        <div class="exit-rule">
            <span>ENTRY TRIGGER</span>
            <b>{plan["trigger"]}</b>
        </div>

        <div class="exit-rule">
            <span>EXIT RULE</span>
            <b>{plan["exit_rule"]}</b>
        </div>
    </div>
    """

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


def render_checks(plan, tf5, tf30, daily):
    checks = []

    if plan:
        checks.append(
            (
                "Setup Score",
                (
                    "PASS"
                    if plan["score"] >= 72
                    else "FAIL"
                ),
                f'{plan["score"]:.0f}/100',
            )
        )

        checks.append(
            (
                "Timeframe Alignment",
                (
                    "PASS"
                    if plan["score"] >= 72
                    and not any(
                        x.get("trend")
                        in (
                            "Unavailable",
                        )
                        for x in (
                            tf5,
                            tf30,
                            daily,
                        )
                    )
                    else "WAIT"
                ),
                "3 timeframe analysis",
            )
        )

        checks.append(
            (
                "Option PoP",
                (
                    "PASS"
                    if np.isfinite(plan["pop"])
                    and plan["pop"] > 60
                    else "WAIT"
                ),
                fmt_pct(plan["pop"]),
            )
        )

        checks.append(
            (
                "Option Spread",
                (
                    "PASS"
                    if plan["spread_pct"] <= 3
                    else "FAIL"
                ),
                f'{plan["spread_pct"]:.1f}%',
            )
        )

        checks.append(
            (
                "Liquidity",
                (
                    "PASS"
                    if plan["volume"] >= 1000
                    and plan["oi"] > 0
                    else "FAIL"
                ),
                f'Vol {fmt_num(plan["volume"])}',
            )
        )

        checks.append(
            (
                "Entry Trigger",
                (
                    "PASS"
                    if plan["trigger_hit"]
                    else "WAIT"
                ),
                (
                    "Triggered"
                    if plan["trigger_hit"]
                    else "Not triggered"
                ),
            )
        )

        checks.append(
            (
                "5m Confirmation",
                (
                    "PASS"
                    if plan["candle_confirmed"]
                    else "WAIT"
                ),
                (
                    "Confirmed"
                    if plan["candle_confirmed"]
                    else "Pending"
                ),
            )
        )

        checks.append(
            (
                "Volume Confirmation",
                (
                    "PASS"
                    if plan["volume_confirmed"]
                    else "WAIT"
                ),
                (
                    "Confirmed"
                    if plan["volume_confirmed"]
                    else "Pending"
                ),
            )
        )

    else:
        checks.append(
            (
                "Trade Setup",
                "FAIL",
                "No valid setup",
            )
        )

    passed = sum(
        1
        for _, status, _ in checks
        if status == "PASS"
    )

    html = [
        '<div class="check-card">'
    ]

    for name, status, detail in checks:
        css = (
            "check-pass"
            if status == "PASS"
            else (
                "check-fail"
                if status == "FAIL"
                else "check-wait"
            )
        )

        html.append(
            f"""
            <div class="check-row">
                <span>{name}</span>
                <strong class="{css}">
                    {status}
                </strong>
                <small>{detail}</small>
            </div>
            """
        )

    html.append(
        f"""
        <div class="check-total">
            <span>Conditions Passed</span>
            <b>{passed}/{len(checks)}</b>
        </div>
        </div>
        """
    )

    st.markdown(
        "".join(html),
        unsafe_allow_html=True,
    )


def render_why(plan):
    if not plan:
        st.markdown(
            """
            <div class="why-card">
                <div class="why-item why-warning">
                    No valid option setup is available for the current
                    market conditions.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    items = []

    for reason in plan["reasons"]:
        warning = (
            "pending"
            in reason.lower()
            or "only"
            in reason.lower()
            or "incomplete"
            in reason.lower()
        )

        css = (
            "why-item why-warning"
            if warning
            else "why-item"
        )

        items.append(
            f'<div class="{css}">{reason}</div>'
        )

    if plan["hard_fail"]:
        for failure in plan["hard_fail"]:
            items.append(
                f"""
                <div class="why-item why-warning">
                    Blocked: {failure}
                </div>
                """
            )

    html = (
        '<div class="why-card">'
        + "".join(items)
        + "</div>"
    )

    st.markdown(
        html,
        unsafe_allow_html=True,
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown(
        "## ⚙️ Controls"
    )

    symbol_input = st.text_input(
        "F&O Symbol",
        value=st.session_state.get(
            "symbol",
            "HDFCBANK",
        ),
        help=(
            "Example: HDFCBANK, RELIANCE, "
            "SBIN, NIFTY, BANKNIFTY"
        ),
    ).strip().upper()

    st.session_state["symbol"] = (
        alias_symbol(symbol_input)
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

    scanner_enabled = st.toggle(
        "🔎 F&O Scanner",
        value=True,
        help=(
            "Shows option candidates with "
            "PoP above 60% using the same live "
            "option-chain data."
        ),
    )

    auto_refresh = st.toggle(
        "Auto Refresh",
        value=True,
    )

    refresh_seconds = st.selectbox(
        "Refresh Interval",
        [30, 60, 90, 120],
        index=1,
    )

    manual_refresh = st.button(
        "🔄 Refresh Now",
        use_container_width=True,
    )

    st.divider()

    st.caption(
        "REST API only • No automatic orders"
    )

    st.caption(
        "Score is a rule-based setup score, "
        "not a guaranteed win probability."
    )


# ============================================================
# RATE LIMIT / AUTO REFRESH
# ============================================================

rate_remaining = cooldown_remaining()

if (
    auto_refresh
    and st_autorefresh is not None
    and market_is_open()
    and rate_remaining <= 0
):
    st_autorefresh(
        interval=refresh_seconds * 1000,
        key="fo_pro_auto_refresh",
    )

if manual_refresh:
    if rate_remaining > 0:
        st.warning(
            f"Upstox cooldown is active. "
            f"Please wait about {rate_remaining} seconds."
        )
    else:
        st.cache_data.clear()
        st.rerun()


# ============================================================
# HEADER
# ============================================================

is_open = market_is_open()

status_text = (
    "● LIVE DATA"
    if is_open
    else "● MARKET CLOSED"
)

status_class = (
    "live-block"
    if is_open
    else "closed-block"
)

current_time = now_ist().strftime(
    "%d %b %Y • %I:%M:%S %p"
)

st.markdown(
    f"""
    <div class="topbar">
        <div class="topbar-dashboard">
            <div>
                <div class="topbar-title">
                    📊 FO PRO Trader Assistant
                </div>
                <div class="topbar-sub">
                    Options Analysis • Upstox REST API •
                    Live Option Chain • Technical + OI Analysis
                </div>
            </div>

            <div class="{status_class}">
                Data Status<br>
                {status_text}
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LOAD MARKET DATA
# ============================================================

try:
    with st.spinner(
        f"Loading {symbol_input} market data..."
    ):
        instrument = search_underlying(
            symbol_input
        )

        underlying_key = instrument.get(
            "instrument_key"
        )

        if not underlying_key:
            raise UpstoxError(
                "Upstox did not return an instrument key."
            )

        trading_symbol = (
            instrument.get("trading_symbol")
            or symbol_input
        )

        contracts = get_contracts(
            underlying_key
        )

        expiries = available_expiries(
            contracts
        )

        if not expiries:
            raise UpstoxError(
                "No valid future option expiry was returned."
            )

        selected_expiry = expiries[0]

        chain_raw = get_option_chain(
            underlying_key,
            selected_expiry,
        )

        chain = normalize_chain(
            chain_raw
        )

        if chain.empty:
            raise UpstoxError(
                "Option chain could not be normalized."
            )

        quote_data = get_quote(
            underlying_key
        )

        spot = extract_last_price(
            quote_data
        )

        if (
            not np.isfinite(spot)
            or spot <= 0
        ):
            raise UpstoxError(
                "Upstox returned an invalid spot price."
            )

        tf5_df = get_intraday_candles(
            underlying_key,
            interval=5,
        )

        tf30_df = get_30m_candles(
            underlying_key
        )

        daily_df = get_daily_candles(
            underlying_key
        )

        tf5 = technicals(
            tf5_df,
            spot,
        )

        tf30 = technicals(
            tf30_df,
            spot,
        )

        daily = technicals(
            daily_df,
            spot,
        )

        (
            support,
            resistance,
            pcr,
            oi_info,
        ) = oi_levels(
            chain,
            spot,
        )

        call_plan = find_best_plan(
            chain,
            "CE",
            spot,
            support,
            resistance,
            pcr,
            tf5,
            tf30,
            daily,
            risk_profile,
            oi_info,
        )

        put_plan = find_best_plan(
            chain,
            "PE",
            spot,
            support,
            resistance,
            pcr,
            tf5,
            tf30,
            daily,
            risk_profile,
            oi_info,
        )

except UpstoxRateLimitError as exc:
    st.markdown(
        f"""
        <div class="status-panel status-red">
            <div class="status-title">
                ⏳ Upstox Rate Limit Active
            </div>

            <div class="status-note">
                {exc}<br><br>
                The application has stopped sending new API requests
                while the cooldown is active.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.stop()

except UpstoxError as exc:
    st.markdown(
        f"""
        <div class="status-panel status-red">
            <div class="status-title">
                ⚠️ DATA ERROR
            </div>

            <div class="status-note">
                {str(exc)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.stop()

except Exception as exc:
    st.markdown(
        f"""
        <div class="status-panel status-red">
            <div class="status-title">
                ⚠️ APPLICATION ERROR
            </div>

            <div class="status-note">
                The application could not complete the analysis.<br>
                {str(exc)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.stop()


# ============================================================
# SELECT PRIMARY DECISION
# ============================================================

plans = [
    plan
    for plan in (
        call_plan,
        put_plan,
    )
    if plan is not None
]

triggered_plans = [
    plan
    for plan in plans
    if plan["action"]
    in (
        "CALL BUY",
        "PUT BUY",
    )
]

if triggered_plans:
    primary_plan = max(
        triggered_plans,
        key=lambda x: x["score"],
    )
else:
    primary_plan = (
        max(
            plans,
            key=lambda x: x["score"],
        )
        if plans
        else None
    )


# ============================================================
# TOP METRICS
# ============================================================

st.markdown(
    f"""
    <div class="card">
        <div style="display:flex;justify-content:space-between;
                    align-items:center;gap:15px;flex-wrap:wrap;">
            <div>
                <div style="font-size:12px;color:#667085;
                            font-weight:800;">
                    {trading_symbol} • F&O OPTIONS ANALYSIS
                </div>

                <div class="hero-price">
                    {fmt_price(spot)}
                </div>
            </div>

            <div style="text-align:right;">
                <div style="font-size:11px;color:#667085;">
                    Expiry
                </div>

                <div style="font-weight:850;color:#182230;">
                    {selected_expiry}
                </div>

                <div style="font-size:10px;color:#98a2b3;">
                    Updated {current_time}
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


trend, trend_count = overall_trend(
    tf5,
    tf30,
    daily,
)

trend_css = (
    "metric-positive"
    if trend == "Bullish"
    else (
        "metric-negative"
        if trend == "Bearish"
        else "metric-neutral"
    )
)

render_metric_grid(
    [
        (
            "MARKET BIAS",
            trend,
            trend_css,
            f"{trend_count}/3 timeframes",
        ),
        (
            "PCR",
            fmt_pct(pcr, 2)
            if np.isfinite(pcr)
            else "—",
            "metric-neutral",
            "OI-based local PCR",
        ),
        (
            "OI SUPPORT",
            fmt_price(support),
            "metric-support",
            "Major PE OI wall",
        ),
        (
            "OI RESISTANCE",
            fmt_price(resistance),
            "metric-resistance",
            "Major CE OI wall",
        ),
    ],
    columns=4,
)


# ============================================================
# DECISION
# ============================================================

st.markdown(
    '<div class="section-heading">🎯 Trade Decision</div>',
    unsafe_allow_html=True,
)

render_decision(
    primary_plan
)


# ============================================================
# SUPPORT / RESISTANCE MAP
# ============================================================

support_room = max(
    (spot - support)
    / max(spot, 1)
    * 100,
    0,
)

resistance_room = max(
    (resistance - spot)
    / max(spot, 1)
    * 100,
    0,
)

st.markdown(
    '<div class="section-heading">📍 OI Support / Resistance Map</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="sr-map">

        <div class="sr-side sr-support">
            <span>SUPPORT</span>
            <b>{fmt_price(support)}</b>
            <small>
                {support_room:.2f}% below spot
            </small>
        </div>

        <div class="sr-line">
            <div class="room-label">
                CURRENT SPOT
            </div>

            <div class="current-marker">
                {fmt_price(spot)}
                <span>SPOT</span>
            </div>

            <div class="room-label">
                {resistance_room:.2f}% to resistance
            </div>
        </div>

        <div class="sr-side sr-resistance">
            <span>RESISTANCE</span>
            <b>{fmt_price(resistance)}</b>
            <small>
                {resistance_room:.2f}% above spot
            </small>
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# TRADE PLANS
# ============================================================

st.markdown(
    '<div class="section-heading">📌 Trade Plans</div>',
    unsafe_allow_html=True,
)

plan_col1, plan_col2 = st.columns(2)

with plan_col1:
    render_plan_card(
        call_plan
    )

with plan_col2:
    render_plan_card(
        put_plan
    )


# ============================================================
# TRADE CHECKS
# ============================================================

st.markdown(
    '<div class="section-heading">✅ Trade Validation</div>',
    unsafe_allow_html=True,
)

render_checks(
    primary_plan,
    tf5,
    tf30,
    daily,
)


# ============================================================
# WHY THIS DECISION
# ============================================================

st.markdown(
    '<div class="section-heading">🧠 Why the Engine Says This</div>',
    unsafe_allow_html=True,
)

render_why(
    primary_plan
)


# ============================================================
# MARKET STATUS
# ============================================================

status_css = (
    "status-green"
    if is_open
    else "status-grey"
)

status_title = (
    "● LIVE DATA"
    if is_open
    else "● MARKET CLOSED"
)

st.markdown(
    '<div class="section-heading">📡 Data Status</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="status-panel {status_css}">
        <div class="status-title">
            {status_title}
        </div>

        <div class="status-grid">

            <div>
                <span>SYMBOL</span>
                <b>{trading_symbol}</b>
            </div>

            <div>
                <span>SPOT</span>
                <b>{fmt_price(spot)}</b>
            </div>

            <div>
                <span>EXPIRY</span>
                <b>{selected_expiry}</b>
            </div>

        </div>

        <div class="status-note">
            Analysis updated {current_time} IST.<br>
            Market-status display follows the NSE regular-session clock.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SCANNER
# ============================================================

if scanner_enabled:
    st.markdown(
        '<div class="section-heading">🔎 F&O Scanner — PoP &gt; 60%</div>',
        unsafe_allow_html=True,
    )

    scanner = scanner_results(
        chain,
        spot,
        support,
        resistance,
        pcr,
        tf5,
        tf30,
        daily,
        risk_profile,
    )

    if not scanner:
        st.markdown(
            """
            <div class="tab-alert tab-danger">
                No option candidate currently satisfies the
                PoP &gt; 60% scanner condition together with
                basic liquidity/spread checks.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for item in scanner:
            side_label = (
                "CALL"
                if item["side"] == "CE"
                else "PUT"
            )

            action_label = item["readiness"]

            st.markdown(
                f"""
                <div class="scanner-card">
                    <div style="display:flex;
                                justify-content:space-between;
                                align-items:center;
                                gap:10px;
                                flex-wrap:wrap;">

                        <div>
                            <div class="scanner-title">
                                {side_label} BUY •
                                {fmt_price(item["strike"])}
                            </div>

                            <div class="scanner-meta">
                                {action_label}
                            </div>
                        </div>

                        <div style="text-align:right;">
                            <div style="font-size:10px;
                                        color:#667085;
                                        font-weight:800;">
                                PoP
                            </div>

                            <div style="font-size:20px;
                                        font-weight:900;
                                        color:#182230;">
                                {fmt_pct(item["pop"])}
                            </div>
                        </div>

                    </div>

                    <div style="display:grid;
                                grid-template-columns:
                                repeat(6,1fr);
                                gap:8px;
                                margin-top:12px;">

                        <div>
                            <span style="font-size:9px;
                                         color:#667085;">
                                SCORE
                            </span>
                            <b>{item["score"]:.0f}</b>
                        </div>

                        <div>
                            <span style="font-size:9px;
                                         color:#667085;">
                                ENTRY
                            </span>
                            <b>{fmt_price(item["entry"])}</b>
                        </div>

                        <div>
                            <span style="font-size:9px;
                                         color:#667085;">
                                SL
                            </span>
                            <b>{fmt_price(item["sl"])}</b>
                        </div>

                        <div>
                            <span style="font-size:9px;
                                         color:#667085;">
                                TARGET
                            </span>
                            <b>{fmt_price(item["target1"])}</b>
                        </div>

                        <div>
                            <span style="font-size:9px;
                                         color:#667085;">
                                DELTA
                            </span>
                            <b>{fmt_delta(item["delta"])}</b>
                        </div>

                        <div>
                            <span style="font-size:9px;
                                         color:#667085;">
                                R:R
                            </span>
                            <b>1:{item["rr1"]:.2f}</b>
                        </div>

                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================
# OPTION CHAIN
# ============================================================

st.markdown(
    '<div class="section-heading">📋 Live Option Chain</div>',
    unsafe_allow_html=True,
)

display_chain = chain.copy()

atm_index = (
    (display_chain["Strike"] - spot)
    .abs()
    .idxmin()
)

atm_strike = safe_float(
    display_chain.loc[
        atm_index,
        "Strike",
    ]
)

display_chain["_distance"] = (
    display_chain["Strike"] - spot
).abs()

# Show a useful local window around ATM.
display_chain = (
    display_chain
    .sort_values("_distance")
    .head(15)
    .sort_values("Strike")
    .drop(columns=["_distance"])
    .copy()
)

table_columns = [
    "CE OI",
    "CE Chg OI",
    "CE Volume",
    "CE IV",
    "CE LTP",
    "Strike",
    "PE LTP",
    "PE IV",
    "PE Volume",
    "PE Chg OI",
    "PE OI",
]

available_columns = [
    c
    for c in table_columns
    if c in display_chain.columns
]

chain_display = display_chain[
    available_columns
].copy()

rename_map = {
    "CE OI": "CE OI",
    "CE Chg OI": "CE ΔOI",
    "CE Volume": "CE Vol",
    "CE IV": "CE IV",
    "CE LTP": "CE LTP",
    "Strike": "STRIKE",
    "PE LTP": "PE LTP",
    "PE IV": "PE IV",
    "PE Volume": "PE Vol",
    "PE Chg OI": "PE ΔOI",
    "PE OI": "PE OI",
}

chain_display = chain_display.rename(
    columns=rename_map
)

st.dataframe(
    chain_display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "CE OI": st.column_config.NumberColumn(
            "CE OI",
            format="%,.0f",
        ),
        "CE ΔOI": st.column_config.NumberColumn(
            "CE ΔOI",
            format="%,.0f",
        ),
        "CE Vol": st.column_config.NumberColumn(
            "CE Vol",
            format="%,.0f",
        ),
        "CE IV": st.column_config.NumberColumn(
            "CE IV",
            format="%.2f",
        ),
        "CE LTP": st.column_config.NumberColumn(
            "CE LTP",
            format="₹%.2f",
        ),
        "STRIKE": st.column_config.NumberColumn(
            "STRIKE",
            format="%.0f",
        ),
        "PE LTP": st.column_config.NumberColumn(
            "PE LTP",
            format="₹%.2f",
        ),
        "PE IV": st.column_config.NumberColumn(
            "PE IV",
            format="%.2f",
        ),
        "PE Vol": st.column_config.NumberColumn(
            "PE Vol",
            format="%,.0f",
        ),
        "PE ΔOI": st.column_config.NumberColumn(
            "PE ΔOI",
            format="%,.0f",
        ),
        "PE OI": st.column_config.NumberColumn(
            "PE OI",
            format="%,.0f",
        ),
    },
)


# ============================================================
# TECHNICAL ANALYSIS
# ============================================================

st.markdown(
    '<div class="section-heading">📈 Technical Analysis</div>',
    unsafe_allow_html=True,
)

technical_table = pd.DataFrame(
    [
        {
            "Timeframe": "5 Minute",
            "Trend": tf5.get("trend"),
            "RSI": round(
                safe_float(tf5.get("rsi"), 50),
                1,
            ),
            "EMA 20": round(
                safe_float(tf5.get("ema20"), spot),
                2,
            ),
            "EMA 50": round(
                safe_float(tf5.get("ema50"), spot),
                2,
            ),
            "ADX": round(
                safe_float(tf5.get("adx"), 0),
                1,
            ),
            "Momentum %": round(
                safe_float(
                    tf5.get("momentum"),
                    0,
                ),
                2,
            ),
            "Volume Ratio": round(
                safe_float(
                    tf5.get("volume_ratio"),
                    1,
                ),
                2,
            ),
        },
        {
            "Timeframe": "30 Minute",
            "Trend": tf30.get("trend"),
            "RSI": round(
                safe_float(tf30.get("rsi"), 50),
                1,
            ),
            "EMA 20": round(
                safe_float(tf30.get("ema20"), spot),
                2,
            ),
            "EMA 50": round(
                safe_float(tf30.get("ema50"), spot),
                2,
            ),
            "ADX": round(
                safe_float(tf30.get("adx"), 0),
                1,
            ),
            "Momentum %": round(
                safe_float(
                    tf30.get("momentum"),
                    0,
                ),
                2,
            ),
            "Volume Ratio": round(
                safe_float(
                    tf30.get("volume_ratio"),
                    1,
                ),
                2,
            ),
        },
        {
            "Timeframe": "Daily",
            "Trend": daily.get("trend"),
            "RSI": round(
                safe_float(daily.get("rsi"), 50),
                1,
            ),
            "EMA 20": round(
                safe_float(daily.get("ema20"), spot),
                2,
            ),
            "EMA 50": round(
                safe_float(daily.get("ema50"), spot),
                2,
            ),
            "ADX": round(
                safe_float(daily.get("adx"), 0),
                1,
            ),
            "Momentum %": round(
                safe_float(
                    daily.get("momentum"),
                    0,
                ),
                2,
            ),
            "Volume Ratio": round(
                safe_float(
                    daily.get("volume_ratio"),
                    1,
                ),
                2,
            ),
        },
    ]
)

st.dataframe(
    technical_table,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# OI WALLS
# ============================================================

st.markdown(
    '<div class="section-heading">🏰 Major OI Walls</div>',
    unsafe_allow_html=True,
)

wall_col1, wall_col2 = st.columns(2)

with wall_col1:
    st.markdown(
        "### 🟢 Put OI Walls"

    )

    put_wall_df = pd.DataFrame(
        oi_info.get(
            "put_walls",
            [],
        )
    )

    if not put_wall_df.empty:
        put_wall_df = put_wall_df.rename(
            columns={
                "Strike": "Strike",
                "PE OI": "PE OI",
                "PE Chg OI": "PE ΔOI",
            }
        )

        st.dataframe(
            put_wall_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No put OI wall data available."
        )

with wall_col2:
    st.markdown(
        "### 🔴 Call OI Walls"
    )

    call_wall_df = pd.DataFrame(
        oi_info.get(
            "call_walls",
            [],
        )
    )

    if not call_wall_df.empty:
        call_wall_df = call_wall_df.rename(
            columns={
                "Strike": "Strike",
                "CE OI": "CE OI",
                "CE Chg OI": "CE ΔOI",
            }
        )

        st.dataframe(
            call_wall_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No call OI wall data available."
        )


# ============================================================
# EXPIRY INFORMATION
# ============================================================

with st.expander(
    "📅 Available Expiries"
):
    st.write(
        ", ".join(expiries[:10])
    )


# ============================================================
# ENGINE NOTES
# ============================================================

with st.expander(
    "🧠 How the Engine Thinks"
):
    st.markdown(
        """
        **The application does not treat one indicator as sufficient.**

        The setup score combines:

        - Multi-timeframe trend alignment
        - 5-minute momentum
        - RSI
        - ADX
        - VWAP relationship
        - PCR
        - Option OI and OI change
        - Delta
        - IV
        - Option spread
        - Option volume
        - Option OI
        - Strike distance from spot
        - OI support/resistance room
        - Upstox PoP

        **Important distinction:**

        `Setup Score` and `PoP` are not the same thing.

        The setup score is a rule-based ranking of the current market
        conditions. PoP is the probability value supplied by the option-chain
        data. Neither should be interpreted as a guarantee that a trade will
        be profitable.

        The engine also deliberately requires an actual price trigger,
        5-minute directional confirmation and volume confirmation before it
        changes the final decision to `CALL BUY` or `PUT BUY`.

        If those conditions are not satisfied, the final decision remains
        `NO TRADE`, even when an option has a high score.
        """
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div style="
        text-align:center;
        color:#98a2b3;
        font-size:10px;
        padding:20px 0 5px;
    ">
        FO PRO Trader Assistant • Upstox REST API •
        Analysis only • No automatic order execution
    </div>
    """,
    unsafe_allow_html=True,
)
