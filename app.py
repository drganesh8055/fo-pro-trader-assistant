import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="F&O Pro Trader Assistant",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONSTANTS
# ============================================================

IST = ZoneInfo("Asia/Kolkata")
UPSTOX_BASE = "https://api.upstox.com"

RISK_PROFILES = {
    "Conservative": {
        "sl": 0.18,
        "t1": 0.25,
        "t2": 0.40,
    },
    "Balanced": {
        "sl": 0.22,
        "t1": 0.35,
        "t2": 0.55,
    },
    "Aggressive": {
        "sl": 0.28,
        "t1": 0.45,
        "t2": 0.70,
    },
}


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
<style>

.stApp {
    background: #f5f7fb;
}

.block-container {
    max-width: 1500px;
    padding-top: 1rem;
    padding-bottom: 2rem;
}

html, body, [class*="css"] {
    font-family: Inter, Segoe UI, Arial, sans-serif;
}

.top-header {
    background: linear-gradient(135deg, #0b5ed7, #173b8f);
    color: white;
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 18px;
    box-shadow: 0 8px 25px rgba(23, 59, 143, 0.18);
}

.top-header-title {
    font-size: 28px;
    font-weight: 800;
}

.top-header-subtitle {
    font-size: 14px;
    opacity: .9;
    margin-top: 5px;
}

.stock-hero {
    background: white;
    border-radius: 16px;
    padding: 22px 24px;
    margin-bottom: 16px;
    border: 1px solid #e7ebf2;
    box-shadow: 0 4px 15px rgba(0,0,0,.04);
}

.stock-name {
    font-size: 30px;
    font-weight: 800;
    color: #16213e;
}

.stock-subtitle {
    color: #687386;
    font-size: 14px;
}

.metric-card {
    background: white;
    border: 1px solid #e7ebf2;
    border-radius: 14px;
    padding: 16px;
    min-height: 105px;
    box-shadow: 0 3px 12px rgba(0,0,0,.035);
}

.metric-label {
    color: #718096;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
}

.metric-value {
    color: #16213e;
    font-size: 22px;
    font-weight: 800;
    margin-top: 7px;
}

.metric-small {
    color: #718096;
    font-size: 12px;
    margin-top: 4px;
}

.section-title {
    color: #16213e;
    font-size: 20px;
    font-weight: 800;
    margin: 18px 0 10px 0;
}

.decision-card {
    background: white;
    border-radius: 16px;
    padding: 22px;
    border: 1px solid #e7ebf2;
    box-shadow: 0 4px 15px rgba(0,0,0,.04);
}

.decision-title {
    font-size: 25px;
    font-weight: 900;
    color: #16213e;
}

.score-box {
    background: #f7f9fc;
    border-radius: 12px;
    padding: 13px;
    margin-top: 10px;
}

.trade-plan {
    background: white;
    border-radius: 16px;
    padding: 22px;
    border: 1px solid #e7ebf2;
    box-shadow: 0 4px 15px rgba(0,0,0,.04);
}

.reason-box {
    background: white;
    border: 1px solid #e7ebf2;
    border-radius: 14px;
    padding: 15px 18px;
    margin-bottom: 9px;
}

.status-open {
    display: inline-block;
    background: #e8f7ee;
    color: #137333;
    border-radius: 20px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 800;
}

.status-closed {
    display: inline-block;
    background: #eef1f5;
    color: #596273;
    border-radius: 20px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 800;
}

.status-stale {
    display: inline-block;
    background: #fff4df;
    color: #9a6700;
    border-radius: 20px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 800;
}

.info-bar {
    background: #edf5ff;
    color: #234b80;
    border: 1px solid #d4e7ff;
    border-radius: 12px;
    padding: 12px 15px;
    font-size: 13px;
    margin: 10px 0 16px 0;
}

.footer {
    text-align: center;
    color: #8a94a6;
    font-size: 11px;
    margin-top: 25px;
    padding: 15px;
}

.sidebar-note {
    color: #6b7280;
    font-size: 12px;
    line-height: 1.5;
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
<div class="top-header">
    <div class="top-header-title">
        📈 F&O Pro Trader Assistant
    </div>

    <div class="top-header-subtitle">
        Options Analysis • Powered by Upstox
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

if "active_symbol" not in st.session_state:
    st.session_state.active_symbol = ""

if "active_risk" not in st.session_state:
    st.session_state.active_risk = "Balanced"

if "active_result" not in st.session_state:
    st.session_state.active_result = None

if "active_chain" not in st.session_state:
    st.session_state.active_chain = None

if "last_error" not in st.session_state:
    st.session_state.last_error = ""

if "last_successful_refresh" not in st.session_state:
    st.session_state.last_successful_refresh = None


# ============================================================
# UPSTOX TOKEN
# ============================================================

def get_token():

    try:

        token = st.secrets["UPSTOX_ACCESS_TOKEN"]

        if token:
            return str(token).strip()

        return None

    except Exception:

        return None


TOKEN = get_token()


# ============================================================
# API HELPERS
# ============================================================

def upstox_headers():

    return {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "FO-Pro-Trader-Assistant",
    }


def api_get(url, params=None, timeout=20):

    if not TOKEN:

        raise RuntimeError(
            "UPSTOX_ACCESS_TOKEN is missing from Streamlit Secrets."
        )

    try:

        response = requests.get(
            url,
            headers=upstox_headers(),
            params=params,
            timeout=timeout,
        )

    except requests.exceptions.Timeout:

        raise RuntimeError(
            "Upstox request timed out. Please try again."
        )

    except requests.exceptions.RequestException as e:

        raise RuntimeError(
            f"Could not connect to Upstox: {e}"
        )

    if response.status_code != 200:

        try:
            detail = response.json()
        except Exception:
            detail = response.text

        raise RuntimeError(
            f"Upstox API error {response.status_code}: {detail}"
        )

    try:

        return response.json()

    except Exception:

        raise RuntimeError(
            "Upstox returned an invalid JSON response."
        )


# ============================================================
# GENERAL HELPERS
# ============================================================

def sf(value):

    try:

        if value is None or value == "":
            return 0.0

        return float(value)

    except Exception:

        return 0.0


def first_valid(*values):

    for value in values:

        if value is not None and value != "":
            return value

    return None


def format_iso_ist(value):

    if not value:
        return "N/A"

    try:

        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            IST
        ).strftime(
            "%d-%b-%Y %I:%M:%S %p IST"
        )

    except Exception:

        return str(value)


def format_ms_ist(value):

    if value in [None, "", 0, "0"]:
        return "N/A"

    try:

        if isinstance(value, str):

            text = value.strip()

            if "T" in text or "-" in text:

                return format_iso_ist(
                    text
                )

        number = float(value)

        dt = datetime.fromtimestamp(
            number / 1000,
            tz=timezone.utc,
        )

        return dt.astimezone(
            IST
        ).strftime(
            "%d-%b-%Y %I:%M:%S %p IST"
        )

    except Exception:

        return "N/A"


def now_ist():

    return datetime.now(IST)


# ============================================================
# IMPORTANT CHANGE-OI FIX
# ============================================================

def ensure_change_oi_columns(df):

    """
    Ensures Change OI columns always exist.

    This is the main fix for:

    KeyError: ce_chg_oi
    KeyError: pe_chg_oi
    """

    df = df.copy()

    required_columns = [
        "ce_oi",
        "ce_prev_oi",
        "pe_oi",
        "pe_prev_oi",
    ]

    for col in required_columns:

        if col not in df.columns:

            df[col] = 0.0

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        ).fillna(0.0)

    df["ce_chg_oi"] = (
        df["ce_oi"]
        - df["ce_prev_oi"]
    )

    df["pe_chg_oi"] = (
        df["pe_oi"]
        - df["pe_prev_oi"]
    )

    return df


