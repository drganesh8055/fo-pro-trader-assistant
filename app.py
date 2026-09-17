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
    page_icon="📈",
    layout="wide"
)


# ============================================================
# CONSTANTS
# ============================================================

UPSTOX_BASE = "https://api.upstox.com"

IST = ZoneInfo("Asia/Kolkata")

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

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

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        return float(value)

    except Exception:
        return default


def first_available(*values, default=0.0):
    for value in values:
        if value is not None:
            try:
                return float(value)
            except Exception:
                continue

    return default


# ============================================================
# UPSTOX AUTHENTICATION
# ============================================================

def get_access_token():

    token = st.secrets.get(
        "UPSTOX_ACCESS_TOKEN",
        ""
    )

    if not token:
        raise RuntimeError(
            "UPSTOX_ACCESS_TOKEN is missing from Streamlit Secrets."
        )

    return token


# ============================================================
# GENERIC UPSTOX GET
# ============================================================

def upstox_get(path, params=None):

    token = get_access_token()

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    url = UPSTOX_BASE + path

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=20,
    )

    if response.status_code != 200:

        raise RuntimeError(
            f"Upstox API error {response.status_code}: "
            f"{response.text[:500]}"
        )

    return response.json()


# ============================================================
# TIME HELPERS
# ============================================================

def format_iso_ist(value):

    if not value:
        return None

    try:

        dt = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(IST)

    except Exception:
        return None


def format_ms_ist(value):

    if value is None:
        return None

    try:

        return datetime.fromtimestamp(
            int(value) / 1000,
            tz=timezone.utc
        ).astimezone(IST)

    except Exception:
        return None


def display_dt(dt):

    if not dt:
        return "Unavailable"

    return dt.strftime(
        "%d-%b-%Y %H:%M:%S IST"
    )


# ============================================================
# MARKET STATUS
# ============================================================

def get_market_status(last_trade_dt):

    now = datetime.now(IST)

    current_date = now.date()
    current_time = now.time()

    # Weekend
    if now.weekday() >= 5:

        return {
            "status": "MARKET CLOSED",
            "label": "🔵 MARKET CLOSED",
            "detail": "Weekend",
        }

    # Before market open
    if current_time < MARKET_OPEN:

        return {
            "status": "MARKET CLOSED",
            "label": "🔵 MARKET CLOSED",
            "detail": "Before NSE market open",
        }

    # After market close
    if current_time > MARKET_CLOSE:

        return {
            "status": "MARKET CLOSED",
            "label": "🔵 MARKET CLOSED",
            "detail": "NSE regular market session has ended",
        }

    # During market hours
    if last_trade_dt:

        if last_trade_dt.date() == current_date:

            age_seconds = (
                now - last_trade_dt
            ).total_seconds()

            if age_seconds <= 120:

                return {
                    "status": "LIVE",
                    "label": "🟢 MARKET OPEN — LIVE",
                    "detail": "Recent underlying trade received",
                }

            else:

                return {
                    "status": "OPEN_STALE",
                    "label": "🟡 MARKET OPEN — NO RECENT TRADE",
                    "detail": (
                        f"Latest underlying trade was "
                        f"{int(age_seconds // 60)} minutes ago"
                    ),
                }

    return {
        "status": "OPEN_NO_TRADE",
        "label": "🟡 MARKET OPEN — NO RECENT TRADE",
        "detail": "No underlying trade reported today",
    }


# ============================================================
# FIND UNDERLYING INSTRUMENT
# ============================================================

def find_underlying(symbol):

    result = upstox_get(
        "/v2/instruments/search",
        params={
            "query": symbol,
            "segments": "EQ,INDEX",
            "page_number": 1,

            # IMPORTANT:
            # Upstox maximum is 30.
            "records": 30,
        },
    )

    rows = result.get("data") or []

    if not rows:

        raise RuntimeError(
            f"Could not find underlying instrument for {symbol}."
        )

    symbol_upper = symbol.upper()

    # Exact trading symbol
    exact = [
        x for x in rows
        if str(
            x.get("trading_symbol", "")
        ).upper()
        == symbol_upper
    ]

    if exact:
        return exact[0]

    # Exact short name
    exact_name = [
        x for x in rows
        if str(
            x.get("short_name", "")
        ).upper()
        == symbol_upper
    ]

    if exact_name:
        return exact_name[0]

    return rows[0]


# ============================================================
# FULL MARKET QUOTE V3
# ============================================================

def get_full_quote_v3(instrument_key):

    result = upstox_get(
        "/v3/market-quote/quotes",
        params={
            "instrument_key": instrument_key
        },
    )

    rows = result.get("data") or {}

    if not rows:

        raise RuntimeError(
            "Upstox returned no full market quote."
        )

    return next(
        iter(rows.values())
    )


# ============================================================
# EXTRACT UNDERLYING MARKET DATA
# ============================================================

def extract_underlying_data(quote):

    ohlc = quote.get("ohlc") or {}

    live_price = first_available(
        quote.get("last_price"),
        quote.get("ltp"),
        default=0
    )

    open_price = safe_float(
        ohlc.get("open")
    )

    high_price = safe_float(
        ohlc.get("high")
    )

    low_price = safe_float(
        ohlc.get("low")
    )

    session_close = safe_float(
        ohlc.get("close")
    )

    previous_close = first_available(
        quote.get("prev_close_price"),
        quote.get("reference_price"),
        default=0
    )

    average_price = safe_float(
        quote.get("average_price")
    )

    volume = first_available(
        quote.get("volume"),
        ohlc.get("volume"),
        default=0
    )

    net_change = safe_float(
        quote.get("net_change")
    )

    oi = safe_float(
        quote.get("oi")
    )

    previous_oi = safe_float(
        quote.get("previous_oi")
    )

    oi_change = (
        oi - previous_oi
        if previous_oi > 0
        else 0
    )

    if previous_close > 0:

        day_change_pct = (
            net_change
            / previous_close
        ) * 100

    else:

        day_change_pct = 0

    if (
        high_price > 0
        and low_price > 0
        and high_price > low_price
    ):

        range_position = (
            (live_price - low_price)
            / (high_price - low_price)
        ) * 100

    else:

        range_position = 50

    price_vs_open_pct = 0

    if open_price > 0:

        price_vs_open_pct = (
            (live_price - open_price)
            / open_price
        ) * 100

    price_vs_avg_pct = 0

    if average_price > 0:

        price_vs_avg_pct = (
            (live_price - average_price)
            / average_price
        ) * 100

    return {
        "live_price": live_price,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "session_close": session_close,
        "previous_close": previous_close,
        "average_price": average_price,
        "volume": volume,
        "net_change": net_change,
        "day_change_pct": day_change_pct,
        "oi": oi,
        "previous_oi": previous_oi,
        "oi_change": oi_change,
        "range_position": range_position,
        "price_vs_open_pct": price_vs_open_pct,
        "price_vs_avg_pct": price_vs_avg_pct,
    }


