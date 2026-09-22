import html
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests
import streamlit as st


# ============================================================
# PAGE CONFIG
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

MIN_API_GAP = 0.80

_API_LOCK = threading.Lock()
_LAST_API_REQUEST = 0.0
_RATE_LIMIT_UNTIL = 0.0


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>

.stApp {
    background: #f6f8fb;
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

.topbar {
    background: linear-gradient(100deg, #102a43, #1f4b73);
    border-radius: 18px;
    padding: 18px 22px;
    color: white;
    margin-bottom: 18px;
    box-shadow: 0 8px 25px rgba(16,42,67,0.12);
}

.topbar-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
}

.topbar-title {
    font-size: 25px;
    font-weight: 900;
    letter-spacing: -0.4px;
}

.topbar-sub {
    font-size: 12px;
    margin-top: 5px;
    opacity: 0.78;
}

.live-block,
.closed-block {
    min-width: 155px;
    padding: 11px 15px;
    border-radius: 12px;
    text-align: center;
    font-size: 11px;
    font-weight: 700;
}

.live-block {
    background: rgba(22,163,74,0.16);
    border: 1px solid rgba(74,222,128,0.45);
    color: #dcfce7;
}

.closed-block {
    background: rgba(220,38,38,0.16);
    border: 1px solid rgba(252,165,165,0.45);
    color: #fee2e2;
}

.live-block strong,
.closed-block strong {
    font-size: 12px;
}

.hero-card {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 14px;
    box-shadow: 0 5px 18px rgba(15,23,42,0.04);
}

.hero-title {
    font-size: 11px;
    color: #667085;
    font-weight: 800;
    letter-spacing: .6px;
}

.hero-price {
    font-size: 32px;
    font-weight: 900;
    color: #182230;
    margin-top: 4px;
}

.hero-meta {
    font-size: 11px;
    color: #667085;
    margin-top: 4px;
}

.metric-card {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 14px;
    padding: 15px;
    min-height: 92px;
    box-shadow: 0 4px 15px rgba(15,23,42,0.035);
}

.metric-label {
    font-size: 10px;
    font-weight: 800;
    color: #667085;
    letter-spacing: .5px;
}

.metric-value {
    font-size: 21px;
    font-weight: 900;
    color: #182230;
    margin-top: 6px;
}

.metric-note {
    font-size: 10px;
    color: #98a2b3;
    margin-top: 3px;
}

.section-title {
    font-size: 18px;
    font-weight: 900;
    color: #182230;
    margin: 22px 0 10px;
}

.decision-card {
    border-radius: 18px;
    padding: 20px;
    margin: 12px 0;
    background: white;
    border: 1px solid #e5eaf0;
    box-shadow: 0 6px 20px rgba(15,23,42,0.05);
}

.decision-call {
    border-left: 6px solid #16a34a;
}

.decision-put {
    border-left: 6px solid #dc2626;
}

.decision-neutral {
    border-left: 6px solid #64748b;
}

.decision-title {
    font-size: 24px;
    font-weight: 950;
    color: #182230;
}

.decision-sub {
    color: #667085;
    font-size: 12px;
    margin-top: 4px;
}

.decision-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 9px;
    margin-top: 15px;
}

.decision-stats > div {
    background: #f8fafc;
    border-radius: 10px;
    padding: 10px;
}

.decision-stats span {
    display: block;
    font-size: 9px;
    color: #667085;
    font-weight: 800;
}

.decision-stats b {
    display: block;
    font-size: 15px;
    color: #182230;
    margin-top: 3px;
}

.option-card {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 16px;
    padding: 17px;
    margin-bottom: 12px;
    box-shadow: 0 5px 18px rgba(15,23,42,0.04);
}

.option-card.call {
    border-top: 4px solid #16a34a;
}

.option-card.put {
    border-top: 4px solid #dc2626;
}

.option-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
}

.option-title {
    font-size: 14px;
    color: #667085;
    font-weight: 800;
}

.option-strike {
    font-size: 24px;
    color: #182230;
    font-weight: 950;
    margin-top: 2px;
}

.option-readiness {
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 10px;
    font-weight: 900;
    white-space: nowrap;
}

.status-green {
    background: #dcfce7;
    color: #166534;
}

.status-red {
    background: #fee2e2;
    color: #991b1b;
}

.status-yellow {
    background: #fef3c7;
    color: #92400e;
}

.option-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-top: 14px;
}

.option-grid > div {
    background: #f8fafc;
    border-radius: 9px;
    padding: 9px;
}

.option-grid span {
    display: block;
    font-size: 9px;
    color: #667085;
    font-weight: 800;
}

.option-grid b {
    display: block;
    color: #182230;
    font-size: 13px;
    margin-top: 3px;
}

.exit-rule {
    background: #f8fafc;
    border-radius: 9px;
    padding: 10px 12px;
    margin-top: 9px;
}

.exit-rule span {
    display: block;
    color: #667085;
    font-size: 9px;
    font-weight: 900;
    margin-bottom: 4px;
}

.exit-rule b {
    font-size: 11px;
    color: #344054;
    line-height: 1.45;
}

.validation-card,
.why-card,
.status-card,
.sr-card {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 16px;
    padding: 17px;
    margin-bottom: 15px;
    box-shadow: 0 5px 18px rgba(15,23,42,0.035);
}

.check-row {
    display: grid;
    grid-template-columns: 1.4fr auto 1fr;
    align-items: center;
    gap: 10px;
    padding: 10px 0;
    border-bottom: 1px solid #eef2f6;
}

.check-row span {
    font-size: 11px;
    font-weight: 700;
    color: #344054;
}

.check-row strong {
    font-size: 10px;
    padding: 5px 8px;
    border-radius: 6px;
}

.check-row small {
    color: #98a2b3;
    font-size: 10px;
    text-align: right;
}

.check-pass {
    background: #dcfce7;
    color: #166534;
}

.check-wait {
    background: #fef3c7;
    color: #92400e;
}

.check-fail {
    background: #fee2e2;
    color: #991b1b;
}

.check-total {
    display: flex;
    justify-content: space-between;
    margin-top: 13px;
    padding-top: 12px;
    border-top: 2px solid #eef2f6;
    font-size: 12px;
    font-weight: 800;
}

.why-item {
    padding: 9px 11px;
    border-radius: 8px;
    margin-bottom: 7px;
    font-size: 11px;
}

.why-pass {
    background: #ecfdf3;
    color: #166534;
}

.why-warning {
    background: #fff7ed;
    color: #9a3412;
}

.why-fail {
    background: #fef2f2;
    color: #991b1b;
}

.sr-map {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 16px;
    padding: 18px;
    display: grid;
    grid-template-columns: 1fr 1.4fr 1fr;
    align-items: center;
    gap: 15px;
}

.sr-side {
    padding: 14px;
    border-radius: 12px;
    text-align: center;
}

.sr-support {
    background: #ecfdf3;
}

.sr-resistance {
    background: #fef2f2;
}

.sr-side span {
    display: block;
    font-size: 9px;
    font-weight: 900;
    color: #667085;
}

.sr-side b {
    display: block;
    font-size: 20px;
    font-weight: 950;
    color: #182230;
    margin-top: 4px;
}

.sr-side small {
    display: block;
    color: #667085;
    font-size: 10px;
    margin-top: 3px;
}

.sr-line {
    text-align: center;
}

.current-marker {
    background: #182230;
    color: white;
    display: inline-block;
    padding: 9px 15px;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 900;
}

.current-marker span {
    display: block;
    font-size: 8px;
    opacity: .7;
}

.room-label {
    font-size: 10px;
    color: #667085;
    font-weight: 700;
    margin: 7px;
}

.scanner-card {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 14px;
    padding: 14px;
    margin-bottom: 9px;
    box-shadow: 0 4px 14px rgba(15,23,42,0.03);
}

.scanner-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
}

.scanner-title {
    font-size: 13px;
    font-weight: 900;
    color: #182230;
}

.scanner-meta {
    font-size: 9px;
    color: #667085;
    font-weight: 800;
    margin-top: 3px;
}

.scanner-stats {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 7px;
    margin-top: 11px;
}

.scanner-stats > div {
    background: #f8fafc;
    padding: 8px;
    border-radius: 8px;
}

.scanner-stats span {
    display: block;
    font-size: 8px;
    color: #667085;
    font-weight: 800;
}

.scanner-stats b {
    display: block;
    font-size: 12px;
    color: #182230;
    margin-top: 2px;
}

.info-box {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1e40af;
    padding: 12px 14px;
    border-radius: 10px;
    font-size: 11px;
    line-height: 1.5;
}

.warning-box {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    color: #9a3412;
    padding: 12px 14px;
    border-radius: 10px;
    font-size: 11px;
    line-height: 1.5;
}

.error-box {
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #991b1b;
    padding: 12px 14px;
    border-radius: 10px;
    font-size: 11px;
    line-height: 1.5;
}

.status-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
}

.status-grid > div {
    background: #f8fafc;
    border-radius: 9px;
    padding: 10px;
}

.status-grid span {
    display: block;
    font-size: 9px;
    color: #667085;
    font-weight: 800;
}

.status-grid b {
    display: block;
    font-size: 13px;
    color: #182230;
    margin-top: 3px;
}

.status-note {
    color: #667085;
    font-size: 10px;
    margin-top: 12px;
    line-height: 1.5;
}

.wall-card {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 13px;
    padding: 13px;
    margin-bottom: 8px;
}

.wall-title {
    font-size: 12px;
    font-weight: 900;
    color: #182230;
}

.wall-meta {
    font-size: 10px;
    color: #667085;
    margin-top: 4px;
}

