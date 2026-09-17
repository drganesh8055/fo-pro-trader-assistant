import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone, time
from zoneinfo import ZoneInfo


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="F&O Pro Trader Assistant",
    page_icon="📊",
    layout="wide",
)


# ============================================================
# CONSTANTS
# ============================================================

UPSTOX_BASE = "https://api.upstox.com"
IST = ZoneInfo("Asia/Kolkata")

RISK_PLANS = {
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
# SESSION STATE
# ============================================================

defaults = {
    "active_symbol": None,
    "active_risk": "Balanced",
    "active_result": None,
    "active_chain": None,
    "last_error": None,
    "last_successful_refresh": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# BASIC HELPERS
# ============================================================

def get_access_token():
    """
    Reads the Upstox access token from Streamlit Secrets.
    """
    token = st.secrets.get("UPSTOX_ACCESS_TOKEN", "")

    if not token:
        raise RuntimeError(
            "UPSTOX_ACCESS_TOKEN is missing from Streamlit Secrets."
        )

    return str(token).strip()


def upstox_get(endpoint, params=None):
    """
    Generic Upstox GET request.
    """
    token = get_access_token()

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    url = f"{UPSTOX_BASE}{endpoint}"

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=20,
    )

    if response.status_code != 200:
        try:
            detail = response.text
        except Exception:
            detail = "Unknown API error"

        raise RuntimeError(
            f"Upstox API error {response.status_code}: {detail}"
        )

    payload = response.json()

    if payload.get("status") not in (None, "success"):
        raise RuntimeError(
            f"Upstox API returned unsuccessful status: {payload}"
        )

    return payload


# ============================================================
# TIME HELPERS
# ============================================================

def format_iso_ist(value):
    """
    Converts an ISO timestamp to IST.
    """
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(IST).strftime(
            "%d-%b-%Y %H:%M:%S"
        )

    except Exception:
        return str(value)


def format_ms_ist(value):
    """
    Converts Unix milliseconds to IST.
    """
    if value in (None, "", 0, "0"):
        return None

    try:
        ms = int(float(value))

        dt = datetime.fromtimestamp(
            ms / 1000,
            tz=timezone.utc,
        )

        return dt.astimezone(IST).strftime(
            "%d-%b-%Y %H:%M:%S"
        )

    except Exception:
        return None


def parse_ms_timestamp(value):
    """
    Returns an aware datetime from Unix milliseconds.
    """
    if value in (None, "", 0, "0"):
        return None

    try:
        ms = int(float(value))

        return datetime.fromtimestamp(
            ms / 1000,
            tz=timezone.utc,
        ).astimezone(IST)

    except Exception:
        return None


def current_ist():
    return datetime.now(IST)


# ============================================================
# MARKET STATUS
# ============================================================

def get_market_status(last_trade_ms=None):
    """
    Equity/F&O NSE-style market-hours check.

    Regular market:
        Monday-Friday
        09:15 to 15:30 IST

    This is a time-window check only.
    Exchange holidays are not inferred here.
    """

    now = current_ist()

    if now.weekday() >= 5:
        return {
            "status": "MARKET CLOSED",
            "reason": "Weekend",
            "age_minutes": None,
        }

    market_open = time(9, 15)
    market_close = time(15, 30)

    if now.time() < market_open:
        return {
            "status": "MARKET CLOSED",
            "reason": "Before regular market hours",
            "age_minutes": None,
        }

    if now.time() > market_close:
        return {
            "status": "MARKET CLOSED",
            "reason": "After regular market hours",
            "age_minutes": None,
        }

    last_trade_dt = parse_ms_timestamp(last_trade_ms)

    if last_trade_dt is None:
        return {
            "status": "MARKET OPEN",
            "reason": "No last-trade timestamp available",
            "age_minutes": None,
        }

    age_seconds = (
        now - last_trade_dt
    ).total_seconds()

    age_minutes = max(0, age_seconds / 60)

    if age_minutes > 10:
        return {
            "status": "DATA STALE",
            "reason": (
                f"Last trade was approximately "
                f"{age_minutes:.1f} minutes ago"
            ),
            "age_minutes": age_minutes,
        }

    return {
        "status": "MARKET OPEN",
        "reason": "Recent market data received",
        "age_minutes": age_minutes,
    }


# ============================================================
# INSTRUMENT SEARCH
# ============================================================

def find_underlying(symbol):
    """
    Finds NSE equity/index instrument.
    """

    symbol = symbol.strip().upper()

    params = {
        "query": symbol,
        "exchanges": "NSE",
        "segments": "SECURITY",
        "page_number": 1,
        "records": 30,
    }

    payload = upstox_get(
        "/v2/instruments/search",
        params=params,
    )

    rows = payload.get("data", [])

    if not rows:
        raise RuntimeError(
            f"Could not find NSE instrument for {symbol}"
        )

    # Exact symbol first
    exact = [
        row
        for row in rows
        if str(row.get("trading_symbol", "")).upper()
        == symbol
    ]

    if exact:
        return exact[0]

    # Then exact short name
    exact_name = [
        row
        for row in rows
        if str(row.get("name", "")).upper()
        == symbol
    ]

    if exact_name:
        return exact_name[0]

    return rows[0]


# ============================================================
# FULL MARKET QUOTE V3
# ============================================================

def get_full_quote_v3(instrument_key):
    """
    Gets live full market snapshot from Upstox V3.
    """

    payload = upstox_get(
        "/v3/market-quote/quotes",
        params={
            "instrument_key": instrument_key
        },
    )

    data = payload.get("data", {})

    if not data:
        raise RuntimeError(
            "Upstox returned empty full market quote."
        )

    # Usually key is instrument_key.
    if instrument_key in data:
        return data[instrument_key]

    # Fallback
    first_value = next(iter(data.values()))

    if isinstance(first_value, dict):
        return first_value

    raise RuntimeError(
        "Unable to read Upstox market quote."
    )


# ============================================================
# OPTION CONTRACTS
# ============================================================

def get_option_contracts(underlying_key):
    """
    Gets option contracts for the underlying.
    """

    payload = upstox_get(
        "/v2/option/contract",
        params={
            "instrument_key": underlying_key
        },
    )

    return payload.get("data", [])


def get_nearest_expiry(contracts):
    """
    Finds nearest available expiry.
    """

    expiries = set()

    for row in contracts:
        expiry = row.get("expiry")

        if expiry:
            expiries.add(str(expiry))

    if not expiries:
        raise RuntimeError(
            "No option expiry found for this instrument."
        )

    today = current_ist().date()

    valid = []

    for expiry in expiries:
        try:
            dt = datetime.strptime(
                expiry,
                "%Y-%m-%d",
            ).date()

            if dt >= today:
                valid.append(dt)

        except Exception:
            pass

    if not valid:
        raise RuntimeError(
            "No future option expiry available."
        )

    return min(valid).strftime("%Y-%m-%d")


# ============================================================
# OPTION CHAIN
# ============================================================

def get_option_chain(
    underlying_key,
    expiry_date,
):
    """
    Gets option chain for selected expiry.
    """

    payload = upstox_get(
        "/v2/option/chain",
        params={
            "instrument_key": underlying_key,
            "expiry_date": expiry_date,
        },
    )

    return payload.get("data", [])


# ============================================================
# NORMALIZE OPTION CHAIN
# ============================================================

def normalize_chain(chain_data):
    """
    Converts Upstox option-chain response into a DataFrame.
    """

    rows = []

    for item in chain_data:

        strike = item.get("strike_price")
        spot = item.get("underlying_spot_price")

        call = item.get("call_options") or {}
        put = item.get("put_options") or {}

        call_md = call.get("market_data") or {}
        call_greek = call.get("option_greeks") or {}

        put_md = put.get("market_data") or {}
        put_greek = put.get("option_greeks") or {}

        call_oi = float(
            call_md.get("oi") or 0
        )

        put_oi = float(
            put_md.get("oi") or 0
        )

        call_prev_oi = float(
            call_md.get("prev_oi") or 0
        )

        put_prev_oi = float(
            put_md.get("prev_oi") or 0
        )

        rows.append(
            {
                "strike": float(strike or 0),
                "spot": float(spot or 0),

                "ce_ltp": float(
                    call_md.get("ltp") or 0
                ),

                "pe_ltp": float(
                    put_md.get("ltp") or 0
                ),

                "ce_oi": call_oi,
                "pe_oi": put_oi,

                "ce_prev_oi": call_prev_oi,
                "pe_prev_oi": put_prev_oi,

                "ce_chg_oi": (
                    call_oi - call_prev_oi
                ),

                "pe_chg_oi": (
                    put_oi - put_prev_oi
                ),

                "ce_volume": float(
                    call_md.get("volume") or 0
                ),

                "pe_volume": float(
                    put_md.get("volume") or 0
                ),

                "ce_iv": float(
                    call_greek.get("iv") or 0
                ),

                "pe_iv": float(
                    put_greek.get("iv") or 0
                ),

                "ce_delta": float(
                    call_greek.get("delta") or 0
                ),

                "pe_delta": float(
                    put_greek.get("delta") or 0
                ),

                "ce_pop": float(
                    call_greek.get("pop") or 0
                ),

                "pe_pop": float(
                    put_greek.get("pop") or 0
                ),

                "ce_bid": float(
                    call_md.get("bid_price") or 0
                ),

                "ce_ask": float(
                    call_md.get("ask_price") or 0
                ),

                "pe_bid": float(
                    put_md.get("bid_price") or 0
                ),

                "pe_ask": float(
                    put_md.get("ask_price") or 0
                ),

                "ce_instrument_key":
                    call.get("instrument_key"),

                "pe_instrument_key":
                    put.get("instrument_key"),
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError(
            "Option chain returned no usable rows."
        )

    return df


# ============================================================
# UNDERLYING MARKET CONTEXT
# ============================================================

def extract_market_context(quote):
    """
    Extracts price/trend information from Upstox V3 quote.
    """

    last_price = float(
        quote.get("last_price") or 0
    )

    prev_close = float(
        quote.get("prev_close_price")
        or quote.get("cp")
        or 0
    )

    average_price = float(
        quote.get("average_price") or 0
    )

    net_change = float(
        quote.get("net_change") or 0
    )

    volume = float(
        quote.get("volume") or 0
    )

    last_trade_time = quote.get(
        "last_trade_time"
    )

    ohlc = quote.get("ohlc") or {}

    open_price = 0.0
    high_price = 0.0
    low_price = 0.0

    # V3 may provide OHLC in different forms
    if isinstance(ohlc, dict):
        open_price = float(
            ohlc.get("open") or 0
        )

        high_price = float(
            ohlc.get("high") or 0
        )

        low_price = float(
            ohlc.get("low") or 0
        )

    elif isinstance(ohlc, list):

        daily = None

        for row in ohlc:
            if row.get("interval") == "1d":
                daily = row
                break

        if daily is None and ohlc:
            daily = ohlc[0]

        if daily:
            open_price = float(
                daily.get("open") or 0
            )

            high_price = float(
                daily.get("high") or 0
            )

            low_price = float(
                daily.get("low") or 0
            )

    change_pct = 0.0

    if prev_close > 0:
        change_pct = (
            (last_price - prev_close)
            / prev_close
        ) * 100

    price_vs_open_pct = 0.0

    if open_price > 0:
        price_vs_open_pct = (
            (last_price - open_price)
            / open_price
        ) * 100

    price_vs_avg_pct = 0.0

    if average_price > 0:
        price_vs_avg_pct = (
            (last_price - average_price)
            / average_price
        ) * 100

    range_position = 50.0

    if (
        high_price > 0
        and low_price > 0
        and high_price > low_price
    ):
        range_position = (
            (last_price - low_price)
            / (high_price - low_price)
        ) * 100

    return {
        "last_price": last_price,
        "prev_close": prev_close,
        "average_price": average_price,
        "net_change": net_change,
        "volume": volume,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "change_pct": change_pct,
        "price_vs_open_pct": price_vs_open_pct,
        "price_vs_avg_pct": price_vs_avg_pct,
        "range_position": range_position,
        "last_trade_time": last_trade_time,
    }


# ============================================================
# ANALYSIS ENGINE
# ============================================================

def analyze_chain(
    df,
    risk_profile,
    market_context,
):
    """
    Combines:
      - PCR
      - OI
      - Change in OI
      - Volume
      - OI walls
      - Underlying price change
      - Price vs open
      - Price vs average traded price
      - Day-range position

    The engine deliberately avoids forcing a trade
    when the evidence is conflicting.
    """

    spot = float(
        df["spot"].iloc[0]
    )

    # --------------------------------------------------------
    # PCR
    # --------------------------------------------------------

    total_call_oi = df["ce_oi"].sum()
    total_put_oi = df["pe_oi"].sum()

    if total_call_oi > 0:
        pcr = total_put_oi / total_call_oi
    else:
        pcr = 0.0

    # --------------------------------------------------------
    # OI WALLS
    # --------------------------------------------------------

    largest_call = df.loc[
        df["ce_oi"].idxmax()
    ]

    largest_put = df.loc[
        df["pe_oi"].idxmax()
    ]

    call_wall = float(
        largest_call["strike"]
    )

    put_wall = float(
        largest_put["strike"]
    )

    # --------------------------------------------------------
    # ATM
    # --------------------------------------------------------

    df = df.copy()

    df["distance"] = (
        (df["strike"] - spot).abs()
    )

    atm_row = df.loc[
        df["distance"].idxmin()
    ]

    atm_strike = float(
        atm_row["strike"]
    )

    # --------------------------------------------------------
    # NEAR ATM
    # --------------------------------------------------------

    lower = spot * 0.97
    upper = spot * 1.03

    near = df[
        (df["strike"] >= lower)
        & (df["strike"] <= upper)
    ].copy()

    if near.empty:
        near = df.copy()

    # --------------------------------------------------------
    # START SCORES
    # --------------------------------------------------------

    bull_score = 50.0
    bear_score = 50.0

    reasons_bull = []
    reasons_bear = []

    # --------------------------------------------------------
    # PCR
    # --------------------------------------------------------

    if pcr >= 1.20:

        bull_score += 10

        reasons_bull.append(
            f"PCR {pcr:.2f} shows stronger put OI relative to call OI."
        )

    elif pcr >= 1.05:

        bull_score += 5

        reasons_bull.append(
            f"PCR {pcr:.2f} is mildly supportive of bullish positioning."
        )

    elif pcr <= 0.80:

        bear_score += 10

        reasons_bear.append(
            f"PCR {pcr:.2f} shows stronger call OI relative to put OI."
        )

    elif pcr <= 0.95:

        bear_score += 5

        reasons_bear.append(
            f"PCR {pcr:.2f} is mildly supportive of bearish positioning."
        )

    # --------------------------------------------------------
    # CHANGE OI
    # --------------------------------------------------------

    near_call_chg = near["ce_chg_oi"].sum()
    near_put_chg = near["pe_chg_oi"].sum()

    if (
        near_put_chg > 0
        and near_put_chg > near_call_chg
    ):

        bull_score += 8

        reasons_bull.append(
            "Near-ATM put OI addition is stronger than call-side OI addition."
        )

    elif (
        near_call_chg > 0
        and near_call_chg > near_put_chg
    ):

        bear_score += 8

        reasons_bear.append(
            "Near-ATM call OI addition is stronger than put-side OI addition."
        )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    near_call_volume = near["ce_volume"].sum()
    near_put_volume = near["pe_volume"].sum()

    if near_call_volume > 0 or near_put_volume > 0:

        if near_call_volume > near_put_volume * 1.15:

            bear_score += 5

            reasons_bear.append(
                "Call-side volume is stronger near ATM."
            )

        elif near_put_volume > near_call_volume * 1.15:

            bull_score += 5

            reasons_bull.append(
                "Put-side volume is stronger near ATM."
            )

    # --------------------------------------------------------
    # OI WALL LOCATION
    # --------------------------------------------------------

    if put_wall < spot:
        bull_score += 4

        reasons_bull.append(
            f"Largest put OI wall is below spot at {put_wall:.0f}."
        )

    elif put_wall > spot:
        bear_score += 3

        reasons_bear.append(
            f"Largest put OI wall is above spot at {put_wall:.0f}."
        )

    if call_wall > spot:
        bear_score += 4

        reasons_bear.append(
            f"Largest call OI wall is above spot at {call_wall:.0f}."
        )

    elif call_wall < spot:
        bull_score += 3

        reasons_bull.append(
            f"Largest call OI wall is below spot at {call_wall:.0f}."
        )

    # --------------------------------------------------------
    # UNDERLYING PRICE CHANGE
    # --------------------------------------------------------

    change_pct = market_context.get(
        "change_pct",
        0.0,
    )

    if change_pct >= 0.50:

        bull_score += 10

        reasons_bull.append(
            f"Underlying is up {change_pct:.2f}% from previous close."
        )

    elif change_pct >= 0.15:

        bull_score += 5

        reasons_bull.append(
            f"Underlying is modestly positive at +{change_pct:.2f}%."
        )

    elif change_pct <= -0.50:

        bear_score += 10

        reasons_bear.append(
            f"Underlying is down {abs(change_pct):.2f}% from previous close."
        )

    elif change_pct <= -0.15:

        bear_score += 5

        reasons_bear.append(
            f"Underlying is modestly negative at {change_pct:.2f}%."
        )

    # --------------------------------------------------------
    # PRICE VS OPEN
    # --------------------------------------------------------

    price_vs_open = market_context.get(
        "price_vs_open_pct",
        0.0,
    )

    if price_vs_open >= 0.30:

        bull_score += 5

        reasons_bull.append(
            f"Price is {price_vs_open:.2f}% above today's open."
        )

    elif price_vs_open <= -0.30:

        bear_score += 5

        reasons_bear.append(
            f"Price is {abs(price_vs_open):.2f}% below today's open."
        )

    # --------------------------------------------------------
    # PRICE VS AVERAGE TRADED PRICE
    # --------------------------------------------------------

    price_vs_avg = market_context.get(
        "price_vs_avg_pct",
        0.0,
    )

    if price_vs_avg >= 0.25:

        bull_score += 5

        reasons_bull.append(
            "Price is above the average traded price."
        )

    elif price_vs_avg <= -0.25:

        bear_score += 5

        reasons_bear.append(
            "Price is below the average traded price."
        )

    # --------------------------------------------------------
    # DAY RANGE POSITION
    # --------------------------------------------------------

    range_position = market_context.get(
        "range_position",
        50.0,
    )

    if range_position >= 70:

        bull_score += 4

        reasons_bull.append(
            "Price is trading in the upper part of today's range."
        )

    elif range_position <= 30:

        bear_score += 4

        reasons_bear.append(
            "Price is trading in the lower part of today's range."
        )

    # --------------------------------------------------------
    # CAP SCORES
    # --------------------------------------------------------

    bull_score = min(
        max(bull_score, 0),
        100,
    )

    bear_score = min(
        max(bear_score, 0),
        100,
    )

    score_difference = abs(
        bull_score - bear_score
    )

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    if bull_score > bear_score:
        direction = "CE"
    elif bear_score > bull_score:
        direction = "PE"
    else:
        direction = None

    # --------------------------------------------------------
    # TRADE DECISION
    # --------------------------------------------------------

    # Strong alignment
    if (
        max(bull_score, bear_score) >= 72
        and score_difference >= 14
    ):
        decision = "TRADE CANDIDATE"

    # Moderate alignment
    elif (
        max(bull_score, bear_score) >= 62
        and score_difference >= 8
    ):
        decision = "WATCH"

    else:
        decision = "NO TRADE"

    # --------------------------------------------------------
    # SELECT OPTION
    # --------------------------------------------------------

    selected = None

    if direction == "CE":

        candidates = near[
            (near["ce_ltp"] > 0)
            & (near["ce_volume"] > 0)
            & near["ce_instrument_key"].notna()
        ].copy()

        if not candidates.empty:

            candidates["option_distance"] = (
                candidates["strike"] - spot
            ).abs()

            selected = candidates.sort_values(
                [
                    "option_distance",
                    "ce_volume",
                ],
                ascending=[
                    True,
                    False,
                ],
            ).iloc[0]

            option_ltp = float(
                selected["ce_ltp"]
            )

            option_bid = float(
                selected["ce_bid"]
            )

            option_ask = float(
                selected["ce_ask"]
            )

            option_delta = float(
                selected["ce_delta"]
            )

            option_iv = float(
                selected["ce_iv"]
            )

            option_pop = float(
                selected["ce_pop"]
            )

            option_oi = float(
                selected["ce_oi"]
            )

            option_chg_oi = float(
                selected["ce_chg_oi"]
            )

            option_volume = float(
                selected["ce_volume"]
            )

            option_key = selected[
                "ce_instrument_key"
            ]

            option_type = "CALL"

    elif direction == "PE":

        candidates = near[
            (near["pe_ltp"] > 0)
            & (near["pe_volume"] > 0)
            & near["pe_instrument_key"].notna()
        ].copy()

        if not candidates.empty:

            candidates["option_distance"] = (
                candidates["strike"] - spot
            ).abs()

            selected = candidates.sort_values(
                [
                    "option_distance",
                    "pe_volume",
                ],
                ascending=[
                    True,
                    False,
                ],
            ).iloc[0]

            option_ltp = float(
                selected["pe_ltp"]
            )

            option_bid = float(
                selected["pe_bid"]
            )

            option_ask = float(
                selected["pe_ask"]
            )

            option_delta = float(
                selected["pe_delta"]
            )

            option_iv = float(
                selected["pe_iv"]
            )

            option_pop = float(
                selected["pe_pop"]
            )

            option_oi = float(
                selected["pe_oi"]
            )

            option_chg_oi = float(
                selected["pe_chg_oi"]
            )

            option_volume = float(
                selected["pe_volume"]
            )

            option_key = selected[
                "pe_instrument_key"
            ]

            option_type = "PUT"

    # --------------------------------------------------------
    # SPREAD CHECK
    # --------------------------------------------------------

    spread_pct = None

    if selected is not None:

        if option_bid > 0 and option_ask > 0:

            mid = (
                option_bid + option_ask
            ) / 2

            if mid > 0:

                spread_pct = (
                    (option_ask - option_bid)
                    / mid
                ) * 100

                # Very wide spread = poor execution quality
                if spread_pct > 10:

                    decision = "NO TRADE"

                    if option_type == "CALL":
                        reasons_bear.append(
                            f"Selected CALL spread is wide at {spread_pct:.1f}%."
                        )
                    else:
                        reasons_bull.append(
                            f"Selected PUT spread is wide at {spread_pct:.1f}%."
                        )

    # --------------------------------------------------------
    # ENTRY
    # --------------------------------------------------------

    if selected is not None:

        if (
            option_bid > 0
            and option_ask > 0
        ):
            entry = (
                option_bid + option_ask
            ) / 2

        else:
            entry = option_ltp

        strike = float(
            selected["strike"]
        )

        risk = RISK_PLANS[
            risk_profile
        ]

        stop_loss = entry * (
            1 - risk["sl"]
        )

        target_1 = entry * (
            1 + risk["t1"]
        )

        target_2 = entry * (
            1 + risk["t2"]
        )

        if decision == "TRADE CANDIDATE":
            entry_status = (
                "ENTER NOW / CONFIRM TRIGGER"
            )

        elif decision == "WATCH":
            entry_status = (
                "WAIT FOR CONFIRMATION"
            )

        else:
            entry_status = "NO TRADE"

    else:

        option_ltp = 0
        option_bid = 0
        option_ask = 0
        option_delta = 0
        option_iv = 0
        option_pop = 0
        option_oi = 0
        option_chg_oi = 0
        option_volume = 0
        option_key = None
        option_type = None

        entry = None
        strike = None
        stop_loss = None
        target_1 = None
        target_2 = None
        entry_status = "NO TRADE"
        spread_pct = None

    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    return {
        "spot": spot,

        "pcr": pcr,

        "put_wall": put_wall,
        "call_wall": call_wall,
        "atm_strike": atm_strike,

        "bull_score": round(
            bull_score,
            1,
        ),

        "bear_score": round(
            bear_score,
            1,
        ),

        "score_difference": round(
            score_difference,
            1,
        ),

        "direction": direction,

        "decision": decision,

        "option_type": option_type,

        "strike": strike,

        "option_key": option_key,

        "option_ltp": option_ltp,

        "option_bid": option_bid,

        "option_ask": option_ask,

        "option_delta": option_delta,

        "option_iv": option_iv,

        "option_pop": option_pop,

        "option_oi": option_oi,

        "option_chg_oi": option_chg_oi,

        "option_volume": option_volume,

        "entry": entry,

        "stop_loss": stop_loss,

        "target_1": target_1,

        "target_2": target_2,

        "entry_status": entry_status,

        "spread_pct": spread_pct,

        "market_context": market_context,

        "bull_reasons": reasons_bull,

        "bear_reasons": reasons_bear,
    }


# ============================================================
# COMPLETE ANALYSIS
# ============================================================

def run_analysis(
    symbol,
    risk_profile,
):
    """
    Main analysis pipeline.
    """

    # --------------------------------------------------------
    # UNDERLYING
    # --------------------------------------------------------

    underlying = find_underlying(
        symbol
    )

    underlying_key = underlying.get(
        "instrument_key"
    )

    if not underlying_key:
        raise RuntimeError(
            "Upstox did not return an underlying instrument key."
        )

    # --------------------------------------------------------
    # FULL MARKET QUOTE
    # --------------------------------------------------------

    underlying_quote = get_full_quote_v3(
        underlying_key
    )

    market_context = extract_market_context(
        underlying_quote
    )

    # --------------------------------------------------------
    # MARKET STATUS
    # --------------------------------------------------------

    market_status = get_market_status(
        market_context.get(
            "last_trade_time"
        )
    )

    # --------------------------------------------------------
    # EXPIRY
    # --------------------------------------------------------

    contracts = get_option_contracts(
        underlying_key
    )

    expiry = get_nearest_expiry(
        contracts
    )

    # --------------------------------------------------------
    # OPTION CHAIN
    # --------------------------------------------------------

    chain_data = get_option_chain(
        underlying_key,
        expiry,
    )

    df = normalize_chain(
        chain_data
    )

    # --------------------------------------------------------
    # ANALYZE
    # --------------------------------------------------------

    result = analyze_chain(
        df,
        risk_profile,
        market_context,
    )

    # --------------------------------------------------------
    # MARKET STATUS OVERRIDE
    # --------------------------------------------------------

    if market_status["status"] == "MARKET CLOSED":

        result["decision"] = "MARKET CLOSED"
        result["entry_status"] = (
            "WAIT FOR MARKET OPEN"
        )

    elif market_status["status"] == "DATA STALE":

        result["decision"] = "DATA STALE"
        result["entry_status"] = (
            "WAIT FOR FRESH DATA"
        )

    # --------------------------------------------------------
    # UPSTOX SNAPSHOT TIME
    # --------------------------------------------------------

    result["upstox_snapshot_time"] = (
        format_iso_ist(
            underlying_quote.get(
                "timestamp"
            )
        )
    )

    result["underlying_last_trade_time"] = (
        format_ms_ist(
            underlying_quote.get(
                "last_trade_time"
            )
        )
    )

    result["app_fetch_time"] = (
        current_ist().strftime(
            "%d-%b-%Y %H:%M:%S"
        )
    )

    result["market_status"] = (
        market_status["status"]
    )

    result["market_status_reason"] = (
        market_status["reason"]
    )

    result["expiry"] = expiry

    # --------------------------------------------------------
    # SELECTED OPTION TIMESTAMP
    # --------------------------------------------------------

    selected_option_snapshot = None
    selected_option_last_trade = None

    selected_option_key = result.get(
        "option_key"
    )

    if selected_option_key:

        try:

            selected_quote = get_full_quote_v3(
                selected_option_key
            )

            selected_option_snapshot = (
                format_iso_ist(
                    selected_quote.get(
                        "timestamp"
                    )
                )
            )

            selected_option_last_trade = (
                format_ms_ist(
                    selected_quote.get(
                        "last_trade_time"
                    )
                )
            )

        except Exception:
            # Do not fail the entire analysis
            # just because option timestamp
            # could not be retrieved.
            pass

    result[
        "selected_option_snapshot_time"
    ] = selected_option_snapshot

    result[
        "selected_option_last_trade_time"
    ] = selected_option_last_trade

    return result, df


# ============================================================
# UI HEADER
# ============================================================

st.title(
    "📊 F&O Pro Trader Assistant"
)

st.caption(
    "Live Upstox market data • OI • PCR • Change OI • "
    "Price trend • Delta • IV • Probability of Profit"
)


# ============================================================
# INPUT AREA
# ============================================================

col1, col2, col3 = st.columns(
    [2, 1, 1]
)

with col1:

    symbol_input = st.text_input(
        "Enter NSE Stock / Index",
        value=(
            st.session_state.active_symbol
            or "KOTAKBANK"
        ),
        placeholder="Example: KOTAKBANK",
    ).strip().upper()

with col2:

    risk_input = st.selectbox(
        "Risk Profile",
        [
            "Conservative",
            "Balanced",
            "Aggressive",
        ],
        index=[
            "Conservative",
            "Balanced",
            "Aggressive",
        ].index(
            st.session_state.active_risk
        ),
    )

with col3:

    st.write("")
    st.write("")

    analyze_clicked = st.button(
        "🔍 Analyze",
        use_container_width=True,
        type="primary",
    )


# ============================================================
# BUTTON ACTION
# ============================================================

if analyze_clicked:

    if not symbol_input:

        st.session_state.last_error = (
            "Please enter a stock or index."
        )

    else:

        try:

            with st.spinner(
                f"Analyzing {symbol_input}..."
            ):

                result, chain = run_analysis(
                    symbol_input,
                    risk_input,
                )

            st.session_state.active_symbol = (
                symbol_input
            )

            st.session_state.active_risk = (
                risk_input
            )

            st.session_state.active_result = (
                result
            )

            st.session_state.active_chain = (
                chain
            )

            st.session_state.last_error = None

            st.session_state.last_successful_refresh = (
                current_ist().strftime(
                    "%d-%b-%Y %H:%M:%S"
                )
            )

            st.rerun()

        except Exception as exc:

            st.session_state.last_error = (
                str(exc)
            )


# ============================================================
# MANUAL REFRESH
# ============================================================

refresh_col1, refresh_col2 = st.columns(
    [1, 5]
)

with refresh_col1:

    refresh_clicked = st.button(
        "🔄 Refresh Now",
        use_container_width=True,
    )

if refresh_clicked:

    active_symbol = (
        st.session_state.active_symbol
    )

    active_risk = (
        st.session_state.active_risk
    )

    if active_symbol:

        try:

            with st.spinner(
                "Refreshing live market data..."
            ):

                result, chain = run_analysis(
                    active_symbol,
                    active_risk,
                )

            st.session_state.active_result = (
                result
            )

            st.session_state.active_chain = (
                chain
            )

            st.session_state.last_error = None

            st.session_state.last_successful_refresh = (
                current_ist().strftime(
                    "%d-%b-%Y %H:%M:%S"
                )
            )

            st.rerun()

        except Exception as exc:

            # Keep the previous successful data.
            st.session_state.last_error = (
                str(exc)
            )


# ============================================================
# ERROR DISPLAY
# ============================================================

if st.session_state.last_error:

    st.error(
        st.session_state.last_error
    )


# ============================================================
# DISPLAY FUNCTION
# ============================================================

def display_analysis():

    result = (
        st.session_state.active_result
    )

    chain = (
        st.session_state.active_chain
    )

    if result is None or chain is None:

        st.info(
            "Enter a stock/index and click Analyze."
        )

        return

    # --------------------------------------------------------
    # MARKET STATUS
    # --------------------------------------------------------

    market_status = result.get(
        "market_status",
        "UNKNOWN",
    )

    if market_status == "MARKET OPEN":

        st.success(
            f"🟢 MARKET OPEN — {result.get('market_status_reason', '')}"
        )

    elif market_status == "MARKET CLOSED":

        st.info(
            f"🔵 MARKET CLOSED — {result.get('market_status_reason', '')}"
        )

    elif market_status == "DATA STALE":

        st.warning(
            f"🟠 DATA MAY BE STALE — {result.get('market_status_reason', '')}"
        )

    # --------------------------------------------------------
    # LIVE DATA TIMESTAMP
    # --------------------------------------------------------

    st.markdown(
        "### 🕐 Live Data Status"
    )

    time1, time2, time3, time4 = st.columns(
        4
    )

    with time1:

        st.metric(
            "Upstox Snapshot",
            result.get(
                "upstox_snapshot_time"
            )
            or "N/A",
        )

    with time2:

        st.metric(
            "Underlying Last Trade",
            result.get(
                "underlying_last_trade_time"
            )
            or "N/A",
        )

    with time3:

        st.metric(
            "App Fetch",
            result.get(
                "app_fetch_time"
            )
            or "N/A",
        )

    with time4:

        st.metric(
            "Expiry",
            result.get(
                "expiry"
            )
            or "N/A",
        )

    # --------------------------------------------------------
    # MARKET SNAPSHOT
    # --------------------------------------------------------

    st.markdown(
        "### 📈 Market Snapshot"
    )

    context = result[
        "market_context"
    ]

    c1, c2, c3, c4, c5 = st.columns(
        5
    )

    with c1:

        st.metric(
            "Live Price",
            f"₹{context['last_price']:,.2f}",
        )

    with c2:

        st.metric(
            "Change",
            f"{context['change_pct']:+.2f}%",
        )

    with c3:

        st.metric(
            "PCR",
            f"{result['pcr']:.2f}",
        )

    with c4:

        st.metric(
            "Put OI Wall",
            f"{result['put_wall']:.0f}",
        )

    with c5:

        st.metric(
            "Call OI Wall",
            f"{result['call_wall']:.0f}",
        )

    c6, c7, c8, c9 = st.columns(
        4
    )

    with c6:

        st.metric(
            "Price vs Open",
            f"{context['price_vs_open_pct']:+.2f}%",
        )

    with c7:

        st.metric(
            "Price vs Avg",
            f"{context['price_vs_avg_pct']:+.2f}%",
        )

    with c8:

        st.metric(
            "Day Range Position",
            f"{context['range_position']:.0f}%",
        )

    with c9:

        st.metric(
            "Volume",
            f"{context['volume']:,.0f}",
        )

    # --------------------------------------------------------
    # SCORES
    # --------------------------------------------------------

    st.markdown(
        "### 🎯 Signal Strength"
    )

    s1, s2, s3 = st.columns(
        3
    )

    with s1:

        st.metric(
            "Bull Score",
            f"{result['bull_score']:.0f}/100",
        )

    with s2:

        st.metric(
            "Bear Score",
            f"{result['bear_score']:.0f}/100",
        )

    with s3:

        st.metric(
            "Signal Gap",
            f"{result['score_difference']:.0f}",
        )

    # --------------------------------------------------------
    # DECISION
    # --------------------------------------------------------

    st.markdown(
        "### 🚦 Trade Decision"
    )

    decision = result[
        "decision"
    ]

    if decision == "TRADE CANDIDATE":

        if result["direction"] == "CE":

            st.success(
                "🟢 CALL — BUY SETUP"
            )

            st.write(
                "Bullish signals are sufficiently aligned."
            )

        elif result["direction"] == "PE":

            st.success(
                "🔴 PUT — BUY SETUP"
            )

            st.write(
                "Bearish signals are sufficiently aligned."
            )

    elif decision == "WATCH":

        if result["direction"] == "CE":

            st.warning(
                "🟡 CALL — WAIT FOR CONFIRMATION"
            )

        elif result["direction"] == "PE":

            st.warning(
                "🟡 PUT — WAIT FOR CONFIRMATION"
            )

        st.write(
            "Signals are pointing in one direction, "
            "but confirmation is still required."
        )

    elif decision == "MARKET CLOSED":

        st.info(
            "🔵 MARKET CLOSED"
        )

        st.write(
            "Do not treat the displayed setup as a live entry."
        )

    elif decision == "DATA STALE":

        st.warning(
            "🟠 DATA STALE"
        )

        st.write(
            "Fresh market data is required before considering an entry."
        )

    else:

        st.info(
            "⚪ NO TRADE"
        )

        st.write(
            "Current signals are not sufficiently aligned."
        )

    # --------------------------------------------------------
    # TRADE PLAN
    # --------------------------------------------------------

    if result.get("option_type"):

        st.markdown(
            "### 💰 Trade Plan"
        )

        p1, p2, p3, p4 = st.columns(
            4
        )

        with p1:

            st.metric(
                "Action",
                (
                    f"BUY {result['option_type']}"
                    if result["decision"]
                    == "TRADE CANDIDATE"
                    else
                    f"WAIT {result['option_type']}"
                ),
            )

        with p2:

            st.metric(
                "Strike",
                f"{result['strike']:.0f}",
            )

        with p3:

            if result["entry"] is not None:

                st.metric(
                    "Entry",
                    f"₹{result['entry']:.2f}",
                )

        with p4:

            st.metric(
                "Probability of Profit",
                (
                    f"{result['option_pop']:.2f}%"
                    if result["option_pop"] > 0
                    else "N/A"
                ),
            )

        p5, p6, p7, p8 = st.columns(
            4
        )

        with p5:

            if result["stop_loss"] is not None:

                st.metric(
                    "Stop Loss",
                    f"₹{result['stop_loss']:.2f}",
                )

        with p6:

            if result["target_1"] is not None:

                st.metric(
                    "Target 1",
                    f"₹{result['target_1']:.2f}",
                )

        with p7:

            if result["target_2"] is not None:

                st.metric(
                    "Target 2",
                    f"₹{result['target_2']:.2f}",
                )

        with p8:

            st.metric(
                "Entry Status",
                result["entry_status"],
            )

        p9, p10, p11, p12 = st.columns(
            4
        )

        with p9:

            st.metric(
                "Delta",
                f"{result['option_delta']:.3f}",
            )

        with p10:

            st.metric(
                "IV",
                f"{result['option_iv']:.2f}%",
            )

        with p11:

            st.metric(
                "Option OI",
                f"{result['option_oi']:,.0f}",
            )

        with p12:

            st.metric(
                "Chg OI",
                f"{result['option_chg_oi']:+,.0f}",
            )

        if result.get("spread_pct") is not None:

            st.caption(
                f"Bid/Ask spread: "
                f"{result['spread_pct']:.2f}%"
            )

        if result.get(
            "selected_option_last_trade_time"
        ):

            st.caption(
                "Selected option last trade: "
                f"{result['selected_option_last_trade_time']}"
            )

    # --------------------------------------------------------
    # REASONS
    # --------------------------------------------------------

    st.markdown(
        "### 🧠 Why the Engine Reached This Result"
    )

    r1, r2 = st.columns(
        2
    )

    with r1:

        st.markdown(
            "**Bullish Factors**"
        )

        if result["bull_reasons"]:

            for reason in result[
                "bull_reasons"
            ]:

                st.write(
                    f"🟢 {reason}"
                )

        else:

            st.write(
                "No strong bullish factor."
            )

    with r2:

        st.markdown(
            "**Bearish Factors**"
        )

        if result["bear_reasons"]:

            for reason in result[
                "bear_reasons"
            ]:

                st.write(
                    f"🔴 {reason}"
                )

        else:

            st.write(
                "No strong bearish factor."
            )

    # --------------------------------------------------------
    # OI SUPPORT / RESISTANCE
    # --------------------------------------------------------

    st.markdown(
        "### 🧱 OI Support / Resistance"
    )

    o1, o2, o3 = st.columns(
        3
    )

    with o1:

        st.metric(
            "Put Support",
            f"{result['put_wall']:.0f}",
        )

    with o2:

        st.metric(
            "ATM",
            f"{result['atm_strike']:.0f}",
        )

    with o3:

        st.metric(
            "Call Resistance",
            f"{result['call_wall']:.0f}",
        )

    # --------------------------------------------------------
    # OPTION CHAIN
    # --------------------------------------------------------

    st.markdown(
        "### 📋 Live Option Chain"
    )

    display_df = chain.copy()

    display_df = display_df[
        [
            "strike",

            "ce_ltp",
            "ce_oi",
            "ce_chg_oi",
            "ce_volume",
            "ce_iv",
            "ce_delta",
            "ce_pop",

            "pe_pop",
            "pe_delta",
            "pe_iv",
            "pe_volume",
            "pe_chg_oi",
            "pe_oi",
            "pe_ltp",
        ]
    ].copy()

    display_df.columns = [
        "Strike",

        "CE LTP",
        "CE OI",
        "CE Chg OI",
        "CE Volume",
        "CE IV",
        "CE Delta",
        "CE PoP",

        "PE PoP",
        "PE Delta",
        "PE IV",
        "PE Volume",
        "PE Chg OI",
        "PE OI",
        "PE LTP",
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    st.markdown(
        "### 🛡️ Data & Signal Quality"
    )

    st.info(
        "Probability of Profit (PoP), Delta and IV are "
        "taken from Upstox's option-chain response. "
        "PoP is not calculated from our Bull/Bear score."
    )

    st.caption(
        "The engine uses OI, Change OI, PCR, volume, "
        "OI walls and underlying price context. "
        "A conflicting signal produces NO TRADE rather "
        "than forcing a CALL or PUT."
    )


# ============================================================
# INITIAL DISPLAY
# ============================================================

display_analysis()


# ============================================================
# AUTO REFRESH
# ============================================================

def auto_refresh():

    active_symbol = (
        st.session_state.active_symbol
    )

    active_risk = (
        st.session_state.active_risk
    )

    if not active_symbol:
        return

    try:

        result, chain = run_analysis(
            active_symbol,
            active_risk,
        )

        st.session_state.active_result = (
            result
        )

        st.session_state.active_chain = (
            chain
        )

        st.session_state.last_error = None

        st.session_state.last_successful_refresh = (
            current_ist().strftime(
                "%d-%b-%Y %H:%M:%S"
            )
        )

    except Exception as exc:

        # Preserve last successful data.
        st.session_state.last_error = (
            str(exc)
        )


# Streamlit modern fragment API
try:

    fragment = st.fragment

except AttributeError:

    fragment = st.experimental_fragment


@fragment(
    run_every="30s"
)
def live_refresh():

    auto_refresh()


live_refresh()