# ============================================================
# OPTION CONTRACTS
# ============================================================

def get_option_contracts(instrument_key):

    result = upstox_get(
        "/v2/option/contract",
        params={
            "instrument_key": instrument_key
        },
    )

    rows = result.get("data") or []

    if not rows:

        raise RuntimeError(
            "Upstox returned no option contracts."
        )

    return rows


# ============================================================
# FIND NEAREST EXPIRY
# ============================================================

def nearest_expiry(contracts):

    today = datetime.now(
        IST
    ).date()

    expiries = []

    for row in contracts:

        expiry = row.get("expiry")

        if not expiry:
            continue

        try:

            expiry_date = datetime.strptime(
                str(expiry),
                "%Y-%m-%d"
            ).date()

            if expiry_date >= today:

                expiries.append(
                    expiry_date
                )

        except Exception:
            continue

    if not expiries:

        raise RuntimeError(
            "No future option expiry found."
        )

    return min(expiries)


# ============================================================
# OPTION CHAIN
# ============================================================

def get_option_chain(
    instrument_key,
    expiry_date
):

    result = upstox_get(
        "/v2/option/chain",
        params={
            "instrument_key": instrument_key,
            "expiry_date": expiry_date.strftime(
                "%Y-%m-%d"
            ),
        },
    )

    rows = result.get("data") or []

    if not rows:

        raise RuntimeError(
            "Upstox returned no option-chain data."
        )

    return rows


# ============================================================
# NORMALIZE OPTION CHAIN
# ============================================================

def normalize_chain(rows):

    normalized = []

    for row in rows:

        strike = first_available(
            row.get("strike_price"),
            row.get("strike"),
            default=0
        )

        spot = first_available(
            row.get("underlying_spot_price"),
            row.get("underlying_price"),
            default=0
        )

        # Upstox documentation currently uses
        # call_options / put_options.
        # We also support the older/current structure
        # used by the existing application.

        call = (
            row.get("call_options")
            or row.get("call")
            or {}
        )

        put = (
            row.get("put_options")
            or row.get("put")
            or {}
        )

        call_market = (
            call.get("market_data")
            or {}
        )

        put_market = (
            put.get("market_data")
            or {}
        )

        call_greeks = (
            call.get("option_greeks")
            or {}
        )

        put_greeks = (
            put.get("option_greeks")
            or {}
        )

        ce_ltp = safe_float(
            call_market.get("ltp")
        )

        pe_ltp = safe_float(
            put_market.get("ltp")
        )

        ce_oi = safe_float(
            call_market.get("oi")
        )

        pe_oi = safe_float(
            put_market.get("oi")
        )

        ce_prev_oi = safe_float(
            call_market.get("prev_oi")
        )

        pe_prev_oi = safe_float(
            put_market.get("prev_oi")
        )

        ce_chg_oi = (
            ce_oi - ce_prev_oi
        )

        pe_chg_oi = (
            pe_oi - pe_prev_oi
        )

        ce_volume = safe_float(
            call_market.get("volume")
        )

        pe_volume = safe_float(
            put_market.get("volume")
        )

        ce_iv = safe_float(
            call_greeks.get("iv")
        )

        pe_iv = safe_float(
            put_greeks.get("iv")
        )

        ce_delta = safe_float(
            call_greeks.get("delta")
        )

        pe_delta = safe_float(
            put_greeks.get("delta")
        )

        ce_pop = safe_float(
            call_greeks.get("pop")
        )

        pe_pop = safe_float(
            put_greeks.get("pop")
        )

        ce_bid = safe_float(
            call_market.get("bid_price")
        )

        ce_ask = safe_float(
            call_market.get("ask_price")
        )

        pe_bid = safe_float(
            put_market.get("bid_price")
        )

        pe_ask = safe_float(
            put_market.get("ask_price")
        )

        ce_key = call.get(
            "instrument_key"
        )

        pe_key = put.get(
            "instrument_key"
        )

        normalized.append({

            "strike": strike,
            "spot": spot,

            "ce_ltp": ce_ltp,
            "ce_oi": ce_oi,
            "ce_prev_oi": ce_prev_oi,
            "ce_chg_oi": ce_chg_oi,
            "ce_volume": ce_volume,
            "ce_iv": ce_iv,
            "ce_delta": ce_delta,
            "ce_pop": ce_pop,
            "ce_bid": ce_bid,
            "ce_ask": ce_ask,
            "ce_key": ce_key,

            "pe_ltp": pe_ltp,
            "pe_oi": pe_oi,
            "pe_prev_oi": pe_prev_oi,
            "pe_chg_oi": pe_chg_oi,
            "pe_volume": pe_volume,
            "pe_iv": pe_iv,
            "pe_delta": pe_delta,
            "pe_pop": pe_pop,
            "pe_bid": pe_bid,
            "pe_ask": pe_ask,
            "pe_key": pe_key,
        })

    if not normalized:

        raise RuntimeError(
            "Unable to normalize option-chain data."
        )

    return pd.DataFrame(
        normalized
    )


# ============================================================
# ANALYZE OPTION CHAIN + UNDERLYING
# ============================================================

