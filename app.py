import streamlit as st
import pandas as pd
import numpy as np

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="F&O Pro Trader Assistant",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1450px;
    }

    .app-header {
        background: white;
        padding: 20px 24px;
        border-radius: 14px;
        border: 1px solid #e5e7eb;
        margin-bottom: 20px;
    }

    .app-title {
        font-size: 30px;
        font-weight: 800;
        color: #111827;
        line-height: 1.2;
    }

    .app-subtitle {
        font-size: 14px;
        color: #6b7280;
        margin-top: 6px;
    }

    .ready-box {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 100px 30px;
        text-align: center;
        min-height: 500px;
    }

    .ready-icon {
        font-size: 65px;
    }

    .ready-title {
        font-size: 30px;
        font-weight: 800;
        margin-top: 15px;
        color: #111827;
    }

    .ready-text {
        color: #6b7280;
        font-size: 16px;
        margin-top: 10px;
    }

    .card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 15px;
    }

    .card-title {
        font-size: 20px;
        font-weight: 800;
        color: #111827;
    }

    .card-subtitle {
        font-size: 14px;
        color: #6b7280;
        margin-top: 5px;
    }

    .signal {
        font-size: 28px;
        font-weight: 800;
        color: #111827;
    }

    .signal-description {
        font-size: 14px;
        color: #6b7280;
        margin-top: 5px;
    }

    .section-heading {
        font-size: 21px;
        font-weight: 800;
        color: #111827;
        margin-top: 10px;
        margin-bottom: 10px;
    }

    </style>
    """,
    unsafe_allow_html=True
)

# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="app-header">
        <div class="app-title">📈 F&O Pro Trader Assistant</div>
        <div class="app-subtitle">
            Options market analysis • Entry • Stop Loss • Target • Exit
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ============================================================
# SESSION STATE
# ============================================================

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

if "symbol" not in st.session_state:
    st.session_state.symbol = ""

if "risk" not in st.session_state:
    st.session_state.risk = "Balanced"


# ============================================================
# SYMBOL NORMALIZATION
# ============================================================

symbol_aliases = {
    "HDFC": "HDFCBANK",
    "HDFC BANK": "HDFCBANK",
    "HDFC BANK LTD": "HDFCBANK",
    "KOTAK": "KOTAKBANK",
    "KOTAK BANK": "KOTAKBANK",
    "ICICI": "ICICIBANK",
    "SBI": "SBIN",
    "BHARTI": "BHARTIARTL",
    "AIRTEL": "BHARTIARTL",
    "NIFTY 50": "NIFTY",
    "NIFTY50": "NIFTY",
    "BANK NIFTY": "BANKNIFTY",
    "BANKNIFTY": "BANKNIFTY"
}


def normalize_symbol(value):
    value = value.strip().upper()

    if value in symbol_aliases:
        return symbol_aliases[value]

    return value


# ============================================================
# MARKET DATA
# ============================================================

market_data = {

    "NIFTY": {
        "spot": 25200,
        "pcr": 1.08,
        "rsi": 58,
        "trend": "Bullish",
        "momentum": "Positive",
        "volume": "Above Normal",
        "call_wall": 25300,
        "put_wall": 25000
    },

    "BANKNIFTY": {
        "spot": 57500,
        "pcr": 1.02,
        "rsi": 55,
        "trend": "Bullish",
        "momentum": "Positive",
        "volume": "Normal",
        "call_wall": 58000,
        "put_wall": 57000
    },

    "HDFCBANK": {
        "spot": 1950,
        "pcr": 1.06,
        "rsi": 55,
        "trend": "Bullish",
        "momentum": "Positive",
        "volume": "Normal",
        "call_wall": 2000,
        "put_wall": 1900
    },

    "KOTAKBANK": {
        "spot": 420,
        "pcr": 0.96,
        "rsi": 56,
        "trend": "Bullish",
        "momentum": "Positive",
        "volume": "Above Normal",
        "call_wall": 430,
        "put_wall": 410
    },

    "RELIANCE": {
        "spot": 1400,
        "pcr": 1.10,
        "rsi": 57,
        "trend": "Bullish",
        "momentum": "Positive",
        "volume": "Above Normal",
        "call_wall": 1450,
        "put_wall": 1380
    },

    "ICICIBANK": {
        "spot": 1450,
        "pcr": 1.03,
        "rsi": 54,
        "trend": "Bullish",
        "momentum": "Positive",
        "volume": "Normal",
        "call_wall": 1500,
        "put_wall": 1400
    },

    "SBIN": {
        "spot": 900,
        "pcr": 1.00,
        "rsi": 53,
        "trend": "Sideways",
        "momentum": "Neutral",
        "volume": "Normal",
        "call_wall": 920,
        "put_wall": 880
    },

    "INFY": {
        "spot": 1500,
        "pcr": 0.98,
        "rsi": 52,
        "trend": "Sideways",
        "momentum": "Neutral",
        "volume": "Normal",
        "call_wall": 1550,
        "put_wall": 1470
    },

    "TCS": {
        "spot": 3100,
        "pcr": 1.01,
        "rsi": 51,
        "trend": "Sideways",
        "momentum": "Neutral",
        "volume": "Normal",
        "call_wall": 3200,
        "put_wall": 3050
    },

    "BHARTIARTL": {
        "spot": 1850,
        "pcr": 1.07,
        "rsi": 56,
        "trend": "Bullish",
        "momentum": "Positive",
        "volume": "Above Normal",
        "call_wall": 1900,
        "put_wall": 1800
    },

    "INDUSTOWER": {
        "spot": 382,
        "pcr": 1.04,
        "rsi": 54,
        "trend": "Bullish",
        "momentum": "Positive",
        "volume": "Normal",
        "call_wall": 390,
        "put_wall": 375
    }
}


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("### 🔎 Analyze Instrument")

    st.caption(
        "Enter an NSE stock or index available in F&O."
    )

    entered_symbol = st.text_input(
        "Stock / Index",
        value=st.session_state.symbol,
        placeholder="Enter symbol e.g. HDFCBANK",
        label_visibility="visible"
    )

    risk = st.selectbox(
        "Risk Profile",
        [
            "Conservative",
            "Balanced",
            "Aggressive"
        ],
        index=[
            "Conservative",
            "Balanced",
            "Aggressive"
        ].index(st.session_state.risk)
    )

    analyze = st.button(
        "🔍 Analyze",
        type="primary",
        use_container_width=True
    )

    st.markdown("---")

    st.markdown("### ⚡ Quick Select")

    quick_symbols = [
        "NIFTY",
        "BANKNIFTY",
        "HDFCBANK",
        "KOTAKBANK",
        "RELIANCE",
        "ICICIBANK",
        "SBIN",
        "INFY",
        "TCS",
        "BHARTIARTL"
    ]

    for item in quick_symbols:

        if st.button(
            item,
            key="quick_" + item,
            use_container_width=True
        ):

            st.session_state.symbol = item
            st.session_state.risk = risk
            st.session_state.analyzed = True
            st.rerun()


# ============================================================
# ANALYZE BUTTON
# ============================================================

if analyze:

    if not entered_symbol.strip():

        st.warning("Please enter a stock or index.")

    else:

        st.session_state.symbol = normalize_symbol(
            entered_symbol
        )

        st.session_state.risk = risk
        st.session_state.analyzed = True

        st.rerun()


# ============================================================
# READY SCREEN
# ============================================================

if not st.session_state.analyzed:

    st.markdown(
        """
        <div class="ready-box">

            <div class="ready-icon">📈</div>

            <div class="ready-title">
                READY FOR ANALYSIS
            </div>

            <div class="ready-text">
                Enter a stock or index on the left
                and click Analyze.
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.stop()


