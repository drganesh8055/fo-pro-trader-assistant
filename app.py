```python
import gzip
import json
import sqlite3
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
# LIVE REST DATA
# CALL BUY / PUT BUY / NO TRADE
#
# IMPORTANT:
# This version adds a measurable decision journal.
#
# Every decision is recorded with:
# - timestamp
# - symbol
# - expiry
# - spot
# - CE / PE scores
# - selected trade
# - PoP
# - Delta
# - IV
# - PCR
# - OI
# - entry / SL / T1 / T2
# - trigger status
# - timeframe alignment
# - decision
#
# Actionable CALL/PUT decisions are subsequently monitored.
# WIN  = Target 1 reached before Stop Loss
# LOSS = Stop Loss reached before Target 1
# TIMEOUT = neither reached within tracking window
#
# The journal is for measurement and calibration.
# It is NOT a guarantee of future performance.
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

DB_FILE = "fo_trade_journal.db"

TRACKING_MINUTES = 60

# This remains deliberately separate from Upstox PoP.
# It is a rule-based quality score, NOT a probability.
MIN_ACTION_SCORE = 72.0

FNO_MASTER_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
)


# ============================================================
# STYLE
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

.topbar-title {
    font-size:27px;
    font-weight:800;
}

.topbar-sub {
    font-size:13px;
    opacity:.82;
    margin-top:3px;
}

.status-live {
    background:#178b45;
    color:white;
    padding:11px 16px;
    border-radius:10px;
    font-weight:800;
    margin-bottom:15px;
}

.status-closed {
    background:#b4232f;
    color:white;
    padding:11px 16px;
    border-radius:10px;
    font-weight:800;
    margin-bottom:15px;
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

.metric-card {
    background:white;
    border:1px solid #e7ebf0;
    border-radius:12px;
    padding:14px;
    min-height:90px;
}

.metric-label {
    color:#667085;
    font-size:12px;
    font-weight:600;
}

.metric-value {
    color:#182230;
    font-size:21px;
    font-weight:800;
    margin-top:4px;
}

.small-muted {
    color:#667085;
    font-size:12px;
}

.reason-box {
    background:#f8fafc;
    border:1px solid #e4e7ec;
    border-radius:10px;
    padding:10px 12px;
    margin-top:8px;
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
        "Upstox access token is not configured. Add UPSTOX_ACCESS_TOKEN "
        "under Streamlit → App settings → Secrets, then reload the app."
    )
    st.stop()


HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}


# ============================================================
# GENERIC API
# ============================================================

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


# ============================================================
# FORMATTING
# ============================================================

def fmt_price(value):

    try:
        x = float(value)
    except Exception:
        return "—"

    if not np.isfinite(x):
        return "—"

    if abs(x) < 1000:
        return f"₹{x:,.2f}"

    return f"₹{x:,.0f}"


def fmt_num(value):

    try:
        x = float(value)
    except Exception:
        return "—"

    if not np.isfinite(x):
        return "—"

    return f"{x:,.0f}"


def safe_float(value, default=np.nan):

    try:
        x = float(value)

        if not np.isfinite(x):
            return default

        return x

    except Exception:
        return default


def now_ist():

    return datetime.now(IST)


# ============================================================
# SYMBOL
# ============================================================

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
# SQLITE DECISION JOURNAL
# ============================================================

def init_journal():

    conn = sqlite3.connect(DB_FILE)

    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            timestamp TEXT NOT NULL,

            symbol TEXT,
            underlying_key TEXT,
            expiry TEXT,

            spot REAL,

            market_bias TEXT,

            support REAL,
            resistance REAL,
            pcr REAL,

            bull_score REAL,
            bear_score REAL,
            confidence REAL,

            decision TEXT,

            selected_side TEXT,
            selected_strike REAL,
            option_key TEXT,

            entry REAL,
            stop_loss REAL,
            target1 REAL,
            target2 REAL,

            pop REAL,
            delta REAL,
            iv REAL,

            option_oi REAL,
            option_chg_oi REAL,
            option_volume REAL,
            spread_pct REAL,

            alignment INTEGER,

            tf5_trend TEXT,
            tf30_trend TEXT,
            daily_trend TEXT,

            trigger_level REAL,
            trigger_hit INTEGER,

            readiness TEXT,

            score_gate INTEGER,
            alignment_gate INTEGER,
            trend_gate INTEGER,
            spread_gate INTEGER,
            delta_gate INTEGER,
            pop_gate INTEGER,
            volume_gate INTEGER,

            fail_reasons TEXT,

            outcome TEXT,
            outcome_timestamp TEXT,
            outcome_price REAL,

            tracking_until TEXT

        )
        """
    )

    conn.commit()
    conn.close()


init_journal()


# ============================================================
# JOURNAL HELPERS
# ============================================================

def get_connection():

    return sqlite3.connect(DB_FILE)


def journal_fingerprint(
    symbol,
    expiry,
    decision,
    selected_side,
    selected_strike,
    spot,
):

    # Prevent the 30-second refresh from creating hundreds
    # of duplicate records for the exact same setup.

    spot_bucket = (
        round(float(spot), 1)
        if np.isfinite(safe_float(spot))
        else None
    )

    return (
        symbol,
        expiry,
        decision,
        selected_side,
        round(safe_float(selected_strike, -999), 1),
        spot_bucket,
    )


def should_log_decision(
    symbol,
    expiry,
    decision,
    selected_side,
    selected_strike,
    spot,
):

    conn = get_connection()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            symbol,
            expiry,
            decision,
            selected_side,
            selected_strike,
            spot,
            timestamp
        FROM decisions
        ORDER BY id DESC
        LIMIT 1
        """
    )

    row = cur.fetchone()

    conn.close()

    if row is None:
        return True

    previous = journal_fingerprint(
        row[0],
        row[1],
        row[2],
        row[3],
        row[4],
        row[5],
    )

    current = journal_fingerprint(
        symbol,
        expiry,
        decision,
        selected_side,
        selected_strike,
        spot,
    )

    if previous != current:
        return True

    try:
        previous_time = datetime.fromisoformat(row[6])

        if previous_time.tzinfo is None:
            previous_time = previous_time.replace(tzinfo=IST)

        minutes = (
            now_ist() - previous_time
        ).total_seconds() / 60

        return minutes >= 10

    except Exception:
        return False


def log_decision(
    symbol,
    underlying_key,
    expiry,
    spot,
    market_bias,
    support,
    resistance,
    pcr,
    bull_score,
    bear_score,
    confidence,
    decision,
    selected_plan,
    tf5,
    tf30,
    daily,
):

    if selected_plan:

        selected_side = selected_plan.get("side")
        selected_strike = selected_plan.get("strike")
        option_key = selected_plan.get("option_key")

        entry = selected_plan.get("entry")
        sl = selected_plan.get("sl")
        target1 = selected_plan.get("target1")
        target2 = selected_plan.get("target2")

        pop = selected_plan.get("pop")
        delta = selected_plan.get("delta")
        iv = selected_plan.get("iv")

        oi = selected_plan.get("oi")
        chg_oi = selected_plan.get("chg_oi")
        volume = selected_plan.get("volume")
        spread_pct = selected_plan.get("spread_pct")

        alignment = selected_plan.get("alignment")

        trigger_level = selected_plan.get("trigger_level")
        trigger_hit = int(bool(selected_plan.get("trigger_hit")))

        readiness = selected_plan.get("readiness")

        fail_reasons = " | ".join(
            selected_plan.get("fail_reasons", [])
        )

        score_gate = int(
            safe_float(selected_plan.get("score"), 0)
            >= MIN_ACTION_SCORE
        )

        alignment_gate = int(
            safe_float(alignment, 0) >= 2
        )

        desired = (
            "Bullish"
            if selected_side == "CE"
            else "Bearish"
        )

        opposite = (
            "Bearish"
            if selected_side == "CE"
            else "Bullish"
        )

        trend_gate = int(
            tf5.get("trend") != opposite
            and tf30.get("trend") != opposite
        )

        spread_gate = int(
            safe_float(spread_pct, 999) <= 4
        )

        delta_gate = int(
            np.isfinite(safe_float(delta))
            and 0.35 <= abs(safe_float(delta)) <= 0.80
        )

        pop_gate = int(
            np.isfinite(safe_float(pop))
            and safe_float(pop) >= 55
        )

        volume_gate = int(
            safe_float(volume, 0) > 0
        )

        tracking_until = (
            now_ist()
            + timedelta(minutes=TRACKING_MINUTES)
        ).isoformat()

    else:

        selected_side = None
        selected_strike = None
        option_key = None

        entry = None
        sl = None
        target1 = None
        target2 = None

        pop = None
        delta = None
        iv = None

        oi = None
        chg_oi = None
        volume = None
        spread_pct = None

        alignment = None
        trigger_level = None
        trigger_hit = 0
        readiness = "NO TRADE"

        fail_reasons = "No qualifying actionable setup"

        score_gate = 0
        alignment_gate = 0
        trend_gate = 0
        spread_gate = 0
        delta_gate = 0
        pop_gate = 0
        volume_gate = 0

        tracking_until = None

    if not should_log_decision(
        symbol,
        expiry,
        decision,
        selected_side,
        selected_strike,
        spot,
    ):
        return

    conn = get_connection()

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO decisions (

            timestamp,

            symbol,
            underlying_key,
            expiry,

            spot,

            market_bias,

            support,
            resistance,
            pcr,

            bull_score,
            bear_score,
            confidence,

            decision,

            selected_side,
            selected_strike,
            option_key,

            entry,
            stop_loss,
            target1,
            target2,

            pop,
            delta,
            iv,

            option_oi,
            option_chg_oi,
            option_volume,
            spread_pct,

            alignment,

            tf5_trend,
            tf30_trend,
            daily_trend,

            trigger_level,
            trigger_hit,

            readiness,

            score_gate,
            alignment_gate,
            trend_gate,
            spread_gate,
            delta_gate,
            pop_gate,
            volume_gate,

            fail_reasons,

            tracking_until

        )
        VALUES (

            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
        """,
        (
            now_ist().isoformat(),

            symbol,
            underlying_key,
            expiry,

            safe_float(spot),

            market_bias,

            safe_float(support),
            safe_float(resistance),
            safe_float(pcr),

            safe_float(bull_score),
            safe_float(bear_score),
            safe_float(confidence),

            decision,

            selected_side,
            safe_float(selected_strike),
            option_key,

            safe_float(entry),
            safe_float(sl),
            safe_float(target1),
            safe_float(target2),

            safe_float(pop),
            safe_float(delta),
            safe_float(iv),

            safe_float(oi),
            safe_float(chg_oi),
            safe_float(volume),
            safe_float(spread_pct),

            int(alignment)
            if alignment is not None
            else None,

            tf5.get("trend"),
            tf30.get("trend"),
            daily.get("trend"),

            safe_float(trigger_level),
            trigger_hit,

            readiness,

            score_gate,
            alignment_gate,
            trend_gate,
            spread_gate,
            delta_gate,
            pop_gate,
            volume_gate,

            fail_reasons,

            tracking_until,
        ),
    )

    conn.commit()
    conn.close()


# ============================================================
# UPDATE OUTCOMES
# ============================================================

def update_outcomes():

    conn = get_connection()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            id,
            option_key,
            entry,
            stop_loss,
            target1,
            tracking_until
        FROM decisions
        WHERE decision IN ('CALL BUY','PUT BUY')
          AND outcome IS NULL
          AND option_key IS NOT NULL
        ORDER BY id ASC
        """
    )

    rows = cur.fetchall()

    for row in rows:

        record_id = row[0]
        option_key = row[1]

        entry = safe_float(row[2])
        sl = safe_float(row[3])
        target1 = safe_float(row[4])

        try:
            tracking_until = datetime.fromisoformat(row[5])

            if tracking_until.tzinfo is None:
                tracking_until = tracking_until.replace(
                    tzinfo=IST
                )

        except Exception:
            continue

        try:
            quote = get_quote(option_key)

            market_data = (
                quote.get("market_data")
                or quote.get("market_data")
                or {}
            )

            current_price = safe_float(
                market_data.get("ltp")
            )

            if not np.isfinite(current_price):
                continue

        except Exception:
            continue

        outcome = None

        # Target 1 first
        if current_price >= target1:

            outcome = "WIN"

        # Stop loss first
        elif current_price <= sl:

            outcome = "LOSS"

        # Time limit reached
        elif now_ist() >= tracking_until:

            if current_price > entry:
                outcome = "TIMEOUT_PROFIT"
            elif current_price < entry:
                outcome = "TIMEOUT_LOSS"
            else:
                outcome = "TIMEOUT_FLAT"

        if outcome:

            cur.execute(
                """
                UPDATE decisions
                SET
                    outcome = ?,
                    outcome_timestamp = ?,
                    outcome_price = ?
                WHERE id = ?
                """,
                (
                    outcome,
                    now_ist().isoformat(),
                    current_price,
                    record_id,
                ),
            )

    conn.commit()
    conn.close()


# ============================================================
# JOURNAL STATISTICS
# ============================================================

def journal_stats():

    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT *
        FROM decisions
        ORDER BY id DESC
        """,
        conn,
    )

    conn.close()

    if df.empty:

        return {
            "total": 0,
            "actionable": 0,
            "completed": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": np.nan,
        }, df

    actionable = df[
        df["decision"].isin(
            ["CALL BUY", "PUT BUY"]
        )
    ]

    completed = actionable[
        actionable["outcome"].notna()
    ]

    wins = completed[
        completed["outcome"] == "WIN"
    ]

    losses = completed[
        completed["outcome"] == "LOSS"
    ]

    win_rate = (
        len(wins) / len(completed) * 100
        if len(completed) > 0
        else np.nan
    )

    stats = {
        "total": len(df),
        "actionable": len(actionable),
        "completed": len(completed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
    }

    return stats, df


# ============================================================
# SEARCH UNDERLYING
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

        results.extend(
            payload.get("data", [])
        )

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


# ============================================================
# OPTION CONTRACTS
# ============================================================

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


# ============================================================
# OPTION CHAIN
# ============================================================

@st.cache_data(ttl=20, show_spinner=False)
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
            f"No option-chain data returned for expiry {expiry}."
        )

    return rows


# ============================================================
# QUOTE
# ============================================================

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


# ============================================================
# CANDLES
# ============================================================

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

    start_date = (
        end_date - timedelta(days=90)
    )

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

    start_date = (
        end_date - timedelta(days=220)
    )

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
# TECHNICAL INDICATORS
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

    rs = gain / loss.replace(
        0,
        np.nan,
    )

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
    volume = (
        df["volume"]
        .fillna(0)
        .astype(float)
    )

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
        / (
            plus_di + minus_di
        ).replace(
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
        ).cumsum() / (
            volume.cumsum()
            .replace(0, np.nan)
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
        volume.iloc[-1]
        / vol_base
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

    bullish = (
        spot > e20 > e50
    )

    bearish = (
        spot < e20 < e50
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


# ============================================================
# TREND
# ============================================================

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

    return float(
        np.clip(
            score,
            0,
            30,
        )
    ), alignment


# ============================================================
# OI LEVELS
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
        & (
            valid["Strike"]
            <= spot * 1.10
        )
    ].copy()

    if band.empty:
        band = valid

    below = band[
        band["Strike"] <= spot
    ]

    above = band[
        band["Strike"] >= spot
    ]

    if not below.empty:

        support_row = below.loc[
            below["PE OI"]
            .fillna(0)
            .idxmax()
        ]

    else:

        support_row = band.loc[
            band["PE OI"]
            .fillna(0)
            .idxmax()
        ]

    if not above.empty:

        resistance_row = above.loc[
            above["CE OI"]
            .fillna(0)
            .idxmax()
        ]

    else:

        resistance_row = band.loc[
            band["CE OI"]
            .fillna(0)
            .idxmax()
        ]

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
        total_put_oi
        / total_call_oi
        if total_call_oi
        else np.nan
    )

    put_walls = (
        band
        .nlargest(3, "PE OI")[
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
        .nlargest(3, "CE OI")[
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


# ============================================================
# NEAREST OPTION
# ============================================================

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

                "CE OI":
                    call_oi,

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

                "PE OI":
                    put_oi,

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

    if not records:
        return pd.DataFrame()

    return (
        pd.DataFrame(records)
        .sort_values("Strike")
        .reset_index(drop=True)
    )


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

    tf_points, alignment = (
        timeframe_score(
            side,
            tf5,
            tf30,
            daily,
        )
    )

    # --------------------------------------------------------
    # FIX:
    # The original code referenced undefined "tf".
    # Use the 5-minute timeframe as the momentum trigger.
    # --------------------------------------------------------

    tf = tf5

    momentum_points = 0

    desired = (
        "Bullish"
        if side == "CE"
        else "Bearish"
    )

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

    # --------------------------------------------------------
    # PCR
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # OI
    # --------------------------------------------------------

    oi_points = (
        4
        if chg_oi <= 0
        else 2
    )

    # --------------------------------------------------------
    # OPTION QUALITY
    # --------------------------------------------------------

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
            or
            0.70 < abs_delta <= 0.80
        ):

            quality += 5

    spread_pct = (
        max(ask - bid, 0)
        / max(
            (ask + bid) / 2,
            0.01,
        )
        * 100
        if (
            np.isfinite(ask)
            and np.isfinite(bid)
            and ask > 0
            and bid > 0
        )
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
                (iv_values <= iv).mean()
            )

            if 0.15 <= iv_rank <= 0.75:

                quality += 4

            elif iv_rank < 0.90:

                quality += 2

        else:

            quality += 2

    # --------------------------------------------------------
    # STRIKE DISTANCE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # BROKER PoP CONTRIBUTION
    # --------------------------------------------------------

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
# BUILD PLAN
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

        "Conservative":
            (0.72, 1.25, 1.55),

        "Balanced":
            (0.70, 1.35, 1.75),

        "Aggressive":
            (0.65, 1.50, 2.00),

    }

    sl_factor, target1_factor, target2_factor = (
        risk_settings[risk_profile]
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
            f"breaks and sustains above "
            f"{fmt_price(trigger_level)}."
        )

        exit_rule = (
            f"Exit if spot loses support "
            f"{fmt_price(support)} or premium "
            f"hits {fmt_price(sl)}. "
            "After Target 1, book partial profit "
            "and trail."
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
            f"breaks and sustains below "
            f"{fmt_price(trigger_level)}."
        )

        exit_rule = (
            f"Exit if spot reclaims resistance "
            f"{fmt_price(resistance)} or premium "
            f"hits {fmt_price(sl)}. "
            "After Target 1, book partial profit "
            "and trail."
        )

    opposite = (
        "Bearish"
        if side == "CE"
        else "Bullish"
    )

    hard_fail = []

    if scored["score"] < MIN_ACTION_SCORE:

        hard_fail.append(
            f"setup score below {MIN_ACTION_SCORE:.0f}"
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

        "strike":
            float(row["Strike"]),

        "option_key":
            row[f"{side} Key"],

        "entry":
            float(entry),

        "sl":
            sl,

        "target1":
            target1,

        "target2":
            target2,

        "pop":
            scored["pop"],

        "delta":
            scored["delta"],

        "iv":
            scored["iv"],

        "score":
            scored["score"],

        "rr1":
            rr1,

        "rr2":
            rr2,

        "trigger":
            trigger,

        "trigger_level":
            trigger_level,

        "trigger_hit":
            trigger_hit,

        "readiness":
            readiness,

        "fail_reasons":
            hard_fail,

        "exit":
            exit_rule,

        "oi":
            row[f"{side} OI"],

        "chg_oi":
            scored["chg_oi"],

        "volume":
            scored["volume"],

        "spread_pct":
            scored["spread_pct"],

        "alignment":
            scored["alignment"],

    }


# ============================================================
# CHOOSE BEST PLAN
# ============================================================

def choose_candidate(
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
):

    if chain.empty:
        return None

    desired_distance = 0.03

    candidates = []

    for _, row in chain.iterrows():

        if (
            not np.isfinite(
                safe_float(
                    row["Strike"]
                )
            )
        ):
            continue

        distance = (
            abs(
                row["Strike"]
                - spot
            )
            / max(spot, 1)
        )

        if distance > desired_distance:
            continue

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

        if plan:
            candidates.append(plan)

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: (
            x["score"],
            x["pop"]
            if np.isfinite(
                x["pop"]
            )
            else -999,
            x["alignment"],
            -abs(
                x["strike"]
                - spot
            ),
        ),
        reverse=True,
    )

    return candidates[0]


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_confidence(
    bull_score,
    bear_score,
    overall_direction,
    ce_plan,
    pe_plan,
):

    directional_gap = abs(
        bull_score - bear_score
    )

    base = 50 + min(
        directional_gap,
        25,
    )

    if overall_direction in {
        "Bullish",
        "Bearish",
    }:
        base += 5

    selected = (
        ce_plan
        if overall_direction == "Bullish"
        else pe_plan
        if overall_direction == "Bearish"
        else None
    )

    if selected:

        base += min(
            selected.get(
                "alignment",
                0
            ) * 3,
            9,
        )

    return float(
        np.clip(
            base,
            0,
            100,
        )
    )


# ============================================================
# DECISION ENGINE
# ============================================================

def make_decision(
    ce_plan,
    pe_plan,
    overall_direction,
):

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

    if (
        ce_plan
        and ce_score >= MIN_ACTION_SCORE
        and ce_score >= pe_score + 8
        and overall_direction == "Bullish"
        and ce_plan["readiness"]
        in {
            "READY",
            "WAIT FOR TRIGGER",
        }
    ):

        if ce_plan["readiness"] == "READY":

            return "CALL BUY"

        return "WAIT FOR TRIGGER"

    if (
        pe_plan
        and pe_score >= MIN_ACTION_SCORE
        and pe_score >= ce_score + 8
        and overall_direction == "Bearish"
        and pe_plan["readiness"]
        in {
            "READY",
            "WAIT FOR TRIGGER",
        }
    ):

        if pe_plan["readiness"] == "READY":

            return "PUT BUY"

        return "WAIT FOR TRIGGER"

    return "NO TRADE"


# ============================================================
# FULL F&O SCANNER
# ============================================================

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
            "Unable to load the Upstox NSE "
            f"F&O instrument list: {exc}"
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

        if not isinstance(
            item,
            dict,
        ):
            continue

        if item.get(
            "segment"
        ) != "NSE_FO":
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
                    datetime
                    .fromtimestamp(
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

        if (
            not underlying_key
            or not symbol
        ):
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
                "expiry":
                    expiry_date,
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

                if not np.isfinite(
                    strike
                ):
                    continue

                for side, action in (
                    (
                        "CE",
                        "CALL BUY",
                    ),
                    (
                        "PE",
                        "PUT BUY",
                    ),
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
                        greeks.get(
                            "pop"
                        )
                    )

                    if (
                        not np.isfinite(pop)
                        or pop <= min_pop
                    ):
                        continue

                    ltp = safe_float(
                        market.get(
                            "ltp"
                        )
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
                        market.get(
                            "oi"
                        ),
                        0,
                    )

                    delta = safe_float(
                        greeks.get(
                            "delta"
                        )
                    )

                    iv = safe_float(
                        greeks.get(
                            "iv"
                        )
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
# MARKET HOURS
# ============================================================

def market_is_open():

    now = now_ist()

    if now.weekday() >= 5:
        return False

    start = now.replace(
        hour=9,
        minute=15,
        second=0,
        microsecond=0,
    )

    end = now.replace(
        hour=15,
        minute=30,
        second=0,
        microsecond=0,
    )

    return start <= now <= end


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
        Options Analysis • Upstox REST API •
        Live market data
    </div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# STATUS
# ============================================================

if market_is_open():

    st.markdown(
        """
        <div class="status-live">
            ● LIVE DATA
        </div>
        """,
        unsafe_allow_html=True,
    )

else:

    st.markdown(
        """
        <div class="status-closed">
            ● MARKET CLOSED
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🔎 Analyze Instrument"
    )

    symbol_input = st.text_input(
        "Stock / Index",
        value="HDFCBANK",
        key="symbol_input",
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
        "📊 Analyze",
        use_container_width=True,
        type="primary",
    )

    refresh = st.button(
        "🔄 Refresh Now",
        use_container_width=True,
    )

    st.markdown("---")

    st.markdown(
        "### ⚡ F&O Scanner"
    )

    scanner_enabled = st.toggle(
        "Full F&O Scanner",
        value=False,
    )

    if scanner_enabled:

        if st.button(
            "🚀 Scan F&O Market",
            use_container_width=True,
        ):

            st.session_state[
                "run_scanner"
            ] = True

    st.markdown("---")

    auto_refresh = st.checkbox(
        "Auto Refresh",
        value=True,
    )

    if auto_refresh and st_autorefresh:

        st_autorefresh(
            interval=30000,
            key="fo_auto_refresh",
        )


# ============================================================
# STATE
# ============================================================

if "analyzed_symbol" not in st.session_state:
    st.session_state[
        "analyzed_symbol"
    ] = symbol_input

if analyze or refresh:

    st.session_state[
        "analyzed_symbol"
    ] = alias_symbol(
        symbol_input
    )

symbol = st.session_state[
    "analyzed_symbol"
]


# ============================================================
# UPDATE EXISTING OUTCOMES
# ============================================================

try:

    update_outcomes()

except Exception:
    # Outcome tracking must never break
    # the live analysis dashboard.
    pass


# ============================================================
# SCANNER
# ============================================================

if st.session_state.get(
    "run_scanner",
    False,
):

    try:

        results, total, scanned, failed = (
            scan_full_fno_pop_market(
                min_pop=75.0
            )
        )

        st.sidebar.success(
            f"Scan complete: {scanned}/{total}"
        )

        if results:

            scanner_df = pd.DataFrame(
                results
            )

            st.sidebar.dataframe(
                scanner_df[
                    [
                        "Stock",
                        "Trade",
                        "Strike",
                        "PoP",
                        "Entry",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.sidebar.info(
                "No options found above the "
                "current scanner PoP threshold."
            )

        if failed:

            st.sidebar.caption(
                f"{failed} instruments could not be scanned."
            )

    except Exception as exc:

        st.sidebar.error(
            f"Scanner error: {exc}"
        )

    st.session_state[
        "run_scanner"
    ] = False


# ============================================================
# ANALYSIS
# ============================================================

try:

    underlying = search_underlying(
        symbol
    )

    underlying_key = underlying.get(
        "instrument_key"
    )

    display_symbol = (
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
            "No future option expiry found."
        )

    expiry = expiries[0]

    rows = get_option_chain(
        underlying_key,
        expiry,
    )

    chain = normalize_chain(
        rows
    )

    if chain.empty:

        raise UpstoxError(
            "Unable to normalize the option chain."
        )

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

    spot = (
        spot_values[0]
        if spot_values
        else np.nan
    )

    if not np.isfinite(spot):

        quote_data = get_quote(
            underlying_key
        )

        market_data = (
            quote_data.get(
                "market_data"
            )
            or {}
        )

        spot = safe_float(
            market_data.get("ltp")
        )

    if not np.isfinite(spot):

        raise UpstoxError(
            "Unable to obtain underlying spot price."
        )

    support, resistance, pcr, oi_wall_info = (
        oi_levels(
            chain,
            spot,
        )
    )

    # --------------------------------------------------------
    # TECHNICAL DATA
    # --------------------------------------------------------

    df5 = get_intraday_candles(
        underlying_key,
        5,
    )

    df30 = get_30m_candles(
        underlying_key
    )

    dfd = get_daily_candles(
        underlying_key
    )

    tf5 = technicals(
        df5,
        spot,
    )

    tf30 = technicals(
        df30,
        spot,
    )

    daily = technicals(
        dfd,
        spot,
    )

    overall_direction, trend_count = (
        overall_trend(
            tf5,
            tf30,
            daily,
        )
    )

    # --------------------------------------------------------
    # CANDIDATES
    # --------------------------------------------------------

    ce_plan = choose_candidate(
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
    )

    pe_plan = choose_candidate(
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
    )

    # --------------------------------------------------------
    # SCORES
    # --------------------------------------------------------

    bull_score = (
        ce_plan["score"]
        if ce_plan
        else 0
    )

    bear_score = (
        pe_plan["score"]
        if pe_plan
        else 0
    )

    confidence = calculate_confidence(
        bull_score,
        bear_score,
        overall_direction,
        ce_plan,
        pe_plan,
    )

    decision = make_decision(
        ce_plan,
        pe_plan,
        overall_direction,
    )

    # --------------------------------------------------------
    # SELECTED PLAN
    # --------------------------------------------------------

    if decision in {
        "CALL BUY",
        "WAIT FOR TRIGGER",
    }:

        selected_plan = ce_plan

    elif decision == "PUT BUY":

        selected_plan = pe_plan

    else:

        # For NO TRADE, still record the strongest
        # candidate so the historical journal can tell
        # us exactly why it was rejected.

        selected_plan = (
            ce_plan
            if bull_score >= bear_score
            else pe_plan
        )

    # --------------------------------------------------------
    # JOURNAL
    # --------------------------------------------------------

    try:

        log_decision(
            symbol=display_symbol,
            underlying_key=underlying_key,
            expiry=expiry,
            spot=spot,
            market_bias=overall_direction,
            support=support,
            resistance=resistance,
            pcr=pcr,
            bull_score=bull_score,
            bear_score=bear_score,
            confidence=confidence,
            decision=decision,
            selected_plan=selected_plan,
            tf5=tf5,
            tf30=tf30,
            daily=daily,
        )

    except Exception:
        # Logging must never stop live analysis.
        pass


    # ========================================================
    # HEADER
    # ========================================================

    st.markdown(
        f"""
        <div class="card">

            <div class="section-title">
                📊 {display_symbol} — F&O Analysis
            </div>

            <div class="small-muted">
                Expiry: {expiry}
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


    # ========================================================
    # MARKET SNAPSHOT
    # ========================================================

    cols = st.columns(6)

    metrics = [
        (
            "Last Traded",
            fmt_price(spot),
        ),
        (
            "Market Bias",
            overall_direction,
        ),
        (
            "PCR",
            f"{pcr:.2f}"
            if np.isfinite(pcr)
            else "—",
        ),
        (
            "OI Support",
            fmt_price(support),
        ),
        (
            "OI Resistance",
            fmt_price(resistance),
        ),
        (
            "Confidence",
            f"{confidence:.0f}/100",
        ),
    ]

    for col, (label, value) in zip(
        cols,
        metrics,
    ):

        with col:

            st.markdown(
                f"""
                <div class="metric-card">

                    <div class="metric-label">
                        {label}
                    </div>

                    <div class="metric-value">
                        {value}
                    </div>

                </div>
                """,
                unsafe_allow_html=True,
            )


    # ========================================================
    # DECISION
    # ========================================================

    st.markdown(
        "<div class='card'>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='section-title'>"
        "🎯 Trade Decision"
        "</div>",
        unsafe_allow_html=True,
    )

    if decision == "CALL BUY":

        st.markdown(
            """
            <div class="trade-call">
                🟢 CALL BUY
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif decision == "PUT BUY":

        st.markdown(
            """
            <div class="trade-put">
                🔴 PUT BUY
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif decision == "WAIT FOR TRIGGER":

        st.markdown(
            """
            <div class="trade-neutral">
                🟡 WAIT FOR TRIGGER
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        st.markdown(
            """
            <div class="trade-neutral">
                ⚪ NO TRADE
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "<br>",
        unsafe_allow_html=True,
    )

    score_cols = st.columns(3)

    with score_cols[0]:

        st.metric(
            "Bull Score",
            f"{bull_score:.0f}/100",
        )

    with score_cols[1]:

        st.metric(
            "Bear Score",
            f"{bear_score:.0f}/100",
        )

    with score_cols[2]:

        st.metric(
            "Confidence",
            f"{confidence:.0f}/100",
        )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )


    # ========================================================
    # TRADE PLAN
    # ========================================================

    st.markdown(
        "<div class='card'>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='section-title'>"
        "📋 Trade Plan"
        "</div>",
        unsafe_allow_html=True,
    )

    if selected_plan and decision in {
        "CALL BUY",
        "PUT BUY",
        "WAIT FOR TRIGGER",
    }:

        p = selected_plan

        plan_cols = st.columns(6)

        plan_metrics = [

            (
                "Strike",
                f"{p['strike']:.0f}",
            ),

            (
                "Entry",
                fmt_price(p["entry"]),
            ),

            (
                "Stop Loss",
                fmt_price(p["sl"]),
            ),

            (
                "Target 1",
                fmt_price(p["target1"]),
            ),

            (
                "Target 2",
                fmt_price(p["target2"]),
            ),

            (
                "Risk / Reward",
                f"{p['rr1']:.2f} / "
                f"{p['rr2']:.2f}",
            ),

        ]

        for col, (label, value) in zip(
            plan_cols,
            plan_metrics,
        ):

            with col:

                st.markdown(
                    f"""
                    <div class="metric-card">

                        <div class="metric-label">
                            {label}
                        </div>

                        <div class="metric-value">
                            {value}
                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        detail_cols = st.columns(4)

        details = [

            (
                "PoP",
                f"{p['pop']:.1f}%"
                if np.isfinite(p["pop"])
                else "—",
            ),

            (
                "Delta",
                f"{p['delta']:.3f}"
                if np.isfinite(p["delta"])
                else "—",
            ),

            (
                "IV",
                f"{p['iv']:.1f}"
                if np.isfinite(p["iv"])
                else "—",
            ),

            (
                "Setup Score",
                f"{p['score']:.0f}/100",
            ),

        ]

        for col, (label, value) in zip(
            detail_cols,
            details,
        ):

            with col:

                st.metric(
                    label,
                    value,
                )

        st.markdown(
            f"""
            <div class="reason-box">

                <b>Entry Trigger:</b>
                {p['trigger']}

                <br><br>

                <b>Exit Rule:</b>
                {p['exit']}

            </div>
            """,
            unsafe_allow_html=True,
        )

        if p.get("fail_reasons"):

            st.markdown(
                "<div class='reason-box'>"
                "<b>Current quality gates:</b><br>"
                + "<br>".join(
                    "• " + x
                    for x in p["fail_reasons"]
                )
                + "</div>",
                unsafe_allow_html=True,
            )

    else:

        st.info(
            "No actionable trade plan currently satisfies "
            "the engine's quality conditions."
        )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )


    # ========================================================
    # TABS
    # ========================================================

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "⭐ Best Trade",
            "📑 Live Option Chain",
            "📈 Market Analysis",
            "🧠 How Engine Thinks",
        ]
    )


    # ========================================================
    # BEST TRADE
    # ========================================================

    with tab1:

        if ce_plan or pe_plan:

            best_plan = (
                ce_plan
                if bull_score >= bear_score
                else pe_plan
            )

            if best_plan:

                st.markdown(
                    "### Best Current Setup"
                )

                st.write(
                    f"**Side:** "
                    f"{'CALL' if best_plan['side'] == 'CE' else 'PUT'}"
                )

                st.write(
                    f"**Strike:** "
                    f"{best_plan['strike']:.0f}"
                )

                st.write(
                    f"**Setup Score:** "
                    f"{best_plan['score']:.0f}/100"
                )

                st.write(
                    f"**Upstox PoP:** "
                    f"{best_plan['pop']:.1f}%"
                    if np.isfinite(
                        best_plan["pop"]
                    )
                    else "**Upstox PoP:** —"
                )

                st.write(
                    f"**Delta:** "
                    f"{best_plan['delta']:.3f}"
                    if np.isfinite(
                        best_plan["delta"]
                    )
                    else "**Delta:** —"
                )

                st.write(
                    f"**OI:** "
                    f"{fmt_num(best_plan['oi'])}"
                )

                st.write(
                    f"**Change in OI:** "
                    f"{fmt_num(best_plan['chg_oi'])}"
                )

        else:

            st.info(
                "No qualifying option setup found."
            )


    # ========================================================
    # OPTION CHAIN
    # ========================================================

    with tab2:

        display_chain = chain.copy()

        display_columns = [

            "Strike",

            "CE LTP",
            "CE OI",
            "CE Chg OI",
            "CE IV",
            "CE Delta",
            "CE PoP",

            "PE PoP",
            "PE Delta",
            "PE IV",
            "PE Chg OI",
            "PE OI",
            "PE LTP",

        ]

        available_columns = [
            c
            for c in display_columns
            if c in display_chain.columns
        ]

        st.dataframe(
            display_chain[
                available_columns
            ],
            use_container_width=True,
            hide_index=True,
        )


    # ========================================================
    # MARKET ANALYSIS
    # ========================================================

    with tab3:

        st.markdown(
            "### Multi-Timeframe Analysis"
        )

        analysis_df = pd.DataFrame(
            [
                {
                    "Timeframe": "5 Min",
                    "Trend": tf5["trend"],
                    "RSI": round(
                        tf5["rsi"],
                        1,
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
                    "Timeframe": "30 Min",
                    "Trend": tf30["trend"],
                    "RSI": round(
                        tf30["rsi"],
                        1,
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
            analysis_df,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown(
            "### OI Walls"
        )

        oi_cols = st.columns(2)

        with oi_cols[0]:

            st.markdown(
                "**Put OI Support**"
            )

            st.write(
                oi_wall_info[
                    "put_walls"
                ]
            )

        with oi_cols[1]:

            st.markdown(
                "**Call OI Resistance**"
            )

            st.write(
                oi_wall_info[
                    "call_walls"
                ]
            )


    # ========================================================
    # ENGINE
    # ========================================================

    with tab4:

        st.markdown(
            "### 🧠 Decision Engine"
        )

        st.write(
            "The engine combines multiple independent "
            "signals instead of relying on one indicator."
        )

        st.markdown(
            f"""
            <div class="reason-box">

            <b>Current direction:</b>
            {overall_direction}

            <br>

            <b>5-minute:</b>
            {tf5['trend']}

            <br>

            <b>30-minute:</b>
            {tf30['trend']}

            <br>

            <b>Daily:</b>
            {daily['trend']}

            <br>

            <b>CALL score:</b>
            {bull_score:.0f}/100

            <br>

            <b>PUT score:</b>
            {bear_score:.0f}/100

            <br>

            <b>Action threshold:</b>
            {MIN_ACTION_SCORE:.0f}/100

            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            "### What is now being measured?"
        )

        st.write(
            """
            Every decision is recorded with its market state,
            option characteristics, technical alignment and
            decision outcome.

            This allows the engine to eventually answer questions
            such as:

            • How often did CALL BUY signals actually reach T1?

            • How often did PUT BUY signals actually reach T1?

            • What happened to setups scoring 60–65?

            • What happened to setups scoring 65–72?

            • Does a high Upstox PoP actually correspond to a
              higher observed success rate?

            • Which timeframe combinations produce the best
              outcomes?

            • Which filters eliminate too many otherwise successful
              trades?
            """
        )

        st.warning(
            "The Setup Score and Upstox PoP are not the same thing "
            "as a statistically validated probability of profit."
        )


    # ========================================================
    # FOOTER
    # ========================================================

    st.markdown(
        "<br><br>",
        unsafe_allow_html=True,
    )

    st.caption(
        "FO PRO Trader Assistant • Live Upstox REST data • "
        "Decision journal enabled • "
        f"Updated {now_ist().strftime('%d-%b-%Y %H:%M:%S IST')}"
    )


except UpstoxError as exc:

    st.error(
        f"Upstox data error: {exc}"
    )

except Exception as exc:

    st.error(
        "Analysis error occurred."
    )

    st.exception(exc)
```