def analyze_chain(
    df,
    risk_profile,
    underlying
):

    df = df.copy()

    if df.empty:

        raise RuntimeError(
            "Option chain is empty."
        )

    # ========================================================
    # SPOT
    # ========================================================

    spot = safe_float(
        underlying["live_price"]
    )

    if spot <= 0:

        spot_values = (
            df["spot"]
            .dropna()
        )

        if (
            spot_values.empty
            or float(spot_values.iloc[0]) <= 0
        ):

            raise RuntimeError(
                "Invalid underlying spot price."
            )

        spot = float(
            spot_values.iloc[0]
        )

    # ========================================================
    # ATM
    # ========================================================

    df["distance"] = (
        df["strike"] - spot
    ).abs()

    atm_row = df.loc[
        df["distance"].idxmin()
    ]

    atm_strike = float(
        atm_row["strike"]
    )

    # ========================================================
    # PCR
    # ========================================================

    total_put_oi = (
        df["pe_oi"].sum()
    )

    total_call_oi = (
        df["ce_oi"].sum()
    )

    if total_call_oi > 0:

        pcr = (
            total_put_oi
            / total_call_oi
        )

    else:

        pcr = 0

    # ========================================================
    # OI WALLS
    # ========================================================

    put_wall_row = df.loc[
        df["pe_oi"].idxmax()
    ]

    call_wall_row = df.loc[
        df["ce_oi"].idxmax()
    ]

    put_wall = float(
        put_wall_row["strike"]
    )

    call_wall = float(
        call_wall_row["strike"]
    )

    # ========================================================
    # NEAR ATM
    # ========================================================

    lower = spot * 0.97
    upper = spot * 1.03

    near = df[
        (df["strike"] >= lower)
        &
        (df["strike"] <= upper)
    ].copy()

    if near.empty:

        near = df.copy()

    # ========================================================
    # START SCORES
    # ========================================================

    bull = 50
    bear = 50

    reasons = []

    bullish_factors = []
    bearish_factors = []

    # ========================================================
    # 1. UNDERLYING DAY CHANGE
    # ========================================================

    day_change_pct = underlying[
        "day_change_pct"
    ]

    if day_change_pct >= 1.0:

        bull += 10

        bullish_factors.append(
            "Strong positive day change"
        )

        reasons.append(
            f"Underlying is up {day_change_pct:.2f}% "
            "from previous close."
        )

    elif day_change_pct >= 0.30:

        bull += 6

        bullish_factors.append(
            "Positive day change"
        )

        reasons.append(
            f"Underlying is up {day_change_pct:.2f}% "
            "from previous close."
        )

    elif day_change_pct <= -1.0:

        bear += 10

        bearish_factors.append(
            "Strong negative day change"
        )

        reasons.append(
            f"Underlying is down "
            f"{abs(day_change_pct):.2f}% "
            "from previous close."
        )

    elif day_change_pct <= -0.30:

        bear += 6

        bearish_factors.append(
            "Negative day change"
        )

        reasons.append(
            f"Underlying is down "
            f"{abs(day_change_pct):.2f}% "
            "from previous close."
        )

    else:

        reasons.append(
            "Underlying day change is relatively small."
        )

    # ========================================================
    # 2. PRICE VS OPEN
    # ========================================================

    price_vs_open_pct = underlying[
        "price_vs_open_pct"
    ]

    if price_vs_open_pct >= 0.40:

        bull += 6

        bullish_factors.append(
            "Price above opening price"
        )

        reasons.append(
            f"Price is {price_vs_open_pct:.2f}% "
            "above today's open."
        )

    elif price_vs_open_pct <= -0.40:

        bear += 6

        bearish_factors.append(
            "Price below opening price"
        )

        reasons.append(
            f"Price is {abs(price_vs_open_pct):.2f}% "
            "below today's open."
        )

    # ========================================================
    # 3. PRICE VS AVERAGE PRICE
    # ========================================================

    price_vs_avg_pct = underlying[
        "price_vs_avg_pct"
    ]

    if price_vs_avg_pct >= 0.30:

        bull += 5

        bullish_factors.append(
            "Price above average traded price"
        )

        reasons.append(
            "Price is above the day's average traded price."
        )

    elif price_vs_avg_pct <= -0.30:

        bear += 5

        bearish_factors.append(
            "Price below average traded price"
        )

        reasons.append(
            "Price is below the day's average traded price."
        )

    # ========================================================
    # 4. DAY RANGE POSITION
    # ========================================================

    range_position = underlying[
        "range_position"
    ]

    if range_position >= 70:

        bull += 5

        bullish_factors.append(
            "Price in upper part of day's range"
        )

        reasons.append(
            "Price is trading in the upper part "
            "of today's range."
        )

    elif range_position <= 30:

        bear += 5

        bearish_factors.append(
            "Price in lower part of day's range"
        )

        reasons.append(
            "Price is trading in the lower part "
            "of today's range."
        )

    # ========================================================
    # 5. UNDERLYING OI RELATIONSHIP
    # ========================================================

    underlying_oi = underlying[
        "oi"
    ]

    previous_oi = underlying[
        "previous_oi"
    ]

    if (
        underlying_oi > 0
        and previous_oi > 0
    ):

        oi_change_pct = (
            (underlying_oi - previous_oi)
            / previous_oi
        ) * 100

        # Price up + OI up
        if (
            day_change_pct > 0.30
            and oi_change_pct > 2
        ):

            bull += 8

            bullish_factors.append(
                "Long buildup"
            )

            reasons.append(
                "Price is rising while underlying OI "
                "is also increasing — long buildup signal."
            )

        # Price down + OI up
        elif (
            day_change_pct < -0.30
            and oi_change_pct > 2
        ):

            bear += 8

            bearish_factors.append(
                "Short buildup"
            )

            reasons.append(
                "Price is falling while underlying OI "
                "is increasing — short buildup signal."
            )

        # Price up + OI down
        elif (
            day_change_pct > 0.30
            and oi_change_pct < -2
        ):

            bull += 6

            bullish_factors.append(
                "Short covering"
            )

            reasons.append(
                "Price is rising while underlying OI "
                "is falling — possible short covering."
            )

        # Price down + OI down
        elif (
            day_change_pct < -0.30
            and oi_change_pct < -2
        ):

            bear += 6

            bearish_factors.append(
                "Long unwinding"
            )

            reasons.append(
                "Price is falling while underlying OI "
                "is falling — possible long unwinding."
            )

    # ========================================================
    # 6. PCR
    # ========================================================

    if pcr >= 1.20:

        bull += 8

        bullish_factors.append(
            "Strong PCR support"
        )

        reasons.append(
            f"PCR {pcr:.2f} indicates stronger "
            "put-side OI relative to call-side OI."
        )

    elif pcr >= 1.00:

        bull += 4

        bullish_factors.append(
            "PCR mildly supportive"
        )

        reasons.append(
            f"PCR {pcr:.2f} is mildly supportive."
        )

    elif pcr <= 0.75:

        bear += 8

        bearish_factors.append(
            "Strong call-side PCR pressure"
        )

        reasons.append(
            f"PCR {pcr:.2f} indicates stronger "
            "call-side OI pressure."
        )

    elif pcr < 1.00:

        bear += 4

        bearish_factors.append(
            "PCR mildly bearish"
        )

        reasons.append(
            f"PCR {pcr:.2f} is mildly bearish."
        )

    else:

        reasons.append(
            "PCR is relatively balanced."
        )

    # ========================================================
    # 7. CHANGE OI NEAR ATM
    # ========================================================

    near_put_chg = (
        near["pe_chg_oi"].sum()
    )

    near_call_chg = (
        near["ce_chg_oi"].sum()
    )

    if near_put_chg > near_call_chg:

        bull += 8

        bullish_factors.append(
            "Stronger near-spot put OI addition"
        )

        reasons.append(
            "Near-spot put OI addition is stronger."
        )

    elif near_call_chg > near_put_chg:

        bear += 8

        bearish_factors.append(
            "Stronger near-spot call OI addition"
        )

        reasons.append(
            "Near-spot call OI addition is stronger."
        )

    else:

        reasons.append(
            "Near-spot change in OI is balanced."
        )

    # ========================================================
    # 8. OPTION VOLUME
    # ========================================================

    near_put_volume = (
        near["pe_volume"].sum()
    )

    near_call_volume = (
        near["ce_volume"].sum()
    )

    if near_put_volume > near_call_volume:

        bull += 5

        bullish_factors.append(
            "Stronger put volume"
        )

        reasons.append(
            "Put-side option volume is stronger near spot."
        )

    elif near_call_volume > near_put_volume:

        bear += 5

        bearish_factors.append(
            "Stronger call volume"
        )

        reasons.append(
            "Call-side option volume is stronger near spot."
        )

    # ========================================================
    # 9. PUT WALL
    # ========================================================

    if put_wall < spot:

        bull += 4

        bullish_factors.append(
            "Put OI support below spot"
        )

        reasons.append(
            f"Largest put OI wall is at "
            f"{put_wall:.0f}, below spot."
        )

    elif put_wall > spot:

        bear += 4

        bearish_factors.append(
            "Put OI wall above spot"
        )

        reasons.append(
            f"Largest put OI wall is at "
            f"{put_wall:.0f}, above spot."
        )

    # ========================================================
    # 10. CALL WALL
    # ========================================================

    if call_wall > spot:

        bear += 4

        bearish_factors.append(
            "Call OI resistance above spot"
        )

        reasons.append(
            f"Largest call OI wall is at "
            f"{call_wall:.0f}, above spot."
        )

    elif call_wall < spot:

        bull += 4

        bullish_factors.append(
            "Call OI wall below spot"
        )

        reasons.append(
            f"Largest call OI wall is at "
            f"{call_wall:.0f}, below spot."
        )

    # ========================================================
    # LIMIT SCORES
    # ========================================================

    bull = min(
        100,
        max(0, bull)
    )

    bear = min(
        100,
        max(0, bear)
    )

    score_gap = abs(
        bull - bear
    )

    # ========================================================
    # DIRECTION
    # ========================================================

    if bull > bear:

        direction = "CE"

    elif bear > bull:

        direction = "PE"

    else:

        direction = "NONE"

    # ========================================================
    # ALIGNMENT
    # ========================================================

    bullish_count = len(
        bullish_factors
    )

    bearish_count = len(
        bearish_factors
    )

    alignment_count = max(
        bullish_count,
        bearish_count
    )

    # ========================================================
    # PRELIMINARY ACTION
    # ========================================================

    if direction == "CE":

        if (
            bull >= 72
            and score_gap >= 16
            and bullish_count >= 4
        ):

            action = "TRADE CANDIDATE"

        elif (
            bull >= 60
            and score_gap >= 9
            and bullish_count >= 3
        ):

            action = "WATCH"

        else:

            action = "NO TRADE"

    elif direction == "PE":

        if (
            bear >= 72
            and score_gap >= 16
            and bearish_count >= 4
        ):

            action = "TRADE CANDIDATE"

        elif (
            bear >= 60
            and score_gap >= 9
            and bearish_count >= 3
        ):

            action = "WATCH"

        else:

            action = "NO TRADE"

    else:

        action = "NO TRADE"

    # ========================================================
    # CONFLICT REASON
    # ========================================================

    if score_gap < 16:

        reasons.append(
            f"Directional conflict remains: "
            f"Bull {bull} vs Bear {bear} "
            f"(gap {score_gap})."
        )

    if alignment_count < 4:

        reasons.append(
            "Not enough independent signals are aligned "
            "for a strong trade candidate."
        )

    # ========================================================
    # SELECT OPTION
    # ========================================================

    selected = None

    option_ltp = None
    option_bid = None
    option_ask = None
    delta = None
    iv = None
    pop = None
    oi = None
    chg_oi = None
    volume = None
    option_key = None

    if direction == "CE":

        candidates = near[
            (near["ce_ltp"] > 0)
            &
            (near["ce_volume"] > 0)
        ].copy()

        if not candidates.empty:

            candidates["atm_distance"] = (
                candidates["strike"]
                - atm_strike
            ).abs()

            candidates = candidates.sort_values(
                [
                    "atm_distance",
                    "ce_volume"
                ],
                ascending=[
                    True,
                    False
                ]
            )

            selected = candidates.iloc[0]

            option_ltp = safe_float(
                selected["ce_ltp"]
            )

            option_bid = safe_float(
                selected["ce_bid"]
            )

            option_ask = safe_float(
                selected["ce_ask"]
            )

            delta = safe_float(
                selected["ce_delta"]
            )

            iv = safe_float(
                selected["ce_iv"]
            )

            pop = safe_float(
                selected["ce_pop"]
            )

            oi = safe_float(
                selected["ce_oi"]
            )

            chg_oi = safe_float(
                selected["ce_chg_oi"]
            )

            volume = safe_float(
                selected["ce_volume"]
            )

            option_key = selected[
                "ce_key"
            ]

    elif direction == "PE":

        candidates = near[
            (near["pe_ltp"] > 0)
            &
            (near["pe_volume"] > 0)
        ].copy()

        if not candidates.empty:

            candidates["atm_distance"] = (
                candidates["strike"]
                - atm_strike
            ).abs()

            candidates = candidates.sort_values(
                [
                    "atm_distance",
                    "pe_volume"
                ],
                ascending=[
                    True,
                    False
                ]
            )

            selected = candidates.iloc[0]

            option_ltp = safe_float(
                selected["pe_ltp"]
            )

            option_bid = safe_float(
                selected["pe_bid"]
            )

            option_ask = safe_float(
                selected["pe_ask"]
            )

            delta = safe_float(
                selected["pe_delta"]
            )

            iv = safe_float(
                selected["pe_iv"]
            )

            pop = safe_float(
                selected["pe_pop"]
            )

            oi = safe_float(
                selected["pe_oi"]
            )

            chg_oi = safe_float(
                selected["pe_chg_oi"]
            )

            volume = safe_float(
                selected["pe_volume"]
            )

            option_key = selected[
                "pe_key"
            ]

    # ========================================================
    # OPTION TRADE PLAN
    # ========================================================

    selected_strike = None
    entry = None
    stop_loss = None
    target1 = None
    target2 = None
    spread_pct = None

    entry_status = "NO TRADE"

    if selected is not None:

        selected_strike = float(
            selected["strike"]
        )

        if (
            option_bid is not None
            and option_ask is not None
            and option_bid > 0
            and option_ask > 0
        ):

            entry = (
                option_bid
                + option_ask
            ) / 2

            spread_pct = (
                (option_ask - option_bid)
                / entry
            ) * 100

        else:

            entry = option_ltp

        # Risk plan
        plan = RISK_PLANS[
            risk_profile
        ]

        if entry and entry > 0:

            stop_loss = (
                entry
                * (1 - plan["sl"])
            )

            target1 = (
                entry
                * (1 + plan["t1"])
            )

            target2 = (
                entry
                * (1 + plan["t2"])
            )

        # Wide spread protection
        if (
            spread_pct is not None
            and spread_pct > 8
        ):

            action = "NO TRADE"

            reasons.append(
                f"Option bid/ask spread is wide "
                f"at {spread_pct:.2f}%. "
                "This reduces execution quality."
            )

        # Entry status
        if action == "TRADE CANDIDATE":

            entry_status = (
                "ENTER NOW / CONFIRM TRIGGER"
            )

        elif action == "WATCH":

            entry_status = (
                "WAIT FOR CONFIRMATION"
            )

        elif action == "MARKET CLOSED":

            entry_status = (
                "MARKET CLOSED"
            )

        else:

            entry_status = "NO TRADE"

    # ========================================================
    # BIAS
    # ========================================================

    if bull - bear >= 16:

        bias = "BULLISH"

    elif bear - bull >= 16:

        bias = "BEARISH"

    else:

        bias = "NEUTRAL"

    # ========================================================
    # RETURN
    # ========================================================

    return {

        "spot": spot,
        "atm_strike": atm_strike,

        "pcr": pcr,

        "put_wall": put_wall,
        "call_wall": call_wall,

        "bull_score": bull,
        "bear_score": bear,
        "score_gap": score_gap,

        "bias": bias,
        "action": action,
        "direction": direction,

        "bullish_count": bullish_count,
        "bearish_count": bearish_count,

        "selected_strike": selected_strike,

        "option_ltp": option_ltp,
        "entry": entry,

        "stop_loss": stop_loss,
        "target1": target1,
        "target2": target2,

        "pop": pop,
        "delta": delta,
        "iv": iv,

        "oi": oi,
        "chg_oi": chg_oi,
        "volume": volume,

        "option_key": option_key,

        "spread_pct": spread_pct,

        "entry_status": entry_status,

        "reasons": reasons,

        "day_change_pct": underlying[
            "day_change_pct"
        ],

        "open": underlying[
            "open"
        ],

        "high": underlying[
            "high"
        ],

        "low": underlying[
            "low"
        ],

        "average_price": underlying[
            "average_price"
        ],

        "underlying_volume": underlying[
            "volume"
        ],

        "underlying_oi": underlying[
            "oi"
        ],

        "underlying_previous_oi": underlying[
            "previous_oi"
        ],

        "underlying_oi_change": underlying[
            "oi_change"
        ],

        "price_vs_open_pct": underlying[
            "price_vs_open_pct"
        ],

        "price_vs_avg_pct": underlying[
            "price_vs_avg_pct"
        ],

        "range_position": underlying[
            "range_position"
        ],
    }


