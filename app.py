import streamlit as st
import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime, date
from urllib.parse import quote

# ============================================================
# F&O PRO TRADER ASSISTANT
# REST-ONLY LIVE UPSTOX VERSION
# ============================================================

st.set_page_config(
    page_title="F&O PRO Trader Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CONFIG
# ============================================================

UPSTOX_BASE = "https://api.upstox.com"

REFRESH_SECONDS = 10

DEFAULT_SYMBOLS = [
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "KOTAKBANK",
    "HDFCBANK",
    "RELIANCE",
    "ICICIBANK",
    "SBIN",
    "AXISBANK",
    "INFY",
    "TCS",
    "BHARTIARTL",
    "INDUSTOWER"
]

INDEX_KEYS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
}

EQUITY_FALLBACK_KEYS = {
    "HDFCBANK": "NSE_EQ|INE040A01034",
    "KOTAKBANK": "NSE_EQ|INE237A01028",
    "RELIANCE": "NSE_EQ|INE002A01018",
    "ICICIBANK": "NSE_EQ|INE090A01021",
    "SBIN": "NSE_EQ|INE062A01020",
    "AXISBANK": "NSE_EQ|INE238A01034",
    "INFY": "NSE_EQ|INE009A01021",
    "TCS": "NSE_EQ|INE467B01029",
    "BHARTIARTL": "NSE_EQ|INE397D01024",
    "INDUSTOWER": "NSE_EQ|INE121J01017",
}

# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>

.main {
    padding-top: 1rem;
}

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

