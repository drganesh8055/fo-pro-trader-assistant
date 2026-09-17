import math
import time
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st


# ============================================================
# OPTION TRADE ASSISTANT
# NSE PUBLIC-DATA VERSION
# ============================================================

st.set_page_config(
    page_title="Option Trade Assistant",
    page_icon="📈",
    layout="wide",
)

IST = timezone(timedelta(hours=5, minutes=30))
NSE = "https://www.nseindia.com"

INDEXES = {
    "NIFTY": "NIFTY 50",
    "BANKNIFTY": "NIFTY BANK",
    "FINNIFTY": "NIFTY FINANCIAL SERVICES",
    "MIDCPNIFTY": "NIFTY MIDCAP SELECT",
}

COMMON = {
    "NIFTY": "NIFTY",
    "NIFTY50": "NIFTY",
    "NIFTY 50": "NIFTY",

    "BANKNIFTY": "BANKNIFTY",
    "NIFTY BANK": "BANKNIFTY",

    "FINNIFTY": "FINNIFTY",
    "NIFTY FINANCIAL SERVICES": "FINNIFTY",

    "MIDCPNIFTY": "MIDCPNIFTY",
    "NIFTY MIDCAP SELECT": "MIDCPNIFTY",

    "KOTAKBANK": "KOTAKBANK",
    "KOTAK MAHINDRA BANK": "KOTAKBANK",

    "INDUSTOWER": "INDUSTOWER",
    "INDUS TOWERS": "INDUSTOWER",

    "RELIANCE": "RELIANCE",
    "HDFCBANK": "HDFCBANK",
    "ICICIBANK": "ICICIBANK",
    "SBIN": "SBIN",
    "AXISBANK": "AXISBANK",
    "INFY": "INFY",
    "TCS": "TCS",
    "BHARTIARTL": "BHARTIARTL",
    "ADANIENT": "ADANIENT",
    "ADANIPORTS": "ADANIPORTS",
    "TATAMOTORS": "TATAMOTORS",
    "TATASTEEL": "TATASTEEL",
    "MARUTI": "MARUTI",
    "BAJFINANCE": "BAJFINANCE",
    "SUNPHARMA": "SUNPHARMA",
    "LT": "LT",
    "HINDALCO": "HINDALCO",
    "COALINDIA": "COALINDIA",
    "BEL": "BEL",
    "TRENT": "TRENT",
    "HAL": "HAL",
    "M&M": "M&M",
    "M&MFIN": "M&MFIN",
}


# ============================================================
# NSE SESSION
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "DNT": "1",
}


@st.cache_resource
def nse_session():
    session = requests.Session()
    session.headers.update(HEADERS)

    # Warm up NSE session to obtain cookies.
    try:
        session.get(
            NSE,
            timeout=15,
            allow_redirects=True,
        )
    except Exception:
        pass

    return session


def reset_nse_session():
    try:
        nse_session.clear()
    except Exception:
        pass


def get_json(path, params=None, tries=3):
    """
    Robust NSE request.

    NSE may temporarily return:
    - 403
    - 429
    - HTML instead of JSON
    - connection errors

    We retry and validate the response before parsing JSON.
    """

    last_error = "Unknown NSE error"

    for attempt in range(tries):
        session = nse_session()

        try:
            url = NSE + path

            response = session.get(
                url,
                params=params,
                timeout=15,
                allow_redirects=True,
                headers={
                    "Referer": NSE + "/",
                    "Origin": NSE,
                },
            )

            if response.status_code == 200:

                content_type = response.headers.get(
                    "content-type", ""
                ).lower()

                text_start = response.text[:100].lower()

                # Reject obvious HTML/block pages.
                if (
                    "text/html" in content_type
                    or text_start.startswith("<!doctype")
                    or text_start.startswith("<html")
                ):
                    last_error = (
                        "NSE returned an HTML page instead of JSON. "
                        "The NSE server may be blocking this request."
                    )
                else:
                    try:
                        return response.json()
                    except Exception:
                        last_error = (
                            "NSE returned HTTP 200 but the response "
                            "was not valid JSON."
                        )

            elif response.status_code == 403:
                last_error = (
                    "NSE returned HTTP 403 (request blocked)."
                )

            elif response.status_code == 429:
                last_error = (
                    "NSE returned HTTP 429 (too many requests)."
                )

            else:
                last_error = (
                    f"NSE returned HTTP {response.status_code}."
                )

        except requests.exceptions.Timeout:
            last_error = "NSE request timed out."

        except requests.exceptions.RequestException as exc:
            last_error = f"Network error: {exc}"

        except Exception as exc:
            last_error = f"Unexpected error: {exc}"

        # Refresh session before next attempt.
        reset_nse_session()

        time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(last_error)