# ============================================================
# MAIN ANALYSIS
# ============================================================

def run_analysis(
    symbol,
    risk_profile
):

    # --------------------------------------------------------
    # FIND UNDERLYING
    # --------------------------------------------------------

    underlying_instrument = find_underlying(
        symbol
    )

    underlying_key = underlying_instrument.get(
        "instrument_key"
    )

    if not underlying_key:

        raise RuntimeError(
            "Underlying instrument key was not found."
        )

    # --------------------------------------------------------
    # LIVE V3 QUOTE
    # --------------------------------------------------------

    quote = get_full_quote_v3(
        underlying_key
    )

    snapshot_dt = format_iso_ist(
        quote.get("timestamp")
    )

    last_trade_dt = format_ms_ist(
        quote.get("last_trade_time")
    )

    underlying = extract_underlying_data(
        quote
    )

    live_price = underlying[
        "live_price"
    ]

    if live_price <= 0:

        raise RuntimeError(
            "Upstox returned an invalid live price."
        )

    # --------------------------------------------------------
    # MARKET STATUS
    # --------------------------------------------------------

    market_status = get_market_status(
        last_trade_dt
    )

    # --------------------------------------------------------
    # OPTION CONTRACTS
    # --------------------------------------------------------

    contracts = get_option_contracts(
        underlying_key
    )

    expiry_date = nearest_expiry(
        contracts
    )

    # --------------------------------------------------------
    # OPTION CHAIN
    # --------------------------------------------------------

    chain_rows = get_option_chain(
        underlying_key,
        expiry_date
    )

    df = normalize_chain(
        chain_rows
    )

    # Use V3 live price
    df["spot"] = live_price

    # --------------------------------------------------------
    # ANALYZE
    # --------------------------------------------------------

    result = analyze_chain(
        df,
        risk_profile,
        underlying
    )

    # --------------------------------------------------------
    # MARKET CLOSED OVERRIDE
    # --------------------------------------------------------

    if market_status["status"] == "MARKET CLOSED":

        result["action"] = (
            "MARKET CLOSED"
        )

        result["entry_status"] = (
            "MARKET CLOSED"
        )

        result["reasons"].insert(
            0,
            "NSE regular market session is currently closed. "
            "Latest available data is being displayed."
        )

    # --------------------------------------------------------
    # EXPIRY
    # --------------------------------------------------------

    result["expiry"] = expiry_date

    today = datetime.now(
        IST
    ).date()

    result["expiry_days"] = (
        expiry_date - today
    ).days

    result["symbol"] = (
        symbol.upper()
    )

    result["underlying_key"] = (
        underlying_key
    )

    result["upstox_snapshot_time"] = (
        snapshot_dt
    )

    result["underlying_last_trade_time"] = (
        last_trade_dt
    )

    result["app_fetch_time"] = (
        datetime.now(IST)
    )

    result["market_status"] = (
        market_status["status"]
    )

    result["market_status_label"] = (
        market_status["label"]
    )

    result["market_status_detail"] = (
        market_status["detail"]
    )

    # Underlying quote details
    result["underlying_open"] = (
        underlying["open"]
    )

    result["underlying_high"] = (
        underlying["high"]
    )

    result["underlying_low"] = (
        underlying["low"]
    )

    result["underlying_previous_close"] = (
        underlying["previous_close"]
    )

    result["underlying_average_price"] = (
        underlying["average_price"]
    )

    result["underlying_net_change"] = (
        underlying["net_change"]
    )

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

        except Exception:
            pass

    result[
        "selected_option_snapshot_time"
    ] = selected_option_snapshot

    result[
        "selected_option_last_trade_time"
    ] = selected_option_last_trade

    return result, df