.topbar {
    background: linear-gradient(135deg, #101828, #1d2939);
    padding: 22px 28px;
    border-radius: 16px;
    margin-bottom: 20px;
    border: 1px solid #344054;
}

.topbar-title {
    font-size: 34px;
    font-weight: 800;
    color: white;
}

.topbar-sub {
    color: #98a2b3;
    font-size: 15px;
    margin-top: 5px;
}

.section-title {
    font-size: 21px;
    font-weight: 750;
    margin-top: 20px;
    margin-bottom: 12px;
}

.metric-card {
    background: #ffffff;
    border: 1px solid #eaecf0;
    border-radius: 14px;
    padding: 16px;
    min-height: 100px;
    box-shadow: 0 2px 8px rgba(16,24,40,0.04);
}

.metric-label {
    color: #667085;
    font-size: 13px;
    font-weight: 600;
}

.metric-value {
    color: #101828;
    font-size: 24px;
    font-weight: 800;
    margin-top: 6px;
}

.live-box {
    background: #ecfdf3;
    border: 1px solid #abefc6;
    color: #067647;
    border-radius: 10px;
    padding: 10px 14px;
    font-weight: 700;
    display: inline-block;
}

.trade-call {
    background: #ecfdf3;
    border: 1px solid #6ce9a6;
    border-radius: 15px;
    padding: 20px;
    margin: 10px 0;
}

.trade-put {
    background: #fef3f2;
    border: 1px solid #fda29b;
    border-radius: 15px;
    padding: 20px;
    margin: 10px 0;
}

.trade-none {
    background: #fffaeb;
    border: 1px solid #fedf89;
    border-radius: 15px;
    padding: 20px;
    margin: 10px 0;
}

.trade-action {
    font-size: 30px;
    font-weight: 850;
}

.small-note {
    color: #667085;
    font-size: 12px;
}

</style>
""",
    unsafe_allow_html=True
)

# ============================================================
# HELPERS
# ============================================================

def get_token():
    token = None

    try:
        token = st.secrets.get("UPSTOX_ACCESS_TOKEN")
    except Exception:
        pass

    if not token:
        try:
            token = st.secrets.get("UPSTOX_TOKEN")
        except Exception:
            pass

    return token


TOKEN = get_token()


def headers():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }


def api_get(endpoint, params=None, timeout=15):
    if not TOKEN:
        raise RuntimeError(
            "UPSTOX_ACCESS_TOKEN is missing from Streamlit Secrets."
        )

    url = UPSTOX_BASE + endpoint

    response = requests.get(
        url,
        params=params,
        headers=headers(),
        timeout=timeout
    )

    if response.status_code != 200:
        try:
            body = response.json()
        except Exception:
            body = response.text

        raise RuntimeError(
            f"Upstox API error {response.status_code}: {body}"
        )

    return response.json()


def safe_float(value, default=np.nan):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(float(value))
    except Exception:
        return default


def fmt_money(value):
    if value is None or pd.isna(value):
        return "—"

    return f"₹{value:,.2f}"


def fmt_num(value):
    if value is None or pd.isna(value):
        return "—"

    return f"{value:,.0f}"


def fmt_pct(value):
    if value is None or pd.isna(value):
        return "—"

    return f"{value:.1f}%"


def fmt_ratio(value):
    if value is None or pd.isna(value):
        return "—"

    return f"{value:.2f}"


# ============================================================
# INSTRUMENT SEARCH
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def search_instrument(symbol):
    """
    Find NSE equity/index instrument key.
    """

    symbol = symbol.strip().upper()

    # Indexes
    if symbol in INDEX_KEYS:
        return {
            "instrument_key": INDEX_KEYS[symbol],
            "name": symbol,
            "type": "INDEX"
        }

    # First use known stable mappings
    if symbol in EQUITY_FALLBACK_KEYS:
        return {
            "instrument_key": EQUITY_FALLBACK_KEYS[symbol],
            "name": symbol,
            "type": "EQUITY"
        }

    params = {
        "query": symbol,
        "exchanges": "NSE",
        "segments": "EQ,INDEX",
        "page_number": 1,
        "records": 30
    }

    data = api_get("/v2/instruments/search", params)

    rows = data.get("data", [])

    if not rows:
        raise RuntimeError(
            f"Could not find NSE instrument for {symbol}."
        )

    # Prefer exact trading symbol
    exact = [
        x for x in rows
        if str(x.get("trading_symbol", "")).upper() == symbol
    ]

    row = exact[0] if exact else rows[0]

    return {
        "instrument_key": row.get("instrument_key"),
        "name": row.get("trading_symbol", symbol),
        "type": row.get("instrument_type", "")
    }


# ============================================================
# LTP
# ============================================================

def get_ltp(instrument_key):
    data = api_get(
        "/v3/market-quote/ltp",
        {
            "instrument_key": instrument_key
        }
    )

    rows = data.get("data", {})

    if not rows:
        raise RuntimeError("No LTP data returned by Upstox.")

    first = next(iter(rows.values()))

    return {
        "ltp": safe_float(first.get("last_price")),
        "volume": safe_int(first.get("volume")),
        "cp": safe_float(first.get("cp")),
        "ltq": safe_int(first.get("ltq"))
    }


# ============================================================
# OPTION CONTRACTS
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def get_option_contracts(instrument_key, expiry_keyword="current_month"):
    params = {
        "instrument_key": instrument_key,
        "expiry_date": expiry_keyword
    }

    data = api_get(
        "/v2/option/contract",
        params
    )

    rows = data.get("data", [])

    return rows


# ============================================================
# OPTION CHAIN
# ============================================================

def get_option_chain(instrument_key, expiry_keyword="current_month"):
    params = {
        "instrument_key": instrument_key,
        "expiry_date": expiry_keyword
    }

    data = api_get(
        "/v2/option/chain",
        params
    )

    rows = data.get("data", [])

    if not rows:
        raise RuntimeError(
            "No option-chain data returned by Upstox."
        )

    return rows


# ============================================================
# INTRADAY DATA
# ============================================================

def get_intraday(instrument_key):
    data = api_get(
        f"/v3/historical-candle/intraday/"
        f"{quote(instrument_key, safe='')}/minutes/5"
    )

    candles = data.get("data", {}).get("candles", [])

    if not candles:
        return pd.DataFrame()

    records = []

    for c in candles:
        if len(c) < 6:
            continue

        records.append(
            {
                "timestamp": c[0],
                "open": safe_float(c[1]),
                "high": safe_float(c[2]),
                "low": safe_float(c[3]),
                "close": safe_float(c[4]),
                "volume": safe_int(c[5])
            }
        )

    df = pd.DataFrame(records)

    if not df.empty:
        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce"
        )

    return df


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

def add_indicators(df):

    if df.empty:
        return df

    out = df.copy()

    out["ema20"] = out["close"].ewm(
        span=20,
        adjust=False
    ).mean()

    out["ema50"] = out["close"].ewm(
        span=50,
        adjust=False
    ).mean()

    delta = out["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    out["rsi"] = 100 - (
        100 / (1 + rs)
    )

    prev_close = out["close"].shift(1)

    tr1 = out["high"] - out["low"]
    tr2 = abs(out["high"] - prev_close)
    tr3 = abs(out["low"] - prev_close)

    out["tr"] = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    out["atr"] = out["tr"].rolling(14).mean()

    out["volume_avg"] = out["volume"].rolling(20).mean()

    out["momentum"] = (
        out["close"] /
        out["close"].shift(5) - 1
    ) * 100

    return out


# ============================================================
# OPTION CHAIN NORMALIZATION
# ============================================================

def normalize_chain(rows):

    records = []

    for row in rows:

        strike = safe_float(
            row.get("strike_price")
        )

        call = row.get("call_options") or {}
        put = row.get("put_options") or {}

        call_md = call.get("market_data") or {}
        put_md = put.get("market_data") or {}

        call_g = call.get("option_greeks") or {}
        put_g = put.get("option_greeks") or {}

        records.append(
            {
                "expiry": row.get("expiry"),
                "strike": strike,

                "spot": safe_float(
                    row.get("underlying_spot_price")
                ),

                "pcr": safe_float(
                    row.get("pcr")
                ),

                "call_key": call.get(
                    "instrument_key"
                ),

                "call_ltp": safe_float(
                    call_md.get("ltp")
                ),

                "call_oi": safe_int(
                    call_md.get("oi")
                ),

                "call_prev_oi": safe_int(
                    call_md.get("prev_oi")
                ),

                "call_volume": safe_int(
                    call_md.get("volume")
                ),

                "call_bid": safe_float(
                    call_md.get("bid_price")
                ),

                "call_ask": safe_float(
                    call_md.get("ask_price")
                ),

                "call_delta": safe_float(
                    call_g.get("delta")
                ),

                "call_iv": safe_float(
                    call_g.get("iv")
                ),

                "call_pop": safe_float(
                    call_g.get("pop")
                ),

                "put_key": put.get(
                    "instrument_key"
                ),

                "put_ltp": safe_float(
                    put_md.get("ltp")
                ),

                "put_oi": safe_int(
                    put_md.get("oi")
                ),

                "put_prev_oi": safe_int(
                    put_md.get("prev_oi")
                ),

                "put_volume": safe_int(
                    put_md.get("volume")
                ),

                "put_bid": safe_float(
                    put_md.get("bid_price")
                ),

                "put_ask": safe_float(
                    put_md.get("ask_price")
                ),

                "put_delta": safe_float(
                    put_g.get("delta")
                ),

                "put_iv": safe_float(
                    put_g.get("iv")
                ),

                "put_pop": safe_float(
                    put_g.get("pop")
                )
            }
        )

    df = pd.DataFrame(records)

    if not df.empty:
        df = df.sort_values("strike").reset_index(
            drop=True
        )

    return df


# ============================================================
# OI LEVELS
# ============================================================

def calculate_oi_levels(chain, spot):

    if chain.empty:
        return np.nan, np.nan

    valid = chain.dropna(
        subset=["strike"]
    ).copy()

    if valid.empty:
        return np.nan, np.nan

    call_oi = valid[
        valid["call_oi"] > 0
    ]

    put_oi = valid[
        valid["put_oi"] > 0
    ]

    if call_oi.empty:
        resistance = np.nan
    else:
        resistance = call_oi.loc[
            call_oi["call_oi"].idxmax(),
            "strike"
        ]

    if put_oi.empty:
        support = np.nan
    else:
        support = put_oi.loc[
            put_oi["put_oi"].idxmax(),
            "strike"
        ]

    return support, resistance


# ============================================================
# PCR
# ============================================================

def calculate_pcr(chain):

    if chain.empty:
        return np.nan

    put_oi = chain["put_oi"].sum()
    call_oi = chain["call_oi"].sum()

    if call_oi <= 0:
        return np.nan

    return put_oi / call_oi


# ============================================================
# BIAS
# ============================================================

def calculate_bias(
    spot,
    support,
    resistance,
    pcr,
    technicals
):

    score = 0

    if not pd.isna(support):
        if spot > support:
            score += 1
        else:
            score -= 1

    if not pd.isna(resistance):
        if spot < resistance:
            score += 0
        else:
            score -= 1

    if not pd.isna(pcr):
        if pcr >= 1.20:
            score += 2
        elif pcr >= 1.00:
            score += 1
        elif pcr <= 0.75:
            score -= 2
        elif pcr < 0.95:
            score -= 1

    rsi = technicals.get("rsi", np.nan)
    ema20 = technicals.get("ema20", np.nan)
    ema50 = technicals.get("ema50", np.nan)
    momentum = technicals.get("momentum", np.nan)

    if not pd.isna(ema20) and not pd.isna(ema50):
        if spot > ema20 > ema50:
            score += 2
        elif spot < ema20 < ema50:
            score -= 2

    if not pd.isna(rsi):

        if rsi >= 60:
            score += 1

        elif rsi <= 40:
            score -= 1

    if not pd.isna(momentum):

        if momentum > 0.25:
            score += 1

        elif momentum < -0.25:
            score -= 1

    if score >= 4:
        return "Strong Bullish", score

    if score >= 2:
        return "Bullish", score

    if score <= -4:
        return "Strong Bearish", score

    if score <= -2:
        return "Bearish", score

    return "Neutral", score


# ============================================================
# SELECT OPTION
# ============================================================

def choose_option(chain, spot, direction):

    if chain.empty:
        return None

    df = chain.copy()

    df["distance"] = abs(
        df["strike"] - spot
    )

    # Keep strikes around ATM
    df = df.sort_values(
        "distance"
    ).head(15)

    if direction == "CALL":

        candidates = df[
            (df["call_ltp"] > 0) &
            (df["call_delta"].notna())
        ].copy()

        if candidates.empty:
            return None

        # Prefer Delta approximately 0.45-0.65
        candidates["delta_distance"] = abs(
            candidates["call_delta"] - 0.55
        )

        candidates = candidates.sort_values(
            ["delta_distance", "distance"]
        )

        row = candidates.iloc[0]

        return {
            "type": "CALL",
            "strike": row["strike"],
            "instrument_key": row["call_key"],
            "ltp": row["call_ltp"],
            "delta": row["call_delta"],
            "iv": row["call_iv"],
            "pop": row["call_pop"],
            "volume": row["call_volume"],
            "oi": row["call_oi"],
            "bid": row["call_bid"],
            "ask": row["call_ask"]
        }

    candidates = df[
        (df["put_ltp"] > 0) &
        (df["put_delta"].notna())
    ].copy()

    if candidates.empty:
        return None

    candidates["delta_distance"] = abs(
        abs(candidates["put_delta"]) - 0.55
    )

    candidates = candidates.sort_values(
        ["delta_distance", "distance"]
    )

    row = candidates.iloc[0]

    return {
        "type": "PUT",
        "strike": row["strike"],
        "instrument_key": row["put_key"],
        "ltp": row["put_ltp"],
        "delta": row["put_delta"],
        "iv": row["put_iv"],
        "pop": row["put_pop"],
        "volume": row["put_volume"],
        "oi": row["put_oi"],
        "bid": row["put_bid"],
        "ask": row["put_ask"]
    }


# ============================================================
# TRADE PLAN
# ============================================================

def create_trade_plan(
    option,
    bias,
    score,
    technicals,
    risk_profile
):

    if option is None:
        return None

    premium = option["ltp"]

    if premium is None or pd.isna(premium) or premium <= 0:
        return None

    if risk_profile == "Conservative":

        sl_pct = 0.18
        t1_pct = 0.30
        t2_pct = 0.50

    elif risk_profile == "Aggressive":

        sl_pct = 0.28
        t1_pct = 0.55
        t2_pct = 0.85

    else:

        sl_pct = 0.22
        t1_pct = 0.42
        t2_pct = 0.65

    entry = premium

    sl = entry * (1 - sl_pct)

    target1 = entry * (1 + t1_pct)

    target2 = entry * (1 + t2_pct)

    risk = entry - sl

    reward = target1 - entry

    rr = reward / risk if risk > 0 else np.nan

    if option["type"] == "CALL":

        trigger = (
            "Underlying sustains above ATM / resistance "
            "breakout with volume."
        )

        exit_rule = (
            "Exit if underlying loses support or option "
            "premium closes below Stop Loss."
        )

    else:

        trigger = (
            "Underlying breaks support and sustains below "
            "support with volume."
        )

        exit_rule = (
            "Exit if underlying reclaims resistance or "
            "option premium closes below Stop Loss."
        )

    return {
        "entry": entry,
        "sl": sl,
        "target1": target1,
        "target2": target2,
        "rr": rr,
        "trigger": trigger,
        "exit_rule": exit_rule
    }


# ============================================================
# SIGNAL ENGINE
# ============================================================

def generate_signal(
    bias,
    score,
    pcr,
    option_call,
    option_put,
    technicals
):

    rsi = technicals.get("rsi", np.nan)

    momentum = technicals.get(
        "momentum",
        np.nan
    )

    # Strong conditions
    bullish_points = 0
    bearish_points = 0

    if bias in ["Bullish", "Strong Bullish"]:
        bullish_points += 2

    if bias in ["Bearish", "Strong Bearish"]:
        bearish_points += 2

    if not pd.isna(pcr):

        if pcr >= 1.10:
            bullish_points += 1

        if pcr <= 0.85:
            bearish_points += 1

    if not pd.isna(rsi):

        if rsi >= 55:
            bullish_points += 1

        if rsi <= 45:
            bearish_points += 1

    if not pd.isna(momentum):

        if momentum > 0:
            bullish_points += 1

        if momentum < 0:
            bearish_points += 1

    if bullish_points >= bearish_points + 2:
        return "CALL BUY", "CALL", bullish_points, bearish_points

    if bearish_points >= bullish_points + 2:
        return "PUT BUY", "PUT", bullish_points, bearish_points

    return "NO TRADE", None, bullish_points, bearish_points


# ============================================================
# TECHNICAL SUMMARY
# ============================================================

def get_technicals(df, spot):

    if df.empty:
        return {
            "rsi": np.nan,
            "ema20": np.nan,
            "ema50": np.nan,
            "atr": np.nan,
            "momentum": np.nan,
            "volume_ratio": np.nan
        }

    df = add_indicators(df)

    last = df.iloc[-1]

    volume_avg = last.get("volume_avg", np.nan)

    if (
        pd.isna(volume_avg)
        or volume_avg == 0
    ):
        volume_ratio = np.nan
    else:
        volume_ratio = (
            last["volume"] /
            volume_avg
        )

    return {
        "rsi": safe_float(last.get("rsi")),
        "ema20": safe_float(last.get("ema20")),
        "ema50": safe_float(last.get("ema50")),
        "atr": safe_float(last.get("atr")),
        "momentum": safe_float(last.get("momentum")),
        "volume_ratio": safe_float(volume_ratio)
    }


# ============================================================
# MAIN ANALYSIS
# ============================================================

def analyze_symbol(
    symbol,
    risk_profile
):

    instrument = search_instrument(symbol)

    instrument_key = instrument["instrument_key"]

    ltp_data = get_ltp(instrument_key)

    spot = ltp_data["ltp"]

    if pd.isna(spot):
        raise RuntimeError(
            "Upstox returned no usable spot price."
        )

    chain_rows = get_option_chain(
        instrument_key,
        "current_month"
    )

    chain = normalize_chain(chain_rows)

    if chain.empty:
        raise RuntimeError(
            "Option chain is empty."
        )

    support, resistance = calculate_oi_levels(
        chain,
        spot
    )

    pcr = calculate_pcr(chain)

    intraday = get_intraday(
        instrument_key
    )

    technicals = get_technicals(
        intraday,
        spot
    )

    bias, bias_score = calculate_bias(
        spot,
        support,
        resistance,
        pcr,
        technicals
    )

    call_option = choose_option(
        chain,
        spot,
        "CALL"
    )

    put_option = choose_option(
        chain,
        spot,
        "PUT"
    )

    action, direction, bullish_points, bearish_points = (
        generate_signal(
            bias,
            bias_score,
            pcr,
            call_option,
            put_option,
            technicals
        )
    )

    selected_option = None

    if direction == "CALL":
        selected_option = call_option

    elif direction == "PUT":
        selected_option = put_option

    trade_plan = create_trade_plan(
        selected_option,
        bias,
        bias_score,
        technicals,
        risk_profile
    )

    # ========================================================
    # EXPIRY
    # ========================================================

    expiry = None

    if chain_rows:

        expiry_values = [
            x.get("expiry")
            for x in chain_rows
            if x.get("expiry")
        ]

        if expiry_values:
            expiry = sorted(
                expiry_values
            )[0]

    return {
        "symbol": symbol,
        "instrument": instrument,
        "instrument_key": instrument_key,
        "spot": spot,
        "ltp_data": ltp_data,
        "chain": chain,
        "expiry": expiry,
        "support": support,
        "resistance": resistance,
        "pcr": pcr,
        "technicals": technicals,
        "bias": bias,
        "bias_score": bias_score,
        "action": action,
        "direction": direction,
        "call_option": call_option,
        "put_option": put_option,
        "selected_option": selected_option,
        "trade_plan": trade_plan,
        "bullish_points": bullish_points,
        "bearish_points": bearish_points
    }


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
<div class="topbar">

<div class="topbar-title">
📊 F&O PRO Trader Assistant
</div>

<div class="topbar-sub">
Options Analysis • Upstox REST API • Live market data
</div>

</div>
""",
    unsafe_allow_html=True
)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🔎 Analyze Instrument")

    symbol = st.text_input(
        "Stock / Index",
        value="HDFCBANK",
        placeholder="Example: HDFCBANK"
    ).strip().upper()

    risk_profile = st.selectbox(
        "Risk Profile",
        [
            "Conservative",
            "Balanced",
            "Aggressive"
        ],
        index=1
    )

    analyze_button = st.button(
        "🚀 Analyze",
        type="primary",
        use_container_width=True
    )

    st.markdown("---")

    st.markdown("### ⚡ Quick Select")

    quick = st.selectbox(
        "Select Instrument",
        [""] + DEFAULT_SYMBOLS
    )

    if quick:
        symbol = quick

    st.markdown("---")

    st.caption(
        "REST-only architecture. "
        "No WebSocket connection is used."
    )