# ============================================================
# FIND UNDERLYING
# ============================================================

def find_underlying(symbol):

    symbol = str(
        symbol
    ).strip().upper()

    if not symbol:

        raise RuntimeError(
            "Please enter a stock or index symbol."
        )

    searches = [

        {
            "query": symbol,
            "exchanges": "NSE",
            "segments": "EQ",
            "records": 30,
        },

        {
            "query": symbol,
            "exchanges": "NSE",
            "segments": "INDEX",
            "records": 30,
        },

    ]

    candidates = []

    for params in searches:

        try:

            data = api_get(
                f"{UPSTOX_BASE}/v2/instruments/search",
                params=params,
            )

            rows = data.get(
                "data",
                []
            )

            if isinstance(rows, list):

                candidates.extend(rows)

        except Exception:

            continue

    if not candidates:

        raise RuntimeError(
            f"Could not find {symbol} in Upstox instruments."
        )

    def exact_match(item):

        values = [
            item.get("trading_symbol"),
            item.get("short_name"),
            item.get("name"),
        ]

        return any(
            str(v or "").upper() == symbol
            for v in values
        )

    exact = [
        item
        for item in candidates
        if exact_match(item)
    ]

    if exact:

        return exact[0]

    preferred = [
        item
        for item in candidates
        if item.get("segment")
        in [
            "NSE_EQ",
            "NSE_INDEX",
        ]
    ]

    if preferred:

        return preferred[0]

    return candidates[0]


# ============================================================
# MARKET QUOTE
# ============================================================

def get_full_quote_v3(
    instrument_key
):

    data = api_get(
        f"{UPSTOX_BASE}/v3/market-quote/quotes",
        params={
            "instrument_key": instrument_key
        },
    )

    quote_data = data.get(
        "data",
        {}
    )

    if (
        not isinstance(
            quote_data,
            dict
        )
        or not quote_data
    ):

        raise RuntimeError(
            "Upstox returned no market quote."
        )

    if instrument_key in quote_data:

        return quote_data[
            instrument_key
        ]

    for value in quote_data.values():

        if isinstance(
            value,
            dict
        ):

            return value

    raise RuntimeError(
        "Could not read market quote from Upstox."
    )


def extract_market_context(
    quote
):

    last_price = sf(
        first_valid(
            quote.get("last_price"),
            quote.get("ltp"),
        )
    )

    prev_close = sf(
        first_valid(
            quote.get("prev_close_price"),
            quote.get("cp"),
        )
    )

    average_price = sf(
        first_valid(
            quote.get("average_price"),
            quote.get("avg_price"),
        )
    )

    net_change = sf(
        first_valid(
            quote.get("net_change"),
            quote.get("change"),
        )
    )

    volume = sf(
        first_valid(
            quote.get("volume"),
            quote.get("vol"),
        )
    )

    ohlc = quote.get(
        "ohlc",
        {}
    )

    if isinstance(
        ohlc,
        list
    ):

        ohlc = next(
            (
                item
                for item in ohlc
                if isinstance(
                    item,
                    dict
                )
            ),
            {},
        )

    if not isinstance(
        ohlc,
        dict
    ):

        ohlc = {}

    open_price = sf(
        first_valid(
            ohlc.get("open"),
            quote.get("open"),
        )
    )

    high_price = sf(
        first_valid(
            ohlc.get("high"),
            quote.get("high"),
        )
    )

    low_price = sf(
        first_valid(
            ohlc.get("low"),
            quote.get("low"),
        )
    )

    close_price = sf(
        first_valid(
            ohlc.get("close"),
            quote.get("close"),
            prev_close,
        )
    )

    if (
        net_change == 0
        and prev_close > 0
    ):

        net_change = (
            last_price
            - prev_close
        )

    pct_change = 0.0

    if prev_close > 0:

        pct_change = (
            net_change
            / prev_close
        ) * 100

    price_vs_open = 0.0

    if open_price > 0:

        price_vs_open = (
            (
                last_price
                - open_price
            )
            / open_price
        ) * 100

    price_vs_average = 0.0

    if average_price > 0:

        price_vs_average = (
            (
                last_price
                - average_price
            )
            / average_price
        ) * 100

    range_position = 50.0

    if high_price > low_price:

        range_position = (
            (
                last_price
                - low_price
            )
            / (
                high_price
                - low_price
            )
        ) * 100

    return {

        "last_price": last_price,

        "prev_close": prev_close,

        "average_price": average_price,

        "net_change": net_change,

        "pct_change": pct_change,

        "volume": volume,

        "open": open_price,

        "high": high_price,

        "low": low_price,

        "close": close_price,

        "price_vs_open": price_vs_open,

        "price_vs_average": price_vs_average,

        "range_position": range_position,

        "last_trade_time": first_valid(
            quote.get(
                "last_trade_time"
            ),
            quote.get(
                "last_trade_time_ms"
            ),
            quote.get(
                "timestamp"
            ),
        ),

        "snapshot_time": now_ist(),
    }


# ============================================================
# OPTION CONTRACTS
# ============================================================

def get_option_contracts(
    underlying_key
):

    data = api_get(
        f"{UPSTOX_BASE}/v2/option/contract",
        params={
            "instrument_key": underlying_key
        },
    )

    contracts = data.get(
        "data",
        []
    )

    if not isinstance(
        contracts,
        list
    ):

        return []

    return contracts