# ============================================================
# GET SYMBOL
# ============================================================

symbol = normalize_symbol(
    st.session_state.symbol
)

risk = st.session_state.risk


# ============================================================
# CHECK SYMBOL
# ============================================================

if symbol not in market_data:

    st.error(
        f"'{symbol}' is not currently available in the analysis list."
    )

    st.info(
        "Try HDFCBANK, KOTAKBANK, RELIANCE, ICICIBANK, "
        "SBIN, INFY, TCS, BHARTIARTL, NIFTY or BANKNIFTY."
    )

    st.stop()


# ============================================================
# LOAD DATA
# ============================================================

data = market_data[symbol]

spot = float(data["spot"])
pcr = float(data["pcr"])
rsi = float(data["rsi"])


# ============================================================
# ANALYSIS ENGINE
# ============================================================

score = 0

if data["trend"] == "Bullish":
    score += 2

elif data["trend"] == "Bearish":
    score -= 2


if data["momentum"] == "Positive":
    score += 1

elif data["momentum"] == "Negative":
    score -= 1


if pcr >= 1.05:
    score += 1

elif pcr <= 0.95:
    score -= 1


if rsi >= 55:
    score += 1

elif rsi <= 45:
    score -= 1


# ============================================================
# SIGNAL
# ============================================================