# ============================================================
# SESSION STATE
# ============================================================

if "analysis" not in st.session_state:
    st.session_state.analysis = None

if "last_symbol" not in st.session_state:
    st.session_state.last_symbol = None

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0


should_analyze = (
    analyze_button
    or st.session_state.analysis is None
    or st.session_state.last_symbol != symbol
    or (
        time.time() -
        st.session_state.last_refresh
        >= REFRESH_SECONDS
    )
)

# ============================================================
# TOKEN CHECK
# ============================================================

if not TOKEN:

    st.error(
        "Upstox access token is not configured."
    )

    st.info(
        "Add your Upstox token in Streamlit "
        "Secrets as UPSTOX_ACCESS_TOKEN."
    )

    st.stop()

# ============================================================
# ANALYSIS
# ============================================================

if should_analyze:

    with st.spinner(
        f"Fetching live data for {symbol}..."
    ):

        try:

            result = analyze_symbol(
                symbol,
                risk_profile
            )

            st.session_state.analysis = result

            st.session_state.last_symbol = symbol

            st.session_state.last_refresh = time.time()

        except Exception as e:

            st.error(
                f"Unable to fetch live market data: {e}"
            )

            st.stop()


result = st.session_state.analysis

if result is None:
    st.info(
        "Enter an NSE F&O stock/index and click Analyze."
    )
    st.stop()