.small-muted {
    font-size: 10px;
    color: #98a2b3;
}

.footer {
    text-align: center;
    color: #98a2b3;
    font-size: 10px;
    padding: 22px 0 5px;
}

@media (max-width: 900px) {

    .topbar-row {
        flex-direction: column;
        align-items: stretch;
    }

    .live-block,
    .closed-block {
        width: 100%;
    }

    .decision-stats {
        grid-template-columns: repeat(2, 1fr);
    }

    .option-grid {
        grid-template-columns: repeat(2, 1fr);
    }

    .scanner-stats {
        grid-template-columns: repeat(3, 1fr);
    }

    .sr-map {
        grid-template-columns: 1fr;
    }

    .status-grid {
        grid-template-columns: 1fr;
    }

}

@media (max-width: 600px) {

    .block-container {
        padding-left: .7rem;
        padding-right: .7rem;
    }

    .topbar-title {
        font-size: 21px;
    }

    .hero-price {
        font-size: 27px;
    }

    .decision-title {
        font-size: 21px;
    }

    .scanner-stats {
        grid-template-columns: repeat(2, 1fr);
    }

    .check-row {
        grid-template-columns: 1fr auto;
    }

    .check-row small {
        grid-column: 1 / -1;
        text-align: left;
    }

}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# EXCEPTIONS
# ============================================================

class UpstoxError(RuntimeError):
    pass


class UpstoxRateLimitError(UpstoxError):
    def __init__(self, message, retry_after=30):
        super().__init__(message)
        self.retry_after = int(max(1, retry_after))


# ============================================================
# TIME / MARKET STATUS
# ============================================================

def now_ist():
    return datetime.now(IST)


def is_market_open(dt=None):
    if dt is None:
        dt = now_ist()

    if dt.weekday() >= 5:
        return False

    current = dt.hour * 60 + dt.minute

    return 9 * 60 + 15 <= current <= 15 * 60 + 30


def rate_limit_remaining():
    return max(0, int(_RATE_LIMIT_UNTIL - time.time()))


# ============================================================
# TOKEN
# ============================================================

def get_token():
    try:
        return str(st.secrets.get("UPSTOX_ACCESS_TOKEN", "")).strip()
    except Exception:
        return ""


TOKEN = get_token()

if not TOKEN:
    st.error(
        "Upstox access token is not configured. "
        "Add UPSTOX_ACCESS_TOKEN under Streamlit → App settings → Secrets."
    )
    st.stop()


HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}


# ============================================================
# API
# ============================================================

def _extract_retry_after(response):
    value = response.headers.get("Retry-After")

    if value:
        try:
            return max(1, int(float(value)))
        except Exception:
            pass

    try:
        body = response.json()
    except Exception:
        body = {}

    if isinstance(body, dict):
        candidates = [
            body.get("retry_after"),
            body.get("retryAfter"),
        ]

        errors = body.get("errors")

        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                candidates.extend(
                    [
                        first.get("retry_after"),
                        first.get("retryAfter"),
                    ]
                )

        for candidate in candidates:
            try:
                return max(1, int(float(candidate)))
            except Exception:
                continue

    return 30


def api_get(path, params=None, timeout=15):
    global _LAST_API_REQUEST
    global _RATE_LIMIT_UNTIL

    remaining = rate_limit_remaining()

    if remaining > 0:
        raise UpstoxRateLimitError(
            f"Upstox rate limit cooldown active. Please wait {remaining} seconds.",
            remaining,
        )

    with _API_LOCK:

        remaining = rate_limit_remaining()

        if remaining > 0:
            raise UpstoxRateLimitError(
                f"Upstox rate limit cooldown active. Please wait {remaining} seconds.",
                remaining,
            )

        elapsed = time.time() - _LAST_API_REQUEST

        if elapsed < MIN_API_GAP:
            time.sleep(MIN_API_GAP - elapsed)

        try:
            response = requests.get(
                f"{API_BASE}{path}",
                headers=HEADERS,
                params=params or {},
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise UpstoxError(f"Unable to connect to Upstox: {exc}") from exc

        _LAST_API_REQUEST = time.time()

    if response.status_code == 429:
        retry_after = _extract_retry_after(response)
        _RATE_LIMIT_UNTIL = time.time() + retry_after

        raise UpstoxRateLimitError(
            f"Upstox API rate limit reached. "
            f"Please wait approximately {retry_after} seconds.",
            retry_after,
        )

    if response.status_code in (401, 403):
        raise UpstoxError(
            "Upstox authentication failed. "
            "Your access token may have expired or may be invalid."
        )

    if response.status_code >= 500:
        raise UpstoxError(
            f"Upstox server temporarily returned HTTP {response.status_code}."
        )

    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:300]

        raise UpstoxError(
            f"Upstox API error {response.status_code}: {detail}"
        )

    try:
        return response.json()
    except Exception as exc:
        raise UpstoxError("Upstox returned an invalid JSON response.") from exc


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_float(value, default=np.nan):
    try:
        if value is None:
            return default

        if isinstance(value, str):
            value = value.replace(",", "").strip()

        x = float(value)

        if not np.isfinite(x):
            return default

        return x

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


def fmt_pct(value):
    x = safe_float(value)

    if not np.isfinite(x):
        return "—"

    return f"{x:.1f}%"


def fmt_delta(value):
    x = safe_float(value)

    if not np.isfinite(x):
        return "—"

    return f"{x:.2f}"


def normalize_pop(value):
    x = safe_float(value)

    if not np.isfinite(x):
        return np.nan

    if 0 <= x <= 1:
        x *= 100

    return x


def esc(value):
    return html.escape(str(value))


def alias_symbol(symbol):
    s = str(symbol).strip().upper().replace(" ", "")

    aliases = {
        "NIFTY50": "NIFTY",
        "NIFTYBANK": "BANKNIFTY",
        "NIFTYFIN": "FINNIFTY",
        "MIDCAPNIFTY": "MIDCPNIFTY",
        "MIDNIFTY": "MIDCPNIFTY",
    }

    return aliases.get(s, s)


def extract_ltp(data):
    if not isinstance(data, dict):
        return np.nan

    for key in (
        "last_price",
        "ltp",
        "last_traded_price",
        "lastTradedPrice",
        "close",
    ):
        value = safe_float(data.get(key))

        if np.isfinite(value):
            return value

    return np.nan


# ============================================================
# INSTRUMENT SEARCH
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def search_underlying(symbol):
    symbol = alias_symbol(symbol)

    index_symbols = {
        "NIFTY",
        "BANKNIFTY",
        "FINNIFTY",
        "MIDCPNIFTY",
    }

    segments = ["INDEX"] if symbol in index_symbols else ["EQ", "INDEX"]

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

        rows = payload.get("data", [])

        if not isinstance(rows, list):
            rows = []

        exact = []

        for row in rows:
            if str(row.get("trading_symbol", "")).upper() == symbol:
                exact.append(row)

        if exact:
            if segment == "INDEX":
                exact.sort(
                    key=lambda x: (
                        0
                        if str(x.get("segment", "")).upper()
                        == "NSE_INDEX"
                        else 1
                    )
                )

            return exact[0]

        if rows:
            rows.sort(
                key=lambda x: len(
                    str(x.get("trading_symbol", ""))
                )
            )

            return rows[0]

    raise UpstoxError(
        f"Could not find NSE instrument for '{symbol}'."
    )


# ============================================================
# OPTION CONTRACTS
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def get_contracts(underlying_key):
    payload = api_get(
        "/v2/option/contract",
        params={
            "instrument_key": underlying_key,
        },
    )

    rows = payload.get("data", [])

    if not isinstance(rows, list) or not rows:
        raise UpstoxError(
            "Upstox returned no option contracts for this instrument."
        )

    return rows


def available_expiries(contracts):
    today = now_ist().date()
    expiries = set()

    for row in contracts:
        raw = row.get("expiry")

        if not raw:
            continue

        try:
            expiry = datetime.fromisoformat(
                str(raw).replace("Z", "+00:00")
            ).date()
        except Exception:
            try:
                expiry = datetime.strptime(
                    str(raw)[:10],
                    "%Y-%m-%d",
                ).date()
            except Exception:
                continue

        if expiry >= today:
            expiries.add(expiry)

    return sorted(expiries)


# ============================================================
# OPTION CHAIN
# ============================================================

@st.cache_data(ttl=45, show_spinner=False)
def get_option_chain(underlying_key, expiry):
    payload = api_get(
        "/v2/option/chain",
        params={
            "instrument_key": underlying_key,
            "expiry_date": str(expiry),
        },
    )

    rows = payload.get("data", [])

    if not isinstance(rows, list) or not rows:
        raise UpstoxError(
            f"No option-chain data returned for expiry {expiry}."
        )

    return rows


def _nested(data, *keys):
    if not isinstance(data, dict):
        return None

    for key in keys:
        if key in data:
            return data[key]

    return None


def _change_oi(option_data):
    if not isinstance(option_data, dict):
        return np.nan

    direct = _nested(
        option_data,
        "change_in_oi",
        "changeInOi",
        "oi_change",
        "chg_oi",
        "change_oi",
    )

    value = safe_float(direct)

    if np.isfinite(value):
        return value

    oi = safe_float(
        _nested(option_data, "oi", "open_interest")
    )

    prev = safe_float(
        _nested(
            option_data,
            "prev_oi",
            "previous_oi",
            "prev_open_interest",
        )
    )

    if np.isfinite(oi) and np.isfinite(prev):
        return oi - prev

    return np.nan