# ============================================================
# SYMBOL HELPERS
# ============================================================

def normalize_symbol(value):
    if not value:
        return ""

    value = str(value).strip().upper()

    return COMMON.get(
        value,
        value.replace(" ", ""),
    )


def is_index(symbol):
    return symbol in INDEXES


# ============================================================
# LIVE QUOTE
# ============================================================

def get_index_quote(symbol):
    data = get_json("/api/allIndices")

    rows = data.get("data", [])

    wanted = INDEXES[symbol].upper()

    for row in rows:
        name = str(row.get("index", "")).upper()

        if name == wanted:
            price = (
                row.get("last")
                or row.get("lastPrice")
                or row.get("ltp")
            )

            change = (
                row.get("percentChange")
                or row.get("variation")
                or row.get("pChange")
                or 0
            )

            if price is not None:
                return {
                    "price": float(price),
                    "change": float(change),
                }

    # Fallback to option-chain underlying value.
    chain = get_json(
        "/api/option-chain-indices",
        {"symbol": symbol},
    )

    records = chain.get("records", {})

    underlying = records.get("underlyingValue")

    if underlying is None:
        raise RuntimeError(
            f"NSE did not return a live price for {symbol}."
        )

    return {
        "price": float(underlying),
        "change": 0.0,
    }


def get_equity_quote(symbol):
    data = get_json(
        "/api/quote-equity",
        {"symbol": symbol},
    )

    price_info = data.get("priceInfo", {})

    price = price_info.get("lastPrice")

    if price is None:
        raise RuntimeError(
            f"NSE did not return a live price for {symbol}."
        )

    change = (
        price_info.get("pChange")
        or price_info.get("change")
        or 0
    )

    return {
        "price": float(price),
        "change": float(change),
    }


def get_quote(symbol):
    if is_index(symbol):
        return get_index_quote(symbol)

    return get_equity_quote(symbol)


# ============================================================
# OPTION CHAIN
# ============================================================

def get_option_chain(symbol):
    endpoint = (
        "/api/option-chain-indices"
        if is_index(symbol)
        else "/api/option-chain-equities"
    )

    return get_json(
        endpoint,
        {"symbol": symbol},
    )


def parse_expiry_date(value):
    formats = [
        "%d-%b-%Y",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                value,
                fmt,
            ).date()
        except Exception:
            pass

    return None


def nearest_expiry(chain):
    records = chain.get("records", {})

    expiry_dates = records.get(
        "expiryDates",
        [],
    )

    today = datetime.now(IST).date()

    valid = []

    for value in expiry_dates:
        dt = parse_expiry_date(value)

        if dt and dt >= today:
            valid.append((dt, value))

    if not valid:
        raise RuntimeError(
            "NSE returned no future option expiry."
        )

    valid.sort(key=lambda x: x[0])

    return valid[0][1]


def expiry_days(expiry):
    dt = parse_expiry_date(expiry)

    if dt is None:
        return 1

    today = datetime.now(IST).date()

    return max(
        1,
        (dt - today).days,
    )


