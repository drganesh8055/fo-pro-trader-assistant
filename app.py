import streamlit as st
import requests
import pandas as pd
from datetime import datetime, date

# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Option Trade Assistant",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Option Trade Assistant")
st.caption(
    "Live Upstox market-data analysis • Read-only • No automatic orders • No simulated prices"
)

# ============================================================
# SETTINGS
# ============================================================

UPSTOX_BASE = "https://api.upstox.com"

RISK_SETTINGS = {
    "Conservative": {
        "sl": 0.18,
        "t1": 0.25,
        "t2": 0.40
    },
    "Balanced": {
        "sl": 0.22,
        "t1": 0.35,
        "t2": 0.55
    },
    "Aggressive": {
        "sl": 0.28,
        "t1": 0.45,
        "t2": 0.70
    }
}

INDEX_NAMES = {
    "NIFTY": "Nifty 50",
    "BANKNIFTY": "Nifty Bank",
    "FINNIFTY": "Nifty Financial Services",
    "MIDCPNIFTY": "Nifty Midcap Select"
}

# ============================================================
# TOKEN
# ============================================================

def get_token():

    token = st.secrets.get(
        "UPSTOX_ACCESS_TOKEN",
        ""
    )

    if not token:

        raise RuntimeError(
            "UPSTOX_ACCESS_TOKEN is missing from Streamlit Secrets."
        )

    return token


def headers():

    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_token()}"
    }


# ============================================================
# UPSTOX REQUEST
# ============================================================

def upstox_get(endpoint, params=None):

    url = f"{UPSTOX_BASE}{endpoint}"

    try:

        response = requests.get(
            url,
            headers=headers(),
            params=params,
            timeout=20
        )

    except requests.exceptions.Timeout:

        raise RuntimeError(
            "Upstox request timed out. Please try Analyze again."
        )

    except requests.exceptions.RequestException as e:

        raise RuntimeError(
            f"Network error while connecting to Upstox: {e}"
        )

    if response.status_code != 200:

        try:
            detail = response.json()

        except Exception:
            detail = response.text[:500]

        raise RuntimeError(
            f"Upstox HTTP {response.status_code}: {detail}"
        )

    try:

        data = response.json()

    except Exception:

        raise RuntimeError(
            "Upstox returned an invalid response."
        )

    if data.get("status") not in (
        None,
        "success"
    ):

        raise RuntimeError(
            f"Upstox returned status: {data.get('status')}"
        )

    return data


# ============================================================
# FIND UNDERLYING
# ============================================================

def find_underlying(symbol):

    symbol = symbol.strip().upper()

    # --------------------------------------------------------
    # INDEX
    # --------------------------------------------------------

    if symbol in INDEX_NAMES:

        result = upstox_get(
            "/v2/instruments/search",
            params={
                "query": INDEX_NAMES[symbol],
                "exchanges": "NSE",
                "segments": "INDEX",
                "page_number": 1,
                "records": 10
            }
        )

        rows = result.get(
            "data",
            []
        )

        if not rows:

            raise RuntimeError(
                f"Could not find Upstox instrument for {symbol}."
            )

        for row in rows:

            if row.get("segment") == "NSE_INDEX":

                return {
                    "symbol": symbol,
                    "name": row.get(
                        "name",
                        symbol
                    ),
                    "instrument_key": row.get(
                        "instrument_key"
                    ),
                    "type": "INDEX"
                }

        raise RuntimeError(
            f"Could not identify NSE index instrument for {symbol}."
        )

    # --------------------------------------------------------
    # STOCK / EQUITY
    # --------------------------------------------------------

    result = upstox_get(
        "/v2/instruments/search",
        params={
            "query": symbol,
            "exchanges": "NSE",
            "segments": "EQ",
            "page_number": 1,
            "records": 20
        }
    )

    rows = result.get(
        "data",
        []
    )

    if not rows:

        raise RuntimeError(
            f"Could not find NSE equity instrument for {symbol}."
        )

    exact = [
        r
        for r in rows
        if str(
            r.get(
                "trading_symbol",
                ""
            )
        ).upper() == symbol
        and r.get("segment") == "NSE_EQ"
    ]

    if exact:

        row = exact[0]

    else:

        nse_rows = [
            r
            for r in rows
            if r.get("segment") == "NSE_EQ"
        ]

        if not nse_rows:

            raise RuntimeError(
                f"Could not identify NSE equity instrument for {symbol}."
            )

        row = nse_rows[0]

    return {
        "symbol": symbol,
        "name": row.get(
            "name",
            symbol
        ),
        "instrument_key": row.get(
            "instrument_key"
        ),
        "type": "EQUITY"
    }


