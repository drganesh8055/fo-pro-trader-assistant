import gzip
import json
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
    padding:18px 24px;
    border-radius:14px;
    color:white;
    margin-bottom:18px;
}

.topbar-title {font-size:27px;font-weight:800;}
.topbar-sub {font-size:13px;opacity:.82;margin-top:3px;}

.status-pill {
    display:inline-block;
    padding:7px 12px;
    border-radius:20px;
    background:#1f9d55;
    color:white;
    font-size:12px;
    font-weight:700;
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
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# BASIC HELPERS
# ============================================================

class UpstoxError(RuntimeError):
    pass


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


def fmt_price(value):
    try:
        x = float(value)
    except Exception:
        return "—"

    if np.isnan(x):
        return "—"

    if abs(x) < 1000:
        return f"₹{x:,.2f}"

    return f"₹{x:,.0f}"


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


# ============================================================
# UNDERLYING / OPTION DATA
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

        results.extend(payload.get("data", []))

    if not results:
        raise UpstoxError(
            f"No NSE instrument found for '{symbol}'. "
            "Enter an NSE F&O stock symbol such as HDFCBANK "
            "or an index such as NIFTY."
        )

    exact = [
        item
        for item in results
        if str(item.get("trading_symbol", "")).upper() == symbol
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


@st.cache_data(ttl=120, show_spinner=False)
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
    today = date.today().isoformat()

    return sorted(
        {
            str(item.get("expiry"))
            for item in contracts
            if item.get("expiry")
            and str(item.get("expiry")) >= today
        }
    )


@st.cache_data(ttl=20, show_spinner=False)
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


@st.cache_data(ttl=20, show_spinner=False)
def get_quote(instrument_key):
    payload = api_get(
        "/v3/market-quote/quotes",
        params={"instrument_key": instrument_key},
    )

    data = payload.get("data", {})

    if not data:
        raise UpstoxError(
            "No live quote returned by Upstox."
        )

    return next(iter(data.values()))


@st.cache_data(ttl=300, show_spinner=False)
def get_daily_candles(instrument_key):
    end_date = date.today()
    start_date = end_date - timedelta(days=160)

    path = (
        f"/v3/historical-candle/"
        f"{quote(instrument_key, safe='')}"
        f"/days/1/"
        f"{end_date.isoformat()}/"
        f"{start_date.isoformat()}"
    )

    payload = api_get(path, timeout=30)

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
# TECHNICAL ANALYSIS
# ============================================================

def technicals(df, spot):
    if df.empty or len(df) < 20:
        return {
            "rsi": 50.0,
            "ema20": spot,
            "ema50": spot,
            "atr": spot * 0.01,
            "trend": "Unavailable",
        }

    close = df["close"]

    delta = close.diff()

    gain = (
        delta
        .clip(lower=0)
        .rolling(14)
        .mean()
    )

    loss = (
        (-delta.clip(upper=0))
        .rolling(14)
        .mean()
    )

    rs = gain / loss.replace(0, np.nan)

    rsi = 100 - (
        100 / (1 + rs)
    )

    ema20 = close.ewm(
        span=20,
        adjust=False,
    ).mean()

    ema50 = close.ewm(
        span=50,
        adjust=False,
    ).mean()

    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (
                df["high"]
                - previous_close
            ).abs(),
            (
                df["low"]
                - previous_close
            ).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = true_range.rolling(14).mean()

    latest_rsi = safe_float(
        rsi.iloc[-1],
        50.0,
    )

    latest_ema20 = safe_float(
        ema20.iloc[-1],
        spot,
    )

    latest_ema50 = safe_float(
        ema50.iloc[-1],
        spot,
    )

    latest_atr = safe_float(
        atr.iloc[-1],
        spot * 0.01,
    )

    if (
        spot > latest_ema20
        and latest_ema20 > latest_ema50
        and latest_rsi >= 50
    ):
        trend = "Bullish"

    elif (
        spot < latest_ema20
        and latest_ema20 < latest_ema50
        and latest_rsi <= 50
    ):
        trend = "Bearish"

    else:
        trend = "Sideways"

    return {
        "rsi": latest_rsi,
        "ema20": latest_ema20,
        "ema50": latest_ema50,
        "atr": latest_atr,
        "trend": trend,
    }


# ============================================================
# OPTION CHAIN NORMALIZATION
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

                "CE Chg OI":
                    call_oi - call_prev_oi,

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

                "CE PoP": safe_float(
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

                "PE Chg OI":
                    put_oi - put_prev_oi,

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

                "PE PoP": safe_float(
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
# OI LEVELS
# ============================================================

def oi_levels(chain, spot):
    valid = chain.dropna(
        subset=["Strike"]
    ).copy()

    if valid.empty:
        return (
            np.nan,
            np.nan,
            np.nan,
        )

    below = valid[
        valid["Strike"] <= spot
    ]

    above = valid[
        valid["Strike"] >= spot
    ]

    support_row = (
        below.loc[
            below["PE OI"].idxmax()
        ]
        if not below.empty
        else valid.loc[
            valid["PE OI"].idxmax()
        ]
    )

    resistance_row = (
        above.loc[
            above["CE OI"].idxmax()
        ]
        if not above.empty
        else valid.loc[
            valid["CE OI"].idxmax()
        ]
    )

    total_call_oi = valid["CE OI"].sum()
    total_put_oi = valid["PE OI"].sum()

    pcr = (
        total_put_oi / total_call_oi
        if total_call_oi
        else np.nan
    )

    return (
        float(support_row["Strike"]),
        float(resistance_row["Strike"]),
        pcr,
    )


def nearest_row(chain, strike):
    if chain.empty:
        return None

    index = (
        chain["Strike"] - strike
    ).abs().idxmin()

    return chain.loc[index]


# ============================================================
# MAIN ENGINE
# ============================================================

def score_option(
    row,
    side,
    spot,
    pcr,
    tech,
):
    if side == "CE":
        premium = row["CE LTP"]
        delta = row["CE Delta"]
        iv = row["CE IV"]
        pop = row["CE PoP"]
        chg_oi = row["CE Chg OI"]
        volume = row["CE Volume"]

        directional = (
            25
            if tech["trend"] == "Bullish"
            else 10
            if tech["trend"] == "Sideways"
            else 0
        )

        pcr_score = (
            10
            if pcr >= 0.90
            else 5
            if pcr >= 0.75
            else 0
        )

    else:
        premium = row["PE LTP"]
        delta = row["PE Delta"]
        iv = row["PE IV"]
        pop = row["PE PoP"]
        chg_oi = row["PE Chg OI"]
        volume = row["PE Volume"]

        directional = (
            25
            if tech["trend"] == "Bearish"
            else 10
            if tech["trend"] == "Sideways"
            else 0
        )

        pcr_score = (
            10
            if pcr <= 1.10
            else 5
            if pcr <= 1.30
            else 0
        )

    distance_pct = (
        abs(
            float(row["Strike"]) - spot
        )
        / max(spot, 1)
    )

    distance_score = max(
        0,
        15 - distance_pct * 500,
    )

    delta_score = (
        np.clip(
            (
                (abs(delta) - 0.30)
                / 0.45
                * 20
            ),
            0,
            20,
        )
        if not np.isnan(delta)
        else 0
    )

    pop_score = (
        np.clip(
            (
                (pop - 40)
                / 30
                * 20
            ),
            0,
            20,
        )
        if not np.isnan(pop)
        else 0
    )

    liquidity_score = (
        10 if volume > 0 else 0
    )

    oi_score = (
        5 if chg_oi < 0 else 2
    )

    score = float(
        np.clip(
            directional
            + pcr_score
            + distance_score
            + delta_score
            + pop_score
            + liquidity_score
            + oi_score,
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
    }


def build_plan(
    row,
    side,
    spot,
    support,
    resistance,
    pcr,
    tech,
    risk_profile,
):
    if row is None:
        return None

    scored = score_option(
        row,
        side,
        spot,
        pcr,
        tech,
    )

    entry = row[
        f"{side} Ask"
    ]

    if (
        np.isnan(entry)
        or entry <= 0
    ):
        entry = row[
            f"{side} LTP"
        ]

    if (
        np.isnan(entry)
        or entry <= 0
    ):
        return None

    risk_settings = {
        "Conservative":
            (0.75, 1.30, 1.60),

        "Balanced":
            (0.70, 1.40, 1.80),

        "Aggressive":
            (0.65, 1.55, 2.10),
    }

    (
        sl_factor,
        target1_factor,
        target2_factor,
    ) = risk_settings[
        risk_profile
    ]

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

    if side == "CE":
        trigger = (
            "Enter only after spot sustains "
            f"above resistance/trigger around "
            f"{fmt_price(resistance)}."
        )

        exit_rule = (
            "Exit if spot closes below support "
            f"{fmt_price(support)} or option "
            f"premium hits {fmt_price(sl)}. "
            "After Target 1, book partial profit "
            "and trail the balance."
        )

    else:
        trigger = (
            "Enter only after spot breaks and sustains "
            f"below support/trigger around "
            f"{fmt_price(support)}."
        )

        exit_rule = (
            "Exit if spot closes above resistance "
            f"{fmt_price(resistance)} or option "
            f"premium hits {fmt_price(sl)}. "
            "After Target 1, book partial profit "
            "and trail the balance."
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
        "exit": exit_rule,
        "oi": row[f"{side} OI"],
        "chg_oi": scored["chg_oi"],
        "volume": scored["volume"],
    }


# ============================================================
# FULL F&O MARKET PoP SCANNER
#
# IMPORTANT:
# PoP remains the Upstox PoP.
# It is NOT renamed as accuracy.
#
# The scanner now uses PoP as one filter inside a
# multi-factor trade-quality model.
# ============================================================

FNO_MASTER_URL = (
    "https://assets.upstox.com/"
    "market-quote/instruments/exchange/"
    "NSE.json.gz"
)

SCANNER_MIN_POP = 75.0
SCANNER_MIN_VOLUME = 5000
SCANNER_MAX_SPREAD_PCT = 3.0
SCANNER_MIN_DELTA = 0.35
SCANNER_MAX_DELTA = 0.80
SCANNER_MAX_DISTANCE_PCT = 5.0


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def get_fno_underlyings():
    """
    Build the current NSE equity F&O universe
    from Upstox's instrument master.
    """

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
            "Unable to load the Upstox NSE F&O "
            f"instrument list: {exc}"
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
                        tz=ZoneInfo(
                            "Asia/Kolkata"
                        ),
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
            or expiry_date
            < current["expiry"]
        ):
            universe[
                underlying_key
            ] = {
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


def scanner_spread_pct(
    bid,
    ask,
):
    """
    Percentage bid/ask spread relative to midpoint.
    """

    if (
        not np.isfinite(bid)
        or not np.isfinite(ask)
        or bid <= 0
        or ask <= 0
        or ask < bid
    ):
        return np.nan

    midpoint = (
        bid + ask
    ) / 2

    if midpoint <= 0:
        return np.nan

    return (
        (ask - bid)
        / midpoint
        * 100
    )


def scanner_static_score(
    pop,
    delta,
    spread_pct,
    volume,
    distance_pct,
    oi,
):
    """
    Score the option BEFORE directional confirmation.

    Maximum = 85.

    This score deliberately does not assume that
    high PoP alone makes a good directional trade.
    """

    # PoP: 30 points
    if pop >= 90:
        pop_score = 30
    elif pop >= 85:
        pop_score = 27
    elif pop >= 80:
        pop_score = 24
    elif pop > 75:
        pop_score = 21
    else:
        pop_score = 0

    # Delta: 15 points
    abs_delta = abs(delta)

    if 0.50 <= abs_delta <= 0.70:
        delta_score = 15
    elif 0.45 <= abs_delta <= 0.75:
        delta_score = 13
    elif 0.40 <= abs_delta <= 0.80:
        delta_score = 10
    else:
        delta_score = 5

    # Spread: 15 points
    if spread_pct <= 1.0:
        spread_score = 15
    elif spread_pct <= 1.5:
        spread_score = 12
    elif spread_pct <= 2.0:
        spread_score = 9
    else:
        spread_score = 5

    # Volume: 10 points
    if volume >= 100000:
        volume_score = 10
    elif volume >= 50000:
        volume_score = 8
    elif volume >= 25000:
        volume_score = 6
    elif volume >= SCANNER_MIN_VOLUME:
        volume_score = 4
    else:
        volume_score = 0

    # Moneyness/distance: 10 points
    if distance_pct <= 1.0:
        distance_score = 10
    elif distance_pct <= 2.0:
        distance_score = 8
    elif distance_pct <= 3.0:
        distance_score = 6
    elif distance_pct <= 5.0:
        distance_score = 3
    else:
        distance_score = 0

    # OI: 5 points
    oi_score = (
        5
        if oi > 0
        else 0
    )

    return float(
        pop_score
        + delta_score
        + spread_score
        + volume_score
        + distance_score
        + oi_score
    )


def scanner_direction_score(
    side,
    trend,
    rsi_value,
):
    """
    Directional confirmation.

    CALL requires a bullish trend.
    PUT requires a bearish trend.

    Sideways is deliberately rejected rather
    than converted into a forced trade.
    """

    if side == "CE":
        if trend != "Bullish":
            return None

        if rsi_value >= 55:
            return 15

        if rsi_value >= 50:
            return 12

        return 8

    if side == "PE":
        if trend != "Bearish":
            return None

        if rsi_value <= 45:
            return 15

        if rsi_value <= 50:
            return 12

        return 8

    return None


def scanner_oi_room(
    side,
    spot,
    support,
    resistance,
):
    """
    Prevents buying directly into a nearby OI wall.

    For CALL:
      reject if resistance is immediately overhead.

    For PUT:
      reject if support is immediately below.

    If the spot has already moved beyond the wall,
    the scanner does not penalize it.
    """

    if not np.isfinite(spot):
        return False, 0

    if side == "CE":

        if np.isfinite(resistance):
            distance = (
                resistance - spot
            ) / max(spot, 1) * 100

            if (
                distance >= 0
                and distance < 0.50
            ):
                return False, 0

            if (
                distance >= 0.50
                and distance < 1.00
            ):
                return True, 2

        return True, 5

    if side == "PE":

        if np.isfinite(support):
            distance = (
                spot - support
            ) / max(spot, 1) * 100

            if (
                distance >= 0
                and distance < 0.50
            ):
                return False, 0

            if (
                distance >= 0.50
                and distance < 1.00
            ):
                return True, 2

        return True, 5

    return False, 0


def scanner_candidate_quality(
    side,
    pop,
    delta,
    spread_pct,
    volume,
    distance_pct,
    oi,
    trend,
    rsi_value,
    support,
    resistance,
    spot,
):
    """
    Final scanner quality score.

    Maximum = 105.

    Components:
      Static option quality: 85
      Directional confirmation: 15
      OI room: 5

    The score is NOT a probability.
    It is only a ranking/quality score.
    """

    static_score = scanner_static_score(
        pop=pop,
        delta=delta,
        spread_pct=spread_pct,
        volume=volume,
        distance_pct=distance_pct,
        oi=oi,
    )

    direction_score = scanner_direction_score(
        side=side,
        trend=trend,
        rsi_value=rsi_value,
    )

    if direction_score is None:
        return None

    oi_ok, oi_score = scanner_oi_room(
        side=side,
        spot=spot,
        support=support,
        resistance=resistance,
    )

    if not oi_ok:
        return None

    return float(
        static_score
        + direction_score
        + oi_score
    )


def scanner_quality_label(score):
    if score >= 95:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 85:
        return "B+"
    if score >= 80:
        return "B"
    return "C"


def scan_full_fno_pop_market(
    min_pop=SCANNER_MIN_POP,
):
    """
    Full NSE equity F&O scan.

    IMPORTANT DESIGN:
    -----------------
    Stage 1:
      Find contracts with genuine Upstox PoP > threshold.

    Stage 2:
      Reject poor liquidity / spread / delta / moneyness.

    Stage 3:
      Confirm underlying technical direction.

    Stage 4:
      Confirm OI support/resistance room.

    Stage 5:
      Rank the remaining candidates using a composite
      quality score.

    Therefore:
        PoP != signal probability
        Quality Score != probability

    The scanner does NOT fabricate a probability.
    """

    universe = get_fno_underlyings()

    candidates_by_stock = {}

    scanned = 0
    failed = 0

    progress = st.progress(
        0,
        text="Starting full F&O market scan...",
    )

    # --------------------------------------------------------
    # STAGE 1 + STAGE 2
    # --------------------------------------------------------

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

            if not np.isfinite(
                spot_value
            ):
                failed += 1
                continue

            # -----------------------------------------------
            # OI levels for this stock
            # -----------------------------------------------

            temp_chain = normalize_chain(
                rows
            )

            if temp_chain.empty:
                failed += 1
                continue

            support, resistance, pcr = (
                oi_levels(
                    temp_chain,
                    spot_value,
                )
            )

            stock_candidates = []

            for raw in rows:

                strike = safe_float(
                    raw.get(
                        "strike_price"
                    )
                )

                if not np.isfinite(strike):
                    continue

                distance_pct = (
                    abs(
                        strike
                        - spot_value
                    )
                    / max(
                        spot_value,
                        1,
                    )
                    * 100
                )

                # Do not chase very far OTM/ITM contracts.
                if (
                    distance_pct
                    > SCANNER_MAX_DISTANCE_PCT
                ):
                    continue

                for side, action in (
                    ("CE", "CALL BUY"),
                    ("PE", "PUT BUY"),
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
                        greeks.get("pop")
                    )

                    # ---------------------------------------
                    # TRUE Upstox PoP filter
                    # ---------------------------------------

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
                        market.get(
                            "volume"
                        ),
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

                    # ---------------------------------------
                    # Delta filter
                    # ---------------------------------------

                    if (
                        not np.isfinite(delta)
                        or abs(delta)
                        < SCANNER_MIN_DELTA
                        or abs(delta)
                        > SCANNER_MAX_DELTA
                    ):
                        continue

                    # ---------------------------------------
                    # Liquidity filter
                    # ---------------------------------------

                    if (
                        not np.isfinite(volume)
                        or volume
                        < SCANNER_MIN_VOLUME
                    ):
                        continue

                    if (
                        not np.isfinite(oi)
                        or oi <= 0
                    ):
                        continue

                    # ---------------------------------------
                    # Spread filter
                    # ---------------------------------------

                    spread_pct = scanner_spread_pct(
                        bid,
                        ask,
                    )

                    if (
                        not np.isfinite(
                            spread_pct
                        )
                        or spread_pct
                        > SCANNER_MAX_SPREAD_PCT
                    ):
                        continue

                    # ---------------------------------------
                    # Entry
                    # ---------------------------------------

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

                    # ---------------------------------------
                    # Static quality
                    # ---------------------------------------

                    static_score = (
                        scanner_static_score(
                            pop=pop,
                            delta=delta,
                            spread_pct=spread_pct,
                            volume=volume,
                            distance_pct=distance_pct,
                            oi=oi,
                        )
                    )

                    if static_score < 55:
                        continue

                    candidate = {
                        "Stock":
                            item["symbol"],

                        "Trade":
                            action,

                        "Side":
                            side,

                        "Strike":
                            strike,

                        "Expiry":
                            item["expiry"],

                        "Spot":
                            spot_value,

                        "PoP":
                            pop,

                        "Entry":
                            entry,

                        "Bid":
                            bid,

                        "Ask":
                            ask,

                        "Spread":
                            spread_pct,

                        "Delta":
                            delta,

                        "IV":
                            iv,

                        "Volume":
                            volume,

                        "OI":
                            oi,

                        "Support":
                            support,

                        "Resistance":
                            resistance,

                        "PCR":
                            pcr,

                        "Distance":
                            distance_pct,

                        "StaticScore":
                            static_score,

                        "UnderlyingKey":
                            item[
                                "underlying_key"
                            ],

                        "QualityScore":
                            np.nan,

                        "Trend":
                            "Pending",

                        "RSI":
                            np.nan,
                    }

                    stock_candidates.append(
                        candidate
                    )

            if stock_candidates:

                # Keep only the strongest few contracts
                # for each stock before technical analysis.
                stock_candidates.sort(
                    key=lambda x: (
                        -x["StaticScore"],
                        -x["PoP"],
                        -x["Volume"],
                        x["Spread"],
                        x["Distance"],
                    )
                )

                candidates_by_stock[
                    item["underlying_key"]
                ] = stock_candidates[:4]

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

    # --------------------------------------------------------
    # STAGE 3 + STAGE 4
    # --------------------------------------------------------

    final_candidates = []

    technical_total = len(
        candidates_by_stock
    )

    technical_done = 0

    for underlying_key, stock_candidates in (
        candidates_by_stock.items()
    ):

        try:
            candles = get_daily_candles(
                underlying_key
            )

            if candles.empty:
                technical_done += 1
                continue

            spot = stock_candidates[0][
                "Spot"
            ]

            tech = technicals(
                candles,
                spot,
            )

            for candidate in stock_candidates:

                side = candidate["Side"]

                direction_score = (
                    scanner_direction_score(
                        side=side,
                        trend=tech["trend"],
                        rsi_value=tech["rsi"],
                    )
                )

                # Direction must agree.
                if direction_score is None:
                    continue

                oi_ok, oi_score = (
                    scanner_oi_room(
                        side=side,
                        spot=spot,
                        support=candidate[
                            "Support"
                        ],
                        resistance=candidate[
                            "Resistance"
                        ],
                    )
                )

                if not oi_ok:
                    continue

                quality_score = (
                    candidate[
                        "StaticScore"
                    ]
                    + direction_score
                    + oi_score
                )

                # Require a genuinely strong setup.
                if quality_score < 80:
                    continue

                candidate["QualityScore"] = (
                    quality_score
                )

                candidate["Trend"] = (
                    tech["trend"]
                )

                candidate["RSI"] = (
                    tech["rsi"]
                )

                candidate["EMA20"] = (
                    tech["ema20"]
                )

                candidate["EMA50"] = (
                    tech["ema50"]
                )

                candidate["Quality"] = (
                    scanner_quality_label(
                        quality_score
                    )
                )

                # Balanced risk settings
                candidate["SL"] = round(
                    candidate["Entry"]
                    * 0.70,
                    2,
                )

                candidate["Target1"] = round(
                    candidate["Entry"]
                    * 1.40,
                    2,
                )

                candidate["Target2"] = round(
                    candidate["Entry"]
                    * 1.80,
                    2,
                )

                candidate["Exit"] = (
                    "Exit at SL or Target 2; "
                    "trail after Target 1"
                )

                final_candidates.append(
                    candidate
                )

        except Exception:
            pass

        technical_done += 1

        # Continue showing scan progress.
        base_progress = 0.70
        technical_progress = (
            technical_done
            / max(
                technical_total,
                1,
            )
        )

        progress.progress(
            min(
                0.70
                + (
                    technical_progress
                    * 0.30
                ),
                1.0,
            ),
            text=(
                "Confirming technical direction: "
                f"{technical_done}/"
                f"{technical_total}"
            ),
        )

    progress.empty()

    # --------------------------------------------------------
    # FINAL RANKING
    # --------------------------------------------------------

    # One opportunity per stock.
    best_by_stock = {}

    for candidate in final_candidates:

        stock = candidate["Stock"]

        current = best_by_stock.get(
            stock
        )

        if current is None:
            best_by_stock[stock] = candidate
            continue

        candidate_key = (
            candidate["QualityScore"],
            candidate["PoP"],
            candidate["Volume"],
            -candidate["Spread"],
        )

        current_key = (
            current["QualityScore"],
            current["PoP"],
            current["Volume"],
            -current["Spread"],
        )

        if candidate_key > current_key:
            best_by_stock[stock] = candidate

    final_candidates = list(
        best_by_stock.values()
    )

    final_candidates.sort(
        key=lambda x: (
            -x["QualityScore"],
            -x["PoP"],
            -x["Volume"],
            x["Spread"],
        )
    )

    return (
        final_candidates[:5],
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
        "Scans the full NSE equity F&O market "
        "using PoP + option quality + trend + OI confirmation."
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
                    SCANNER_MIN_POP
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
                ZoneInfo("Asia/Kolkata")
            ).strftime(
                "%H:%M:%S"
            )

        except UpstoxError as exc:

            st.session_state[
                "fno_pop_results"
            ] = []

            st.error(str(exc))

        except Exception as exc:

            st.session_state[
                "fno_pop_results"
            ] = []

            st.error(
                f"F&O scan failed: {exc}"
            )

    pop_results = st.session_state.get(
        "fno_pop_results",
        []
    )

    scan_info = st.session_state.get(
        "fno_pop_scan_info"
    )

    scan_time = st.session_state.get(
        "fno_pop_scan_time"
    )

    if pop_results:

        st.success(
            f"Top {len(pop_results)} "
            "quality-filtered trades with "
            f"PoP > {SCANNER_MIN_POP:.0f}%"
        )

        if scan_info:

            total, scanned, failed = (
                scan_info
            )

            st.caption(
                f"Scanned {scanned}/{total} "
                f"F&O stocks • {failed} unavailable"
            )

        if scan_time:

            st.caption(
                f"Last scan: {scan_time} IST"
            )

        scanner_display = pd.DataFrame(
            [
                {
                    "Stock":
                        row["Stock"],

                    "Trade":
                        row["Trade"],

                    "Strike":
                        int(row["Strike"]),

                    "PoP":
                        f"{row['PoP']:.1f}%",

                    "Score":
                        f"{row['QualityScore']:.0f}",

                    "Quality":
                        row["Quality"],

                    "Trend":
                        row["Trend"],

                    "Delta":
                        f"{row['Delta']:.2f}",

                    "Spread":
                        f"{row['Spread']:.1f}%",

                    "Entry":
                        fmt_price(
                            row["Entry"]
                        ),

                    "SL":
                        fmt_price(
                            row["SL"]
                        ),

                    "Target1":
                        fmt_price(
                            row["Target1"]
                        ),

                    "Target2":
                        fmt_price(
                            row["Target2"]
                        ),

                    "Exit":
                        row["Exit"],
                }
                for row in pop_results
            ]
        )

        st.dataframe(
            scanner_display,
            use_container_width=True,
            hide_index=True,
            height=min(
                500,
                58
                + len(
                    scanner_display
                )
                * 52,
            ),
        )

        st.caption(
            "PoP = Upstox Probability of Profit. "
            "Score = scanner setup-quality score, "
            "not probability of winning."
        )

    elif (
        "fno_pop_results"
        in st.session_state
    ):

        st.info(
            "No F&O stock currently satisfies "
            "all scanner quality conditions."
        )

    st.divider()

    st.markdown(
        "### 🔎 Analyze Instrument"
    )

    symbol_label = (
        "Stock / Index"
    )

    symbol_default = (
        st.session_state.get(
            "symbol",
            "KOTAKBANK",
        )
    )

    symbol_placeholder = (
        "e.g. KOTAKBANK, HDFCBANK, NIFTY"
    )

    symbol_input = st.text_input(
        symbol_label,
        value=symbol_default,
        placeholder=symbol_placeholder,
        label_visibility="collapsed",
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
            "Auto refresh every 30 seconds",
            value=True,
        )

        if auto_refresh:
            st_autorefresh(
                interval=30_000,
                key="upstox_live_refresh",
            )

    st.divider()

    st.caption(
        "LIVE DATA • Powered by Upstox"
    )

    st.caption(
        "No simulated market values are used."
    )


# ============================================================
# SIDEBAR ACTIONS
# ============================================================

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
        symbol_input
        or "KOTAKBANK",
    )
)


# ============================================================
# LIVE DATA
# ============================================================

try:

    with st.spinner(
        f"Fetching live Upstox data for {symbol}..."
    ):

        underlying = (
            search_underlying(
                symbol
            )
        )

        underlying_key = (
            underlying[
                "instrument_key"
            ]
        )

        contracts = (
            get_contracts(
                underlying_key
            )
        )

        expiries = (
            available_expiries(
                contracts
            )
        )

        if not expiries:

            raise UpstoxError(
                "Upstox did not return an "
                "upcoming F&O expiry for this instrument."
            )

        selected_expiry = expiries[0]

        raw_chain = (
            get_option_chain(
                underlying_key,
                selected_expiry,
            )
        )

        chain = normalize_chain(
            raw_chain
        )

        quote_data = get_quote(
            underlying_key
        )

        spot = safe_float(
            quote_data.get(
                "last_price"
            )
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

        candles = (
            get_daily_candles(
                underlying_key
            )
        )

        tech = technicals(
            candles,
            spot,
        )

except UpstoxError as exc:

    st.error(str(exc))
    st.stop()

except Exception as exc:

    st.error(
        "Unexpected error while loading "
        f"live data: {exc}"
    )

    st.stop()


support, resistance, pcr = (
    oi_levels(
        chain,
        spot,
    )
)


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
    max(
        0,
        atm_index - 3,
    ):
    min(
        len(chain),
        atm_index + 4,
    )
]


ce_scores = []
pe_scores = []


for _, row in (
    candidate_rows.iterrows()
):

    ce_scores.append(
        (
            score_option(
                row,
                "CE",
                spot,
                pcr,
                tech,
            )["score"],
            float(
                row["Strike"]
            ),
        )
    )

    pe_scores.append(
        (
            score_option(
                row,
                "PE",
                spot,
                pcr,
                tech,
            )["score"],
            float(
                row["Strike"]
            ),
        )
    )


best_ce_strike = max(
    ce_scores,
    default=(
        0,
        atm_strike,
    ),
)[1]

best_pe_strike = max(
    pe_scores,
    default=(
        0,
        atm_strike,
    ),
)[1]


ce_plan = build_plan(
    nearest_row(
        chain,
        best_ce_strike,
    ),
    "CE",
    spot,
    support,
    resistance,
    pcr,
    tech,
    risk_profile,
)


pe_plan = build_plan(
    nearest_row(
        chain,
        best_pe_strike,
    ),
    "PE",
    spot,
    support,
    resistance,
    pcr,
    tech,
    risk_profile,
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


if (
    ce_plan
    and ce_score >= 60
    and ce_score
    >= pe_score + 5
    and tech["trend"]
    == "Bullish"
):

    decision = "CALL BUY"
    decision_class = "trade-call"
    best_plan = ce_plan

elif (
    pe_plan
    and pe_score >= 60
    and pe_score
    >= ce_score + 5
    and tech["trend"]
    == "Bearish"
):

    decision = "PUT BUY"
    decision_class = "trade-put"
    best_plan = pe_plan

else:

    decision = "NO TRADE"
    decision_class = "trade-neutral"

    best_plan = (
        ce_plan
        if ce_score >= pe_score
        else pe_plan
    )


updated = quote_data.get(
    "timestamp",
    datetime.now()
    .astimezone()
    .isoformat(),
)


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
        Options Analysis • Powered by Upstox • Live market data
    </div>
</div>
""",
    unsafe_allow_html=True,
)


h1, h2, h3 = st.columns(
    [
        2.2,
        1.2,
        1.0,
    ]
)


with h1:

    st.markdown(
        f"## {symbol} — F&O Options Analysis"
    )


with h2:

    st.markdown(
        "**Last Traded**"
    )

    st.markdown(
        f"""
        <span style="
            font-size:25px;
            font-weight:800
        ">
            {fmt_price(spot)}
        </span>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        f"{net_change:+.2f} "
        f"({change_pct:+.2f}%)"
    )


with h3:

    st.markdown(
        "**Data Status**"
    )

    market_now = datetime.now(
        ZoneInfo(
            "Asia/Kolkata"
        )
    )

    market_open = (
        market_now.weekday() < 5
        and (
            market_now.hour,
            market_now.minute,
        )
        >= (
            9,
            15,
        )
        and (
            market_now.hour,
            market_now.minute,
        )
        < (
            15,
            30,
        )
    )

    if market_open:

        st.markdown(
            """
            <div style="
                background:#16a34a;
                color:#ffffff;
                padding:10px 16px;
                border-radius:8px;
                font-weight:700;
                font-size:15px;
                text-align:center;
                width:100%;
                box-sizing:border-box;
                margin:6px 0 10px 0;
            ">
                ● LIVE DATA
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        st.markdown(
            """
            <div style="
                background:#dc2626;
                color:#ffffff;
                padding:10px 16px;
                border-radius:8px;
                font-weight:700;
                font-size:15px;
                text-align:center;
                width:100%;
                box-sizing:border-box;
                margin:6px 0 10px 0;
            ">
                ● MARKET CLOSED
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.caption(
        f"Expiry: {selected_expiry}"
    )


# ============================================================
# MARKET SNAPSHOT
# ============================================================

st.markdown(
    '<div class="card">',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-title">'
    '📊 Market Snapshot'
    '</div>',
    unsafe_allow_html=True,
)


m1, m2, m3, m4, m5, m6 = (
    st.columns(6)
)


m1.metric(
    "Live Price",
    fmt_price(spot),
    f"{net_change:+.2f} "
    f"({change_pct:+.2f}%)",
)

m2.metric(
    "Bias",
    tech["trend"],
)

m3.metric(
    "PCR",
    (
        f"{pcr:.2f}"
        if not np.isnan(pcr)
        else "—"
    ),
)

m4.metric(
    "Support",
    fmt_price(support),
)

m5.metric(
    "Resistance",
    fmt_price(resistance),
)

m6.metric(
    "RSI",
    f"{tech['rsi']:.1f}",
)


st.markdown(
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# TRADE DECISION
# ============================================================

st.markdown(
    '<div class="card">',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-title">'
    '🎯 Trade Decision'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="{decision_class}">'
    f'Decision: {decision}'
    '</div>',
    unsafe_allow_html=True,
)


d1, d2, d3, d4 = (
    st.columns(4)
)

d1.metric(
    "Bull Score",
    f"{ce_score:.0f}/100",
)

d2.metric(
    "Bear Score",
    f"{pe_score:.0f}/100",
)

d3.metric(
    "Trend",
    tech["trend"],
)

d4.metric(
    "ATR",
    fmt_price(tech["atr"]),
)


st.markdown(
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# TRADE PLAN
# ============================================================

st.markdown(
    '<div class="card">',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-title">'
    '🎯 Trade Plan'
    '</div>',
    unsafe_allow_html=True,
)


plan_rows = []


for label, plan in [
    ("CALL", ce_plan),
    ("PUT", pe_plan),
]:

    if plan:

        plan_rows.append(
            {
                "Side":
                    label,

                "Strike":
                    int(
                        plan["strike"]
                    ),

                "Entry (₹)":
                    round(
                        plan["entry"],
                        2,
                    ),

                "SL (₹)":
                    round(
                        plan["sl"],
                        2,
                    ),

                "Target 1 (₹)":
                    round(
                        plan["target1"],
                        2,
                    ),

                "Target 2 (₹)":
                    round(
                        plan["target2"],
                        2,
                    ),

                "PoP":
                    (
                        f"{plan['pop']:.1f}%"
                        if not np.isnan(
                            plan["pop"]
                        )
                        else "—"
                    ),

                "Delta":
                    (
                        round(
                            plan["delta"],
                            3,
                        )
                        if not np.isnan(
                            plan["delta"]
                        )
                        else "—"
                    ),

                "IV":
                    (
                        f"{plan['iv']:.1f}%"
                        if not np.isnan(
                            plan["iv"]
                        )
                        else "—"
                    ),

                "R:R T1":
                    f"1:{plan['rr1']:.2f}",
            }
        )


if plan_rows:

    st.dataframe(
        pd.DataFrame(
            plan_rows
        ),
        use_container_width=True,
        hide_index=True,
    )


if best_plan:

    st.markdown(
        "### Entry / Exit Rules"
    )

    e1, e2 = st.columns(2)

    with e1:

        st.markdown(
            "**Entry Trigger**"
        )

        st.write(
            best_plan["trigger"]
        )

        st.markdown(
            "**Entry**"
        )

        st.write(
            fmt_price(
                best_plan["entry"]
            )
        )

        st.markdown(
            "**Stop Loss**"
        )

        st.write(
            fmt_price(
                best_plan["sl"]
            )
        )

        st.markdown(
            "**Target 1 / Target 2**"
        )

        st.write(
            f"{fmt_price(best_plan['target1'])} "
            f"/ {fmt_price(best_plan['target2'])}"
        )

    with e2:

        st.markdown(
            "**Exit Rule**"
        )

        st.write(
            best_plan["exit"]
        )

        st.markdown(
            "**PoP**"
        )

        st.write(
            (
                f"{best_plan['pop']:.1f}%"
                if not np.isnan(
                    best_plan["pop"]
                )
                else "Not returned by Upstox"
            )
        )

        st.markdown(
            "**Risk / Reward**"
        )

        st.write(
            f"Target 1: 1:{best_plan['rr1']:.2f} | "
            f"Target 2: 1:{best_plan['rr2']:.2f}"
        )


st.caption(
    "PoP is the Probability of Profit returned by "
    "Upstox for the option contract; it is not a "
    "guarantee of profit."
)


st.markdown(
    '</div>',
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


with tab1:

    if decision == "NO TRADE":

        st.info(
            "NO TRADE: the live conditions do not "
            "currently meet the directional quality gate. "
            "Wait for the entry trigger instead of "
            "forcing an option position."
        )

    elif best_plan:

        st.success(
            f"{decision} | "
            f"Strike {best_plan['strike']:.0f} | "
            f"Entry {fmt_price(best_plan['entry'])} | "
            f"SL {fmt_price(best_plan['sl'])} | "
            f"T1 {fmt_price(best_plan['target1'])} | "
            f"T2 {fmt_price(best_plan['target2'])}"
        )

    st.markdown(
        "### Why the Engine Says This"
    )

    reasons = [
        f"Live spot is {fmt_price(spot)}; "
        f"nearest ATM strike is {atm_strike:.0f}.",

        f"Trend from live historical candles: "
        f"{tech['trend']}.",

        f"RSI is {tech['rsi']:.1f}.",

        f"PCR is {pcr:.2f}.",

        f"OI support is {fmt_price(support)} "
        f"and resistance is {fmt_price(resistance)}.",
    ]

    if (
        best_plan
        and not np.isnan(
            best_plan["pop"]
        )
    ):

        reasons.append(
            "Selected option PoP from Upstox is "
            f"{best_plan['pop']:.1f}%."
        )

    for reason in reasons:

        st.write(
            "✓",
            reason,
        )


with tab2:

    st.markdown(
        f"### Live Option Chain — "
        f"{selected_expiry}"
    )

    view = chain.copy()

    display = pd.DataFrame(
        {
            "Strike":
                view["Strike"]
                .round(0)
                .astype(int),

            "CE LTP":
                view["CE LTP"]
                .round(2),

            "CE OI":
                view["CE OI"]
                .round(0)
                .astype("int64"),

            "CE Chg OI":
                view["CE Chg OI"]
                .round(0)
                .astype("int64"),

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
                .astype("int64"),

            "PE Chg OI":
                view["PE Chg OI"]
                .round(0)
                .astype("int64"),

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
        display["Strike"] - spot
    ).abs()

    display = (
        display
        .sort_values(
            "_distance"
        )
        .drop(
            columns="_distance"
        )
        .head(11)
    )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )


with tab3:

    a1, a2, a3 = (
        st.columns(3)
    )

    a1.metric(
        "EMA 20",
        fmt_price(
            tech["ema20"]
        ),
    )

    a2.metric(
        "EMA 50",
        fmt_price(
            tech["ema50"]
        ),
    )

    a3.metric(
        "ATR 14",
        fmt_price(
            tech["atr"]
        ),
    )

    left, right = (
        st.columns(2)
    )

    with left:

        st.markdown(
            "### 🟢 Support / Put OI"
        )

        st.write(
            "Major support from Put OI: "
            f"**{fmt_price(support)}**"
        )

        support_row = (
            nearest_row(
                chain,
                support,
            )
        )

        if support_row is not None:

            st.write(
                "Put OI: "
                f"**{fmt_num(support_row['PE OI'])}**"
            )

            st.write(
                "Put Chg OI: "
                f"**{fmt_num(support_row['PE Chg OI'])}**"
            )

    with right:

        st.markdown(
            "### 🔴 Resistance / Call OI"
        )

        st.write(
            "Major resistance from Call OI: "
            f"**{fmt_price(resistance)}**"
        )

        resistance_row = (
            nearest_row(
                chain,
                resistance,
            )
        )

        if resistance_row is not None:

            st.write(
                "Call OI: "
                f"**{fmt_num(resistance_row['CE OI'])}**"
            )

            st.write(
                "Call Chg OI: "
                f"**{fmt_num(resistance_row['CE Chg OI'])}**"
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


with tab4:

    st.markdown(
        """
### Live-data decision framework

**1. Market direction**
- Live spot
- Daily EMA20 / EMA50
- RSI
- ATR

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
- The app can return **NO TRADE** when live evidence is mixed.
- It does not manufacture a trade simply because an instrument was entered.

**6. F&O scanner**
- PoP > 75% is only the first filter.
- Liquidity and bid/ask spread are checked.
- Delta is checked.
- Distance from spot is checked.
- Underlying trend must agree with the option direction.
- OI support/resistance must not immediately invalidate the setup.
- The scanner ranks candidates using a separate quality score.

**Important**
- Scanner Score is a setup-quality ranking.
- Scanner Score is NOT probability of profit.
- Upstox PoP is NOT the historical win rate of this scanner.
"""
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    f"Live Upstox snapshot • {symbol} • "
    f"Expiry {selected_expiry} • "
    f"Updated {updated}. "
    "For educational/decision-support use; "
    "review live market conditions before trading."
)