# ============================================================
# LIVE HEADER
# ============================================================

st.markdown(
    f"""
### {result["symbol"]} — F&O Options Analysis

<div class="live-box">
🟢 LIVE DATA
</div>

&nbsp;&nbsp;&nbsp;

<strong>Updated:</strong>
{datetime.now().strftime("%d-%b-%Y %H:%M:%S")}

&nbsp;&nbsp;&nbsp;

<strong>Expiry:</strong>
{result["expiry"] or "—"}
""",
    unsafe_allow_html=True
)

# ============================================================
# TOP METRICS
# ============================================================

st.markdown(
    '<div class="section-title">📊 Market Snapshot</div>',
    unsafe_allow_html=True
)

m1, m2, m3, m4, m5, m6 = st.columns(6)

with m1:
    st.metric(
        "Spot",
        fmt_money(result["spot"])
    )

with m2:
    st.metric(
        "Market Bias",
        result["bias"]
    )

with m3:
    st.metric(
        "PCR",
        fmt_ratio(result["pcr"])
    )

with m4:
    st.metric(
        "OI Support",
        (
            f"{result['support']:,.0f}"
            if not pd.isna(result["support"])
            else "—"
        )
    )

with m5:
    st.metric(
        "OI Resistance",
        (
            f"{result['resistance']:,.0f}"
            if not pd.isna(result["resistance"])
            else "—"
        )
    )