def normalize_chain(rows):
    records = []

    for item in rows:

        strike = safe_float(
            _nested(
                item,
                "strike_price",
                "strike",
                "strikePrice",
            )
        )

        if not np.isfinite(strike):
            continue

        ce = _nested(
            item,
            "call_options",
            "ce",
            "CE",
            "call",
        )

        pe = _nested(
            item,
            "put_options",
            "pe",
            "PE",
            "put",
        )

        if not isinstance(ce, dict):
            ce = {}

        if not isinstance(pe, dict):
            pe = {}

        ce_md = _nested(
            ce,
            "market_data",
            "marketData",
        )

        pe_md = _nested(
            pe,
            "market_data",
            "marketData",
        )

        ce_g = _nested(
            ce,
            "option_greeks",
            "optionGreeks",
            "greeks",
        )

        pe_g = _nested(
            pe,
            "option_greeks",
            "optionGreeks",
            "greeks",
        )

        if not isinstance(ce_md, dict):
            ce_md = ce

        if not isinstance(pe_md, dict):
            pe_md = pe

        if not isinstance(ce_g, dict):
            ce_g = ce

        if not isinstance(pe_g, dict):
            pe_g = pe

        ce_oi = safe_float(
            _nested(
                ce_md,
                "oi",
                "open_interest",
            )
        )

        pe_oi = safe_float(
            _nested(
                pe_md,
                "oi",
                "open_interest",
            )
        )

        ce_ltp = safe_float(
            _nested(
                ce_md,
                "ltp",
                "last_price",
                "last_traded_price",
            )
        )

        pe_ltp = safe_float(
            _nested(
                pe_md,
                "ltp",
                "last_price",
                "last_traded_price",
            )
        )

        ce_bid = safe_float(
            _nested(
                ce_md,
                "bid_price",
                "best_bid_price",
                "bid",
            )
        )

        ce_ask = safe_float(
            _nested(
                ce_md,
                "ask_price",
                "best_ask_price",
                "ask",
            )
        )

        pe_bid = safe_float(
            _nested(
                pe_md,
                "bid_price",
                "best_bid_price",
                "bid",
            )
        )

        pe_ask = safe_float(
            _nested(
                pe_md,
                "ask_price",
                "best_ask_price",
                "ask",
            )
        )

        ce_volume = safe_float(
            _nested(
                ce_md,
                "volume",
                "traded_volume",
            )
        )

        pe_volume = safe_float(
            _nested(
                pe_md,
                "volume",
                "traded_volume",
            )
        )

        ce_iv = safe_float(
            _nested(
                ce_g,
                "iv",
                "implied_volatility",
            )
        )

        pe_iv = safe_float(
            _nested(
                pe_g,
                "iv",
                "implied_volatility",
            )
        )

        ce_delta = safe_float(
            _nested(
                ce_g,
                "delta",
            )
        )

        pe_delta = safe_float(
            _nested(
                pe_g,
                "delta",
            )
        )

        ce_pop = normalize_pop(
            _nested(
                ce_g,
                "pop",
                "probability_of_profit",
                "probabilityOfProfit",
            )
        )

        pe_pop = normalize_pop(
            _nested(
                pe_g,
                "pop",
                "probability_of_profit",
                "probabilityOfProfit",
            )
        )

        ce_key = _nested(
            ce,
            "instrument_key",
            "instrumentKey",
        )

        pe_key = _nested(
            pe,
            "instrument_key",
            "instrumentKey",
        )

        records.append(
            {
                "Strike": strike,

                "CE Key": ce_key,
                "CE LTP": ce_ltp,
                "CE Bid": ce_bid,
                "CE Ask": ce_ask,
                "CE OI": ce_oi,
                "CE Chg OI": _change_oi(ce_md),
                "CE Volume": ce_volume,
                "CE IV": ce_iv,
                "CE Delta": ce_delta,
                "CE PoP": ce_pop,

                "PE Key": pe_key,
                "PE LTP": pe_ltp,
                "PE Bid": pe_bid,
                "PE Ask": pe_ask,
                "PE OI": pe_oi,
                "PE Chg OI": _change_oi(pe_md),
                "PE Volume": pe_volume,
                "PE IV": pe_iv,
                "PE Delta": pe_delta,
                "PE PoP": pe_pop,
            }
        )

    columns = [
        "Strike",
        "CE Key",
        "CE LTP",
        "CE Bid",
        "CE Ask",
        "CE OI",
        "CE Chg OI",
        "CE Volume",
        "CE IV",
        "CE Delta",
        "CE PoP",
        "PE Key",
        "PE LTP",
        "PE Bid",
        "PE Ask",
        "PE OI",
        "PE Chg OI",
        "PE Volume",
        "PE IV",
        "PE Delta",
        "PE PoP",
    ]

    if not records:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(records)

    return (
        df.sort_values("Strike")
        .drop_duplicates("Strike")
        .reset_index(drop=True)
    )


# ============================================================
# QUOTE
# ============================================================

@st.cache_data(ttl=30, show_spinner=False)
def get_quote(instrument_key):
    payload = api_get(
        "/v3/market-quote/quotes",
        params={
            "instrument_key": instrument_key,
        },
    )

    data = payload.get("data", {})

    if not isinstance(data, dict):
        return {}

    if instrument_key in data:
        return data[instrument_key]

    if data:
        return next(iter(data.values()))

    return {}


# ============================================================
# HISTORICAL DATA
# ============================================================

def _parse_candles(payload):
    rows = payload.get("data", {}).get("candles", [])

    if not isinstance(rows, list) or not rows:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "oi",
            ]
        )

    records = []

    for row in rows:

        if len(row) < 6:
            continue

        records.append(
            {
                "timestamp": row[0],
                "open": safe_float(row[1]),
                "high": safe_float(row[2]),
                "low": safe_float(row[3]),
                "close": safe_float(row[4]),
                "volume": safe_float(row[5], 0),
                "oi": safe_float(row[6], 0)
                if len(row) > 6
                else 0,
            }
        )

    df = pd.DataFrame(records)

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
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

    df = df.dropna(
        subset=["timestamp", "close"]
    ).sort_values("timestamp")

    return df.reset_index(drop=True)


@st.cache_data(ttl=60, show_spinner=False)
def get_intraday_candles(instrument_key, interval=5):
    encoded = quote(instrument_key, safe="")

    payload = api_get(
        f"/v3/historical-candle/intraday/"
        f"{encoded}/minutes/{interval}",
        timeout=15,
    )

    return _parse_candles(payload)


@st.cache_data(ttl=900, show_spinner=False)
def get_30m_candles(instrument_key):
    end = now_ist().date()
    start = end - timedelta(days=45)

    encoded = quote(instrument_key, safe="")

    payload = api_get(
        f"/v3/historical-candle/"
        f"{encoded}/minutes/30/"
        f"{end}/{start}",
        timeout=15,
    )

    return _parse_candles(payload)


@st.cache_data(ttl=1800, show_spinner=False)
def get_daily_candles(instrument_key):
    end = now_ist().date()
    start = end - timedelta(days=180)

    encoded = quote(instrument_key, safe="")

    payload = api_get(
        f"/v3/historical-candle/"
        f"{encoded}/days/1/"
        f"{end}/{start}",
        timeout=15,
    )

    return _parse_candles(payload)


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
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (
        100 / (1 + rs)
    )

    rsi = rsi.where(
        avg_loss != 0,
        100,
    )

    return rsi