def get_nearest_expiry(
    contracts
):

    today = now_ist().date()

    dates = []

    for item in contracts:

        expiry = item.get(
            "expiry"
        )

        if not expiry:
            continue

        try:

            date_value = datetime.strptime(
                str(expiry),
                "%Y-%m-%d",
            ).date()

            if date_value >= today:

                dates.append(
                    date_value
                )

        except Exception:

            continue

    if not dates:

        return None

    return min(dates)


def get_option_chain(
    underlying_key,
    expiry_date,
):

    data = api_get(
        f"{UPSTOX_BASE}/v2/option/chain",
        params={
            "instrument_key": underlying_key,
            "expiry_date": str(
                expiry_date
            ),
        },
    )

    chain = data.get(
        "data",
        []
    )

    if not isinstance(
        chain,
        list
    ):

        return []

    return chain


# ============================================================
# NORMALIZE OPTION CHAIN
# ============================================================

def normalize_chain(
    chain
):

    rows = []

    if not isinstance(
        chain,
        list
    ):

        return pd.DataFrame()

    for item in chain:

        if not isinstance(
            item,
            dict
        ):

            continue

        strike = sf(
            item.get(
                "strike_price"
            )
        )

        spot = sf(
            item.get(
                "underlying_spot_price"
            )
        )

        call_options = item.get(
            "call_options",
            {}
        )

        put_options = item.get(
            "put_options",
            {}
        )

        if not isinstance(
            call_options,
            dict
        ):

            call_options = {}

        if not isinstance(
            put_options,
            dict
        ):

            put_options = {}

        call_market = call_options.get(
            "market_data",
            {}
        )

        put_market = put_options.get(
            "market_data",
            {}
        )

        call_greeks = call_options.get(
            "option_greeks",
            {}
        )

        put_greeks = put_options.get(
            "option_greeks",
            {}
        )

        if not isinstance(
            call_market,
            dict
        ):

            call_market = {}

        if not isinstance(
            put_market,
            dict
        ):

            put_market = {}

        if not isinstance(
            call_greeks,
            dict
        ):

            call_greeks = {}

        if not isinstance(
            put_greeks,
            dict
        ):

            put_greeks = {}

        ce_prev_oi = first_valid(

            call_market.get(
                "prev_oi"
            ),

            call_market.get(
                "previous_oi"
            ),

            call_market.get(
                "prev_open_interest"
            ),
        )

        pe_prev_oi = first_valid(

            put_market.get(
                "prev_oi"
            ),

            put_market.get(
                "previous_oi"
            ),

            put_market.get(
                "prev_open_interest"
            ),
        )

        ce_pop = first_valid(

            call_greeks.get(
                "pop"
            ),

            call_greeks.get(
                "probability_of_profit"
            ),
        )

        pe_pop = first_valid(

            put_greeks.get(
                "pop"
            ),

            put_greeks.get(
                "probability_of_profit"
            ),
        )

        row = {

            "strike": strike,

            "spot": spot,

            # ---------------- CALL ----------------

            "ce_ltp": sf(
                first_valid(
                    call_market.get(
                        "ltp"
                    ),
                    call_market.get(
                        "last_price"
                    ),
                )
            ),

            "ce_oi": sf(
                call_market.get(
                    "oi"
                )
            ),

            "ce_prev_oi": sf(
                ce_prev_oi
            ),

            "ce_volume": sf(
                call_market.get(
                    "volume"
                )
            ),

            "ce_iv": sf(
                first_valid(
                    call_greeks.get(
                        "iv"
                    ),
                    call_greeks.get(
                        "implied_volatility"
                    ),
                )
            ),

            "ce_delta": sf(
                call_greeks.get(
                    "delta"
                )
            ),

            "ce_pop": sf(
                ce_pop
            ),

            "ce_bid": sf(
                first_valid(
                    call_market.get(
                        "bid_price"
                    ),
                    call_market.get(
                        "bid"
                    ),
                )
            ),

            "ce_ask": sf(
                first_valid(
                    call_market.get(
                        "ask_price"
                    ),
                    call_market.get(
                        "ask"
                    ),
                )
            ),

            "ce_instrument_key":
                first_valid(
                    call_options.get(
                        "instrument_key"
                    ),
                    call_options.get(
                        "instrument_token"
                    ),
                ),

            # ---------------- PUT ----------------

            "pe_ltp": sf(
                first_valid(
                    put_market.get(
                        "ltp"
                    ),
                    put_market.get(
                        "last_price"
                    ),
                )
            ),

            "pe_oi": sf(
                put_market.get(
                    "oi"
                )
            ),

            "pe_prev_oi": sf(
                pe_prev_oi
            ),

            "pe_volume": sf(
                put_market.get(
                    "volume"
                )
            ),

            "pe_iv": sf(
                first_valid(
                    put_greeks.get(
                        "iv"
                    ),
                    put_greeks.get(
                        "implied_volatility"
                    ),
                )
            ),

            "pe_delta": sf(
                put_greeks.get(
                    "delta"
                )
            ),

            "pe_pop": sf(
                pe_pop
            ),

            "pe_bid": sf(
                first_valid(
                    put_market.get(
                        "bid_price"
                    ),
                    put_market.get(
                        "bid"
                    ),
                )
            ),

            "pe_ask": sf(
                first_valid(
                    put_market.get(
                        "ask_price"
                    ),
                    put_market.get(
                        "ask"
                    ),
                )
            ),

            "pe_instrument_key":
                first_valid(
                    put_options.get(
                        "instrument_key"
                    ),
                    put_options.get(
                        "instrument_token"
                    ),
                ),
        }

        rows.append(row)

    df = pd.DataFrame(
        rows
    )

    # ========================================================
    # IMPORTANT FIX
    # ========================================================

    df = ensure_change_oi_columns(
        df
    )

    return df


# ============================================================
# MARKET STATUS
# ============================================================

def get_market_status(
    last_trade_time=None
):

    now = now_ist()

    if now.weekday() >= 5:

        return "MARKET CLOSED"

    market_open = now.replace(
        hour=9,
        minute=15,
        second=0,
        microsecond=0,
    )

    market_close = now.replace(
        hour=15,
        minute=30,
        second=0,
        microsecond=0,
    )

    if (
        now < market_open
        or now > market_close
    ):

        return "MARKET CLOSED"

    if last_trade_time:

        try:

            trade_dt = None

            if isinstance(
                last_trade_time,
                str
            ):

                text = (
                    last_trade_time
                    .strip()
                )

                if "T" in text:

                    trade_dt = (
                        datetime.fromisoformat(
                            text.replace(
                                "Z",
                                "+00:00",
                            )
                        )
                    )

                    if (
                        trade_dt.tzinfo
                        is None
                    ):

                        trade_dt = (
                            trade_dt.replace(
                                tzinfo=timezone.utc
                            )
                        )

                    trade_dt = (
                        trade_dt.astimezone(
                            IST
                        )
                    )

            else:

                number = float(
                    last_trade_time
                )

                trade_dt = (
                    datetime.fromtimestamp(
                        number / 1000,
                        tz=timezone.utc,
                    ).astimezone(
                        IST
                    )
                )

            if trade_dt is not None:

                age = (
                    now - trade_dt
                ).total_seconds()

                if age > 600:

                    return "DATA STALE"

        except Exception:

            pass

    return "MARKET OPEN"