with m6:

    rsi = result["technicals"]["rsi"]

    st.metric(
        "RSI",
        (
            f"{rsi:.1f}"
            if not pd.isna(rsi)
            else "—"
        )
    )

# ============================================================
# TRADE SIGNAL
# ============================================================

st.markdown(
    '<div class="section-title">🎯 Trade Decision</div>',
    unsafe_allow_html=True
)

action = result["action"]
direction = result["direction"]

if action == "CALL BUY":
    box_class = "trade-call"
elif action == "PUT BUY":
    box_class = "trade-put"
else:
    box_class = "trade-none"


selected = result["selected_option"]
plan = result["trade_plan"]

if selected and plan:

    st.markdown(
        f"""
<div class="{box_class}">

<div class="trade-action">
{action}
</div>

<div style="margin-top:8px;">
<strong>Instrument:</strong>
{result["symbol"]} {selected["strike"]:.0f}
{selected["type"]}
</div>

</div>
""",
        unsafe_allow_html=True
    )

    p1, p2, p3, p4, p5 = st.columns(5)

    with p1:
        st.metric(
            "Entry",
            fmt_money(plan["entry"])
        )

    with p2:
        st.metric(
            "Stop Loss",
            fmt_money(plan["sl"])
        )

    with p3:
        st.metric(
            "Target 1",
            fmt_money(plan["target1"])
        )

    with p4:
        st.metric(
            "Target 2",
            fmt_money(plan["target2"])
        )

    with p5:
        st.metric(
            "Risk / Reward",
            (
                f"1:{plan['rr']:.2f}"
                if not pd.isna(plan["rr"])
                else "—"
            )
        )