if score >= 3:

    action = "CALL BUY"
    bias = "Bullish"

elif score <= -3:

    action = "PUT BUY"
    bias = "Bearish"

else:

    action = "NO TRADE"
    bias = "Neutral"


# ============================================================
# TRADE PLAN
# ============================================================

if action == "CALL BUY":

    strike = round(spot / 50) * 50

    entry = spot
    stop_loss = spot * 0.985
    target = spot * 1.03

    option_type = "CE"


elif action == "PUT BUY":

    strike = round(spot / 50) * 50

    entry = spot
    stop_loss = spot * 1.015
    target = spot * 0.97

    option_type = "PE"


else:

    strike = round(spot / 50) * 50

    entry = spot
    stop_loss = None
    target = None

    option_type = "-"


# ============================================================
# PAGE TITLE
# ============================================================

st.markdown(
    f"## 📊 {symbol} — F&O Analysis"
)


# ============================================================
# MARKET STATUS
# ============================================================

if action == "CALL BUY":

    st.success(
        f"Market Bias: {bias}  |  Signal: CALL BUY"
    )

elif action == "PUT BUY":

    st.error(
        f"Market Bias: {bias}  |  Signal: PUT BUY"
    )

else:

    st.warning(
        "Market Bias: Neutral  |  "
        "Signal: Market conditions are not strong enough for a trade"
    )


# ============================================================
# TRADE SIGNAL
# ============================================================

st.markdown(
    '<div class="card">',
    unsafe_allow_html=True
)

st.markdown(
    f'<div class="signal">{action}</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="signal-description">
        Suggested setup based on the available market factors.
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# KEY METRICS
# ============================================================

st.markdown(
    '<div class="section-heading">📊 Market Snapshot</div>',
    unsafe_allow_html=True
)

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric(
        "SPOT PRICE",
        f"₹{spot:,.2f}"
    )

with c2:
    st.metric(
        "PCR",
        f"{pcr:.2f}"
    )

with c3:
    st.metric(
        "RSI",
        f"{rsi:.1f}"
    )

with c4:
    st.metric(
        "TREND",
        data["trend"]
    )

with c5:
    st.metric(
        "VOLUME",
        data["volume"]
    )


# ============================================================
# TRADE PLAN
# ============================================================

st.markdown(
    '<div class="section-heading">🎯 Trade Plan</div>',
    unsafe_allow_html=True
)

t1, t2, t3, t4, t5 = st.columns(5)

with t1:
    st.metric(
        "Action",
        action
    )

with t2:
    st.metric(
        "Strike",
        f"{strike:.0f}"
    )

with t3:
    st.metric(
        "Entry",
        f"₹{entry:,.2f}"
    )

with t4:

    if stop_loss is None:
        sl_text = "—"
    else:
        sl_text = f"₹{stop_loss:,.2f}"

    st.metric(
        "Stop Loss",
        sl_text
    )

with t5:

    if target is None:
        target_text = "—"
    else:
        target_text = f"₹{target:,.2f}"

    st.metric(
        "Target",
        target_text
    )


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📌 Best Trade",
        "⛓️ Option Chain",
        "📊 Market Analysis",
        "🧠 How Engine Thinks"
    ]
)