# ============================================================
# ANALYSIS ENGINE
# ============================================================

def analyze_chain(
    df,
    market
):

    if df.empty:

        raise RuntimeError(
            "Option chain returned no usable rows."
        )

    # IMPORTANT FIX
    df = ensure_change_oi_columns(
        df
    )

    spot = sf(
        market.get(
            "last_price"
        )
    )

    if spot <= 0:

        raise RuntimeError(
            "Invalid underlying price received from Upstox."
        )

    df["atm_distance"] = (
        df["strike"] - spot
    ).abs()

    atm_row = df.loc[
        df["atm_distance"].idxmin()
    ]

    atm = sf(
        atm_row["strike"]
    )

    total_call_oi = (
        df["ce_oi"].sum()
    )

    total_put_oi = (
        df["pe_oi"].sum()
    )

    if total_call_oi > 0:

        pcr = (
            total_put_oi
            / total_call_oi
        )

    else:

        pcr = 0.0

    resistance_row = df.loc[
        df["ce_oi"].idxmax()
    ]

    support_row = df.loc[
        df["pe_oi"].idxmax()
    ]

    call_resistance = sf(
        resistance_row["strike"]
    )

    put_support = sf(
        support_row["strike"]
    )

    near = df[
        df["atm_distance"]
        <= spot * 0.03
    ].copy()

    if near.empty:

        near = df.nsmallest(
            min(5, len(df)),
            "atm_distance",
        ).copy()

    bull = 50
    bear = 50

    reasons = []

    # --------------------------------------------------------
    # PCR
    # --------------------------------------------------------

    if pcr >= 1.20:

        bull += 9

        reasons.append(
            f"PCR {pcr:.2f} indicates stronger Put OI support."
        )

    elif (
        pcr <= 0.80
        and pcr > 0
    ):

        bear += 9

        reasons.append(
            f"PCR {pcr:.2f} indicates stronger Call-side OI."
        )

    # --------------------------------------------------------
    # CHANGE OI
    # --------------------------------------------------------

    near_put_change = (
        near["pe_chg_oi"].sum()
    )

    near_call_change = (
        near["ce_chg_oi"].sum()
    )

    if (
        near_put_change
        > near_call_change
    ):

        bull += 8

        reasons.append(
            "Near-ATM Put Change OI is stronger than Call Change OI."
        )

    elif (
        near_call_change
        > near_put_change
    ):

        bear += 8

        reasons.append(
            "Near-ATM Call Change OI is stronger than Put Change OI."
        )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    near_put_volume = (
        near["pe_volume"].sum()
    )

    near_call_volume = (
        near["ce_volume"].sum()
    )

    if (
        near_put_volume
        > near_call_volume * 1.15
    ):

        bull += 7

        reasons.append(
            "Near-ATM Put volume is stronger than Call volume."
        )

    elif (
        near_call_volume
        > near_put_volume * 1.15
    ):

        bear += 7

        reasons.append(
            "Near-ATM Call volume is stronger than Put volume."
        )

    # --------------------------------------------------------
    # SUPPORT / RESISTANCE
    # --------------------------------------------------------

    if put_support < spot:

        bull += 5

        reasons.append(
            f"Put OI support is below spot near {put_support:.2f}."
        )

    if call_resistance > spot:

        bear += 5

        reasons.append(
            f"Call OI resistance is above spot near {call_resistance:.2f}."
        )

    # --------------------------------------------------------
    # PRICE MOMENTUM
    # --------------------------------------------------------

    pct_change = sf(
        market.get(
            "pct_change"
        )
    )

    if pct_change > 0.50:

        bull += 8

        reasons.append(
            f"Underlying is up {pct_change:.2f}% today."
        )

    elif pct_change < -0.50:

        bear += 8

        reasons.append(
            f"Underlying is down {abs(pct_change):.2f}% today."
        )

    price_vs_open = sf(
        market.get(
            "price_vs_open"
        )
    )

    if price_vs_open > 0.30:

        bull += 5

    elif price_vs_open < -0.30:

        bear += 5

    price_vs_average = sf(
        market.get(
            "price_vs_average"
        )
    )

    if price_vs_average > 0.30:

        bull += 4

    elif price_vs_average < -0.30:

        bear += 4

    range_position = sf(
        market.get(
            "range_position"
        )
    )

    if range_position >= 70:

        bull += 4

    elif range_position <= 30:

        bear += 4

    bull = min(
        100,
        int(round(bull))
    )

    bear = min(
        100,
        int(round(bear))
    )

    gap = abs(
        bull - bear
    )

    maximum = max(
        bull,
        bear
    )

    if (
        maximum >= 72
        and gap >= 14
    ):

        decision = (
            "TRADE CANDIDATE"
        )

    elif (
        maximum >= 62
        and gap >= 8
    ):

        decision = "WATCH"

    else:

        decision = "NO TRADE"

    if bull > bear:

        direction = "CALL"

    elif bear > bull:

        direction = "PUT"

    else:

        direction = "CALL"

    market_status = (
        get_market_status(
            market.get(
                "last_trade_time"
            )
        )
    )

    if market_status == "MARKET CLOSED":

        decision = "MARKET CLOSED"

    elif market_status == "DATA STALE":

        decision = "DATA STALE"

    # --------------------------------------------------------
    # OPTION SELECTION
    # --------------------------------------------------------

    if direction == "CALL":

        prefix = "ce"

    else:

        prefix = "pe"

    candidates = df[
        (
            df[
                f"{prefix}_ltp"
            ] > 0
        )
        &
        (
            df[
                f"{prefix}_volume"
            ] > 0
        )
        &
        (
            df[
                f"{prefix}_instrument_key"
            ].notna()
        )
    ].copy()

    if candidates.empty:

        candidates = df[
            (
                df[
                    f"{prefix}_ltp"
                ] > 0
            )
            &
            (
                df[
                    f"{prefix}_instrument_key"
                ].notna()
            )
        ].copy()

    trade_plan = {

        "direction": direction,

        "strike": atm,

        "entry": 0.0,

        "sl": 0.0,

        "target1": 0.0,

        "target2": 0.0,

        "pop": 0.0,

        "delta": 0.0,

        "iv": 0.0,

        "oi": 0.0,

        "chg_oi": 0.0,

        "volume": 0.0,

        "bid": 0.0,

        "ask": 0.0,

        "spread_pct": 0.0,

        "trigger": spot,

        "entry_status": "WAIT",

        "instrument_key": None,
    }

    if not candidates.empty:

        candidates["distance"] = (
            candidates["strike"]
            - spot
        ).abs()

        candidates = candidates.sort_values(
            [
                "distance",
                f"{prefix}_volume",
            ],
            ascending=[
                True,
                False,
            ],
        )

        selected = candidates.iloc[0]

        ltp = sf(
            selected[
                f"{prefix}_ltp"
            ]
        )

        bid = sf(
            selected[
                f"{prefix}_bid"
            ]
        )

        ask = sf(
            selected[
                f"{prefix}_ask"
            ]
        )

        if (
            bid > 0
            and ask > 0
        ):

            entry = (
                bid + ask
            ) / 2

            spread_pct = (
                (
                    ask - bid
                )
                / entry
            ) * 100 if entry > 0 else 0.0

        else:

            entry = ltp

            spread_pct = 0.0

        if spread_pct > 10:

            decision = "NO TRADE"

            reasons.append(
                f"Selected option spread is wide at {spread_pct:.1f}%."
            )

        trade_plan.update({

            "direction": direction,

            "strike": sf(
                selected[
                    "strike"
                ]
            ),

            "entry": entry,

            "pop": sf(
                selected[
                    f"{prefix}_pop"
                ]
            ),

            "delta": sf(
                selected[
                    f"{prefix}_delta"
                ]
            ),

            "iv": sf(
                selected[
                    f"{prefix}_iv"
                ]
            ),

            "oi": sf(
                selected[
                    f"{prefix}_oi"
                ]
            ),

            "chg_oi": sf(
                selected[
                    f"{prefix}_chg_oi"
                ]
            ),

            "volume": sf(
                selected[
                    f"{prefix}_volume"
                ]
            ),

            "bid": bid,

            "ask": ask,

            "spread_pct": spread_pct,

            "instrument_key":
                selected[
                    f"{prefix}_instrument_key"
                ],
        })

        if direction == "CALL":

            trade_plan[
                "trigger"
            ] = max(
                spot,
                atm
            )

        else:

            trade_plan[
                "trigger"
            ] = min(
                spot,
                atm
            )

        if decision == "TRADE CANDIDATE":

            trade_plan[
                "entry_status"
            ] = (
                "READY — CHECK LIVE PRICE"
            )

        elif decision == "WATCH":

            trade_plan[
                "entry_status"
            ] = (
                "WAIT FOR CONFIRMATION"
            )

        else:

            trade_plan[
                "entry_status"
            ] = "NO ENTRY"

    return {

        "spot": spot,

        "market": market,

        "pcr": pcr,

        "put_support": put_support,

        "call_resistance":
            call_resistance,

        "atm": atm,

        "bull": bull,

        "bear": bear,

        "gap": gap,

        "decision": decision,

        "direction": direction,

        "reasons": reasons,

        "trade_plan": trade_plan,

        "market_status":
            market_status,

        "expiry_days": None,
    }