else:

    st.markdown(
        f"""
<div class="{box_class}">

<div class="trade-action">
NO TRADE
</div>

<div style="margin-top:8px;">
Current market conditions do not provide
a sufficiently aligned setup.
</div>

</div>
""",
        unsafe_allow_html=True
    )

# ============================================================
# OPTION DETAILS
# ============================================================

if selected:

    st.markdown(
        '<div class="section-title">📌 Selected Option</div>',
        unsafe_allow_html=True
    )

    o1, o2, o3, o4, o5, o6 = st.columns(6)

    with o1:
        st.metric(
            "Option",
            f"{selected['strike']:.0f} {selected['type']}"
        )

    with o2:
        st.metric(
            "Premium",
            fmt_money(selected["ltp"])
        )

    with o3:
        st.metric(
            "Delta",
            (
                f"{selected['delta']:.2f}"
                if not pd.isna(selected["delta"])
                else "—"
            )
        )

    with o4:
        st.metric(
            "IV",
            (
                f"{selected['iv']:.2f}"
                if not pd.isna(selected["iv"])
                else "—"
            )
        )

    with o5:
        st.metric(
            "PoP",
            (
                f"{selected['pop']:.1f}%"
                if not pd.isna(selected["pop"])
                else "—"
            )
        )

    with o6:
        st.metric(
            "OI",
            fmt_num(selected["oi"])
        )