# ============================================================
# OPTION CONTRACTS / EXPIRY
# ============================================================

def get_option_contracts(underlying_key):

    result = upstox_get(
        "/v2/option/contract",
        params={
            "instrument_key": underlying_key
        }
    )

    rows = result.get(
        "data",
        []
    )

    if not rows:

        raise RuntimeError(
            "Upstox returned no option contracts for this underlying."
        )

    return rows


def nearest_expiry(contracts):

    today = date.today()

    expiries = sorted({
        str(
            row.get("expiry")
        )
        for row in contracts
        if row.get("expiry")
    })

    valid = []

    for expiry in expiries:

        try:

            d = datetime.strptime(
                expiry,
                "%Y-%m-%d"
            ).date()

            if d >= today:

                valid.append(d)

        except Exception:

            continue

    if not valid:

        raise RuntimeError(
            "No current or future option expiry was returned by Upstox."
        )

    return valid[0].strftime(
        "%Y-%m-%d"
    )


# ============================================================
# OPTION CHAIN
# ============================================================

def get_option_chain(
    underlying_key,
    expiry
):

    result = upstox_get(
        "/v2/option/chain",
        params={
            "instrument_key": underlying_key,
            "expiry_date": expiry
        }
    )

    rows = result.get(
        "data",
        []
    )

    if not rows:

        raise RuntimeError(
            "Upstox returned an empty option chain."
        )

    return rows


# ============================================================
# NORMALIZE OPTION CHAIN
# ============================================================

def normalize_chain(rows):

    records = []

    for row in rows:

        strike = row.get(
            "strike_price"
        )

        spot = row.get(
            "underlying_spot_price"
        )

        if strike is None:

            continue

        call = row.get(
            "call_options"
        ) or {}

        put = row.get(
            "put_options"
        ) or {}

        call_md = call.get(
            "market_data"
        ) or {}

        put_md = put.get(
            "market_data"
        ) or {}

        call_g = call.get(
            "option_greeks"
        ) or {}

        put_g = put.get(
            "option_greeks"
        ) or {}

        # ----------------------------------------------------
        # OI
        # ----------------------------------------------------

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

        call_chg_oi = (
            call_oi -
            call_prev_oi
        )

        put_chg_oi = (
            put_oi -
            put_prev_oi
        )

        # ----------------------------------------------------
        # PROBABILITY OF PROFIT
        # Upstox provides this directly in option_greeks.pop
        # ----------------------------------------------------

        ce_pop = float(
            call_g.get("pop") or 0
        )

        pe_pop = float(
            put_g.get("pop") or 0
        )

        records.append({

            "strike": float(
                strike
            ),

            "spot": float(
                spot or 0
            ),

            # =================================================
            # CALL
            # =================================================

            "ce_ltp": float(
                call_md.get("ltp") or 0
            ),

            "ce_oi": call_oi,

            "ce_prev_oi": call_prev_oi,

            "ce_chg_oi": call_chg_oi,

            "ce_volume": float(
                call_md.get("volume") or 0
            ),

            "ce_iv": float(
                call_g.get("iv") or 0
            ),

            "ce_delta": float(
                call_g.get("delta") or 0
            ),

            "ce_pop": ce_pop,

            "ce_bid": float(
                call_md.get("bid_price") or 0
            ),

            "ce_ask": float(
                call_md.get("ask_price") or 0
            ),

            "ce_key": call.get(
                "instrument_key"
            ),

            # =================================================
            # PUT
            # =================================================

            "pe_ltp": float(
                put_md.get("ltp") or 0
            ),

            "pe_oi": put_oi,

            "pe_prev_oi": put_prev_oi,

            "pe_chg_oi": put_chg_oi,

            "pe_volume": float(
                put_md.get("volume") or 0
            ),

            "pe_iv": float(
                put_g.get("iv") or 0
            ),

            "pe_delta": float(
                put_g.get("delta") or 0
            ),

            "pe_pop": pe_pop,

            "pe_bid": float(
                put_md.get("bid_price") or 0
            ),

            "pe_ask": float(
                put_md.get("ask_price") or 0
            ),

            "pe_key": put.get(
                "instrument_key"
            )
        })

    df = pd.DataFrame(
        records
    )

    if df.empty:

        raise RuntimeError(
            "Unable to construct the option chain from Upstox data."
        )

    return df.sort_values(
        "strike"
    ).reset_index(
        drop=True
    )