# ============================================================
# RUN ANALYSIS
# ============================================================

def run_analysis(
    symbol,
    risk_profile
):

    underlying = (
        find_underlying(
            symbol
        )
    )

    underlying_key = (
        underlying.get(
            "instrument_key"
        )
    )

    if not underlying_key:

        raise RuntimeError(
            "Could not find Upstox instrument key."
        )

    quote = (
        get_full_quote_v3(
            underlying_key
        )
    )

    market = (
        extract_market_context(
            quote
        )
    )

    contracts = (
        get_option_contracts(
            underlying_key
        )
    )

    expiry = (
        get_nearest_expiry(
            contracts
        )
    )

    if expiry is None:

        raise RuntimeError(
            "Could not find a valid future option expiry."
        )

    raw_chain = (
        get_option_chain(
            underlying_key,
            expiry,
        )
    )

    chain_df = (
        normalize_chain(
            raw_chain
        )
    )

    if chain_df.empty:

        raise RuntimeError(
            "Upstox returned an empty option chain."
        )

    # ========================================================
    # IMPORTANT FIX
    # ========================================================

    chain_df = (
        ensure_change_oi_columns(
            chain_df
        )
    )

    result = (
        analyze_chain(
            chain_df,
            market
        )
    )

    today = (
        now_ist().date()
    )

    expiry_days = (
        expiry - today
    ).days

    result["symbol"] = (
        underlying.get(
            "trading_symbol"
        )
        or underlying.get(
            "short_name"
        )
        or symbol.upper()
    )

    result["input_symbol"] = (
        symbol.upper()
    )

    result["underlying_key"] = (
        underlying_key
    )

    result["expiry"] = str(
        expiry
    )

    result["expiry_days"] = (
        expiry_days
    )

    result["snapshot_time"] = (
        market.get(
            "snapshot_time"
        )
    )

    result["last_trade_time"] = (
        market.get(
            "last_trade_time"
        )
    )

    result["app_fetch_time"] = (
        now_ist()
    )

    # --------------------------------------------------------
    # RISK PROFILE
    # --------------------------------------------------------

    profile = RISK_PROFILES[
        risk_profile
    ]

    trade_plan = (
        result["trade_plan"]
    )

    entry = sf(
        trade_plan.get(
            "entry"
        )
    )

    if entry > 0:

        trade_plan["sl"] = (
            entry
            * (
                1
                - profile["sl"]
            )
        )

        trade_plan["target1"] = (
            entry
            * (
                1
                + profile["t1"]
            )
        )

        trade_plan["target2"] = (
            entry
            * (
                1
                + profile["t2"]
            )
        )

    result["trade_plan"] = (
        trade_plan
    )

    # --------------------------------------------------------
    # SELECTED OPTION TIMESTAMP
    # --------------------------------------------------------

    selected_key = (
        trade_plan.get(
            "instrument_key"
        )
    )

    if selected_key:

        try:

            selected_quote = (
                get_full_quote_v3(
                    selected_key
                )
            )

            result[
                "selected_option_last_trade_time"
            ] = first_valid(

                selected_quote.get(
                    "last_trade_time"
                ),

                selected_quote.get(
                    "timestamp"
                ),
            )

        except Exception:

            result[
                "selected_option_last_trade_time"
            ] = None

    else:

        result[
            "selected_option_last_trade_time"
        ] = None

    return (
        result,
        chain_df,
    )


# ============================================================
# DISPLAY HELPERS
# ============================================================

def fmt_price(value):

    value = sf(value)

    if value == 0:

        return "—"

    return f"₹{value:,.2f}"