# ============================================================
# ENTRY / EXIT RULES
# ============================================================

if plan:

    st.markdown(
        '<div class="section-title">⚡ Trade Management</div>',
        unsafe_allow_html=True
    )

    e1, e2 = st.columns(2)

    with e1:

        st.markdown(
            f"""
**Entry Trigger**

{plan["trigger"]}
"""
        )

    with e2:

        st.markdown(
            f"""
**Exit Rule**

{plan["exit_rule"]}
"""
        )

# ============================================================
# TECHNICAL ANALYSIS
# ============================================================

st.markdown(
    '<div class="section-title">📈 Technical Analysis</div>',
    unsafe_allow_html=True
)

t1, t2, t3, t4, t5, t6 = st.columns(6)

technical_map = [
    ("EMA 20", result["technicals"]["ema20"]),
    ("EMA 50", result["technicals"]["ema50"]),
    ("RSI", result["technicals"]["rsi"]),
    ("ATR", result["technicals"]["atr"]),
    ("Momentum", result["technicals"]["momentum"]),
    ("Volume Ratio", result["technicals"]["volume_ratio"])
]

for col, (label, value) in zip(
    [t1, t2, t3, t4, t5, t6],
    technical_map
):

    with col:

        if pd.isna(value):
            display = "—"

        elif label == "Momentum":
            display = f"{value:.2f}%"

        elif label == "Volume Ratio":
            display = f"{value:.2f}x"

        else:
            display = f"{value:.2f}"

        st.metric(
            label,
            display
        )

# ============================================================
# OPTION CHAIN
# ============================================================

st.markdown(
    '<div class="section-title">🔗 Live Option Chain</div>',
    unsafe_allow_html=True
)

chain = result["chain"].copy()

if not chain.empty:

    spot = result["spot"]

    chain["distance"] = abs(
        chain["strike"] - spot
    )

    display_chain = (
        chain
        .sort_values("distance")
        .head(15)
        .sort_values("strike")
        .copy()
    )

    option_table = pd.DataFrame(
        {
            "CALL OI": display_chain["call_oi"],
            "CALL ΔOI": (
                display_chain["call_oi"] -
                display_chain["call_prev_oi"]
            ),
            "CALL LTP": display_chain["call_ltp"],
            "CALL Delta": display_chain["call_delta"],
            "CALL IV": display_chain["call_iv"],
            "STRIKE": display_chain["strike"],
            "PUT IV": display_chain["put_iv"],
            "PUT Delta": display_chain["put_delta"],
            "PUT LTP": display_chain["put_ltp"],
            "PUT ΔOI": (
                display_chain["put_oi"] -
                display_chain["put_prev_oi"]
            ),
            "PUT OI": display_chain["put_oi"]
        }
    )

    st.dataframe(
        option_table,
        use_container_width=True,
        hide_index=True
    )

# ============================================================
# OI ANALYSIS
# ============================================================

st.markdown(
    '<div class="section-title">🧱 Open Interest Analysis</div>',
    unsafe_allow_html=True
)

oi1, oi2, oi3 = st.columns(3)

with oi1:

    st.metric(
        "Highest Call OI",
        (
            f"{chain.loc[chain['call_oi'].idxmax(), 'strike']:.0f}"
            if not chain.empty and chain["call_oi"].max() > 0
            else "—"
        )
    )

with oi2:

    st.metric(
        "Highest Put OI",
        (
            f"{chain.loc[chain['put_oi'].idxmax(), 'strike']:.0f}"
            if not chain.empty and chain["put_oi"].max() > 0
            else "—"
        )
    )

with oi3:

    total_call_oi = chain["call_oi"].sum()
    total_put_oi = chain["put_oi"].sum()

    st.metric(
        "Total OI PCR",
        (
            f"{total_put_oi / total_call_oi:.2f}"
            if total_call_oi > 0
            else "—"
        )
    )

# ============================================================
# OPTION COMPARISON
# ============================================================

st.markdown(
    '<div class="section-title">⚖️ ATM Option Comparison</div>',
    unsafe_allow_html=True
)

c1, c2 = st.columns(2)

call = result["call_option"]
put = result["put_option"]

