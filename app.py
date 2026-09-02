import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="F&O Pro Trader Assistant — Live Dhan",
    page_icon="📈",
    layout="wide"
)

BASE_URL = "https://api.dhan.co/v2"

# Dhan's official Option Chain documentation uses:
# NIFTY -> Security ID 13, Segment IDX_I
# BANKNIFTY -> Security ID 25, Segment IDX_I
# Other index IDs can be verified from Dhan's instrument master.
INDEX_MAP = {
    "NIFTY": {"security_id": 13, "segment": "IDX_I"},
    "BANKNIFTY": {"security_id": 25, "segment": "IDX_I"},
    "FINNIFTY": {"security_id": 27, "segment": "IDX_I"},
    "MIDCPNIFTY": {"security_id": 442, "segment": "IDX_I"},
}

STOCKS = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "KOTAKBANK",
    "INFY", "TCS", "SBIN", "AXISBANK", "LT", "BHARTIARTL"
]


def headers():
    return {
        "access-token": st.secrets["DHAN_ACCESS_TOKEN"],
        "client-id": st.secrets["DHAN_CLIENT_ID"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def dhan_post(path, payload):
    response = requests.post(
        BASE_URL + path,
        headers=headers(),
        json=payload,
        timeout=20
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Dhan returned HTTP {response.status_code}: "
            f"{response.text[:800]}"
        )

    data = response.json()

    if isinstance(data, dict):
        status = str(data.get("status", "")).lower()
        if status == "failure":
            raise RuntimeError(str(data))

    return data


@st.cache_data(ttl=3600)
def load_master():
    url = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
    return pd.read_csv(url, low_memory=False)


def resolve_underlying(symbol):
    symbol = symbol.strip().upper()

    # IMPORTANT: indices must use IDX_I.
    if symbol in INDEX_MAP:
        item = INDEX_MAP[symbol]
        return item["security_id"], item["segment"]

    # Stocks are resolved from Dhan's instrument master.
    master = load_master()

    # First try direct NSE equity symbol.
    cols = set(master.columns)
    needed = {"EXCH_ID", "SEGMENT", "SYMBOL_NAME", "SECURITY_ID"}

    if needed.issubset(cols):
        m = master[
            master["EXCH_ID"].astype(str).str.upper().eq("NSE")
            & master["SEGMENT"].astype(str).str.upper().eq("E")
            & master["SYMBOL_NAME"].astype(str).str.upper().eq(symbol)
        ]

        if not m.empty:
            sid = m.iloc[0]["SECURITY_ID"]
            return int(float(sid)), "NSE_EQ"

    # Fallback: find the underlying ID from an option contract.
    needed2 = {"UNDERLYING_SYMBOL", "INSTRUMENT", "UNDERLYING_SECURITY_ID"}

    if needed2.issubset(cols):
        m = master[
            master["UNDERLYING_SYMBOL"].astype(str).str.upper().eq(symbol)
            & master["INSTRUMENT"].astype(str).str.upper().isin(
                ["OPTSTK", "OPTIDX"]
            )
        ]

        if not m.empty:
            sid = m.iloc[0]["UNDERLYING_SECURITY_ID"]
            if pd.notna(sid):
                return int(float(sid)), "NSE_EQ"

    raise RuntimeError(
        f"Could not find Dhan security ID for {symbol}. "
        "For indices, use the built-in Dhan IDX_I mapping."
    )


def get_expiries(security_id, segment):
    result = dhan_post(
        "/optionchain/expirylist",
        {
            "UnderlyingScrip": int(security_id),
            "UnderlyingSeg": segment,
        },
    )

    expiries = result.get("data", [])

    if not isinstance(expiries, list):
        raise RuntimeError(f"Unexpected expiry response: {result}")

    return expiries


def get_chain(security_id, segment, expiry):
    return dhan_post(
        "/optionchain",
        {
            "UnderlyingScrip": int(security_id),
            "UnderlyingSeg": segment,
            "Expiry": expiry,
        },
    )


def flatten_chain(result):
    data = result.get("data", {})
    oc = data.get("oc", {})

    rows = []

    for strike, pair in oc.items():
        try:
            strike_value = float(strike)
        except Exception:
            continue

        for side, key in [("CE", "ce"), ("PE", "pe")]:
            item = pair.get(key)

            if not item:
                continue

            greeks = item.get("greeks", {}) or {}

            rows.append({
                "Strike": strike_value,
                "Side": side,
                "LTP": item.get("last_price", 0),
                "OI": item.get("oi", 0),
                "Previous OI": item.get("previous_oi", 0),
                "OI Change": (
                    item.get("oi", 0) - item.get("previous_oi", 0)
                ),
                "Volume": item.get("volume", 0),
                "IV": item.get("implied_volatility", 0),
                "Delta": greeks.get("delta", 0),
                "Theta": greeks.get("theta", 0),
                "Gamma": greeks.get("gamma", 0),
                "Vega": greeks.get("vega", 0),
                "Bid": item.get("top_bid_price", 0),
                "Ask": item.get("top_ask_price", 0),
                "Security ID": item.get("security_id", ""),
            })

    return pd.DataFrame(rows)


def analyze(result):
    data = result.get("data", {})
    spot = float(data.get("last_price", 0))

    chain = flatten_chain(result)

    if chain.empty:
        raise RuntimeError("Dhan returned an empty option chain.")

    calls = chain[chain["Side"] == "CE"]
    puts = chain[chain["Side"] == "PE"]

    call_oi = calls["OI"].sum()
    put_oi = puts["OI"].sum()

    pcr = put_oi / call_oi if call_oi else 0

    call_wall = (
        float(calls.loc[calls["OI"].idxmax(), "Strike"])
        if not calls.empty else 0
    )

    put_wall = (
        float(puts.loc[puts["OI"].idxmax(), "Strike"])
        if not puts.empty else 0
    )

    strikes = sorted(chain["Strike"].unique())

    atm = min(strikes, key=lambda x: abs(x - spot))

    atm_ce = calls[calls["Strike"] == atm]
    atm_pe = puts[puts["Strike"] == atm]

    ce_change = (
        float(atm_ce["OI Change"].iloc[0])
        if not atm_ce.empty else 0
    )

    pe_change = (
        float(atm_pe["OI Change"].iloc[0])
        if not atm_pe.empty else 0
    )

    if pcr > 1.15 and pe_change > 0:
        view = "BULLISH"
    elif pcr < 0.85 and ce_change > 0:
        view = "BEARISH"
    else:
        view = "NEUTRAL / WAIT"

    return {
        "spot": spot,
        "pcr": pcr,
        "atm": atm,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "view": view,
        "chain": chain,
    }


# =========================
# APP
# =========================

st.title("📈 F&O Pro Trader Assistant — Live Dhan")

st.caption(
    "LIVE DATA VALIDATION MODE — no automatic orders are placed."
)

if "DHAN_ACCESS_TOKEN" not in st.secrets:
    st.error("DHAN_ACCESS_TOKEN is missing from Streamlit Secrets.")
    st.stop()

if "DHAN_CLIENT_ID" not in st.secrets:
    st.error("DHAN_CLIENT_ID is missing from Streamlit Secrets.")
    st.stop()

symbol = st.selectbox(
    "Select underlying",
    ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"] + STOCKS
)

# Resolve before the button so the ID is visibly confirmed.
try:
    security_id, segment = resolve_underlying(symbol)

    st.success(
        f"✓ Dhan mapping confirmed: {symbol} | "
        f"Security ID {security_id} | Segment {segment}"
    )

except Exception as e:
    st.error(str(e))
    st.stop()

try:
    expiries = get_expiries(security_id, segment)

except Exception as e:
    st.error(f"Could not retrieve expiry list from Dhan: {e}")
    st.stop()

if not expiries:
    st.error("Dhan returned no active expiries for this underlying.")
    st.stop()

expiry = st.selectbox("Select expiry", expiries)

if st.button("🔄 READ LIVE OPTION CHAIN", type="primary"):

    try:
        result = get_chain(
            security_id,
            segment,
            expiry
        )

        analysis = analyze(result)

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric(
            "Spot",
            f"₹{analysis['spot']:,.2f}"
        )

        c2.metric(
            "PCR",
            f"{analysis['pcr']:.2f}"
        )

        c3.metric(
            "ATM",
            f"{analysis['atm']:g}"
        )

        c4.metric(
            "Call OI Wall",
            f"{analysis['call_wall']:g}"
        )

        c5.metric(
            "Put OI Wall",
            f"{analysis['put_wall']:g}"
        )

        if analysis["view"] == "BULLISH":
            st.success("🟢 Initial view: BULLISH")
        elif analysis["view"] == "BEARISH":
            st.error("🔴 Initial view: BEARISH")
        else:
            st.warning("🟡 Initial view: NEUTRAL / WAIT")

        st.subheader("Live Option Chain")

        st.dataframe(
            analysis["chain"].sort_values(
                ["Strike", "Side"]
            ),
            use_container_width=True,
            hide_index=True
        )

        st.info(
            "This is the live-data validation stage. "
            "The future Pro Trader engine will combine price action, "
            "trend, support/resistance, OI buildup/unwinding, volume, "
            "IV, Greeks, liquidity, risk/reward and historical backtesting "
            "before assigning a statistically calibrated probability."
        )

    except Exception as e:
        st.error(
            f"Could not read live option chain: {e}"
        )