# ============================================================
# ANALYSIS
# ============================================================

def analyze_chain(
    df,
    risk_profile
):

    spot = float(
        df["spot"].iloc[0]
    )

    if spot <= 0:

        raise RuntimeError(
            "Invalid underlying price received from Upstox."
        )

    # --------------------------------------------------------
    # ATM
    # --------------------------------------------------------

    df["distance"] = abs(
        df["strike"] -
        spot
    )

    atm_index = df[
        "distance"
    ].idxmin()

    atm_strike = float(
        df.loc[
            atm_index,
            "strike"
        ]
    )

    # --------------------------------------------------------
    # PCR
    # --------------------------------------------------------

    total_call_oi = df[
        "ce_oi"
    ].sum()

    total_put_oi = df[
        "pe_oi"
    ].sum()

    if total_call_oi > 0:

        pcr = (
            total_put_oi /
            total_call_oi
        )

    else:

        pcr = 0

    # --------------------------------------------------------
    # OI WALLS
    # --------------------------------------------------------

    call_wall_row = df.loc[
        df["ce_oi"].idxmax()
    ]

    put_wall_row = df.loc[
        df["pe_oi"].idxmax()
    ]

    call_wall = float(
        call_wall_row["strike"]
    )

    put_wall = float(
        put_wall_row["strike"]
    )

    # --------------------------------------------------------
    # NEAR ATM
    # --------------------------------------------------------

    near = df[
        (df["strike"] >= spot * 0.97) &
        (df["strike"] <= spot * 1.03)
    ].copy()

    if near.empty:

        near = df.copy()

    call_chg_oi = near[
        "ce_chg_oi"
    ].sum()

    put_chg_oi = near[
        "pe_chg_oi"
    ].sum()

    call_volume = near[
        "ce_volume"
    ].sum()

    put_volume = near[
        "pe_volume"
    ].sum()

    # ========================================================
    # SCORE
    # ========================================================

    bull = 50
    bear = 50

    reasons = []

    # --------------------------------------------------------
    # PCR
    # --------------------------------------------------------

    if pcr >= 1.20:

        bull += 12

        reasons.append(
            "PCR indicates stronger put-side OI support."
        )

    elif pcr <= 0.75:

        bear += 12

        reasons.append(
            "PCR indicates stronger call-side OI pressure."
        )

    elif pcr >= 1.00:

        bull += 5

    else:

        bear += 5

    # --------------------------------------------------------
    # CHANGE OI
    # --------------------------------------------------------

    if put_chg_oi > call_chg_oi * 1.10:

        bull += 10

        reasons.append(
            "Near-spot put OI addition is stronger."
        )

    elif call_chg_oi > put_chg_oi * 1.10:

        bear += 10

        reasons.append(
            "Near-spot call OI addition is stronger."
        )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    if put_volume > call_volume * 1.15:

        bull += 8

        reasons.append(
            "Put-side option volume is stronger near spot."
        )

    elif call_volume > put_volume * 1.15:

        bear += 8

        reasons.append(
            "Call-side option volume is stronger near spot."
        )

    # --------------------------------------------------------
    # OI WALL
    # --------------------------------------------------------

    if put_wall < spot:

        bull += 8

        reasons.append(
            "Largest put OI wall is below spot."
        )

    else:

        bear += 5

    if call_wall > spot:

        bull += 5

        reasons.append(
            "Largest call OI wall is above spot."
        )

    else:

        bear += 8

        reasons.append(
            "Largest call OI wall is at/below spot."
        )

    # --------------------------------------------------------
    # CLAMP
    # --------------------------------------------------------

    bull = min(
        bull,
        100
    )

    bear = min(
        bear,
        100
    )

    difference = abs(
        bull -
        bear
    )

    if difference < 8:

        bias = "NEUTRAL"

    elif bull > bear:

        bias = "BULLISH"

    else:

        bias = "BEARISH"

    strength = max(
        bull,
        bear
    )

    # ========================================================
    # ACTION
    # ========================================================

    if (
        strength >= 70
        and
        difference >= 15
    ):

        action = "TRADE CANDIDATE"

    elif (
        strength >= 58
        and
        difference >= 9
    ):

        action = "WATCH"

    else:

        action = "NO TRADE"

    # ========================================================
    # SELECT OPTION
    # ========================================================

    if bull > bear:

        side = "CE"

        candidates = near[
            (near["ce_ltp"] > 0) &
            (near["ce_volume"] > 0)
        ].copy()

        if not candidates.empty:

            candidates[
                "atm_distance"
            ] = abs(
                candidates["strike"] -
                atm_strike
            )

            selected = candidates.sort_values(
                [
                    "atm_distance",
                    "ce_volume"
                ],
                ascending=[
                    True,
                    False
                ]
            ).iloc[0]

            suggested_strike = float(
                selected["strike"]
            )

            premium = float(
                selected["ce_ltp"]
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

            bid = float(
                selected["ce_bid"]
            )

            ask = float(
                selected["ce_ask"]
            )

            option_key = selected[
                "ce_key"
            ]

        else:

            selected = None

    else:

        side = "PE"

        candidates = near[
            (near["pe_ltp"] > 0) &
            (near["pe_volume"] > 0)
        ].copy()

        if not candidates.empty:

            candidates[
                "atm_distance"
            ] = abs(
                candidates["strike"] -
                atm_strike
            )

            selected = candidates.sort_values(
                [
                    "atm_distance",
                    "pe_volume"
                ],
                ascending=[
                    True,
                    False
                ]
            ).iloc[0]

            suggested_strike = float(
                selected["strike"]
            )

            premium = float(
                selected["pe_ltp"]
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

            bid = float(
                selected["pe_bid"]
            )

            ask = float(
                selected["pe_ask"]
            )

            option_key = selected[
                "pe_key"
            ]

        else:

            selected = None

    # ========================================================
    # NO LIQUID OPTION
    # ========================================================

    if selected is None:

        action = "NO TRADE"

        reasons.append(
            "No liquid near-ATM option was returned."
        )

        return {

            "spot": spot,

            "atm": atm_strike,

            "suggested_strike": None,

            "pcr": pcr,

            "call_wall": call_wall,

            "put_wall": put_wall,

            "bull": bull,

            "bear": bear,

            "bias": bias,

            "action": action,

            "side": side,

            "expiry_days": None,

            "option_key": None,

            "premium": 0,

            "delta": 0,

            "iv": 0,

            "pop": 0,

            "oi": 0,

            "chg_oi": 0,

            "volume": 0,

            "bid": 0,

            "ask": 0,

            "entry": 0,

            "sl": 0,

            "t1": 0,

            "t2": 0,

            "trigger": 0,

            "reasons": reasons
        }

    # ========================================================
    # LIQUIDITY CHECK
    # ========================================================

    spread = 0

    if (
        bid > 0
        and
        ask > 0
    ):

        spread = (
            (ask - bid) /
            ((ask + bid) / 2)
        ) * 100

    if spread > 8:

        action = "NO TRADE"

        reasons.append(
            f"Option spread is too wide ({spread:.1f}%)."
        )

    # ========================================================
    # POP QUALITY CHECK
    # ========================================================

    if pop <= 0:

        reasons.append(
            "Upstox did not provide a valid Probability of Profit "
            "for the selected option."
        )

    # ========================================================
    # RISK PLAN
    # ========================================================

    risk = RISK_SETTINGS[
        risk_profile
    ]

    if (
        bid > 0
        and
        ask > 0
    ):

        entry = (
            bid +
            ask
        ) / 2

    else:

        entry = premium

    if entry <= 0:

        action = "NO TRADE"

        reasons.append(
            "Invalid option entry price."
        )

    sl = entry * (
        1 -
        risk["sl"]
    )

    t1 = entry * (
        1 +
        risk["t1"]
    )

    t2 = entry * (
        1 +
        risk["t2"]
    )

    # ========================================================
    # TRIGGER
    # ========================================================

    if side == "CE":

        trigger = max(
            spot,
            atm_strike
        )

    else:

        trigger = min(
            spot,
            atm_strike
        )

    # ========================================================
    # ENTRY STATUS
    # ========================================================

    if action == "TRADE CANDIDATE":

        entry_status = "ENTER NOW / CONFIRM TRIGGER"

    elif action == "WATCH":

        entry_status = "WAIT FOR CONFIRMATION"

    else:

        entry_status = "NO TRADE"

    # ========================================================
    # RETURN
    # ========================================================

    return {

        "spot": spot,

        "atm": atm_strike,

        "suggested_strike":
            suggested_strike,

        "pcr": pcr,

        "call_wall":
            call_wall,

        "put_wall":
            put_wall,

        "bull":
            bull,

        "bear":
            bear,

        "bias":
            bias,

        "action":
            action,

        "side":
            side,

        "option_key":
            option_key,

        "premium":
            premium,

        "delta":
            delta,

        "iv":
            iv,

        "pop":
            pop,

        "oi":
            oi,

        "chg_oi":
            chg_oi,

        "volume":
            volume,

        "bid":
            bid,

        "ask":
            ask,

        "spread":
            spread,

        "entry":
            entry,

        "sl":
            sl,

        "t1":
            t1,

        "t2":
            t2,

        "trigger":
            trigger,

        "entry_status":
            entry_status,

        "reasons":
            reasons
    }


# ============================================================
# MAIN ANALYSIS
# ============================================================

def run_analysis(
    symbol,
    risk_profile
):

    underlying = find_underlying(
        symbol
    )

    contracts = get_option_contracts(
        underlying[
            "instrument_key"
        ]
    )

    expiry = nearest_expiry(
        contracts
    )

    chain_rows = get_option_chain(
        underlying[
            "instrument_key"
        ],
        expiry
    )

    df = normalize_chain(
        chain_rows
    )

    result = analyze_chain(
        df,
        risk_profile
    )

    expiry_date = datetime.strptime(
        expiry,
        "%Y-%m-%d"
    ).date()

    result["expiry"] = expiry

    result["expiry_days"] = (
        expiry_date -
        date.today()
    ).days

    result["underlying_name"] = (
        underlying["name"]
    )

    result["underlying_key"] = (
        underlying["instrument_key"]
    )

    return result, df


# ============================================================
# USER INTERFACE
# ============================================================

st.info(
    "Enter an NSE F&O stock or index. The app uses Upstox read-only "
    "market data and does not place orders."
)

col1, col2 = st.columns(
    [2, 1]
)

with col1:

    symbol_input = st.text_input(
        "Enter F&O stock / index",
        placeholder=(
            "Example: KOTAKBANK, RELIANCE, "
            "NIFTY, BANKNIFTY"
        )
    )

with col2:

    risk_profile = st.selectbox(
        "Risk profile",
        list(
            RISK_SETTINGS.keys()
        ),
        index=1
    )

analyze_button = st.button(
    "🔍 ANALYZE",
    type="primary",
    use_container_width=True
)

# ============================================================
# ANALYZE
# ============================================================

if analyze_button:

    symbol = symbol_input.strip().upper()

    if not symbol:

        st.warning(
            "Please enter an F&O stock or index."
        )

        st.stop()

    try:

        with st.spinner(
            f"Connecting to Upstox and analysing {symbol}..."
        ):

            result, chain = run_analysis(
                symbol,
                risk_profile
            )

        st.success(
            f"🟢 LIVE DATA RECEIVED from Upstox • "
            f"{datetime.now().strftime('%d-%b-%Y %H:%M:%S')}"
        )

        # ====================================================
        # MARKET SNAPSHOT
        # ====================================================

        st.subheader(
            "📊 Market Snapshot"
        )

        m1, m2, m3, m4, m5, m6 = st.columns(6)

        m1.metric(
            "Live Price",
            f"₹{result['spot']:,.2f}"
        )

        m2.metric(
            "Bias",
            result["bias"]
        )

        m3.metric(
            "PCR",
            f"{result['pcr']:.2f}"
        )

        m4.metric(
            "Put OI Wall",
            f"{result['put_wall']:,.0f}"
        )

        m5.metric(
            "Call OI Wall",
            f"{result['call_wall']:,.0f}"
        )

        m6.metric(
            "Expiry",
            result["expiry"]
        )

        st.divider()

        # ====================================================
        # SCORES
        # ====================================================

        s1, s2, s3 = st.columns(3)

        s1.metric(
            "Bull Score",
            f"{result['bull']}/100"
        )

        s2.metric(
            "Bear Score",
            f"{result['bear']}/100"
        )

        s3.metric(
            "Expiry Days",
            result["expiry_days"]
        )

        # ====================================================
        # TRADE DECISION
        # ====================================================

        st.subheader(
            "🎯 Trade Decision"
        )

        if result["action"] == "TRADE CANDIDATE":

            if result["side"] == "CE":

                st.success(
                    f"🟢 CALL — BUY\n\n"
                    f"Suggested Strike: "
                    f"{result['suggested_strike']:,.0f} CE"
                )

            else:

                st.success(
                    f"🟢 PUT — BUY\n\n"
                    f"Suggested Strike: "
                    f"{result['suggested_strike']:,.0f} PE"
                )

        elif result["action"] == "WATCH":

            if result["side"] == "CE":

                st.warning(
                    f"🟡 CALL — BUY AFTER CONFIRMATION\n\n"
                    f"Suggested Strike: "
                    f"{result['suggested_strike']:,.0f} CE"
                )

            else:

                st.warning(
                    f"🟡 PUT — BUY AFTER CONFIRMATION\n\n"
                    f"Suggested Strike: "
                    f"{result['suggested_strike']:,.0f} PE"
                )

        else:

            st.error(
                "⚪ NO TRADE\n\n"
                "Current market conditions do not meet "
                "the required strength/liquidity rules."
            )

        # ====================================================
        # TRADE PLAN
        # ====================================================

        if result["action"] != "NO TRADE":

            st.subheader(
                "💰 Trade Plan"
            )

            # First row
            t1, t2, t3, t4 = st.columns(4)

            t1.metric(
                "Action",
                (
                    "CALL BUY"
                    if result["side"] == "CE"
                    else "PUT BUY"
                )
            )

            t2.metric(
                "Strike",
                f"{result['suggested_strike']:,.0f}"
            )

            t3.metric(
                "Entry",
                f"₹{result['entry']:.2f}"
            )

            t4.metric(
                "Probability of Profit",
                (
                    f"{result['pop']:.2f}%"
                    if result["pop"] > 0
                    else "N/A"
                )
            )

            # Second row
            t5, t6, t7, t8 = st.columns(4)

            t5.metric(
                "Stop Loss",
                f"₹{result['sl']:.2f}"
            )

            t6.metric(
                "Target 1",
                f"₹{result['t1']:.2f}"
            )

            t7.metric(
                "Target 2",
                f"₹{result['t2']:.2f}"
            )

            t8.metric(
                "Entry Status",
                result["entry_status"]
            )

            # Third row
            t9, t10, t11, t12 = st.columns(4)

            t9.metric(
                "Delta",
                f"{result['delta']:.3f}"
            )

            t10.metric(
                "IV",
                f"{result['iv']:.2f}%"
            )

            t11.metric(
                "Expiry",
                result["expiry"]
            )

            t12.metric(
                "Signal Strength",
                (
                    f"{result['bull']}/100"
                    if result["side"] == "CE"
                    else f"{result['bear']}/100"
                )
            )

            st.info(
                f"Entry trigger: underlying around "
                f"₹{result['trigger']:,.2f} "
                f"with the selected option maintaining liquidity."
            )

            # ------------------------------------------------
            # IMPORTANT PO P EXPLANATION
            # ------------------------------------------------

            if result["pop"] > 0:

                st.info(
                    f"📊 **Probability of Profit: "
                    f"{result['pop']:.2f}%**\n\n"
                    "This is the Probability of Profit supplied "
                    "by Upstox for the selected option. It should "
                    "not be treated as a guarantee of profit and "
                    "does not indicate how large the profit may be."
                )

            else:

                st.warning(
                    "Probability of Profit is currently unavailable "
                    "from Upstox for the selected option."
                )

            st.write(
                "**Exit plan:** Book partial profit at Target 1. "
                "After Target 1, protect the remaining position by "
                "moving the stop toward entry/breakeven. Exit the "
                "remaining position at Target 2 or if the original "
                "setup becomes invalid."
            )

        # ====================================================
        # SUGGESTED OPTION
        # ====================================================

        st.subheader(
            "🔎 Suggested Trade Option"
        )

        if result["suggested_strike"] is not None:

            st.info(
                f"📌 Suggested Option: "
                f"{result['suggested_strike']:,.0f} "
                f"{result['side']}"
            )

        o1, o2, o3, o4, o5, o6, o7, o8 = st.columns(8)

        o1.metric(
            "Strike",
            (
                f"{result['suggested_strike']:,.0f}"
                if result["suggested_strike"] is not None
                else "—"
            )
        )

        o2.metric(
            "Option",
            result["side"]
        )

        o3.metric(
            "LTP",
            f"₹{result['premium']:.2f}"
        )

        o4.metric(
            "PoP",
            (
                f"{result['pop']:.2f}%"
                if result["pop"] > 0
                else "N/A"
            )
        )

        o5.metric(
            "Delta",
            f"{result['delta']:.3f}"
        )

        o6.metric(
            "IV",
            f"{result['iv']:.2f}%"
        )

        o7.metric(
            "OI",
            f"{result['oi']:,.0f}"
        )

        o8.metric(
            "Chg OI",
            f"{result['chg_oi']:,.0f}"
        )

        st.caption(
            "The suggested strike is the live near-ATM strike "
            "selected from the Upstox option chain."
        )

        # ====================================================
        # REASONS
        # ====================================================

        st.subheader(
            "🧠 Why the Engine Reached This View"
        )

        if result["reasons"]:

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

        r1, r2, r3 = st.columns(3)

        r1.metric(
            "Put OI Support",
            f"₹{result['put_wall']:,.0f}"
        )

        r2.metric(
            "ATM",
            f"₹{result['atm']:,.0f}"
        )

        r3.metric(
            "Call OI Resistance",
            f"₹{result['call_wall']:,.0f}"
        )

        # ====================================================
        # OPTION CHAIN
        # ====================================================

        with st.expander(
            "📋 View Live Option Chain"
        ):

            display = chain.copy()

            display["CE LTP"] = (
                display["ce_ltp"].round(2)
            )

            display["CE OI"] = (
                display["ce_oi"].round(0)
            )

            display["CE Chg OI"] = (
                display["ce_chg_oi"].round(0)
            )

            display["CE Vol"] = (
                display["ce_volume"].round(0)
            )

            display["CE IV"] = (
                display["ce_iv"].round(2)
            )

            display["CE Delta"] = (
                display["ce_delta"].round(3)
            )

            display["CE PoP"] = (
                display["ce_pop"].round(2)
            )

            display["Strike"] = (
                display["strike"].round(2)
            )

            display["PE Delta"] = (
                display["pe_delta"].round(3)
            )

            display["PE IV"] = (
                display["pe_iv"].round(2)
            )

            display["PE PoP"] = (
                display["pe_pop"].round(2)
            )

            display["PE Vol"] = (
                display["pe_volume"].round(0)
            )

            display["PE Chg OI"] = (
                display["pe_chg_oi"].round(0)
            )

            display["PE OI"] = (
                display["pe_oi"].round(0)
            )

            display["PE LTP"] = (
                display["pe_ltp"].round(2)
            )

            final_columns = [

                "CE LTP",
                "CE OI",
                "CE Chg OI",
                "CE Vol",
                "CE IV",
                "CE Delta",
                "CE PoP",

                "Strike",

                "PE PoP",
                "PE Delta",
                "PE IV",
                "PE Vol",
                "PE Chg OI",
                "PE OI",
                "PE LTP"
            ]

            st.dataframe(
                display[
                    final_columns
                ],
                use_container_width=True,
                hide_index=True
            )

        # ====================================================
        # DATA QUALITY
        # ====================================================

        with st.expander(
            "ℹ️ Data & Signal Quality"
        ):

            st.write(
                "Data source: Upstox Market Data / Option Chain API."
            )

            st.write(
                "The app does not create simulated prices, OI "
                "or option-chain values."
            )

            st.write(
                "Delta, IV and Probability of Profit are taken "
                "from the Upstox option-chain response."
            )

            st.write(
                "Probability of Profit is shown separately from "
                "the Bull/Bear directional score. The app does "
                "not convert its signal score into a fake probability."
            )

            st.write(
                "The app currently focuses on live "
                "option-chain/OI structure rather than "
                "inventing RSI or EMA values when reliable "
                "historical data is unavailable."
            )

            st.write(
                f"Underlying instrument: "
                f"{result['underlying_key']}"
            )

    except Exception as e:

        st.error(
            "🔴 UPSTOX DATA UNAVAILABLE"
        )

        st.write(
            "The app could not obtain valid live Upstox data."
        )

        st.code(
            str(e)
        )

        st.info(
            "No simulated data has been used. "
            "Check that your Upstox Analytics Token is present "
            "in Streamlit Secrets and try again."
        )

else:

    st.subheader(
        "👋 How to use"
    )

    st.write(
        "1. Enter an F&O stock or index."
    )

    st.write(
        "2. Select Conservative, Balanced or Aggressive risk."
    )

    st.write(
        "3. Click ANALYZE."
    )

    st.write(
        "4. The app reads live Upstox market data and "
        "analyses the option chain."
    )

    st.write(
        "5. Weak setups are shown as NO TRADE."
    )

    st.write(
        "6. No orders are automatically placed."
    )

    st.caption(
        "Examples: KOTAKBANK • RELIANCE • HDFCBANK • "
        "ICICIBANK • NIFTY • BANKNIFTY"
    )