def _atr(df, period=14):
    previous_close = df["close"].shift(1)

    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - previous_close).abs(),
            (df["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()


def _adx(df, period=14):
    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where(
            (up_move > down_move)
            & (up_move > 0),
            up_move,
            0,
        ),
        index=df.index,
    )

    minus_dm = pd.Series(
        np.where(
            (down_move > up_move)
            & (down_move > 0),
            down_move,
            0,
        ),
        index=df.index,
    )

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
        alpha=1 / period,
        adjust=False,
    ).mean()

    plus_di = (
        100
        * plus_dm.ewm(
            alpha=1 / period,
            adjust=False,
        ).mean()
        / atr.replace(0, np.nan)
    )

    minus_di = (
        100
        * minus_dm.ewm(
            alpha=1 / period,
            adjust=False,
        ).mean()
        / atr.replace(0, np.nan)
    )

    dx = (
        100
        * (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(
            0,
            np.nan,
        )
    )

    return dx.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()


def technicals(df, spot):
    defaults = {
        "rsi": 50.0,
        "ema20": spot,
        "ema50": spot,
        "atr": max(spot * 0.01, 0.01),
        "trend": "Sideways",
        "adx": 0.0,
        "momentum": 0.0,
        "volume_ratio": 1.0,
        "vwap": spot,
    }

    if df is None or df.empty:
        return defaults

    if len(df) < 20:
        return defaults

    work = df.copy()

    work["ema20"] = work["close"].ewm(
        span=20,
        adjust=False,
    ).mean()

    work["ema50"] = work["close"].ewm(
        span=50,
        adjust=False,
    ).mean()

    work["rsi"] = _rsi(
        work["close"],
        14,
    )

    work["atr"] = _atr(
        work,
        14,
    )

    work["adx"] = _adx(
        work,
        14,
    )

    typical = (
        work["high"]
        + work["low"]
        + work["close"]
    ) / 3

    volume = work["volume"].fillna(0)

    cumulative_volume = volume.cumsum()

    cumulative_pv = (
        typical * volume
    ).cumsum()

    work["vwap"] = (
        cumulative_pv
        / cumulative_volume.replace(
            0,
            np.nan,
        )
    )

    if "timestamp" in work.columns:

        try:
            timestamps = pd.to_datetime(
                work["timestamp"],
                errors="coerce",
            )

            if timestamps.dt.tz is not None:
                local_dates = timestamps.dt.tz_convert(
                    IST
                ).dt.date
            else:
                local_dates = timestamps.dt.date

            latest_date = local_dates.iloc[-1]

            session = work[
                local_dates == latest_date
            ]

            if len(session) >= 2:
                sv = session["volume"].fillna(0)
                stp = (
                    (
                        session["high"]
                        + session["low"]
                        + session["close"]
                    )
                    / 3
                )

                total_v = sv.sum()

                if total_v > 0:
                    session_vwap = (
                        stp * sv
                    ).sum() / total_v

                    work.loc[
                        work.index[-1],
                        "vwap",
                    ] = session_vwap

        except Exception:
            pass

    latest = work.iloc[-1]

    close = safe_float(
        latest["close"],
        spot,
    )

    ema20 = safe_float(
        latest["ema20"],
        spot,
    )

    ema50 = safe_float(
        latest["ema50"],
        spot,
    )

    rsi = safe_float(
        latest["rsi"],
        50,
    )

    atr = safe_float(
        latest["atr"],
        max(spot * 0.01, 0.01),
    )

    adx = safe_float(
        latest["adx"],
        0,
    )

    vwap = safe_float(
        latest["vwap"],
        spot,
    )

    lookback = min(5, len(work) - 1)

    previous_close = safe_float(
        work["close"].iloc[-1 - lookback],
        close,
    )

    momentum = (
        (close - previous_close)
        / max(abs(previous_close), 0.01)
    ) * 100

    previous_volume = (
        work["volume"]
        .shift(1)
        .rolling(
            20,
            min_periods=5,
        )
        .median()
        .iloc[-1]
    )

    current_volume = safe_float(
        latest["volume"],
        0,
    )

    if (
        np.isfinite(previous_volume)
        and previous_volume > 0
    ):
        volume_ratio = (
            current_volume
            / previous_volume
        )
    else:
        volume_ratio = 1.0

    if close > ema20 > ema50:
        trend = "Bullish"
    elif close < ema20 < ema50:
        trend = "Bearish"
    else:
        trend = "Sideways"

    return {
        "rsi": rsi,
        "ema20": ema20,
        "ema50": ema50,
        "atr": max(atr, 0.01),
        "trend": trend,
        "adx": max(adx, 0),
        "momentum": momentum,
        "volume_ratio": max(volume_ratio, 0),
        "vwap": vwap,
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

    return "Mixed", max(
        bullish,
        bearish,
    )


# ============================================================
# OI ANALYSIS
# ============================================================

def oi_levels(chain, spot):
    if chain is None or chain.empty:
        return {
            "pcr": np.nan,
            "support": spot,
            "resistance": spot,
            "major_support": spot,
            "major_resistance": spot,
            "put_walls": [],
            "call_walls": [],
        }

    work = chain.copy()

    work = work[
        np.isfinite(work["Strike"])
    ]

    if work.empty:
        return {
            "pcr": np.nan,
            "support": spot,
            "resistance": spot,
            "major_support": spot,
            "major_resistance": spot,
            "put_walls": [],
            "call_walls": [],
        }

    distance = (
        work["Strike"] - spot
    ).abs() / max(abs(spot), 1)

    band = work[
        distance <= 0.10
    ].copy()

    if band.empty:
        band = work.copy()

    ce_oi = pd.to_numeric(
        band["CE OI"],
        errors="coerce",
    ).fillna(0)

    pe_oi = pd.to_numeric(
        band["PE OI"],
        errors="coerce",
    ).fillna(0)

    total_ce = ce_oi.sum()
    total_pe = pe_oi.sum()

    if total_ce > 0:
        pcr = total_pe / total_ce
    else:
        pcr = np.nan

    below = band[
        band["Strike"] < spot
    ]

    above = band[
        band["Strike"] > spot
    ]

    if below.empty:
        below = band[
            band["Strike"] <= spot
        ]

    if above.empty:
        above = band[
            band["Strike"] >= spot
        ]

    if not below.empty:
        support = float(
            below["Strike"].max()
        )
    else:
        support = spot

    if not above.empty:
        resistance = float(
            above["Strike"].min()
        )
    else:
        resistance = spot

    put_wall_df = (
        below.sort_values(
            "PE OI",
            ascending=False,
        )
        .head(3)
    )

    call_wall_df = (
        above.sort_values(
            "CE OI",
            ascending=False,
        )
        .head(3)
    )

    put_walls = [
        {
            "strike": safe_float(row["Strike"]),
            "oi": safe_float(row["PE OI"], 0),
            "chg": safe_float(
                row["PE Chg OI"]
            ),
        }
        for _, row in put_wall_df.iterrows()
        if safe_float(row["PE OI"], 0) > 0
    ]

    call_walls = [
        {
            "strike": safe_float(row["Strike"]),
            "oi": safe_float(row["CE OI"], 0),
            "chg": safe_float(
                row["CE Chg OI"]
            ),
        }
        for _, row in call_wall_df.iterrows()
        if safe_float(row["CE OI"], 0) > 0
    ]

    major_support = (
        put_walls[0]["strike"]
        if put_walls
        else support
    )

    major_resistance = (
        call_walls[0]["strike"]
        if call_walls
        else resistance
    )

    return {
        "pcr": pcr,
        "support": support,
        "resistance": resistance,
        "major_support": major_support,
        "major_resistance": major_resistance,
        "put_walls": put_walls,
        "call_walls": call_walls,
    }


# ============================================================
# OPTION SCORING
# ============================================================

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

    score = 0
    alignment = 0

    for tf in [tf5, tf30, daily]:

        trend = tf.get(
            "trend",
            "Sideways",
        )

        if trend == desired:
            score += 10
            alignment += 1

        elif trend == "Sideways":
            score += 3

        elif trend == opposite:
            score -= 8

    return max(0, min(30, score)), alignment


def score_option(
    row,
    side,
    spot,
    pcr,
    tf5,
    tf30,
    daily,
    support=None,
    resistance=None,
):
    if row is None:
        return {
            "score": 0,
            "alignment": 0,
            "pop": np.nan,
            "delta": np.nan,
            "iv": np.nan,
            "ltp": np.nan,
            "bid": np.nan,
            "ask": np.nan,
            "oi": 0,
            "volume": 0,
            "spread_pct": np.inf,
            "chg_oi": np.nan,
        }

    prefix = "CE" if side == "CE" else "PE"

    ltp = safe_float(
        row.get(f"{prefix} LTP")
    )

    bid = safe_float(
        row.get(f"{prefix} Bid")
    )

    ask = safe_float(
        row.get(f"{prefix} Ask")
    )

    oi = safe_float(
        row.get(f"{prefix} OI"),
        0,
    )

    chg_oi = safe_float(
        row.get(f"{prefix} Chg OI")
    )

    volume = safe_float(
        row.get(f"{prefix} Volume"),
        0,
    )

    iv = safe_float(
        row.get(f"{prefix} IV")
    )

    delta = safe_float(
        row.get(f"{prefix} Delta")
    )

    pop = normalize_pop(
        row.get(f"{prefix} PoP")
    )

    if (
        np.isfinite(bid)
        and np.isfinite(ask)
        and ask > 0
        and ask >= bid >= 0
    ):
        spread_pct = (
            (ask - bid)
            / max(ask, 0.01)
        ) * 100
    else:
        spread_pct = np.inf

    tf_points, alignment = timeframe_score(
        side,
        tf5,
        tf30,
        daily,
    )

    score = tf_points

    momentum = safe_float(
        tf5.get("momentum"),
        0,
    )

    desired_momentum = (
        momentum
        if side == "CE"
        else -momentum
    )

    if desired_momentum > 0:
        score += min(
            15,
            5 + desired_momentum * 2,
        )
    elif desired_momentum < 0:
        score += 0
    else:
        score += 3

    vwap = safe_float(
        tf5.get("vwap"),
        spot,
    )

    if side == "CE":
        if spot > vwap:
            score += 10
        else:
            score += 0
    else:
        if spot < vwap:
            score += 10
        else:
            score += 0

    if np.isfinite(pcr):

        if side == "CE":

            if 0.85 <= pcr <= 1.20:
                score += 10
            elif pcr < 0.75:
                score += 3
            else:
                score += 5

        else:

            if 0.80 <= pcr <= 1.25:
                score += 10
            elif pcr > 1.35:
                score += 3
            else:
                score += 5

    if np.isfinite(chg_oi):

        if side == "CE":
            if chg_oi < 0:
                score += 5
            elif chg_oi == 0:
                score += 3
        else:
            if chg_oi < 0:
                score += 5
            elif chg_oi == 0:
                score += 3

    if np.isfinite(delta):

        delta_abs = abs(delta)

        if 0.45 <= delta_abs <= 0.70:
            score += 15
        elif 0.35 <= delta_abs <= 0.80:
            score += 10
        elif delta_abs <= 0.90:
            score += 5

    if np.isfinite(pop):

        if pop >= 70:
            score += 10
        elif pop >= 60:
            score += 8
        elif pop >= 55:
            score += 4

    if np.isfinite(oi) and oi > 0:
        score += 5

    if volume >= 100000:
        score += 5
    elif volume >= 10000:
        score += 3
    elif volume >= 1000:
        score += 1

    if np.isfinite(spread_pct):

        if spread_pct <= 1.5:
            score += 5
        elif spread_pct <= 3:
            score += 3

    strike = safe_float(
        row.get("Strike")
    )

    if np.isfinite(strike):

        if side == "CE":

            if np.isfinite(resistance):
                room = (
                    resistance - spot
                ) / max(spot, 1) * 100

                if room >= 1.0:
                    score += 5
                elif room >= 0.5:
                    score += 3

        else:

            if np.isfinite(support):
                room = (
                    spot - support
                ) / max(spot, 1) * 100

                if room >= 1.0:
                    score += 5
                elif room >= 0.5:
                    score += 3

    score = max(
        0,
        min(100, round(score)),
    )

    return {
        "score": score,
        "alignment": alignment,
        "pop": pop,
        "delta": delta,
        "iv": iv,
        "ltp": ltp,
        "bid": bid,
        "ask": ask,
        "oi": oi,
        "volume": volume,
        "spread_pct": spread_pct,
        "chg_oi": chg_oi,
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
    market_open=True,
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
        support,
        resistance,
    )

    ask = safe_float(
        scored["ask"]
    )

    ltp = safe_float(
        scored["ltp"]
    )

    entry = (
        ask
        if np.isfinite(ask) and ask > 0
        else ltp
    )

    if not np.isfinite(entry) or entry <= 0:
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

    risk = max(
        entry - sl,
        0.01,
    )

    rr1 = (
        target1 - entry
    ) / risk

    rr2 = (
        target2 - entry
    ) / risk

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

    if side == "CE":

        trigger_level = (
            resistance
            + trigger_buffer
        )

        trigger_hit = (
            spot >= trigger_level
        )

        candle_confirmed = (
            tf5.get("trend") == "Bullish"
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
            f"Enter only after spot breaks and "
            f"sustains above {fmt_price(trigger_level)} "
            f"with 5-minute bullish confirmation."
        )

        exit_rule = (
            f"Exit if spot loses support "
            f"{fmt_price(support)} or option premium "
            f"falls to {fmt_price(sl)}. "
            f"After Target 1, consider partial booking "
            f"and trail."
        )

    else:

        trigger_level = (
            support
            - trigger_buffer
        )

        trigger_hit = (
            spot <= trigger_level
        )

        candle_confirmed = (
            tf5.get("trend") == "Bearish"
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
            f"Enter only after spot breaks and "
            f"sustains below {fmt_price(trigger_level)} "
            f"with 5-minute bearish confirmation."
        )

        exit_rule = (
            f"Exit if spot reclaims resistance "
            f"{fmt_price(resistance)} or option premium "
            f"falls to {fmt_price(sl)}. "
            f"After Target 1, consider partial booking "
            f"and trail."
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

    opposite = (
        "Bearish"
        if side == "CE"
        else "Bullish"
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

    delta_abs = abs(
        safe_float(
            scored["delta"]
        )
    )

    if (
        not np.isfinite(delta_abs)
        or not 0.35 <= delta_abs <= 0.80
    ):
        hard_fail.append(
            "delta outside 0.35–0.80"
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

    if hard_fail:
        status = "NO TRADE"
    elif not market_open:
        status = "MARKET CLOSED"
    elif not trigger_hit:
        status = "WAIT FOR TRIGGER"
    elif not candle_confirmed:
        status = "WAIT FOR 5M CONFIRMATION"
    else:
        status = "READY"

    ready = (
        status == "READY"
        and market_open
    )

    return {
        "side": side,
        "strike": safe_float(
            row.get("Strike")
        ),
        "entry": entry,
        "sl": sl,
        "target1": target1,
        "target2": target2,
        "rr1": rr1,
        "rr2": rr2,
        "score": scored["score"],
        "pop": scored["pop"],
        "delta": scored["delta"],
        "iv": scored["iv"],
        "oi": scored["oi"],
        "volume": scored["volume"],
        "spread_pct": scored["spread_pct"],
        "chg_oi": scored["chg_oi"],
        "alignment": scored["alignment"],
        "trigger_level": trigger_level,
        "trigger_hit": trigger_hit,
        "candle_confirmed": candle_confirmed,
        "volume_confirmed": volume_confirmed,
        "trigger": trigger,
        "exit_rule": exit_rule,
        "hard_fail": hard_fail,
        "status": status,
        "ready": ready,
    }


# ============================================================
# BEST PLAN
# ============================================================

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
    market_open,
):
    if chain is None or chain.empty:
        return None

    distance = (
        (chain["Strike"] - spot).abs()
        / max(abs(spot), 1)
    )

    candidates = chain[
        distance <= 0.04
    ].copy()

    if candidates.empty:
        candidates = (
            chain.assign(
                _distance=distance
            )
            .sort_values("_distance")
            .head(10)
            .drop(columns="_distance")
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
            market_open,
        )

        if plan is not None:
            plans.append(plan)

    if not plans:
        return None

    plans.sort(
        key=lambda x: (
            x["ready"],
            x["score"],
            x["alignment"],
            x["pop"]
            if np.isfinite(x["pop"])
            else -1,
        ),
        reverse=True,
    )

    return plans[0]


# ============================================================
# SCANNER
# ============================================================

def scanner_candidates(
    chain,
    spot,
    pcr,
    tf5,
    tf30,
    daily,
    support,
    resistance,
):
    results = []

    if chain is None or chain.empty:
        return results

    distance = (
        (chain["Strike"] - spot).abs()
        / max(abs(spot), 1)
    )

    candidates = chain[
        distance <= 0.05
    ].copy()

    for _, row in candidates.iterrows():

        for side in ("CE", "PE"):

            prefix = (
                "CE"
                if side == "CE"
                else "PE"
            )

            pop = normalize_pop(
                row.get(f"{prefix} PoP")
            )

            if (
                not np.isfinite(pop)
                or pop <= 60
            ):
                continue

            scored = score_option(
                row,
                side,
                spot,
                pcr,
                tf5,
                tf30,
                daily,
                support,
                resistance,
            )

            delta = abs(
                safe_float(
                    scored["delta"]
                )
            )

            if (
                not np.isfinite(delta)
                or delta < 0.35
                or delta > 0.80
            ):
                continue

            if (
                not np.isfinite(
                    scored["spread_pct"]
                )
                or scored["spread_pct"] > 3
            ):
                continue

            if scored["volume"] < 1000:
                continue

            if scored["oi"] <= 0:
                continue

            if scored["score"] < 72:
                continue

            results.append(
                {
                    "side": side,
                    "strike": safe_float(
                        row.get("Strike")
                    ),
                    "score": scored["score"],
                    "pop": scored["pop"],
                    "delta": scored["delta"],
                    "iv": scored["iv"],
                    "ltp": scored["ltp"],
                    "volume": scored["volume"],
                    "oi": scored["oi"],
                    "spread": scored[
                        "spread_pct"
                    ],
                    "alignment": scored[
                        "alignment"
                    ],
                }
            )

    results.sort(
        key=lambda x: (
            x["score"],
            x["pop"],
            x["alignment"],
        ),
        reverse=True,
    )

    return results[:12]


# ============================================================
# RENDER HELPERS
# ============================================================

def render_metric(
    label,
    value,
    note="",
):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">
                {esc(label)}
            </div>
            <div class="metric-value">
                {esc(value)}
            </div>
            <div class="metric-note">
                {esc(note)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_trade_plan(plan, title):
    if plan is None:
        st.markdown(
            f"""
            <div class="option-card">
                <div class="option-title">
                    {esc(title)}
                </div>
                <div class="option-strike">
                    No valid option
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    side_class = (
        "call"
        if plan["side"] == "CE"
        else "put"
    )

    if plan["status"] == "READY":
        status_class = "status-green"
    elif plan["status"] == "NO TRADE":
        status_class = "status-red"
    else:
        status_class = "status-yellow"

    side_label = (
        "CALL BUY"
        if plan["side"] == "CE"
        else "PUT BUY"
    )

    st.markdown(
        f"""
        <div class="option-card {side_class}">

            <div class="option-header">

                <div>
                    <div class="option-title">
                        {esc(side_label)}
                    </div>

                    <div class="option-strike">
                        {esc(fmt_price(plan["strike"]))}
                    </div>
                </div>

                <div class="option-readiness {status_class}">
                    {esc(plan["status"])}
                </div>

            </div>

            <div class="option-grid">

                <div>
                    <span>ENTRY</span>
                    <b>{esc(fmt_price(plan["entry"]))}</b>
                </div>

                <div>
                    <span>STOP LOSS</span>
                    <b>{esc(fmt_price(plan["sl"]))}</b>
                </div>

                <div>
                    <span>TARGET 1</span>
                    <b>{esc(fmt_price(plan["target1"]))}</b>
                </div>

                <div>
                    <span>TARGET 2</span>
                    <b>{esc(fmt_price(plan["target2"]))}</b>
                </div>

                <div>
                    <span>PoP</span>
                    <b>{esc(fmt_pct(plan["pop"]))}</b>
                </div>

                <div>
                    <span>DELTA</span>
                    <b>{esc(fmt_delta(plan["delta"]))}</b>
                </div>

                <div>
                    <span>IV</span>
                    <b>{esc(fmt_pct(plan["iv"]))}</b>
                </div>

                <div>
                    <span>R:R</span>
                    <b>1:{esc(f"{plan['rr1']:.2f}")}</b>
                </div>

            </div>

            <div class="exit-rule">
                <span>ENTRY TRIGGER</span>
                <b>{esc(plan["trigger"])}</b>
            </div>

            <div class="exit-rule">
                <span>EXIT RULE</span>
                <b>{esc(plan["exit_rule"])}</b>
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


def render_validation(plan):
    if plan is None:
        return

    checks = []

    alignment_pass = (
        plan["alignment"] >= 2
    )

    pop_pass = (
        np.isfinite(plan["pop"])
        and plan["pop"] >= 55
    )

    spread_pass = (
        np.isfinite(plan["spread_pct"])
        and plan["spread_pct"] <= 3
    )

    liquidity_pass = (
        plan["volume"] >= 1000
        and plan["oi"] > 0
    )

    trigger_pass = plan["trigger_hit"]

    candle_pass = (
        plan["candle_confirmed"]
    )

    volume_pass = (
        plan["volume_confirmed"]
    )

    score_pass = (
        plan["score"] >= 72
    )

    checks.extend(
        [
            (
                "Setup Score",
                score_pass,
                f"{plan['score']}/100",
            ),
            (
                "Timeframe Alignment",
                alignment_pass,
                f"{plan['alignment']}/3 aligned",
            ),
            (
                "Option PoP",
                pop_pass,
                fmt_pct(plan["pop"]),
            ),
            (
                "Option Spread",
                spread_pass,
                fmt_pct(plan["spread_pct"]),
            ),
            (
                "Liquidity",
                liquidity_pass,
                f"Vol {fmt_num(plan['volume'])}",
            ),
            (
                "Entry Trigger",
                trigger_pass,
                (
                    "Triggered"
                    if trigger_pass
                    else "Not triggered"
                ),
            ),
            (
                "5m Confirmation",
                candle_pass,
                (
                    "Confirmed"
                    if candle_pass
                    else "Pending"
                ),
            ),
            (
                "Volume Confirmation",
                volume_pass,
                (
                    "Confirmed"
                    if volume_pass
                    else "Pending"
                ),
            ),
        ]
    )

    passed = sum(
        1
        for _, value, _ in checks
        if value
    )

    st.markdown(
        '<div class="section-title">'
        '✅ Trade Validation'
        '</div>',
        unsafe_allow_html=True,
    )

    rows_html = ""

    for label, passed_flag, detail in checks:

        if passed_flag:
            cls = "check-pass"
            text = "PASS"
        else:
            cls = "check-wait"

            if label == "Setup Score" and plan[
                "score"
            ] < 72:
                text = "FAIL"
            else:
                text = "WAIT"

        rows_html += f"""
        <div class="check-row">
            <span>{esc(label)}</span>
            <strong class="{cls}">
                {text}
            </strong>
            <small>{esc(detail)}</small>
        </div>
        """

    st.markdown(
        f"""
        <div class="validation-card">

            {rows_html}

            <div class="check-total">
                <span>Conditions Passed</span>
                <b>{passed}/{len(checks)}</b>
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


def render_why(plan):
    if plan is None:
        return

    reasons = []

    if plan["score"] >= 72:
        reasons.append(
            (
                "pass",
                f"Setup score {plan['score']}/100"
            )
        )
    else:
        reasons.append(
            (
                "fail",
                f"Blocked: setup score below 72"
            )
        )

    if plan["alignment"] >= 2:
        reasons.append(
            (
                "pass",
                f"Timeframe alignment "
                f"{plan['alignment']}/3"
            )
        )
    else:
        reasons.append(
            (
                "warning",
                "Blocked: fewer than 2 aligned timeframes"
            )
        )

    if (
        np.isfinite(plan["pop"])
        and plan["pop"] >= 55
    ):
        reasons.append(
            (
                "pass",
                f"PoP {plan['pop']:.1f}%"
            )
        )
    else:
        reasons.append(
            (
                "warning",
                "Blocked: low option PoP"
            )
        )

    if (
        np.isfinite(plan["delta"])
        and 0.35 <= abs(plan["delta"]) <= 0.80
    ):
        reasons.append(
            (
                "pass",
                f"Delta {plan['delta']:.2f}"
            )
        )
    else:
        reasons.append(
            (
                "warning",
                "Delta outside preferred range"
            )
        )

    if (
        np.isfinite(plan["spread_pct"])
        and plan["spread_pct"] <= 3
    ):
        reasons.append(
            (
                "pass",
                f"Spread {plan['spread_pct']:.1f}%"
            )
        )
    else:
        reasons.append(
            (
                "warning",
                "Option spread too wide"
            )
        )

    if plan["candle_confirmed"]:
        reasons.append(
            (
                "pass",
                "5m candle confirmation present"
            )
        )
    else:
        reasons.append(
            (
                "warning",
                "5m candle confirmation pending"
            )
        )

    if plan["volume_confirmed"]:
        reasons.append(
            (
                "pass",
                "Volume confirmation present"
            )
        )
    else:
        reasons.append(
            (
                "warning",
                "Volume confirmation pending"
            )
        )

    if plan["hard_fail"]:
        for failure in plan["hard_fail"]:
            reasons.append(
                (
                    "warning",
                    f"Blocked: {failure}"
                )
            )

    items = ""

    for kind, text_value in reasons:

        if kind == "pass":
            cls = "why-pass"
        elif kind == "fail":
            cls = "why-fail"
        else:
            cls = "why-warning"

        items += f"""
        <div class="why-item {cls}">
            {esc(text_value)}
        </div>
        """

    st.markdown(
        f"""
        <div class="section-title">
            🧠 Why the Engine Says This
        </div>

        <div class="why-card">
            {items}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_scanner(results):
    st.markdown(
        '<div class="section-title">'
        '🔎 F&O Scanner — Qualified PoP > 60%'
        '</div>',
        unsafe_allow_html=True,
    )

    if not results:
        st.markdown(
            """
            <div class="info-box">
                No option currently meets all scanner
                requirements. The scanner requires PoP >60%,
                setup score ≥72, Delta 0.35–0.80,
                acceptable spread, liquidity and OI.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for item in results:

        side_label = (
            "CALL BUY"
            if item["side"] == "CE"
            else "PUT BUY"
        )

        st.markdown(
            f"""
            <div class="scanner-card">

                <div class="scanner-header">

                    <div>
                        <div class="scanner-title">
                            {esc(side_label)}
                            •
                            {esc(fmt_price(item["strike"]))}
                        </div>

                        <div class="scanner-meta">
                            QUALIFIED • PoP above 60%
                        </div>
                    </div>

                    <div style="text-align:right;">
                        <div class="small-muted">
                            PoP
                        </div>
                        <div style="
                            font-size:20px;
                            font-weight:900;
                            color:#182230;">
                            {esc(fmt_pct(item["pop"]))}
                        </div>
                    </div>

                </div>

                <div class="scanner-stats">

                    <div>
                        <span>SCORE</span>
                        <b>{item["score"]}</b>
                    </div>

                    <div>
                        <span>LTP</span>
                        <b>{esc(fmt_price(item["ltp"]))}</b>
                    </div>

                    <div>
                        <span>DELTA</span>
                        <b>{esc(fmt_delta(item["delta"]))}</b>
                    </div>

                    <div>
                        <span>IV</span>
                        <b>{esc(fmt_pct(item["iv"]))}</b>
                    </div>

                    <div>
                        <span>R:R SCREEN</span>
                        <b>QUALIFIED</b>
                    </div>

                    <div>
                        <span>ALIGNMENT</span>
                        <b>{item["alignment"]}/3</b>
                    </div>

                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# MAIN APPLICATION
# ============================================================

def main():

    current = now_ist()
    market_open = is_market_open(
        current
    )

    # --------------------------------------------------------
    # SIDEBAR
    # --------------------------------------------------------

    with st.sidebar:

        st.markdown(
            "## ⚙️ Analysis Settings"
        )

        symbol_input = st.text_input(
            "F&O Symbol",
            value="HDFCBANK",
            help=(
                "Enter NSE F&O stock/index symbol, "
                "for example HDFCBANK, RELIANCE, "
                "NIFTY or BANKNIFTY."
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

        scanner_on = st.toggle(
            "F&O Scanner",
            value=True,
            help=(
                "Shows only qualified options with "
                "PoP above 60% and setup-quality filters."
            ),
        )

        refresh = st.button(
            "🔄 Refresh Data",
            use_container_width=True,
        )

        if refresh:
            st.rerun()

        st.divider()

        if market_open:
            st.success(
                "● LIVE DATA\n\n"
                "NSE regular session is open."
            )
        else:
            st.warning(
                "● MARKET CLOSED\n\n"
                "NSE regular session is closed."
            )

        remaining = rate_limit_remaining()

        if remaining > 0:
            st.error(
                f"Upstox rate-limit cooldown active: "
                f"{remaining}s"
            )

        st.caption(
            "REST API only • No automatic order execution"
        )

    symbol = alias_symbol(
        symbol_input
    )

    if not symbol:
        st.error(
            "Please enter an F&O symbol."
        )
        return

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    try:

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

        actual_symbol = (
            underlying.get(
                "trading_symbol"
            )
            or symbol
        )

        contracts = get_contracts(
            underlying_key
        )

        expiries = available_expiries(
            contracts
        )

        if not expiries:
            raise UpstoxError(
                "No future option expiries are available."
            )

        expiry_options = [
            str(x)
            for x in expiries
        ]

        selected_expiry = st.sidebar.selectbox(
            "Expiry",
            expiry_options,
            index=0,
        )

        raw_chain = get_option_chain(
            underlying_key,
            selected_expiry,
        )

        chain = normalize_chain(
            raw_chain
        )

        if chain.empty:
            raise UpstoxError(
                "Option chain is empty after normalization."
            )

        quote_data = get_quote(
            underlying_key
        )

        spot = extract_ltp(
            quote_data
        )

        # ----------------------------------------------------
        # FALLBACK SPOT FROM OPTION CHAIN
        # ----------------------------------------------------

        if not np.isfinite(spot):

            for raw in raw_chain:

                possible = []

                if isinstance(raw, dict):
                    possible.extend(
                        [
                            raw.get(
                                "underlying_spot_price"
                            ),
                            raw.get(
                                "underlying_value"
                            ),
                            raw.get(
                                "spot_price"
                            ),
                        ]
                    )

                for value in possible:

                    candidate = safe_float(
                        value
                    )

                    if np.isfinite(candidate):
                        spot = candidate
                        break

                if np.isfinite(spot):
                    break

        if not np.isfinite(spot):
            raise UpstoxError(
                "Unable to obtain the current underlying spot price."
            )

        # ----------------------------------------------------
        # TECHNICAL DATA
        # ----------------------------------------------------

        try:
            candles_5 = get_intraday_candles(
                underlying_key,
                5,
            )
        except UpstoxError:
            candles_5 = pd.DataFrame()

        try:
            candles_30 = get_30m_candles(
                underlying_key
            )
        except UpstoxError:
            candles_30 = pd.DataFrame()

        try:
            candles_daily = get_daily_candles(
                underlying_key
            )
        except UpstoxError:
            candles_daily = pd.DataFrame()

        tf5 = technicals(
            candles_5,
            spot,
        )

        tf30 = technicals(
            candles_30,
            spot,
        )

        daily = technicals(
            candles_daily,
            spot,
        )

        bias, bias_count = overall_trend(
            tf5,
            tf30,
            daily,
        )

        oi = oi_levels(
            chain,
            spot,
        )

        pcr = oi["pcr"]

        support = oi["major_support"]

        resistance = oi[
            "major_resistance"
        ]

        # ----------------------------------------------------
        # BEST CE / PE
        # ----------------------------------------------------

        best_ce = find_best_plan(
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
            market_open,
        )

        best_pe = find_best_plan(
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
            market_open,
        )

        # ----------------------------------------------------
        # FINAL DECISION
        # ----------------------------------------------------

        ready_plans = [
            x
            for x in (
                best_ce,
                best_pe,
            )
            if x is not None
            and x.get("ready")
        ]

        if ready_plans:

            ready_plans.sort(
                key=lambda x: (
                    x["score"],
                    x["alignment"],
                    x["pop"]
                    if np.isfinite(
                        x["pop"]
                    )
                    else -1,
                ),
                reverse=True,
            )

            final_plan = ready_plans[0]

            action = (
                "CALL BUY"
                if final_plan["side"] == "CE"
                else "PUT BUY"
            )

        else:

            final_plan = (
                best_ce
                if best_ce is not None
                else best_pe
            )

            action = "NO TRADE"

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        status_block = (
            """
            <div class="live-block">
                Data Status<br>
                <strong>● LIVE DATA</strong>
            </div>
            """
            if market_open
            else
            """
            <div class="closed-block">
                Data Status<br>
                <strong>● MARKET CLOSED</strong>
            </div>
            """
        )

        st.markdown(
            f"""
            <div class="topbar">

                <div class="topbar-row">

                    <div>
                        <div class="topbar-title">
                            📊 FO PRO Trader Assistant
                        </div>

                        <div class="topbar-sub">
                            Options Analysis • Upstox REST API •
                            Live Option Chain • Technical + OI Analysis
                        </div>
                    </div>

                    {status_block}

                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # HERO
        # ----------------------------------------------------

        st.markdown(
            f"""
            <div class="hero-card">

                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    gap:15px;
                    flex-wrap:wrap;">

                    <div>
                        <div class="hero-title">
                            {esc(actual_symbol)}
                            • F&O OPTIONS ANALYSIS
                        </div>

                        <div class="hero-price">
                            {esc(fmt_price(spot))}
                        </div>

                        <div class="hero-meta">
                            Last Traded Price
                        </div>
                    </div>

                    <div style="text-align:right;">

                        <div class="small-muted">
                            EXPIRY
                        </div>

                        <div style="
                            font-weight:850;
                            color:#182230;">
                            {esc(str(selected_expiry))}
                        </div>

                        <div class="small-muted"
                             style="margin-top:5px;">
                            Updated
                            {current.strftime(
                                "%d %b %Y • %I:%M:%S %p"
                            )}
                        </div>

                    </div>

                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        m1, m2, m3, m4, m5 = st.columns(5)

        with m1:
            render_metric(
                "MARKET BIAS",
                bias,
                f"{bias_count}/3 timeframes",
            )

        with m2:
            render_metric(
                "PCR",
                fmt_pct(pcr),
                "OI-based local PCR",
            )

        with m3:
            render_metric(
                "OI SUPPORT",
                fmt_price(support),
                "Major PE OI wall",
            )

        with m4:
            render_metric(
                "OI RESISTANCE",
                fmt_price(resistance),
                "Major CE OI wall",
            )

        with m5:
            render_metric(
                "5M RSI",
                f"{tf5['rsi']:.1f}",
                f"Trend: {tf5['trend']}",
            )

        # ----------------------------------------------------
        # DECISION
        # ----------------------------------------------------

        if action == "CALL BUY":
            decision_class = "decision-call"
            decision_sub = (
                "Qualified bullish setup with "
                "trigger confirmation."
            )
        elif action == "PUT BUY":
            decision_class = "decision-put"
            decision_sub = (
                "Qualified bearish setup with "
                "trigger confirmation."
            )
        else:
            decision_class = "decision-neutral"

            if not market_open:
                decision_sub = (
                    "Market is closed. No new trade is permitted."
                )
            elif final_plan is not None:
                decision_sub = (
                    "Current conditions do not satisfy "
                    "all trade-entry requirements."
                )
            else:
                decision_sub = (
                    "No sufficiently qualified option setup found."
                )

        score_value = (
            final_plan["score"]
            if final_plan
            else 0
        )

        pop_value = (
            final_plan["pop"]
            if final_plan
            and np.isfinite(
                final_plan["pop"]
            )
            else np.nan
        )

        entry_value = (
            final_plan["entry"]
            if final_plan
            else np.nan
        )

        rr_value = (
            final_plan["rr1"]
            if final_plan
            else np.nan
        )

        st.markdown(
            f"""
            <div class="section-title">
                🎯 Trade Decision
            </div>

            <div class="decision-card {decision_class}">

                <div class="decision-title">
                    {esc(action)}
                </div>

                <div class="decision-sub">
                    {esc(decision_sub)}
                </div>

                <div class="decision-stats">

                    <div>
                        <span>SETUP SCORE</span>
                        <b>{score_value}/100</b>
                    </div>

                    <div>
                        <span>PoP</span>
                        <b>{esc(fmt_pct(pop_value))}</b>
                    </div>

                    <div>
                        <span>ENTRY</span>
                        <b>{esc(fmt_price(entry_value))}</b>
                    </div>

                    <div>
                        <span>R:R</span>
                        <b>
                            {
                                "1:" + f"{rr_value:.2f}"
                                if np.isfinite(rr_value)
                                else "—"
                            }
                        </b>
                    </div>

                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # SUPPORT / RESISTANCE
        # ----------------------------------------------------

        support_distance = (
            (spot - support)
            / max(abs(spot), 1)
        ) * 100

        resistance_distance = (
            (resistance - spot)
            / max(abs(spot), 1)
        ) * 100

        st.markdown(
            """
            <div class="section-title">
                📍 OI Support / Resistance Map
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="sr-map">

                <div class="sr-side sr-support">

                    <span>SUPPORT</span>

                    <b>
                        {esc(fmt_price(support))}
                    </b>

                    <small>
                        {support_distance:.2f}% below spot
                    </small>

                </div>

                <div class="sr-line">

                    <div class="room-label">
                        CURRENT SPOT
                    </div>

                    <div class="current-marker">
                        {esc(fmt_price(spot))}
                        <span>SPOT</span>
                    </div>

                    <div class="room-label">
                        {resistance_distance:.2f}%
                        to resistance
                    </div>

                </div>

                <div class="sr-side sr-resistance">

                    <span>RESISTANCE</span>

                    <b>
                        {esc(fmt_price(resistance))}
                    </b>

                    <small>
                        {resistance_distance:.2f}% above spot
                    </small>

                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # TRADE PLANS
        # ----------------------------------------------------

        st.markdown(
            '<div class="section-title">'
            '📌 Trade Plans'
            '</div>',
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)

        with c1:
            render_trade_plan(
                best_ce,
                "CALL BUY",
            )

        with c2:
            render_trade_plan(
                best_pe,
                "PUT BUY",
            )

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        validation_plan = (
            final_plan
            if final_plan is not None
            else best_ce
            or best_pe
        )

        render_validation(
            validation_plan
        )

        render_why(
            validation_plan
        )

        # ----------------------------------------------------
        # DATA STATUS
        # ----------------------------------------------------

        st.markdown(
            '<div class="section-title">'
            '📡 Data Status'
            '</div>',
            unsafe_allow_html=True,
        )

        status_text = (
            "● LIVE DATA"
            if market_open
            else "● MARKET CLOSED"
        )

        st.markdown(
            f"""
            <div class="status-card">

                <div style="
                    font-size:20px;
                    font-weight:900;
                    color:#182230;
                    margin-bottom:12px;">
                    {esc(status_text)}
                </div>

                <div class="status-grid">

                    <div>
                        <span>SYMBOL</span>
                        <b>{esc(actual_symbol)}</b>
                    </div>

                    <div>
                        <span>SPOT</span>
                        <b>{esc(fmt_price(spot))}</b>
                    </div>

                    <div>
                        <span>EXPIRY</span>
                        <b>{esc(str(selected_expiry))}</b>
                    </div>

                </div>

                <div class="status-note">
                    Analysis updated
                    {current.strftime(
                        "%d %b %Y • %I:%M:%S %p"
                    )}
                    IST.<br>
                    Market-status display follows
                    the NSE regular-session clock.
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # SCANNER
        # ----------------------------------------------------

        if scanner_on:

            results = scanner_candidates(
                chain,
                spot,
                pcr,
                tf5,
                tf30,
                daily,
                support,
                resistance,
            )

            render_scanner(
                results
            )

        # ----------------------------------------------------
        # TABS
        # ----------------------------------------------------

        tabs = st.tabs(
            [
                "📋 Live Option Chain",
                "📈 Technical Analysis",
                "🏰 Major OI Walls",
                "📅 Available Expiries",
                "🧠 How the Engine Thinks",
            ]
        )

        # ----------------------------------------------------
        # OPTION CHAIN TAB
        # ----------------------------------------------------

        with tabs[0]:

            st.subheader(
                "📋 Live Option Chain"
            )

            display = chain.copy()

            display = display[
                [
                    "CE OI",
                    "CE Chg OI",
                    "CE LTP",
                    "CE IV",
                    "CE Delta",
                    "Strike",
                    "PE Delta",
                    "PE IV",
                    "PE LTP",
                    "PE Chg OI",
                    "PE OI",
                ]
            ]

            display.columns = [
                "CE OI",
                "CE Chg OI",
                "CE LTP",
                "CE IV",
                "CE Delta",
                "STRIKE",
                "PE Delta",
                "PE IV",
                "PE LTP",
                "PE Chg OI",
                "PE OI",
            ]

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "CE OI": st.column_config.NumberColumn(
                        format="%.0f"
                    ),
                    "CE Chg OI": st.column_config.NumberColumn(
                        format="%.0f"
                    ),
                    "CE LTP": st.column_config.NumberColumn(
                        format="₹%.2f"
                    ),
                    "CE IV": st.column_config.NumberColumn(
                        format="%.1f"
                    ),
                    "CE Delta": st.column_config.NumberColumn(
                        format="%.2f"
                    ),
                    "STRIKE": st.column_config.NumberColumn(
                        format="%.2f"
                    ),
                    "PE Delta": st.column_config.NumberColumn(
                        format="%.2f"
                    ),
                    "PE IV": st.column_config.NumberColumn(
                        format="%.1f"
                    ),
                    "PE LTP": st.column_config.NumberColumn(
                        format="₹%.2f"
                    ),
                    "PE Chg OI": st.column_config.NumberColumn(
                        format="%.0f"
                    ),
                    "PE OI": st.column_config.NumberColumn(
                        format="%.0f"
                    ),
                },
            )

        # ----------------------------------------------------
        # TECHNICAL TAB
        # ----------------------------------------------------

        with tabs[1]:

            st.subheader(
                "📈 Technical Analysis"
            )

            tech_df = pd.DataFrame(
                [
                    {
                        "Timeframe": "5 Minute",
                        "Trend": tf5["trend"],
                        "RSI": round(
                            tf5["rsi"],
                            1,
                        ),
                        "EMA20": round(
                            tf5["ema20"],
                            2,
                        ),
                        "EMA50": round(
                            tf5["ema50"],
                            2,
                        ),
                        "ATR": round(
                            tf5["atr"],
                            2,
                        ),
                        "ADX": round(
                            tf5["adx"],
                            1,
                        ),
                        "Momentum %": round(
                            tf5["momentum"],
                            2,
                        ),
                        "Volume Ratio": round(
                            tf5["volume_ratio"],
                            2,
                        ),
                    },
                    {
                        "Timeframe": "30 Minute",
                        "Trend": tf30["trend"],
                        "RSI": round(
                            tf30["rsi"],
                            1,
                        ),
                        "EMA20": round(
                            tf30["ema20"],
                            2,
                        ),
                        "EMA50": round(
                            tf30["ema50"],
                            2,
                        ),
                        "ATR": round(
                            tf30["atr"],
                            2,
                        ),
                        "ADX": round(
                            tf30["adx"],
                            1,
                        ),
                        "Momentum %": round(
                            tf30["momentum"],
                            2,
                        ),
                        "Volume Ratio": round(
                            tf30["volume_ratio"],
                            2,
                        ),
                    },
                    {
                        "Timeframe": "Daily",
                        "Trend": daily["trend"],
                        "RSI": round(
                            daily["rsi"],
                            1,
                        ),
                        "EMA20": round(
                            daily["ema20"],
                            2,
                        ),
                        "EMA50": round(
                            daily["ema50"],
                            2,
                        ),
                        "ATR": round(
                            daily["atr"],
                            2,
                        ),
                        "ADX": round(
                            daily["adx"],
                            1,
                        ),
                        "Momentum %": round(
                            daily["momentum"],
                            2,
                        ),
                        "Volume Ratio": round(
                            daily["volume_ratio"],
                            2,
                        ),
                    },
                ]
            )

            st.dataframe(
                tech_df,
                use_container_width=True,
                hide_index=True,
            )

            st.markdown(
                f"""
                <div class="info-box">
                    Overall trend:
                    <strong>{esc(bias)}</strong>.
                    The engine requires at least two aligned
                    timeframes before an option can become
                    READY.
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------
        # OI WALLS TAB
        # ----------------------------------------------------

        with tabs[2]:

            left, right = st.columns(2)

            with left:

                st.subheader(
                    "🟢 Put OI Walls"
                )

                if oi["put_walls"]:

                    for wall in oi[
                        "put_walls"
                    ]:

                        st.markdown(
                            f"""
                            <div class="wall-card">

                                <div class="wall-title">
                                    {esc(
                                        fmt_price(
                                            wall["strike"]
                                        )
                                    )}
                                </div>

                                <div class="wall-meta">
                                    Put OI:
                                    {esc(
                                        fmt_num(
                                            wall["oi"]
                                        )
                                    )}
                                    &nbsp; • &nbsp;
                                    Chg OI:
                                    {esc(
                                        fmt_num(
                                            wall["chg"]
                                        )
                                    )}
                                </div>

                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                else:
                    st.info(
                        "No significant Put OI wall found."
                    )

            with right:

                st.subheader(
                    "🔴 Call OI Walls"
                )

                if oi["call_walls"]:

                    for wall in oi[
                        "call_walls"
                    ]:

                        st.markdown(
                            f"""
                            <div class="wall-card">

                                <div class="wall-title">
                                    {esc(
                                        fmt_price(
                                            wall["strike"]
                                        )
                                    )}
                                </div>

                                <div class="wall-meta">
                                    Call OI:
                                    {esc(
                                        fmt_num(
                                            wall["oi"]
                                        )
                                    )}
                                    &nbsp; • &nbsp;
                                    Chg OI:
                                    {esc(
                                        fmt_num(
                                            wall["chg"]
                                        )
                                    )}
                                </div>

                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                else:
                    st.info(
                        "No significant Call OI wall found."
                    )

        # ----------------------------------------------------
        # EXPIRIES TAB
        # ----------------------------------------------------

        with tabs[3]:

            st.subheader(
                "📅 Available Expiries"
            )

            expiry_df = pd.DataFrame(
                {
                    "Expiry": [
                        str(x)
                        for x in expiries
                    ],
                    "Selected": [
                        "✓"
                        if str(x)
                        == str(selected_expiry)
                        else ""
                        for x in expiries
                    ],
                }
            )

            st.dataframe(
                expiry_df,
                use_container_width=True,
                hide_index=True,
            )

        # ----------------------------------------------------
        # ENGINE TAB
        # ----------------------------------------------------

        with tabs[4]:

            st.subheader(
                "🧠 How the Engine Thinks"
            )

            st.markdown(
                """
                <div class="info-box">

                <strong>1. Market direction</strong><br>
                The engine checks 5-minute, 30-minute and
                daily trends using EMA, momentum and RSI.

                <br><br>

                <strong>2. OI structure</strong><br>
                Put OI is used to identify potential support
                and Call OI to identify potential resistance.

                <br><br>

                <strong>3. Option quality</strong><br>
                Delta, IV, volume, OI, spread and Upstox PoP
                are evaluated.

                <br><br>

                <strong>4. Setup score</strong><br>
                The score combines the above factors into a
                normalized 0–100 setup-quality score.

                <br><br>

                <strong>5. Entry trigger</strong><br>
                A high score alone does not create a trade.
                The underlying must also break the relevant
                support/resistance trigger and show 5-minute
                confirmation.

                <br><br>

                <strong>6. NO TRADE protection</strong><br>
                If the setup score, timeframe alignment,
                Delta, PoP, spread, liquidity or OI fails
                the required conditions, the engine blocks
                the trade.

                <br><br>

                <strong>Important:</strong>
                PoP is an input supplied by the market-data
                system. It is not a guarantee of actual trade
                success, and the setup score is not a historical
                win-rate percentage.

                </div>
                """,
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------
        # FOOTER
        # ----------------------------------------------------

        st.markdown(
            """
            <div class="footer">
                FO PRO Trader Assistant • Upstox REST API •
                Analysis only • No automatic order execution
            </div>
            """,
            unsafe_allow_html=True,
        )

    except UpstoxRateLimitError as exc:

        st.markdown(
            f"""
            <div class="error-box">

                <strong>⏳ Upstox rate limit reached</strong>

                <br><br>

                The app has stopped sending additional
                requests during the cooldown.

                <br><br>

                Please wait approximately
                <strong>{exc.retry_after} seconds</strong>
                before refreshing.

                <br><br>

                This protection is intentional so the app
                does not repeatedly hammer the Upstox API.

            </div>
            """,
            unsafe_allow_html=True,
        )

    except UpstoxError as exc:

        st.markdown(
            f"""
            <div class="error-box">

                <strong>Upstox data error</strong>

                <br><br>

                {esc(str(exc))}

            </div>
            """,
            unsafe_allow_html=True,
        )

    except Exception as exc:

        st.markdown(
            f"""
            <div class="error-box">

                <strong>Application error</strong>

                <br><br>

                {esc(str(exc))}

                <br><br>

                Please use the Refresh Data button once
                the error condition has cleared.

            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# RUN
# ============================================================

main()