def normalize_option_chain(chain, expiry):
    records = chain.get("records", {})

    rows = []

    for item in records.get("data", []):

        if item.get("expiryDate") != expiry:
            continue

        strike = item.get("strikePrice")

        if strike is None:
            continue

        ce = item.get("CE") or {}
        pe = item.get("PE") or {}

        rows.append(
            {
                "strike": float(strike),

                "ce_ltp": float(
                    ce.get("lastPrice", 0) or 0
                ),
                "ce_oi": int(
                    ce.get("openInterest", 0) or 0
                ),
                "ce_chg_oi": int(
                    ce.get("changeinOpenInterest", 0) or 0
                ),
                "ce_volume": int(
                    ce.get("totalTradedVolume", 0) or 0
                ),
                "ce_iv": float(
                    ce.get("impliedVolatility", 0) or 0
                ),
                "ce_bid": float(
                    ce.get("bidprice", 0) or 0
                ),
                "ce_ask": float(
                    ce.get("askPrice", 0) or 0
                ),

                "pe_ltp": float(
                    pe.get("lastPrice", 0) or 0
                ),
                "pe_oi": int(
                    pe.get("openInterest", 0) or 0
                ),
                "pe_chg_oi": int(
                    pe.get("changeinOpenInterest", 0) or 0
                ),
                "pe_volume": int(
                    pe.get("totalTradedVolume", 0) or 0
                ),
                "pe_iv": float(
                    pe.get("impliedVolatility", 0) or 0
                ),
                "pe_bid": float(
                    pe.get("bidprice", 0) or 0
                ),
                "pe_ask": float(
                    pe.get("askPrice", 0) or 0
                ),
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError(
            "NSE returned no option-chain data "
            f"for expiry {expiry}."
        )

    return df.sort_values(
        "strike"
    ).reset_index(drop=True)


# ============================================================
# OPTION / MARKET CALCULATIONS
# ============================================================

def estimated_delta(
    spot,
    strike,
    iv,
    days,
    call=True,
):
    """
    Black-Scholes style estimated delta.

    This is calculated by the app.
    It is NOT presented as an NSE-provided Greek.
    """

    if (
        spot <= 0
        or strike <= 0
        or iv <= 0
    ):
        return 0.5 if call else -0.5

    sigma = max(
        iv / 100.0,
        0.01,
    )

    T = max(
        days / 365.0,
        1 / 3650,
    )

    risk_free = 0.06

    d1 = (
        math.log(spot / strike)
        + (
            risk_free
            + 0.5 * sigma * sigma
        ) * T
    ) / (
        sigma * math.sqrt(T)
    )

    cdf = 0.5 * (
        1 + math.erf(
            d1 / math.sqrt(2)
        )
    )

    return cdf if call else cdf - 1


def calculate_rsi_from_option_pressure(
    near,
):
    """
    NSE public option-chain data does not reliably provide
    a stock/index historical candle series.

    Therefore we do NOT invent RSI.

    This function returns None.
    """

    return None


def derive_strike_step(df):
    strikes = sorted(
        df["strike"].dropna().unique()
    )

    if len(strikes) < 2:
        return 1

    differences = np.diff(strikes)

    positive = [
        float(x)
        for x in differences
        if x > 0
    ]

    if not positive:
        return 1

    return min(positive)


# ============================================================
# MARKET ANALYSIS
# ============================================================

def analyze_market(
    symbol,
    risk_profile,
):
    quote = get_quote(symbol)

    spot = quote["price"]

    if spot <= 0:
        raise RuntimeError(
            "NSE returned an invalid underlying price."
        )

    chain = get_option_chain(symbol)

    expiry = nearest_expiry(chain)

    df = normalize_option_chain(
        chain,
        expiry,
    )

    step = derive_strike_step(df)

    atm_index = (
        df["strike"] - spot
    ).abs().idxmin()

    atm = float(
        df.loc[
            atm_index,
            "strike",
        ]
    )

    # Keep analysis around spot.
    near = df[
        (
            df["strike"]
            >= spot - 5 * step
        )
        &
        (
            df["strike"]
            <= spot + 5 * step
        )
    ].copy()

    if near.empty:
        near = df.copy()

    total_call_oi = float(
        near["ce_oi"].sum()
    )

    total_put_oi = float(
        near["pe_oi"].sum()
    )

    pcr = (
        total_put_oi
        / max(total_call_oi, 1)
    )

    call_wall = float(
        near.loc[
            near["ce_oi"].idxmax(),
            "strike",
        ]
    )

    put_wall = float(
        near.loc[
            near["pe_oi"].idxmax(),
            "strike",
        ]
    )

    near3 = near[
        (
            near["strike"]
            >= spot - 3 * step
        )
        &
        (
            near["strike"]
            <= spot + 3 * step
        )
    ]

    call_chg = float(
        near3["ce_chg_oi"].sum()
    )

    put_chg = float(
        near3["pe_chg_oi"].sum()
    )

    call_volume = float(
        near3["ce_volume"].sum()
    )

    put_volume = float(
        near3["pe_volume"].sum()
    )

    # --------------------------------------------------------
    # Price/OI pressure model
    # --------------------------------------------------------

    bull_score = 0.0
    bear_score = 0.0

    # PCR contribution.
    if pcr >= 1.15:
        bull_score += 25
    elif pcr >= 1.00:
        bull_score += 18
    elif pcr >= 0.90:
        bull_score += 10

    if pcr <= 0.75:
        bear_score += 25
    elif pcr <= 0.90:
        bear_score += 18
    elif pcr <= 1.00:
        bear_score += 10

    # OI-change interpretation.
    oi_bullish = (
        put_chg > 0
        and call_chg < 0
    )

    oi_bearish = (
        call_chg > 0
        and put_chg < 0
    )

    if oi_bullish:
        bull_score += 25
    elif put_chg > 0:
        bull_score += 10

    if oi_bearish:
        bear_score += 25
    elif call_chg > 0:
        bear_score += 10

    # Volume pressure.
    if call_volume > put_volume * 1.20:
        bull_score += 12

    elif put_volume > call_volume * 1.20:
        bear_score += 12

    # OI-wall location.
    if put_wall < spot:
        bull_score += 10

    if call_wall > spot:
        bear_score += 10

    # Near ATM option liquidity.
    atm_row = near.iloc[
        (near["strike"] - atm)
        .abs()
        .argsort()
        .iloc[0]
    ]

    atm_ce_volume = float(
        atm_row["ce_volume"]
    )

    atm_pe_volume = float(
        atm_row["pe_volume"]
    )

    if atm_ce_volume > 0:
        bull_score += 8

    if atm_pe_volume > 0:
        bear_score += 8

    bull_score = min(
        100,
        bull_score,
    )

    bear_score = min(
        100,
        bear_score,
    )

    difference = abs(
        bull_score - bear_score
    )

    if difference < 10:
        bias = "NEUTRAL"

    elif bull_score > bear_score:
        bias = "BULLISH"

    else:
        bias = "BEARISH"

    strength = max(
        bull_score,
        bear_score,
    )

    # --------------------------------------------------------
    # Quality gate
    # --------------------------------------------------------

    if (
        strength >= 68
        and difference >= 15
    ):
        action = "TRADE"

    elif (
        strength >= 52
        and difference >= 8
    ):
        action = "WAIT"

    else:
        action = "NO TRADE"

    side = (
        "CE"
        if bull_score > bear_score
        else "PE"
    )

    # --------------------------------------------------------
    # Select option
    # --------------------------------------------------------

    if side == "CE":

        candidates = near[
            (
                near["strike"]
                >= atm
            )
            &
            (
                near["strike"]
                <= atm + 2 * step
            )
            &
            (
                near["ce_ltp"] > 0
            )
        ].copy()

        if candidates.empty:
            candidates = near[
                near["ce_ltp"] > 0
            ].copy()

        if candidates.empty:
            raise RuntimeError(
                "No usable CE option found."
            )

        # Prefer liquid near-ATM option.
        candidates["selection_score"] = (
            candidates["ce_volume"].clip(
                lower=1
            )
            /
            (
                1
                + (
                    candidates["strike"]
                    - spot
                ).abs()
            )
        )

        row = candidates.sort_values(
            "selection_score",
            ascending=False,
        ).iloc[0]

        premium = float(
            row["ce_ltp"]
        )

        iv = float(
            row["ce_iv"]
        )

        delta = abs(
            estimated_delta(
                spot,
                float(row["strike"]),
                iv,
                expiry_days(expiry),
                True,
            )
        )

        oi = int(
            row["ce_oi"]
        )

        chg_oi = int(
            row["ce_chg_oi"]
        )

        volume = int(
            row["ce_volume"]
        )

        bid = float(
            row["ce_bid"]
        )

        ask = float(
            row["ce_ask"]
        )

    else:

        candidates = near[
            (
                near["strike"]
                <= atm
            )
            &
            (
                near["strike"]
                >= atm - 2 * step
            )
            &
            (
                near["pe_ltp"] > 0
            )
        ].copy()

        if candidates.empty:
            candidates = near[
                near["pe_ltp"] > 0
            ].copy()

        if candidates.empty:
            raise RuntimeError(
                "No usable PE option found."
            )

        candidates["selection_score"] = (
            candidates["pe_volume"].clip(
                lower=1
            )
            /
            (
                1
                + (
                    candidates["strike"]
                    - spot
                ).abs()
            )
        )

        row = candidates.sort_values(
            "selection_score",
            ascending=False,
        ).iloc[0]

        premium = float(
            row["pe_ltp"]
        )

        iv = float(
            row["pe_iv"]
        )

        delta = abs(
            estimated_delta(
                spot,
                float(row["strike"]),
                iv,
                expiry_days(expiry),
                False,
            )
        )

        oi = int(
            row["pe_oi"]
        )

        chg_oi = int(
            row["pe_chg_oi"]
        )

        volume = int(
            row["pe_volume"]
        )

        bid = float(
            row["pe_bid"]
        )

        ask = float(
            row["pe_ask"]
        )

    # --------------------------------------------------------
    # Liquidity check
    # --------------------------------------------------------

    if bid > 0 and ask > 0:
        spread_pct = (
            (ask - bid)
            / max(
                (ask + bid) / 2,
                0.01,
            )
            * 100
        )
    else:
        spread_pct = 999

    if volume <= 0:
        liquidity = "POOR"

    elif spread_pct <= 3:
        liquidity = "GOOD"

    elif spread_pct <= 7:
        liquidity = "MODERATE"

    else:
        liquidity = "POOR"

    if liquidity == "POOR":
        action = "NO TRADE"

    if premium <= 0:
        action = "NO TRADE"

    # --------------------------------------------------------
    # Risk profile
    # --------------------------------------------------------

    risk_settings = {
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

    settings = risk_settings[
        risk_profile
    ]

    if bid > 0 and ask > 0:
        entry = round(
            (bid + ask) / 2,
            2,
        )
    else:
        entry = round(
            premium,
            2,
        )

    sl = round(
        entry
        * (
            1
            - settings["sl"]
        ),
        2,
    )

    target1 = round(
        entry
        * (
            1
            + settings["t1"]
        ),
        2,
    )

    target2 = round(
        entry
        * (
            1
            + settings["t2"]
        ),
        2,
    )

    # --------------------------------------------------------
    # Underlying trigger
    # --------------------------------------------------------

    if side == "CE":

        trigger = max(
            spot,
            call_wall
            if call_wall > spot
            else spot + step * 0.10,
        )

        trigger_text = (
            "Consider CE only after the "
            "underlying confirms strength above "
            f"₹{trigger:,.2f}."
        )

    else:

        trigger = min(
            spot,
            put_wall
            if put_wall < spot
            else spot - step * 0.10,
        )

        trigger_text = (
            "Consider PE only after the "
            "underlying confirms weakness below "
            f"₹{trigger:,.2f}."
        )

    # --------------------------------------------------------
    # Reasons
    # --------------------------------------------------------

    reasons = []

    reasons.append(
        f"PCR is {pcr:.2f}."
    )

    reasons.append(
        f"Put OI wall is around "
        f"₹{put_wall:,.0f}; "
        f"Call OI wall is around "
        f"₹{call_wall:,.0f}."
    )

    if oi_bullish:
        reasons.append(
            "Near-spot OI pattern shows "
            "put OI addition with call OI reduction."
        )

    elif oi_bearish:
        reasons.append(
            "Near-spot OI pattern shows "
            "call OI addition with put OI reduction."
        )

    else:
        reasons.append(
            "Near-spot OI change is mixed."
        )

    reasons.append(
        f"Selected {side} strike has "
        f"estimated delta {delta:.2f}, "
        f"IV {iv:.1f}% and volume {volume:,}."
    )

    reasons.append(
        f"Option liquidity is {liquidity}; "
        f"bid/ask spread is approximately "
        f"{spread_pct:.1f}%."
    )

    if action == "TRADE":
        reasons.append(
            "Multiple option-chain factors align, "
            "but confirmation of the underlying "
            "price trigger is still required."
        )

    elif action == "WAIT":
        reasons.append(
            "The setup has some supporting factors "
            "but is not strong enough for immediate entry."
        )

    else:
        reasons.append(
            "The available factors do not meet "
            "the app's trade-quality threshold."
        )

    return {
        "symbol": symbol,
        "spot": spot,
        "change": quote["change"],
        "expiry": expiry,
        "expiry_days": expiry_days(expiry),
        "atm": atm,
        "step": step,

        "pcr": pcr,
        "put_wall": put_wall,
        "call_wall": call_wall,

        "put_chg": put_chg,
        "call_chg": call_chg,

        "call_volume": call_volume,
        "put_volume": put_volume,

        "bull": bull_score,
        "bear": bear_score,
        "strength": strength,
        "difference": difference,

        "bias": bias,
        "side": side,
        "action": action,

        "strike": float(
            row["strike"]
        ),

        "premium": premium,
        "entry": entry,
        "sl": sl,
        "target1": target1,
        "target2": target2,

        "delta": delta,
        "iv": iv,
        "oi": oi,
        "chg_oi": chg_oi,
        "volume": volume,

        "bid": bid,
        "ask": ask,
        "spread_pct": spread_pct,
        "liquidity": liquidity,

        "trigger": trigger,
        "trigger_text": trigger_text,

        "reasons": reasons,
        "rows": near,
    }


# ============================================================
# DISPLAY HELPERS
# ============================================================

def money(value):
    if value is None:
        return "—"

    if abs(value) >= 1000:
        return f"₹{value:,.0f}"

    return f"₹{value:,.2f}"


def score_text(value):
    return f"{value:.0f}/100"


# ============================================================
# USER INTERFACE
# ============================================================

st.title("📈 Option Trade Assistant")

st.caption(
    "NSE public-data analysis • "
    "No automatic order placement • "
    "No simulated prices"
)

st.info(
    "Enter an F&O stock or index and click ANALYZE. "
    "If NSE does not return valid data, the app will show "
    "NSE DATA UNAVAILABLE and will not create a trade signal."
)


with st.container(border=True):

    col1, col2 = st.columns(
        [4, 1]
    )

    with col1:

        symbol_input = st.text_input(
            "Enter F&O stock / index",
            placeholder=(
                "KOTAKBANK, RELIANCE, "
                "HDFCBANK, NIFTY..."
            ),
        )

    with col2:

        risk_profile = st.selectbox(
            "Risk profile",
            [
                "Conservative",
                "Balanced",
                "Aggressive",
            ],
            index=1,
        )

    analyze_button = st.button(
        "🔎 ANALYZE",
        type="primary",
        use_container_width=True,
    )


# ============================================================
# ANALYZE
# ============================================================

if analyze_button:

    symbol = normalize_symbol(
        symbol_input
    )

    if not symbol:

        st.error(
            "Please enter an F&O stock or index."
        )

        st.stop()

    with st.spinner(
        f"Connecting to NSE and analysing {symbol}..."
    ):

        try:

            result = analyze_market(
                symbol,
                risk_profile,
            )

        except Exception as exc:

            st.error(
                "🔴 NSE DATA UNAVAILABLE"
            )

            st.warning(
                "The app could not obtain valid NSE "
                "data right now. No simulated data "
                "has been used."
            )

            st.code(
                str(exc)
            )

            st.info(
                "Possible causes: NSE temporarily "
                "blocked the request, rate limiting, "
                "market closed, network issue, or an "
                "NSE endpoint change. Wait briefly and "
                "try ANALYZE again."
            )

            st.stop()

    timestamp = datetime.now(
        IST
    ).strftime(
        "%d-%b-%Y %H:%M:%S IST"
    )

    st.success(
        f"🟢 NSE DATA RECEIVED • "
        f"{timestamp}"
    )

    # --------------------------------------------------------
    # Dashboard
    # --------------------------------------------------------

    st.subheader(
        "1️⃣ Market Dashboard"
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric(
        "Live Price",
        money(result["spot"]),
        f"{result['change']:.2f}%",
    )

    c2.metric(
        "Bias",
        result["bias"],
    )

    c3.metric(
        "PCR",
        f"{result['pcr']:.2f}",
    )

    c4.metric(
        "Put OI Wall",
        money(result["put_wall"]),
    )

    c5.metric(
        "Call OI Wall",
        money(result["call_wall"]),
    )

    c6.metric(
        "Expiry",
        result["expiry"],
    )

    c7, c8, c9 = st.columns(3)

    c7.metric(
        "Bull Score",
        score_text(
            result["bull"]
        ),
    )

    c8.metric(
        "Bear Score",
        score_text(
            result["bear"]
        ),
    )

    c9.metric(
        "Expiry Days",
        str(result["expiry_days"]),
    )

    st.divider()

    # --------------------------------------------------------
    # Main decision
    # --------------------------------------------------------

    st.subheader(
        "2️⃣ Trade Decision"
    )

    if result["action"] == "TRADE":

        if result["side"] == "CE":

            st.success(
                f"## 🟢 CE SETUP — "
                f"{result['strike']:.0f} CE"
            )

        else:

            st.error(
                f"## 🔴 PE SETUP — "
                f"{result['strike']:.0f} PE"
            )

    elif result["action"] == "WAIT":

        st.warning(
            f"## 🟡 WAIT — "
            f"{result['side']} setup developing"
        )

    else:

        st.info(
            "## ⚪ NO TRADE"
        )

    score_cols = st.columns(4)

    score_cols[0].metric(
        "Decision",
        result["action"],
    )

    score_cols[1].metric(
        "Bull Score",
        score_text(
            result["bull"]
        ),
    )

    score_cols[2].metric(
        "Bear Score",
        score_text(
            result["bear"]
        ),
    )

    score_cols[3].metric(
        "Signal Strength",
        score_text(
            result["strength"]
        ),
    )

    # --------------------------------------------------------
    # Trade levels
    # --------------------------------------------------------

    if result["action"] != "NO TRADE":

        st.subheader(
            "3️⃣ Trade Plan"
        )

        t1, t2, t3, t4, t5, t6 = st.columns(6)

        t1.metric(
            "Option",
            f"{result['strike']:.0f} "
            f"{result['side']}",
        )

        t2.metric(
            "Entry",
            money(result["entry"]),
        )

        t3.metric(
            "Stop Loss",
            money(result["sl"]),
        )

        t4.metric(
            "Target 1",
            money(result["target1"]),
        )

        t5.metric(
            "Target 2",
            money(result["target2"]),
        )

        t6.metric(
            "Est. Delta",
            f"{result['delta']:.2f}",
        )

        st.markdown(
            "### Entry Trigger"
        )

        st.info(
            result["trigger_text"]
        )

        st.markdown(
            "### Exit Plan"
        )

        st.write(
            f"1. **Stop Loss:** "
            f"₹{result['sl']:,.2f}"
        )

        st.write(
            f"2. **Target 1:** "
            f"₹{result['target1']:,.2f}"
        )

        st.write(
            f"3. **Target 2:** "
            f"₹{result['target2']:,.2f}"
        )

        st.write(
            "4. If the underlying invalidates "
            "the setup, consider exiting rather "
            "than waiting for the premium target."
        )

        st.write(
            "5. Do not carry an intraday option "
            "position simply because the target "
            "has not been reached."
        )

    else:

        st.info(
            "No trade levels are displayed because "
            "the setup did not pass the quality gate."
        )

    # --------------------------------------------------------
    # Option information
    # --------------------------------------------------------

    st.subheader(
        "4️⃣ Selected Option"
    )

    o1, o2, o3, o4, o5, o6 = st.columns(6)

    o1.metric(
        "LTP",
        money(result["premium"]),
    )

    o2.metric(
        "Delta",
        f"{result['delta']:.2f}",
    )

    o3.metric(
        "IV",
        f"{result['iv']:.1f}%",
    )

    o4.metric(
        "OI",
        f"{result['oi']:,}",
    )

    o5.metric(
        "Chg OI",
        f"{result['chg_oi']:+,}",
    )

    o6.metric(
        "Volume",
        f"{result['volume']:,}",
    )

    st.caption(
        "Delta shown here is an estimate calculated "
        "by the app from spot, strike, IV and time "
        "to expiry. It is not presented as an "
        "NSE-provided Greek."
    )

    # --------------------------------------------------------
    # Why
    # --------------------------------------------------------

    st.subheader(
        "5️⃣ Why the Engine Says This"
    )

    for reason in result["reasons"]:
        st.write(
            "•",
            reason,
        )

    # --------------------------------------------------------
    # OI analysis
    # --------------------------------------------------------

    st.subheader(
        "6️⃣ OI & Support / Resistance"
    )

    left, right = st.columns(2)

    with left:

        st.markdown(
            "### 🟢 Put Side"
        )

        st.write(
            f"**Put OI Wall:** "
            f"{money(result['put_wall'])}"
        )

        st.write(
            f"**Near-spot Put Chg OI:** "
            f"{result['put_chg']:+,.0f}"
        )

        if result["put_chg"] > 0:

            st.success(
                "Put OI is increasing around the "
                "analysed area."
            )

        else:

            st.warning(
                "Put OI is not showing strong "
                "building around the analysed area."
            )

    with right:

        st.markdown(
            "### 🔴 Call Side"
        )

        st.write(
            f"**Call OI Wall:** "
            f"{money(result['call_wall'])}"
        )

        st.write(
            f"**Near-spot Call Chg OI:** "
            f"{result['call_chg']:+,.0f}"
        )

        if result["call_chg"] > 0:

            st.warning(
                "Call OI is increasing around the "
                "analysed area."
            )

        else:

            st.success(
                "Call OI is not showing strong "
                "building around the analysed area."
            )

    # --------------------------------------------------------
    # Detailed option chain
    # --------------------------------------------------------

    with st.expander(
        "🔎 View Live NSE Option Chain"
    ):

        display = result[
            "rows"
        ].copy()

        display = display[
            [
                "strike",

                "ce_ltp",
                "ce_oi",
                "ce_chg_oi",
                "ce_volume",
                "ce_iv",

                "pe_ltp",
                "pe_oi",
                "pe_chg_oi",
                "pe_volume",
                "pe_iv",
            ]
        ]

        display.columns = [
            "Strike",

            "CE LTP",
            "CE OI",
            "CE Chg OI",
            "CE Volume",
            "CE IV",

            "PE LTP",
            "PE OI",
            "PE Chg OI",
            "PE Volume",
            "PE IV",
        ]

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
        )

    # --------------------------------------------------------
    # Data quality
    # --------------------------------------------------------

    with st.expander(
        "ℹ️ Data & Signal Quality"
    ):

        st.write(
            f"**Underlying:** {result['symbol']}"
        )

        st.write(
            f"**Expiry analysed:** "
            f"{result['expiry']}"
        )

        st.write(
            f"**Days to expiry:** "
            f"{result['expiry_days']}"
        )

        st.write(
            f"**Strike interval detected from "
            f"live chain:** {result['step']}"
        )

        st.write(
            f"**Option liquidity:** "
            f"{result['liquidity']}"
        )

        st.write(
            f"**Bid/ask spread:** "
            f"{result['spread_pct']:.1f}%"
        )

        st.write(
            "**Technical RSI:** Not used unless a "
            "reliable historical/intraday price series "
            "is available. The app does not invent RSI."
        )


# ============================================================
# HOME SCREEN
# ============================================================

else:

    st.subheader(
        "How to use"
    )

    st.markdown(
        """
1. Enter an F&O stock or index.
2. Select your risk profile.
3. Click **ANALYZE**.
4. The app attempts to obtain the latest available NSE data.
5. It analyses the option chain.
6. It produces **TRADE / WAIT / NO TRADE**.
7. When a setup passes the quality gate, it displays the option, entry, stop loss and targets.

### Example symbols

- `KOTAKBANK`
- `RELIANCE`
- `HDFCBANK`
- `ICICIBANK`
- `SBIN`
- `INFY`
- `TCS`
- `BHARTIARTL`
- `NIFTY`
- `BANKNIFTY`
- `FINNIFTY`
- `MIDCPNIFTY`

### Important

This version does **not** create synthetic prices.

If NSE blocks or refuses the request, the app will show:

**🔴 NSE DATA UNAVAILABLE**

and will not generate a trade using fake data.
"""
    )

    st.divider()

    st.caption(
        "Option Trade Assistant • NSE public-data "
        "connector • Analysis only • No automatic orders"
    )