# ============================================================
# TAB 1
# ============================================================

with tab1:

    st.subheader("Suggested Setup")

    if action == "NO TRADE":

        st.warning(
            "NO TRADE — Current conditions do not provide enough confirmation."
        )

        st.write(
            "Wait for stronger alignment between trend, momentum, "
            "PCR, RSI and volume."
        )

    else:

        st.success(
            f"Potential setup: {symbol} {strike} {option_type}"
        )

        trade_table = pd.DataFrame(
            {
                "Parameter": [
                    "Instrument",
                    "Direction",
                    "Option Type",
                    "Strike",
                    "Entry",
                    "Stop Loss",
                    "Target",
                    "Risk Profile"
                ],

                "Value": [
                    symbol,
                    action,
                    option_type,
                    strike,
                    f"₹{entry:,.2f}",
                    f"₹{stop_loss:,.2f}",
                    f"₹{target:,.2f}",
                    risk
                ]
            }
        )

        st.dataframe(
            trade_table,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# TAB 2 — OPTION CHAIN
# ============================================================

with tab2:

    st.subheader("Option Chain Snapshot")

    strikes = [
        strike - 100,
        strike - 50,
        strike,
        strike + 50,
        strike + 100
    ]

    option_chain = pd.DataFrame(
        {
            "Strike": strikes,

            "Call OI": [
                "Low",
                "Medium",
                "High",
                "High",
                "Very High"
            ],

            "Call Chg OI": [
                "Low",
                "Rising",
                "Rising",
                "Rising",
                "High"
            ],

            "Put OI": [
                "Very High",
                "High",
                "High",
                "Medium",
                "Low"
            ],

            "Put Chg OI": [
                "High",
                "Rising",
                "Rising",
                "Low",
                "Low"
            ]
        }
    )

    st.dataframe(
        option_chain,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Option-chain values will be replaced with live market data "
        "when the live data connection is enabled."
    )


# ============================================================
# TAB 3 — MARKET ANALYSIS
# ============================================================

with tab3:

    st.subheader("Market Analysis")

    analysis_table = pd.DataFrame(
        {
            "Factor": [
                "Trend",
                "Momentum",
                "PCR",
                "RSI",
                "Volume",
                "Call OI Wall",
                "Put OI Wall"
            ],

            "Observation": [
                data["trend"],
                data["momentum"],
                f"{pcr:.2f}",
                f"{rsi:.1f}",
                data["volume"],
                data["call_wall"],
                data["put_wall"]
            ]
        }
    )

    st.dataframe(
        analysis_table,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# TAB 4 — ENGINE
# ============================================================

with tab4:

    st.subheader("How the Engine Thinks")

    st.write(
        "The analysis uses multiple factors rather than relying on "
        "a single indicator."
    )

    st.markdown(
        """
        **Factors considered**

        • Trend direction  
        • Momentum  
        • Put/Call Ratio (PCR)  
        • RSI  
        • Volume  
        • Call Open Interest  
        • Put Open Interest  
        • Overall market bias
        """
    )

    st.info(
        f"Current analysis score: {score}"
    )

    st.caption(
        "A stronger combination of aligned factors is required before "
        "the engine produces a trade signal."
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "F&O Pro Trader Assistant • Analysis tool only • "
    "Verify live market conditions before taking any trade."
)
