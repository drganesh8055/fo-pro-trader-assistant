import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone
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
# UPSTOX AUTHENTICATION
# ============================================================

def get_access_token():
    token = st.secrets.get("UPSTOX_ACCESS_TOKEN", "")

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
    """
    Convert ISO timestamp returned by Upstox to IST.
    """
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(IST)

    except Exception:
        return None


def format_ms_ist(value):
    """
    Convert Unix milliseconds returned by Upstox to IST.
    """
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

    return dt.strftime("%d-%b-%Y %H:%M:%S IST")


# ============================================================
# FIND UNDERLYING INSTRUMENT
# ============================================================

def find_underlying(symbol):
    """
    Search Upstox instrument database.
    """

    result = upstox_get(
        "/v2/instruments/search",
        params={
            "query": symbol,
            "segments": "EQ,INDEX",
            "page_number": 1,
            "records": 30,
        },
    )

    rows = result.get("data") or []

    if not rows:
        raise RuntimeError(
            f"Could not find underlying instrument for {symbol}."
        )

    symbol_upper = symbol.upper()

    # Prefer exact trading symbol
    exact = [
        x for x in rows
        if str(x.get("trading_symbol", "")).upper()
        == symbol_upper
    ]

    if exact:
        return exact[0]

    # Prefer exact short name
    exact_name = [
        x for x in rows
        if str(x.get("short_name", "")).upper()
        == symbol_upper
    ]

    if exact_name:
        return exact_name[0]

    # Otherwise use first result
    return rows[0]


# ============================================================
# FULL MARKET QUOTE V3
# ============================================================

def get_full_quote_v3(instrument_key):
    """
    Upstox V3 Full Market Quote.

    This gives:
      - timestamp = snapshot response time
      - last_trade_time = underlying's latest trade time
      - last_price
    """

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

    # The dictionary key can vary.
    # Take the first returned quote.
    quote = next(iter(rows.values()))

    return quote


# ============================================================
# GET OPTION CONTRACTS
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
    today = datetime.now(IST).date()

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
                expiries.append(expiry_date)

        except Exception:
            continue

    if not expiries:
        raise RuntimeError(
            "No future option expiry found."
        )

    return min(expiries)


# ============================================================
# GET OPTION CHAIN
# ============================================================