def fmt_number(value):

    value = sf(value)

    if value == 0:

        return "—"

    if abs(value) >= 10_000_000:

        return (
            f"{value / 10_000_000:.2f} Cr"
        )

    if abs(value) >= 100_000:

        return (
            f"{value / 100_000:.2f} L"
        )

    if abs(value) >= 1_000:

        return (
            f"{value / 1_000:.1f}K"
        )

    return f"{value:,.0f}"


def fmt_pct(value):

    value = sf(value)

    if value == 0:

        return "—"

    return f"{value:.2f}%"


def decision_display(
    decision,
    direction,
):

    if decision == "TRADE CANDIDATE":

        return (
            f"🟢 {direction} — BUY"
        )

    if decision == "WATCH":

        return (
            f"🟡 {direction} — BUY AFTER CONFIRMATION"
        )

    if decision == "MARKET CLOSED":

        return "⚪ MARKET CLOSED"

    if decision == "DATA STALE":

        return "🟠 DATA STALE"

    return "⚪ NO TRADE"


# ============================================================
# DISPLAY ANALYSIS
# ============================================================

def display_analysis(
    result,
    chain_df,
):

    symbol = result.get(
        "symbol",
        "N/A"
    )

    market = result.get(
        "market",
        {}
    )

    decision = result.get(
        "decision",
        "NO TRADE"
    )

    direction = result.get(
        "direction",
        "CALL"
    )

    trade = result.get(
        "trade_plan",
        {}
    )

    market_status = result.get(
        "market_status",
        "MARKET CLOSED"
    )

    spot = sf(
        result.get(
            "spot"
        )
    )

    pct_change = sf(
        market.get(
            "pct_change"
        )
    )

    net_change = sf(
        market.get(
            "net_change"
        )
    )

    status_class = (
        "status-closed"
    )

    if market_status == "MARKET OPEN":

        status_class = (
            "status-open"
        )

    elif market_status == "DATA STALE":

        status_class = (
            "status-stale"
        )

    last_trade_text = (
        format_ms_ist(
            result.get(
                "last_trade_time"
            )
        )
    )

    if last_trade_text == "N/A":

        last_trade_text = (
            format_iso_ist(
                result.get(
                    "last_trade_time"
                )
            )
        )

    app_time = result.get(
        "app_fetch_time"
    )

    # ========================================================
    # HERO
    # ========================================================

    st.markdown(
        f"""
<div class="stock-hero">

    <div style="
        display:flex;
        justify-content:space-between;
        align-items:flex-start;
        gap:15px;
        flex-wrap:wrap;
    ">

        <div>

            <div class="stock-name">
                {symbol}
            </div>

            <div class="stock-subtitle">
                F&O Options Analysis • Live Upstox Data
            </div>

        </div>

        <div class="{status_class}">
            {market_status}
        </div>

    </div>

    <div style="
        margin-top:14px;
        color:#687386;
        font-size:13px;
    ">

        Last traded:
        {last_trade_text}

        &nbsp; • &nbsp;

        Updated:
        {format_iso_ist(app_time)}

    </div>

</div>
""",
        unsafe_allow_html=True,
    )

    # ========================================================
    # MARKET SNAPSHOT
    # ========================================================

    st.markdown(
        '<div class="section-title">Market Snapshot</div>',
        unsafe_allow_html=True,
    )

    snapshot_cols = st.columns(
        5
    )

    snapshot_items = [

        (
            "LIVE PRICE",
            fmt_price(spot),
            f"{net_change:+.2f} "
            f"({pct_change:+.2f}%)",
        ),

        (
            "MARKET BIAS",
            (
                "BULLISH"
                if result.get("bull", 0)
                > result.get("bear", 0)
                else "BEARISH"
            ),
            f"Bull {result.get('bull', 0)} "
            f"/ Bear {result.get('bear', 0)}",
        ),

        (
            "PCR",
            f"{sf(result.get('pcr')):.2f}",
            "Put OI ÷ Call OI",
        ),

        (
            "PUT OI SUPPORT",
            fmt_price(
                result.get(
                    "put_support"
                )
            ),
            "Highest Put OI strike",
        ),

        (
            "CALL OI RESISTANCE",
            fmt_price(
                result.get(
                    "call_resistance"
                )
            ),
            "Highest Call OI strike",
        ),

    ]

    for col, item in zip(
        snapshot_cols,
        snapshot_items,
    ):

        with col:

            st.markdown(
                f"""
<div class="metric-card">

    <div class="metric-label">
        {item[0]}
    </div>

    <div class="metric-value">
        {item[1]}
    </div>

    <div class="metric-small">
        {item[2]}
    </div>

</div>
""",
                unsafe_allow_html=True,
            )

    # ========================================================
    # DECISION
    # ========================================================

    st.markdown(
        '<div class="section-title">Engine Decision</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
<div class="decision-card">

    <div class="decision-title">
        {decision_display(
            decision,
            direction
        )}
    </div>

    <div style="
        color:#687386;
        margin-top:7px;
    ">

        Signal gap:
        <b>{result.get("gap", 0)}</b>

        &nbsp; • &nbsp;

        Expiry:
        <b>{result.get("expiry", "N/A")}</b>

        &nbsp; • &nbsp;

        Days left:
        <b>{result.get("expiry_days", "N/A")}</b>

    </div>

</div>
""",
        unsafe_allow_html=True,
    )

    score_cols = st.columns(
        2
    )

    with score_cols[0]:

        st.markdown(
            f"""
<div class="score-box">
    <b>
        🟢 Bullish Score:
        {result.get("bull", 0)}/100
    </b>
</div>
""",
            unsafe_allow_html=True,
        )

        st.progress(
            min(
                max(
                    int(
                        result.get(
                            "bull",
                            0
                        )
                    ),
                    0,
                ),
                100,
            )
            / 100
        )

    with score_cols[1]:

        st.markdown(
            f"""
<div class="score-box">
    <b>
        🔴 Bearish Score:
        {result.get("bear", 0)}/100
    </b>
</div>
""",
            unsafe_allow_html=True,
        )

        st.progress(
            min(
                max(
                    int(
                        result.get(
                            "bear",
                            0
                        )
                    ),
                    0,
                ),
                100,
            )
            / 100
        )

    # ========================================================
    # TRADE PLAN
    # ========================================================

    st.markdown(
        '<div class="section-title">Trade Plan</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="trade-plan">',
        unsafe_allow_html=True,
    )

    plan_cols = st.columns(
        6
    )

    plan_items = [

        (
            "DIRECTION / STRIKE",
            f"{trade.get('direction', direction)} "
            f"{sf(trade.get('strike')):.0f}",
        ),

        (
            "ENTRY",
            fmt_price(
                trade.get(
                    "entry"
                )
            ),
        ),

        (
            "STOP LOSS",
            fmt_price(
                trade.get(
                    "sl"
                )
            ),
        ),

        (
            "TARGET 1",
            fmt_price(
                trade.get(
                    "target1"
                )
            ),
        ),

        (
            "TARGET 2",
            fmt_price(
                trade.get(
                    "target2"
                )
            ),
        ),

        (
            "PoP",
            fmt_pct(
                trade.get(
                    "pop"
                )
            ),
        ),

    ]

    for col, item in zip(
        plan_cols,
        plan_items,
    ):

        with col:

            st.markdown(
                f"""
<div class="metric-card">

    <div class="metric-label">
        {item[0]}
    </div>

    <div class="metric-value">
        {item[1]}
    </div>

</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown(
        "<div style='height:10px'></div>",
        unsafe_allow_html=True,
    )

    detail_cols = st.columns(
        5
    )

    delta_value = sf(
        trade.get(
            "delta"
        )
    )

    detail_items = [

        (
            "DELTA",
            (
                f"{delta_value:.3f}"
                if delta_value != 0
                else "—"
            ),
        ),

        (
            "IV",
            fmt_pct(
                trade.get(
                    "iv"
                )
            ),
        ),

        (
            "OI",
            fmt_number(
                trade.get(
                    "oi"
                )
            ),
        ),

        (
            "CHANGE OI",
            fmt_number(
                trade.get(
                    "chg_oi"
                )
            ),
        ),

        (
            "VOLUME",
            fmt_number(
                trade.get(
                    "volume"
                )
            ),
        ),

    ]

    for col, item in zip(
        detail_cols,
        detail_items,
    ):

        with col:

            st.markdown(
                f"""
<div class="metric-card">

    <div class="metric-label">
        {item[0]}
    </div>

    <div class="metric-value">
        {item[1]}
    </div>

</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown(
        f"""
<div style="
    margin-top:15px;
    color:#687386;
    font-size:13px;
">

    Entry status:
    <b>
        {trade.get(
            "entry_status",
            "WAIT"
        )}
    </b>

    &nbsp; • &nbsp;

    Trigger:
    <b>
        {fmt_price(
            trade.get(
                "trigger"
            )
        )}
    </b>

    &nbsp; • &nbsp;

    Bid:
    <b>
        {fmt_price(
            trade.get(
                "bid"
            )
        )}
    </b>

    &nbsp; • &nbsp;

    Ask:
    <b>
        {fmt_price(
            trade.get(
                "ask"
            )
        )}
    </b>

    &nbsp; • &nbsp;

    Spread:
    <b>
        {fmt_pct(
            trade.get(
                "spread_pct"
            )
        )}
    </b>

</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )

    # ========================================================
    # REASONS
    # ========================================================

    st.markdown(
        '<div class="section-title">'
        'Why the Engine Reached This View'
        '</div>',
        unsafe_allow_html=True,
    )

    reasons = result.get(
        "reasons",
        []
    )

    if not reasons:

        reasons = [
            "No strong confirming factor was detected."
        ]

    for reason in reasons:

        st.markdown(
            f"""
<div class="reason-box">
    • {reason}
</div>
""",
            unsafe_allow_html=True,
        )

    # ========================================================
    # SUPPORT / RESISTANCE
    # ========================================================

    st.markdown(
        '<div class="section-title">'
        'OI Support / Resistance'
        '</div>',
        unsafe_allow_html=True,
    )

    sr_cols = st.columns(
        3
    )

    sr_items = [

        (
            "CURRENT PRICE",
            fmt_price(
                spot
            ),
        ),

        (
            "PUT SUPPORT",
            fmt_price(
                result.get(
                    "put_support"
                )
            ),
        ),

        (
            "CALL RESISTANCE",
            fmt_price(
                result.get(
                    "call_resistance"
                )
            ),
        ),

    ]

    for col, item in zip(
        sr_cols,
        sr_items,
    ):

        with col:

            st.markdown(
                f"""
<div class="metric-card">

    <div class="metric-label">
        {item[0]}
    </div>

    <div class="metric-value">
        {item[1]}
    </div>

</div>
""",
                unsafe_allow_html=True,
            )

    # ========================================================
    # LIVE OPTION CHAIN
    # ========================================================

    st.markdown(
        '<div class="section-title">'
        'Live Option Chain'
        '</div>',
        unsafe_allow_html=True,
    )

    if (
        chain_df is None
        or chain_df.empty
    ):

        st.warning(
            "No option-chain rows are available."
        )

    else:

        # ====================================================
        # IMPORTANT FIX
        # ====================================================

        display_df = (
            chain_df.copy()
        )

        display_df = (
            ensure_change_oi_columns(
                display_df
            )
        )

        display_df["distance"] = (
            display_df["strike"]
            - spot
        ).abs()

        display_df = (
            display_df
            .sort_values(
                "distance"
            )
            .head(15)
        )

        display_df = (
            display_df
            .sort_values(
                "strike"
            )
        )

        table_df = pd.DataFrame({

            "CALL LTP":
                display_df[
                    "ce_ltp"
                ].map(
                    lambda x:
                    fmt_price(x)
                ),

            "CALL OI":
                display_df[
                    "ce_oi"
                ].map(
                    lambda x:
                    fmt_number(x)
                ),

            "CALL Chg OI":
                display_df[
                    "ce_chg_oi"
                ].map(
                    lambda x:
                    fmt_number(x)
                ),

            "CALL IV":
                display_df[
                    "ce_iv"
                ].map(
                    lambda x:
                    fmt_pct(x)
                ),

            "STRIKE":
                display_df[
                    "strike"
                ].map(
                    lambda x:
                    f"{sf(x):,.0f}"
                ),

            "PUT LTP":
                display_df[
                    "pe_ltp"
                ].map(
                    lambda x:
                    fmt_price(x)
                ),

            "PUT OI":
                display_df[
                    "pe_oi"
                ].map(
                    lambda x:
                    fmt_number(x)
                ),

            "PUT Chg OI":
                display_df[
                    "pe_chg_oi"
                ].map(
                    lambda x:
                    fmt_number(x)
                ),

            "PUT IV":
                display_df[
                    "pe_iv"
                ].map(
                    lambda x:
                    fmt_pct(x)
                ),

            "CALL PoP":
                display_df[
                    "ce_pop"
                ].map(
                    lambda x:
                    fmt_pct(x)
                ),

            "PUT PoP":
                display_df[
                    "pe_pop"
                ].map(
                    lambda x:
                    fmt_pct(x)
                ),
        })

        st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # INFO
    # ========================================================

    st.markdown(
        """
<div class="info-bar">

    <b>Live data source:</b>
    Upstox API

    &nbsp; • &nbsp;

    Underlying quote +
    option chain +
    OI +
    Change OI +
    IV +
    Delta +
    PoP +
    Volume

    &nbsp; • &nbsp;

    The app does not place automatic orders.

</div>
""",
        unsafe_allow_html=True,
    )

    # ========================================================
    # FOOTER
    # ========================================================

    st.markdown(
        f"""
<div class="footer">

    Underlying last trade:
    {last_trade_text}

    &nbsp; • &nbsp;

    App refresh:
    {format_iso_ist(app_time)}

    <br>

    Educational analysis only.
    Always verify the live option price,
    liquidity, spread and market conditions
    before taking any trade.

</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# REFRESH ANALYSIS
# ============================================================

def refresh_analysis():

    symbol = st.session_state.get(
        "active_symbol",
        ""
    )

    risk_profile = st.session_state.get(
        "active_risk",
        "Balanced"
    )

    if not symbol:

        return

    try:

        result, chain = (
            run_analysis(
                symbol,
                risk_profile
            )
        )

        st.session_state.active_result = (
            result
        )

        st.session_state.active_chain = (
            chain
        )

        st.session_state.last_error = ""

        st.session_state.last_successful_refresh = (
            now_ist()
        )

    except Exception as e:

        # Keep the last successful analysis
        # visible if a temporary refresh fails.

        st.session_state.last_error = (
            str(e)
        )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🔎 Analyze Instrument"
    )

    st.markdown(
        """
<div class="sidebar-note">

Enter an NSE stock or index available in F&O.

Examples:

KOTAKBANK, HDFCBANK, RELIANCE,
ICICIBANK, SBIN, INFY, TCS,
NIFTY, BANKNIFTY.

</div>
""",
        unsafe_allow_html=True,
    )

    symbol_input = st.text_input(
        "Stock / Index",
        value=st.session_state.active_symbol,
        placeholder="Example: KOTAKBANK",
    )

    risk_profile = st.selectbox(
        "Risk Profile",
        list(
            RISK_PROFILES.keys()
        ),
        index=list(
            RISK_PROFILES.keys()
        ).index(
            st.session_state.active_risk
        ),
    )

    analyze_clicked = st.button(
        "🚀 Analyze",
        use_container_width=True,
        type="primary",
    )

    st.markdown("---")

    st.markdown(
        "### ⚡ Quick Select"
    )

    quick_symbols = [

        "NIFTY",
        "BANKNIFTY",
        "KOTAKBANK",
        "HDFCBANK",
        "RELIANCE",
        "ICICIBANK",
        "SBIN",
        "AXISBANK",
        "INFY",
        "TCS",
        "BHARTIARTL",

    ]

    quick_cols = st.columns(
        2
    )

    for index, quick_symbol in enumerate(
        quick_symbols
    ):

        with quick_cols[
            index % 2
        ]:

            if st.button(
                quick_symbol,
                use_container_width=True,
                key=f"quick_{quick_symbol}",
            ):

                st.session_state.active_symbol = (
                    quick_symbol
                )

                st.session_state.active_risk = (
                    risk_profile
                )

                st.session_state.active_result = (
                    None
                )

                st.session_state.active_chain = (
                    None
                )

                st.session_state.last_error = ""

                st.rerun()

    st.markdown("---")

    st.markdown(
        """
<div class="info-bar">

<b>Live Upstox data</b>

<br>

Market quote • Option chain •
OI • Change OI • IV • Delta •
PoP • Volume

</div>
""",
        unsafe_allow_html=True,
    )

    st.caption(
        "No automatic orders are placed by this app."
    )


# ============================================================
# ANALYZE BUTTON
# ============================================================

if analyze_clicked:

    cleaned_symbol = (
        symbol_input
        or ""
    ).strip().upper()

    if not cleaned_symbol:

        st.session_state.last_error = (
            "Please enter a stock or index symbol."
        )

    else:

        st.session_state.active_symbol = (
            cleaned_symbol
        )

        st.session_state.active_risk = (
            risk_profile
        )

        try:

            result, chain = (
                run_analysis(
                    cleaned_symbol,
                    risk_profile
                )
            )

            st.session_state.active_result = (
                result
            )

            st.session_state.active_chain = (
                chain
            )

            st.session_state.last_error = ""

            st.session_state.last_successful_refresh = (
                now_ist()
            )

        except Exception as e:

            st.session_state.last_error = (
                str(e)
            )


# ============================================================
# MAIN LIVE ANALYSIS AREA
# ============================================================

fragment = getattr(
    st,
    "fragment",
    None
)


if fragment:

    @fragment(
        run_every="30s"
    )
    def live_analysis_area():

        if st.session_state.active_symbol:

            refresh_analysis()

        if (
            st.session_state.active_result
            is not None
        ):

            display_analysis(
                st.session_state.active_result,
                st.session_state.active_chain,
            )

            if st.session_state.last_error:

                st.warning(
                    "Latest automatic refresh "
                    "could not update the data: "
                    f"{st.session_state.last_error}"
                )

        elif st.session_state.last_error:

            st.error(
                st.session_state.last_error
            )

        else:

            st.markdown(
                """
<div class="stock-hero"
     style="
        text-align:center;
        padding:55px 25px;
     ">

    <div style="font-size:45px;">
        📈
    </div>

    <div class="stock-name"
         style="
            font-size:25px;
            margin-top:10px;
         ">

        READY FOR ANALYSIS

    </div>

    <div class="stock-subtitle"
         style="
            margin-top:8px;
         ">

        Enter a stock or index on the left
        and click Analyze.

    </div>

</div>
""",
                unsafe_allow_html=True,
            )

    live_analysis_area()


else:

    if st.session_state.active_symbol:

        refresh_analysis()

    if (
        st.session_state.active_result
        is not None
    ):

        display_analysis(
            st.session_state.active_result,
            st.session_state.active_chain,
        )

        if st.session_state.last_error:

            st.warning(
                "Latest refresh could not "
                "update the data: "
                f"{st.session_state.last_error}"
            )

    elif st.session_state.last_error:

        st.error(
            st.session_state.last_error
        )

    else:

        st.markdown(
            """
<div class="stock-hero"
     style="
        text-align:center;
        padding:55px 25px;
     ">

    <div style="font-size:45px;">
        📈
    </div>

    <div class="stock-name"
         style="
            font-size:25px;
            margin-top:10px;
         ">

        READY FOR ANALYSIS

    </div>

    <div class="stock-subtitle"
         style="
            margin-top:8px;
         ">

        Enter a stock or index on the left
        and click Analyze.

    </div>

</div>
""",
            unsafe_allow_html=True,
        )