# ============================================================
# HEADER
# ============================================================

st.title(
    "📈 F&O Pro Trader Assistant"
)

st.caption(
    "Live Upstox market data • Multi-factor F&O analysis • "
    "Entry / SL / Target • No automatic order placement"
)


# ============================================================
# INPUT AREA
# ============================================================

col1, col2, col3 = st.columns(
    [2, 1, 1]
)

with col1:

    symbol_input = st.text_input(
        "Enter F&O Stock / Index",
        value=(
            st.session_state.active_symbol
            or "KOTAKBANK"
        ),
        placeholder=(
            "Example: KOTAKBANK, "
            "RELIANCE, SBIN, NIFTY"
        ),
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

    analyze_button = st.button(
        "🔍 ANALYZE",
        type="primary",
        use_container_width=True,
    )


# ============================================================
# ANALYZE BUTTON
# ============================================================

if analyze_button:

    if not symbol_input:

        st.error(
            "Please enter a stock or index symbol."
        )

    else:

        st.session_state.active_symbol = (
            symbol_input
        )

        st.session_state.active_risk = (
            risk_input
        )

        st.session_state.active_result = None
        st.session_state.active_chain = None
        st.session_state.last_error = None

        st.rerun()


# ============================================================
# FRAGMENT SUPPORT
# ============================================================

fragment_decorator = getattr(
    st,
    "fragment",
    None
)

if fragment_decorator is None:

    fragment_decorator = getattr(
        st,
        "experimental_fragment",
        None
    )


# ============================================================
# LIVE ANALYSIS
# ============================================================

if fragment_decorator is None:

    st.error(
        "Your Streamlit version does not support "
        "automatic 30-second refresh. "
        "Please update Streamlit to version 1.37 or newer."
    )

else:

    @fragment_decorator(
        run_every="30s"
    )
    def render_live_analysis():

        active_symbol = (
            st.session_state.active_symbol
        )

        active_risk = (
            st.session_state.active_risk
        )

        if not active_symbol:

            st.info(
                "Enter an F&O stock/index above "
                "and click ANALYZE."
            )

            return

        # ----------------------------------------------------
        # AUTO REFRESH HEADER
        # ----------------------------------------------------

        top1, top2 = st.columns(
            [4, 1]
        )

        with top1:

            st.info(
                f"🔄 **AUTO-REFRESH ON** • "
                f"Refreshing **{active_symbol}** "
                f"every 30 seconds"
            )

        with top2:

            refresh_now = st.button(
                "🔄 Refresh Now",
                use_container_width=True,
            )

        # ----------------------------------------------------
        # RUN ANALYSIS
        # ----------------------------------------------------

        should_refresh = (
            refresh_now
            or
            st.session_state.active_result is None
        )

        if should_refresh:

            try:

                result, chain = run_analysis(
                    active_symbol,
                    active_risk
                )

                st.session_state.active_result = (
                    result
                )

                st.session_state.active_chain = (
                    chain
                )

                st.session_state.last_error = None

                st.session_state.last_successful_refresh = (
                    datetime.now(IST)
                )

            except Exception as exc:

                st.session_state.last_error = str(
                    exc
                )

        result = (
            st.session_state.active_result
        )

        chain = (
            st.session_state.active_chain
        )

        # ----------------------------------------------------
        # ERROR
        # ----------------------------------------------------

        if result is None:

            st.error(
                "❌ Unable to fetch live data."
            )

            if st.session_state.last_error:

                st.code(
                    st.session_state.last_error
                )

            return

        if st.session_state.last_error:

            st.warning(
                "⚠️ Automatic refresh encountered a "
                "temporary problem. Showing the last "
                "successful data."
            )

            st.caption(
                "Refresh error: "
                + st.session_state.last_error
            )

        # ====================================================
        # MARKET STATUS
        # ====================================================

        st.subheader(
            "📡 Market Status"
        )

        status_col1, status_col2, status_col3 = st.columns(
            3
        )

        with status_col1:

            if result["market_status"] == "LIVE":

                st.success(
                    result["market_status_label"]
                )

            elif result["market_status"] == "MARKET CLOSED":

                st.info(
                    result["market_status_label"]
                )

            else:

                st.warning(
                    result["market_status_label"]
                )

        with status_col2:

            st.caption(
                result["market_status_detail"]
            )

        with status_col3:

            st.caption(
                "Auto-refresh: every 30 seconds"
            )

        # ====================================================
        # TIMESTAMP
        # ====================================================

        snapshot_text = display_dt(
            result.get(
                "upstox_snapshot_time"
            )
        )

        underlying_last_trade_text = display_dt(
            result.get(
                "underlying_last_trade_time"
            )
        )

        app_fetch_text = display_dt(
            result.get(
                "app_fetch_time"
            )
        )

        selected_option_last_trade_text = display_dt(
            result.get(
                "selected_option_last_trade_time"
            )
        )

        if result["market_status"] == "LIVE":

            st.success(
                f"🟢 **LIVE UPSTOX SNAPSHOT** • "
                f"{snapshot_text}"
            )

        elif result["market_status"] == "MARKET CLOSED":

            st.info(
                f"🔵 **LATEST AVAILABLE UPSTOX DATA** • "
                f"{snapshot_text}"
            )

        else:

            st.warning(
                f"🟡 **UPSTOX DATA AVAILABLE — "
                f"CHECK LAST TRADE TIME** • "
                f"{snapshot_text}"
            )

        time_col1, time_col2, time_col3 = st.columns(
            3
        )

        with time_col1:

            st.metric(
                "Underlying Last Trade",
                underlying_last_trade_text
            )

        with time_col2:

            st.metric(
                "App Fetch Time",
                app_fetch_text
            )

        with time_col3:

            st.metric(
                "Selected Option Last Trade",
                selected_option_last_trade_text
            )

        # ====================================================
        # UNDERLYING MARKET DATA
        # ====================================================

        st.subheader(
            "📊 Underlying Market Data"
        )

        u1, u2, u3, u4, u5, u6 = st.columns(
            6
        )

        with u1:

            st.metric(
                "Live Price",
                f"₹{result['spot']:.2f}"
            )

        with u2:

            st.metric(
                "Day Change",
                f"{result['day_change_pct']:+.2f}%"
            )

        with u3:

            st.metric(
                "Open",
                f"₹{result['underlying_open']:.2f}"
            )

        with u4:

            st.metric(
                "Day High",
                f"₹{result['underlying_high']:.2f}"
            )

        with u5:

            st.metric(
                "Day Low",
                f"₹{result['underlying_low']:.2f}"
            )

        with u6:

            st.metric(
                "Average Price",
                f"₹{result['average_price']:.2f}"
            )

        u7, u8, u9, u10 = st.columns(
            4
        )

        with u7:

            st.metric(
                "Price vs Open",
                f"{result['price_vs_open_pct']:+.2f}%"
            )

        with u8:

            st.metric(
                "Price vs Average",
                f"{result['price_vs_avg_pct']:+.2f}%"
            )

        with u9:

            st.metric(
                "Day Range Position",
                f"{result['range_position']:.0f}%"
            )

        with u10:

            st.metric(
                "Volume",
                f"{result['underlying_volume']:,.0f}"
            )

        # ====================================================
        # MARKET SNAPSHOT
        # ====================================================

        st.subheader(
            "📈 Options Market Snapshot"
        )

        c1, c2, c3, c4, c5, c6 = st.columns(
            6
        )

        with c1:

            st.metric(
                "Bias",
                result["bias"]
            )

        with c2:

            st.metric(
                "PCR",
                f"{result['pcr']:.2f}"
            )

        with c3:

            st.metric(
                "Put OI Wall",
                f"{result['put_wall']:.0f}"
            )

        with c4:

            st.metric(
                "Call OI Wall",
                f"{result['call_wall']:.0f}"
            )

        with c5:

            st.metric(
                "ATM",
                f"{result['atm_strike']:.0f}"
            )

        with c6:

            st.metric(
                "Expiry",
                result["expiry"].strftime(
                    "%d-%b-%Y"
                )
            )

        # ====================================================
        # SCORE
        # ====================================================

        st.subheader(
            "🎯 Multi-Factor Directional Score"
        )

        s1, s2, s3, s4 = st.columns(
            4
        )

        with s1:

            st.metric(
                "Bull Score",
                f"{result['bull_score']}/100"
            )

        with s2:

            st.metric(
                "Bear Score",
                f"{result['bear_score']}/100"
            )

        with s3:

            st.metric(
                "Score Gap",
                f"{result['score_gap']}"
            )

        with s4:

            st.metric(
                "Signal Alignment",
                (
                    f"{result['bullish_count']}"
                    if result["bull_score"]
                    > result["bear_score"]
                    else
                    f"{result['bearish_count']}"
                )
            )

        st.caption(
            "The score now combines underlying price behaviour "
            "with option-chain OI, change OI, volume, PCR and "
            "OI-wall information."
        )

        # ====================================================
        # TRADE DECISION
        # ====================================================

        st.subheader(
            "🚦 Trade Decision"
        )

        action = result["action"]
        direction = result["direction"]

        if action == "MARKET CLOSED":

            st.info(
                "🔵 **MARKET CLOSED**\n\n"
                "Latest available data is shown, but "
                "the engine will not recommend a new entry "
                "while the regular market is closed."
            )

        elif action == "TRADE CANDIDATE":

            if direction == "CE":

                st.success(
                    f"🟢 **CALL — BUY SETUP**\n\n"
                    f"Suggested Strike: "
                    f"{result['selected_strike']:.0f}"
                )

            else:

                st.success(
                    f"🔴 **PUT — BUY SETUP**\n\n"
                    f"Suggested Strike: "
                    f"{result['selected_strike']:.0f}"
                )

        elif action == "WATCH":

            if direction == "CE":

                st.warning(
                    f"🟡 **CALL — WAIT FOR CONFIRMATION**\n\n"
                    f"Reference Strike: "
                    f"{result['selected_strike']:.0f}"
                )

            elif direction == "PE":

                st.warning(
                    f"🟡 **PUT — WAIT FOR CONFIRMATION**\n\n"
                    f"Reference Strike: "
                    f"{result['selected_strike']:.0f}"
                )

            else:

                st.warning(
                    "🟡 **WAIT FOR CONFIRMATION**"
                )

        else:

            st.info(
                "⚪ **NO TRADE**\n\n"
                "The current market factors are not "
                "sufficiently aligned for a high-quality setup."
            )

        # ====================================================
        # TRADE PLAN
        # ====================================================

        if (
            result["selected_strike"] is not None
            and action != "MARKET CLOSED"
        ):

            st.subheader(
                "📋 Trade Plan"
            )

            p1, p2, p3, p4 = st.columns(
                4
            )

            with p1:

                st.metric(
                    "Action",
                    (
                        "BUY CALL"
                        if direction == "CE"
                        else "BUY PUT"
                    )
                )

            with p2:

                st.metric(
                    "Strike",
                    f"{result['selected_strike']:.0f}"
                )

            with p3:

                st.metric(
                    "Entry",
                    (
                        f"₹{result['entry']:.2f}"
                        if result["entry"] is not None
                        else "N/A"
                    )
                )

            with p4:

                st.metric(
                    "Probability of Profit",
                    (
                        f"{result['pop']:.2f}%"
                        if result["pop"] is not None
                        else "N/A"
                    )
                )

            p5, p6, p7, p8 = st.columns(
                4
            )

            with p5:

                st.metric(
                    "Stop Loss",
                    (
                        f"₹{result['stop_loss']:.2f}"
                        if result["stop_loss"] is not None
                        else "N/A"
                    )
                )

            with p6:

                st.metric(
                    "Target 1",
                    (
                        f"₹{result['target1']:.2f}"
                        if result["target1"] is not None
                        else "N/A"
                    )
                )

            with p7:

                st.metric(
                    "Target 2",
                    (
                        f"₹{result['target2']:.2f}"
                        if result["target2"] is not None
                        else "N/A"
                    )
                )

            with p8:

                st.metric(
                    "Entry Status",
                    result["entry_status"]
                )

            p9, p10, p11 = st.columns(
                3
            )

            with p9:

                st.metric(
                    "Delta",
                    (
                        f"{result['delta']:.3f}"
                        if result["delta"] is not None
                        else "N/A"
                    )
                )

            with p10:

                st.metric(
                    "IV",
                    (
                        f"{result['iv']:.2f}%"
                        if result["iv"] is not None
                        else "N/A"
                    )
                )

            with p11:

                st.metric(
                    "Signal Strength",
                    f"{max(result['bull_score'], result['bear_score'])}/100"
                )

            if result["spread_pct"] is not None:

                st.caption(
                    f"Bid/Ask spread: "
                    f"{result['spread_pct']:.2f}%"
                )

        # ====================================================
        # UNDERLYING OI
        # ====================================================

        if result["underlying_oi"] > 0:

            st.subheader(
                "📌 Underlying Futures OI"
            )

            oi1, oi2, oi3 = st.columns(
                3
            )

            with oi1:

                st.metric(
                    "Current OI",
                    f"{result['underlying_oi']:,.0f}"
                )

            with oi2:

                st.metric(
                    "Previous OI",
                    f"{result['underlying_previous_oi']:,.0f}"
                )

            with oi3:

                st.metric(
                    "OI Change",
                    f"{result['underlying_oi_change']:+,.0f}"
                )

        # ====================================================
        # SELECTED OPTION
        # ====================================================

        st.subheader(
            "🎯 Selected / Reference Option"
        )

        if result["selected_strike"] is not None:

            o1, o2, o3, o4 = st.columns(
                4
            )

            with o1:

                st.metric(
                    "Strike",
                    f"{result['selected_strike']:.0f}"
                )

            with o2:

                st.metric(
                    "Option",
                    direction
                )

            with o3:

                st.metric(
                    "LTP",
                    f"₹{result['option_ltp']:.2f}"
                )

            with o4:

                st.metric(
                    "PoP",
                    (
                        f"{result['pop']:.2f}%"
                        if result["pop"] is not None
                        else "N/A"
                    )
                )

            o5, o6, o7, o8 = st.columns(
                4
            )

            with o5:

                st.metric(
                    "Delta",
                    (
                        f"{result['delta']:.3f}"
                        if result["delta"] is not None
                        else "N/A"
                    )
                )

            with o6:

                st.metric(
                    "IV",
                    (
                        f"{result['iv']:.2f}%"
                        if result["iv"] is not None
                        else "N/A"
                    )
                )

            with o7:

                st.metric(
                    "OI",
                    f"{result['oi']:,.0f}"
                )

            with o8:

                st.metric(
                    "Chg OI",
                    f"{result['chg_oi']:+,.0f}"
                )

            if action == "NO TRADE":

                st.caption(
                    "ℹ️ This is a reference option only. "
                    "The engine is currently saying NO TRADE."
                )

        # ====================================================
        # SIGNAL BREAKDOWN
        # ====================================================

        st.subheader(
            "🧠 Signal Breakdown"
        )

        breakdown_col1, breakdown_col2 = st.columns(
            2
        )

        with breakdown_col1:

            st.markdown(
                "### 🟢 Bullish Factors"
            )

            if result["bullish_count"] > 0:

                for item in result.get(
                    "bullish_factors",
                    []
                ):

                    st.write(
                        f"• {item}"
                    )

            else:

                st.write(
                    "• No strong bullish factor detected."
                )

        with breakdown_col2:

            st.markdown(
                "### 🔴 Bearish Factors"
            )

            if result["bearish_count"] > 0:

                for item in result.get(
                    "bearish_factors",
                    []
                ):

                    st.write(
                        f"• {item}"
                    )

            else:

                st.write(
                    "• No strong bearish factor detected."
                )

        # ====================================================
        # ENGINE REASONS
        # ====================================================

        st.subheader(
            "🔎 Why the Engine Reached This Decision"
        )

        for reason in result["reasons"]:

            st.write(
                f"• {reason}"
            )

        # ====================================================
        # SUPPORT / RESISTANCE
        # ====================================================

        st.subheader(
            "🧱 OI Support / Resistance"
        )

        r1, r2, r3 = st.columns(
            3
        )

        with r1:

            st.metric(
                "Put Support",
                f"{result['put_wall']:.0f}"
            )

        with r2:

            st.metric(
                "ATM",
                f"{result['atm_strike']:.0f}"
            )

        with r3:

            st.metric(
                "Call Resistance",
                f"{result['call_wall']:.0f}"
            )

        # ====================================================
        # LIVE OPTION CHAIN
        # ====================================================

        st.subheader(
            "📑 Live Option Chain"
        )

        if (
            chain is not None
            and not chain.empty
        ):

            display_chain = chain.copy()

            display_chain = display_chain[
                [
                    "strike",

                    "ce_ltp",
                    "ce_pop",
                    "ce_delta",
                    "ce_iv",
                    "ce_oi",
                    "ce_chg_oi",
                    "ce_volume",

                    "pe_ltp",
                    "pe_pop",
                    "pe_delta",
                    "pe_iv",
                    "pe_oi",
                    "pe_chg_oi",
                    "pe_volume",
                ]
            ]

            display_chain = (
                display_chain
                .sort_values(
                    "strike"
                )
                .reset_index(
                    drop=True
                )
            )

            display_chain.columns = [

                "Strike",

                "CE LTP",
                "CE PoP %",
                "CE Delta",
                "CE IV %",
                "CE OI",
                "CE Chg OI",
                "CE Volume",

                "PE LTP",
                "PE PoP %",
                "PE Delta",
                "PE IV %",
                "PE OI",
                "PE Chg OI",
                "PE Volume",
            ]

            st.dataframe(
                display_chain,
                use_container_width=True,
                hide_index=True,
            )

        # ====================================================
        # DATA QUALITY
        # ====================================================

        st.subheader(
            "🛡️ Data & Signal Quality"
        )

        st.write(
            "• Underlying live price, OHLC, volume, "
            "average price and day change come from "
            "Upstox Full Market Quote V3."
        )

        st.write(
            "• Option-chain OI, Change OI, volume, "
            "bid/ask, IV, Delta and PoP come from "
            "the Upstox option-chain response."
        )

        st.write(
            "• Probability of Profit is the PoP value "
            "provided by Upstox. It is not calculated "
            "from the Bull/Bear score."
        )

        st.write(
            "• Bull/Bear scoring now combines underlying "
            "price behaviour and option-chain factors."
        )

        st.write(
            "• A wide option spread can force the setup "
            "to NO TRADE."
        )

        st.write(
            "• The application does not place orders "
            "automatically."
        )

        # ====================================================
        # REFRESH INFORMATION
        # ====================================================

        st.divider()

        refresh_col1, refresh_col2 = st.columns(
            2
        )

        with refresh_col1:

            st.success(
                "🔄 Auto-refresh: ON • Every 30 seconds"
            )

        with refresh_col2:

            if (
                st.session_state
                .last_successful_refresh
            ):

                st.caption(
                    "Last successful app refresh: "
                    + display_dt(
                        st.session_state
                        .last_successful_refresh
                    )
                )

        st.caption(
            f"Current search: {active_symbol} • "
            f"Risk profile: {active_risk}"
        )

        st.caption(
            "Auto-refresh works while this browser "
            "session is open. It does not run as a "
            "background process when the page is closed."
        )

    # ========================================================
    # RUN
    # ========================================================

    render_live_analysis()