def get_option_chain(instrument_key, expiry_date):
    result = upstox_get(
        "/v2/option/chain",
        params={
            "instrument_key": instrument_key,
            "expiry_date": expiry_date.strftime("%Y-%m-%d"),
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

        strike = float(
            row.get("strike_price")
            or row.get("strike")
            or 0
        )

        spot = float(
            row.get("underlying_spot_price")
            or row.get("underlying_price")
            or 0
        )

        call = row.get("call") or {}
        put = row.get("put") or {}

        call_market = call.get("market_data") or {}
        put_market = put.get("market_data") or {}

        call_greeks = call.get("option_greeks") or {}
        put_greeks = put.get("option_greeks") or {}

        ce_ltp = float(
            call_market.get("ltp") or 0
        )

        pe_ltp = float(
            put_market.get("ltp") or 0
        )

        ce_oi = float(
            call_market.get("oi") or 0
        )

        pe_oi = float(
            put_market.get("oi") or 0
        )

        ce_prev_oi = float(
            call_market.get("prev_oi") or 0
        )

        pe_prev_oi = float(
            put_market.get("prev_oi") or 0
        )

        ce_chg_oi = ce_oi - ce_prev_oi
        pe_chg_oi = pe_oi - pe_prev_oi

        ce_volume = float(
            call_market.get("volume") or 0
        )

        pe_volume = float(
            put_market.get("volume") or 0
        )

        ce_iv = float(
            call_greeks.get("iv") or 0
        )

        pe_iv = float(
            put_greeks.get("iv") or 0
        )

        ce_delta = float(
            call_greeks.get("delta") or 0
        )

        pe_delta = float(
            put_greeks.get("delta") or 0
        )

        ce_pop = float(
            call_greeks.get("pop") or 0
        )

        pe_pop = float(
            put_greeks.get("pop") or 0
        )

        ce_bid = float(
            call_market.get("bid_price") or 0
        )

        ce_ask = float(
            call_market.get("ask_price") or 0
        )

        pe_bid = float(
            put_market.get("bid_price") or 0
        )

        pe_ask = float(
            put_market.get("ask_price") or 0
        )

        ce_key = call.get("instrument_key")
        pe_key = put.get("instrument_key")

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

    return pd.DataFrame(normalized)


# ============================================================
# ANALYZE OPTION CHAIN
# ============================================================

def analyze_chain(df, risk_profile):

    df = df.copy()

    if df.empty:
        raise RuntimeError(
            "Option chain is empty."
        )

    # --------------------------------------------------------
    # SPOT
    # --------------------------------------------------------

    spot_values = df["spot"].dropna()

    if spot_values.empty or float(spot_values.iloc[0]) <= 0:
        raise RuntimeError(
            "Invalid underlying spot price."
        )

    spot = float(spot_values.iloc[0])

    # --------------------------------------------------------
    # ATM
    # --------------------------------------------------------

    df["distance"] = (
        df["strike"] - spot
    ).abs()

    atm_row = df.loc[
        df["distance"].idxmin()
    ]

    atm_strike = float(
        atm_row["strike"]
    )

    # --------------------------------------------------------
    # PCR
    # --------------------------------------------------------

    total_put_oi = df["pe_oi"].sum()
    total_call_oi = df["ce_oi"].sum()

    if total_call_oi > 0:
        pcr = total_put_oi / total_call_oi
    else:
        pcr = 0

    # --------------------------------------------------------
    # OI WALLS
    # --------------------------------------------------------

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
    # SCORES
    # --------------------------------------------------------

    bull = 50
    bear = 50

    reasons = []

    # PCR
    if pcr >= 1.20:
        bull += 10
        reasons.append(
            "PCR indicates stronger put-side OI support."
        )

    elif pcr <= 0.80:
        bear += 10
        reasons.append(
            "PCR indicates stronger call-side OI pressure."
        )

    else:
        reasons.append(
            "PCR is relatively balanced."
        )

    # --------------------------------------------------------
    # Change OI
    # --------------------------------------------------------

    near_put_chg = near["pe_chg_oi"].sum()
    near_call_chg = near["ce_chg_oi"].sum()

    if near_put_chg > near_call_chg:
        bull += 8
        reasons.append(
            "Near-spot put OI addition is stronger."
        )

    elif near_call_chg > near_put_chg:
        bear += 8
        reasons.append(
            "Near-spot call OI addition is stronger."
        )

    else:
        reasons.append(
            "Near-spot change in OI is balanced."
        )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    near_put_volume = near["pe_volume"].sum()
    near_call_volume = near["ce_volume"].sum()

    if near_put_volume > near_call_volume:
        bull += 5
        reasons.append(
            "Put-side option volume is stronger near spot."
        )

    elif near_call_volume > near_put_volume:
        bear += 5
        reasons.append(
            "Call-side option volume is stronger near spot."
        )

    # --------------------------------------------------------
    # PUT WALL
    # --------------------------------------------------------

    if put_wall < spot:
        bull += 5
        reasons.append(
            "Largest put OI wall is below spot."
        )

    elif put_wall > spot:
        bear += 5
        reasons.append(
            "Largest put OI wall is above spot."
        )

    # --------------------------------------------------------
    # CALL WALL
    # --------------------------------------------------------

    if call_wall > spot:
        bear += 5
        reasons.append(
            "Largest call OI wall is above spot."
        )

    elif call_wall < spot:
        bull += 5
        reasons.append(
            "Largest call OI wall is below spot."
        )

    # Keep scores within 0-100
    bull = min(100, max(0, bull))
    bear = min(100, max(0, bear))

    score_gap = abs(
        bull - bear
    )

    # --------------------------------------------------------
    # TRADE DECISION
    # --------------------------------------------------------

    if max(bull, bear) >= 70 and score_gap >= 15:
        action = "TRADE CANDIDATE"

    elif max(bull, bear) >= 58 and score_gap >= 9:
        action = "WATCH"

    else:
        action = "NO TRADE"

    if bull > bear:
        direction = "CE"
    else:
        direction = "PE"

    # --------------------------------------------------------
    # ADD CONFLICT REASON
    # --------------------------------------------------------

    if score_gap < 15:
        reasons.append(
            f"Directional conflict: Bull {bull} vs Bear {bear} "
            f"(gap {score_gap}). Trade candidate requires "
            f"a gap of at least 15."
        )

    # --------------------------------------------------------
    # SELECT OPTION
    # --------------------------------------------------------

    if direction == "CE":

        candidates = near[
            (near["ce_ltp"] > 0)
            & (near["ce_volume"] > 0)
        ].copy()

        if not candidates.empty:

            candidates["atm_distance"] = (
                candidates["strike"] - atm_strike
            ).abs()

            candidates = candidates.sort_values(
                ["atm_distance", "ce_volume"],
                ascending=[True, False]
            )

            selected = candidates.iloc[0]

            option_ltp = float(
                selected["ce_ltp"]
            )

            option_bid = float(
                selected["ce_bid"]
            )

            option_ask = float(
                selected["ce_ask"]
            )

            delta = float(
                selected["ce_delta"]
            )

            iv = float(
                selected["ce_iv"]
            )

            pop = float(
                selected["ce_pop"]
            )

            oi = float(
                selected["ce_oi"]
            )

            chg_oi = float(
                selected["ce_chg_oi"]
            )

            volume = float(
                selected["ce_volume"]
            )

            option_key = selected["ce_key"]

        else:
            selected = None

    else:

        candidates = near[
            (near["pe_ltp"] > 0)
            & (near["pe_volume"] > 0)
        ].copy()

        if not candidates.empty:

            candidates["atm_distance"] = (
                candidates["strike"] - atm_strike
            ).abs()

            candidates = candidates.sort_values(
                ["atm_distance", "pe_volume"],
                ascending=[True, False]
            )

            selected = candidates.iloc[0]

            option_ltp = float(
                selected["pe_ltp"]
            )

            option_bid = float(
                selected["pe_bid"]
            )

            option_ask = float(
                selected["pe_ask"]
            )

            delta = float(
                selected["pe_delta"]
            )

            iv = float(
                selected["pe_iv"]
            )

            pop = float(
                selected["pe_pop"]
            )

            oi = float(
                selected["pe_oi"]
            )

            chg_oi = float(
                selected["pe_chg_oi"]
            )

            volume = float(
                selected["pe_volume"]
            )

            option_key = selected["pe_key"]

        else:
            selected = None

    # --------------------------------------------------------
    # OPTION INFORMATION
    # --------------------------------------------------------

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

        # Use bid/ask midpoint when available.
        if option_bid > 0 and option_ask > 0:

            entry = (
                option_bid + option_ask
            ) / 2

        else:
            entry = option_ltp

        # ----------------------------------------------------
        # SPREAD
        # ----------------------------------------------------

        if option_bid > 0 and option_ask > 0:

            spread_pct = (
                (option_ask - option_bid)
                / entry
            ) * 100

        # ----------------------------------------------------
        # RISK PLAN
        # ----------------------------------------------------

        plan = RISK_PLANS[
            risk_profile
        ]

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

        # ----------------------------------------------------
        # WIDE SPREAD CHECK
        # ----------------------------------------------------

        if (
            spread_pct is not None
            and spread_pct > 8
        ):
            action = "NO TRADE"

            reasons.append(
                f"Option bid/ask spread is wide "
                f"({spread_pct:.2f}%)."
            )

        # ----------------------------------------------------
        # ENTRY STATUS
        # ----------------------------------------------------

        if action == "TRADE CANDIDATE":
            entry_status = (
                "ENTER NOW / CONFIRM TRIGGER"
            )

        elif action == "WATCH":
            entry_status = (
                "WAIT FOR CONFIRMATION"
            )

        else:
            entry_status = "NO TRADE"

    # --------------------------------------------------------
    # BIAS
    # --------------------------------------------------------

    if bull - bear >= 15:
        bias = "BULLISH"

    elif bear - bull >= 15:
        bias = "BEARISH"

    else:
        bias = "NEUTRAL"

    # --------------------------------------------------------
    # EXPIRY DAYS
    # --------------------------------------------------------

    expiry = (
        selected.get("expiry")
        if selected is not None
        else None
    )

    # expiry is not inside normalized row.
    # It will be supplied separately later.
    expiry_days = None

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

        "selected_strike": selected_strike,
        "option_ltp": option_ltp if selected is not None else None,
        "entry": entry,

        "stop_loss": stop_loss,
        "target1": target1,
        "target2": target2,

        "pop": pop if selected is not None else None,
        "delta": delta if selected is not None else None,
        "iv": iv if selected is not None else None,

        "oi": oi if selected is not None else None,
        "chg_oi": chg_oi if selected is not None else None,
        "volume": volume if selected is not None else None,

        "option_key": option_key if selected is not None else None,

        "spread_pct": spread_pct,

        "entry_status": entry_status,

        "reasons": reasons,

        "expiry_days": expiry_days,
    }


# ============================================================
# MAIN ANALYSIS
# ============================================================

def run_analysis(symbol, risk_profile):

    # --------------------------------------------------------
    # FIND UNDERLYING
    # --------------------------------------------------------

    underlying = find_underlying(
        symbol
    )

    underlying_key = underlying.get(
        "instrument_key"
    )

    if not underlying_key:
        raise RuntimeError(
            "Underlying instrument key was not found."
        )

    # --------------------------------------------------------
    # GET LIVE V3 QUOTE
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

    live_price = float(
        quote.get("last_price")
        or quote.get("ltp")
        or 0
    )

    if live_price <= 0:

        # Fallback to nested last traded price
        ltpc = quote.get("ltpc") or {}

        live_price = float(
            ltpc.get("ltp")
            or 0
        )

    if live_price <= 0:
        raise RuntimeError(
            "Upstox returned an invalid live price."
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

    # Use the V3 live price for spot.
    df["spot"] = live_price

    # --------------------------------------------------------
    # ANALYZE
    # --------------------------------------------------------

    result = analyze_chain(
        df,
        risk_profile
    )

    result["expiry"] = expiry_date

    today = datetime.now(
        IST
    ).date()

    result["expiry_days"] = (
        expiry_date - today
    ).days

    result["symbol"] = symbol.upper()

    result["underlying_key"] = underlying_key

    result["upstox_snapshot_time"] = snapshot_dt

    result["underlying_last_trade_time"] = (
        last_trade_dt
    )

    result["app_fetch_time"] = (
        datetime.now(IST)
    )

    # --------------------------------------------------------
    # GET SELECTED OPTION TIMESTAMP
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

    result["selected_option_snapshot_time"] = (
        selected_option_snapshot
    )

    result["selected_option_last_trade_time"] = (
        selected_option_last_trade
    )

    return result, df


# ============================================================
# HEADER
# ============================================================

st.title(
    "📈 F&O Pro Trader Assistant"
)

st.caption(
    "Live Upstox market data • Option-chain analysis • "
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
        placeholder="Example: KOTAKBANK, RELIANCE, SBIN, NIFTY",
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
# LIVE ANALYSIS FUNCTION
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

        # ----------------------------------------------------
        # NOTHING SELECTED YET
        # ----------------------------------------------------

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
                f"Refreshing **{active_symbol}** every 30 seconds"
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
            or st.session_state.active_result is None
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
        # ERROR HANDLING
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
                "successful data while the next refresh "
                "continues."
            )

            st.caption(
                f"Refresh error: "
                f"{st.session_state.last_error}"
            )

        # ====================================================
        # TIMESTAMP SECTION
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

        st.success(
            f"🟢 **LIVE UPSTOX SNAPSHOT** • "
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

        st.caption(
            "The Upstox snapshot time is the market-data "
            "response timestamp. The last-trade time is the "
            "time of the latest underlying trade reported by "
            "Upstox. App Fetch Time is only the time this "
            "Streamlit app fetched the data."
        )

        # ====================================================
        # MARKET SNAPSHOT
        # ====================================================

        st.subheader(
            "📊 Market Snapshot"
        )

        c1, c2, c3, c4, c5, c6 = st.columns(
            6
        )

        with c1:

            st.metric(
                "Live Price",
                f"₹{result['spot']:.2f}"
            )

        with c2:

            st.metric(
                "Bias",
                result["bias"]
            )

        with c3:

            st.metric(
                "PCR",
                f"{result['pcr']:.2f}"
            )

        with c4:

            st.metric(
                "Put OI Wall",
                f"{result['put_wall']:.0f}"
            )

        with c5:

            st.metric(
                "Call OI Wall",
                f"{result['call_wall']:.0f}"
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
            "🎯 Directional Score"
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
                "Expiry Days",
                result["expiry_days"]
            )

        # ====================================================
        # TRADE DECISION
        # ====================================================

        st.subheader(
            "🚦 Trade Decision"
        )

        action = result["action"]
        direction = result["direction"]

        if action == "TRADE CANDIDATE":

            if direction == "CE":

                st.success(
                    f"🟢 **CALL — BUY**\n\n"
                    f"Suggested Strike: "
                    f"{result['selected_strike']:.0f}"
                )

            else:

                st.success(
                    f"🟢 **PUT — BUY**\n\n"
                    f"Suggested Strike: "
                    f"{result['selected_strike']:.0f}"
                )

        elif action == "WATCH":

            if direction == "CE":

                st.warning(
                    f"🟡 **CALL — BUY AFTER CONFIRMATION**\n\n"
                    f"Suggested Strike: "
                    f"{result['selected_strike']:.0f}"
                )

            else:

                st.warning(
                    f"🟡 **PUT — BUY AFTER CONFIRMATION**\n\n"
                    f"Suggested Strike: "
                    f"{result['selected_strike']:.0f}"
                )

        else:

            st.info(
                "⚪ **NO TRADE**\n\n"
                "Current signals are not sufficiently aligned."
            )

        # ====================================================
        # TRADE PLAN
        # ====================================================

        if result["selected_strike"] is not None:

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
                    f"₹{result['entry']:.2f}"
                    if result["entry"] is not None
                    else "N/A"
                )

            with p4:

                st.metric(
                    "Probability of Profit",
                    f"{result['pop']:.2f}%"
                    if result["pop"] is not None
                    else "N/A"
                )

            p5, p6, p7, p8 = st.columns(
                4
            )

            with p5:

                st.metric(
                    "Stop Loss",
                    f"₹{result['stop_loss']:.2f}"
                    if result["stop_loss"] is not None
                    else "N/A"
                )

            with p6:

                st.metric(
                    "Target 1",
                    f"₹{result['target1']:.2f}"
                    if result["target1"] is not None
                    else "N/A"
                )

            with p7:

                st.metric(
                    "Target 2",
                    f"₹{result['target2']:.2f}"
                    if result["target2"] is not None
                    else "N/A"
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
                    f"{result['delta']:.3f}"
                    if result["delta"] is not None
                    else "N/A"
                )

            with p10:

                st.metric(
                    "IV",
                    f"{result['iv']:.2f}%"
                    if result["iv"] is not None
                    else "N/A"
                )

            with p11:

                st.metric(
                    "Signal Strength",
                    f"{max(result['bull_score'], result['bear_score'])}/100"
                )

        # ====================================================
        # REFERENCE / SELECTED OPTION
        # ====================================================

        st.subheader(
            "🎯 Selected Option"
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
                    f"{result['pop']:.2f}%"
                    if result["pop"] is not None
                    else "N/A"
                )

            o5, o6, o7, o8 = st.columns(
                4
            )

            with o5:

                st.metric(
                    "Delta",
                    f"{result['delta']:.3f}"
                )

            with o6:

                st.metric(
                    "IV",
                    f"{result['iv']:.2f}%"
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
                    "ℹ️ This option is shown only as a "
                    "**reference option**. The engine is "
                    "currently saying NO TRADE."
                )

        # ====================================================
        # REASONS
        # ====================================================

        st.subheader(
            "🧠 Why the Engine Reached This Decision"
        )

        for reason in result["reasons"]:

            st.write(
                f"• {reason}"
            )

        # ====================================================
        # OI SUPPORT / RESISTANCE
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

        if chain is not None and not chain.empty:

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
                .sort_values("strike")
                .reset_index(drop=True)
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
            "• Live price is obtained from Upstox V3 "
            "Full Market Quote."
        )

        st.write(
            "• Option-chain data is obtained directly "
            "from the Upstox option-chain API."
        )

        st.write(
            "• Probability of Profit (PoP) is taken "
            "from the Upstox option-chain Greeks response."
        )

        st.write(
            "• PoP is NOT calculated from the Bull/Bear score."
        )

        st.write(
            "• Bull/Bear score is a directional signal "
            "based on PCR, OI, Change OI, volume and OI walls."
        )

        st.write(
            "• The application can return NO TRADE when "
            "signals are conflicting or the option spread "
            "is too wide."
        )

        st.write(
            "• This application does not place orders "
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

            if st.session_state.last_successful_refresh:

                st.caption(
                    "Last successful app refresh: "
                    + display_dt(
                        st.session_state.last_successful_refresh
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
    # RUN LIVE ANALYSIS
    # ========================================================

    render_live_analysis()