with c1:

    if call:

        st.markdown("### 🟢 ATM Call")

        st.write(
            f"**Strike:** {call['strike']:.0f}"
        )

        st.write(
            f"**Premium:** {fmt_money(call['ltp'])}"
        )

        st.write(
            f"**Delta:** "
            f"{call['delta']:.2f}"
            if not pd.isna(call["delta"])
            else "**Delta:** —"
        )

        st.write(
            f"**IV:** "
            f"{call['iv']:.2f}"
            if not pd.isna(call["iv"])
            else "**IV:** —"
        )

        st.write(
            f"**PoP:** "
            f"{call['pop']:.1f}%"
            if not pd.isna(call["pop"])
            else "**PoP:** —"
        )

        st.write(
            f"**OI:** {fmt_num(call['oi'])}"
        )

    else:
        st.info("Call data unavailable.")

with c2:

    if put:

        st.markdown("### 🔴 ATM Put")

        st.write(
            f"**Strike:** {put['strike']:.0f}"
        )

        st.write(
            f"**Premium:** {fmt_money(put['ltp'])}"
        )

        st.write(
            f"**Delta:** "
            f"{put['delta']:.2f}"
            if not pd.isna(put["delta"])
            else "**Delta:** —"
        )

        st.write(
            f"**IV:** "
            f"{put['iv']:.2f}"
            if not pd.isna(put["iv"])
            else "**IV:** —"
        )

        st.write(
            f"**PoP:** "
            f"{put['pop']:.1f}%"
            if not pd.isna(put["pop"])
            else "**PoP:** —"
        )

        st.write(
            f"**OI:** {fmt_num(put['oi'])}"
        )

    else:
        st.info("Put data unavailable.")

# ============================================================
# MARKET ANALYSIS
# ============================================================

st.markdown(
    '<div class="section-title">🧠 Market Analysis</div>',
    unsafe_allow_html=True
)

analysis_text = []

if result["bias"] in [
    "Bullish",
    "Strong Bullish"
]:
    analysis_text.append(
        "Underlying structure is currently "
        "tilted toward the bullish side."
    )

elif result["bias"] in [
    "Bearish",
    "Strong Bearish"
]:
    analysis_text.append(
        "Underlying structure is currently "
        "tilted toward the bearish side."
    )

else:
    analysis_text.append(
        "Underlying structure is currently mixed "
        "and does not show a strong directional edge."
    )

if not pd.isna(result["pcr"]):

    if result["pcr"] > 1.20:
        analysis_text.append(
            f"PCR is {result['pcr']:.2f}, showing "
            "relatively higher Put OI than Call OI."
        )

    elif result["pcr"] < 0.80:
        analysis_text.append(
            f"PCR is {result['pcr']:.2f}, showing "
            "relatively higher Call OI than Put OI."
        )

    else:
        analysis_text.append(
            f"PCR is {result['pcr']:.2f}, indicating "
            "a relatively balanced OI structure."
        )

if not pd.isna(result["support"]):

    analysis_text.append(
        f"Major OI support is around "
        f"{result['support']:,.0f}."
    )

if not pd.isna(result["resistance"]):

    analysis_text.append(
        f"Major OI resistance is around "
        f"{result['resistance']:,.0f}."
    )

if not pd.isna(result["technicals"]["rsi"]):

    analysis_text.append(
        f"RSI is {result['technicals']['rsi']:.1f}."
    )

for item in analysis_text:
    st.write("• " + item)

# ============================================================
# HOW ENGINE THINKS
# ============================================================

with st.expander("ℹ️ How the Analysis Engine Works"):

    st.markdown(
        """
The application combines live Upstox market data with
rule-based technical and option-chain analysis.

### Data used

- Live underlying LTP
- Live option-chain LTP
- Call OI
- Put OI
- Change in OI
- PCR
- Bid / Ask
- Option volume
- Delta
- Gamma
- Theta
- Vega
- IV
- Probability of Profit
- Intraday OHLC
- EMA 20
- EMA 50
- RSI
- ATR
- Momentum
- Relative volume

### Signal logic

The engine checks multiple conditions before producing:

- CALL BUY
- PUT BUY
- NO TRADE

The application does not place orders.

### Risk management

The displayed Entry, Stop Loss, Target 1,
Target 2 and Risk/Reward are calculated from
the selected option premium and the selected
risk profile.

Always verify the live option price, liquidity,
spread and market conditions before taking a trade.
"""
    )

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "F&O PRO Trader Assistant • "
    "Upstox REST-only live-data architecture • "
    f"Auto-refresh: {REFRESH_SECONDS} seconds"
)

# ============================================================
# AUTO REFRESH
# ============================================================

time.sleep(0.1)

try:
    from streamlit_autorefresh import st_autorefresh

    st_autorefresh(
        interval=REFRESH_SECONDS * 1000,
        key="fo_live_refresh"
    )

except Exception:
    pass
