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
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

    /* --------------------------------------------------------
       GLOBAL
    -------------------------------------------------------- */

    .stApp {
        background: #f7f9fc;
    }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        max-width: 1450px;
    }

    /* --------------------------------------------------------
       HEADER
    -------------------------------------------------------- */

    .main-header {
        width: 100%;
        padding: 18px 25px;
        border-radius: 14px;
        background: white;
        border: 1px solid #e5e7eb;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }

    .main-title {
        font-size: 30px;
        font-weight: 800;
        color: #111827;
        line-height: 1.2;
        white-space: nowrap;
    }

    .main-subtitle {
        font-size: 14px;
        color: #6b7280;
        margin-top: 5px;
    }

    /* --------------------------------------------------------
       SIDEBAR
       -------------------------------------------------------- */

    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e5e7eb;
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.4rem;
        padding-left: 1.2rem;
        padding-right: 1.2rem;
    }

    .sidebar-title {
        font-size: 22px;
        font-weight: 800;
        color: #111827;
        margin-bottom: 4px;
    }

    .sidebar-subtitle {
        font-size: 13px;
        color: #6b7280;
        margin-bottom: 20px;
    }

    .input-label {
        font-size: 13px;
        font-weight: 700;
        color: #374151;
        margin-bottom: 5px;
    }

    /* --------------------------------------------------------
       READY SCREEN
       -------------------------------------------------------- */

    .ready-container {
        min-height: 570px;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        box-shadow: 0 3px 12px rgba(0,0,0,0.04);
        padding: 40px;
    }

    .ready-icon {
        font-size: 72px;
        line-height: 1;
        margin-bottom: 18px;
    }

    .ready-title {
        font-size: 30px;
        font-weight: 800;
        color: #111827;
        margin-bottom: 10px;
    }

    .ready-subtitle {
        font-size: 16px;
        color: #6b7280;
        max-width: 550px;
        line-height: 1.6;
    }

    /* --------------------------------------------------------
       SECTION HEADERS
       -------------------------------------------------------- */

    .section-title {
        font-size: 21px;
        font-weight: 800;
        color: #111827;
        margin-top: 8px;
        margin-bottom: 12px;
    }

    /* --------------------------------------------------------
       CARDS
       -------------------------------------------------------- */

    .info-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 15px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    }

    .metric-label {
        font-size: 12px;
        color: #6b7280;
        font-weight: 600;
    }

    .metric-value {
        font-size: 23px;
        font-weight: 800;
        color: #111827;
        margin-top: 3px;
    }

    /* --------------------------------------------------------
       TRADE SIGNAL
       -------------------------------------------------------- */

    .trade-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 18px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.04);
    }

    .trade-action {
        font-size: 28px;
        font-weight: 900;
        color: #111827;
    }

    .trade-description {
        color: #6b7280;
        font-size: 14px;
        margin-top: 5px;
    }

    /* --------------------------------------------------------
       STATUS
       -------------------------------------------------------- */

    .status-box {
        border-radius: 12px;
        padding: 15px 18px;
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        margin-bottom: 15px;
    }

    /* --------------------------------------------------------
       BUTTONS
       -------------------------------------------------------- */

    .stButton > button {
        border-radius: 9px;
        font-weight: 700;
        min-height: 42px;
    }

    /* --------------------------------------------------------
       TABLE
       -------------------------------------------------------- */

    .dataframe {
        border-radius: 10px;
        overflow: hidden;
    }

</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================

st.markdown("""
<div class="main-header">
    <div class="main-title">
        📈 F&O Pro Trader Assistant
    </div>
    <div class="main-subtitle">
        Options market analysis • Entry • Stop Loss • Target • Exit
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE
# ============================================================

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = ""

if "risk_profile" not in st.session_state:
    st.session_state.risk_profile = "Balanced"

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("""
    <div class="sidebar-title">
        🔎 Analyze Instrument
    </div>
    <div class="sidebar-subtitle">
        Enter an NSE stock or index available in F&O.
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="input-label">Stock / Index</div>',
        unsafe_allow_html=True
    )

    symbol = st.text_input(
        "Stock / Index",
        value=st.session_state.selected_symbol,
        placeholder="Example: KOTAKBANK",
        label_visibility="collapsed"
    )

    st.markdown(
        '<div class="input-label" style="margin-top:15px;">Risk Profile</div>',
        unsafe_allow_html=True
    )

    risk = st.selectbox(
        "Risk Profile",
        ["Conservative", "Balanced", "Aggressive"],
        index=["Conservative", "Balanced", "Aggressive"].index(
            st.session_state.risk_profile
        ),
        label_visibility="collapsed"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    analyze_clicked = st.button(
        "🔍 Analyze",
        use_container_width=True,
        type="primary"
    )

    # --------------------------------------------------------
    # QUICK SELECT
    # --------------------------------------------------------

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        '<div class="input-label">⚡ Quick Select</div>',
        unsafe_allow_html=True
    )

    quick_symbols = [
        "NIFTY",
        "BANKNIFTY",
        "KOTAKBANK",
        "HDFCBANK",
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
            key=f"quick_{item}",
            use_container_width=True
        ):
            st.session_state.selected_symbol = item
            st.session_state.analyzed = False
            st.rerun()

# ============================================================
# PROCESS ANALYZE
# ============================================================

if analyze_clicked:

    clean_symbol = symbol.strip().upper()

    if clean_symbol:

        st.session_state.selected_symbol = clean_symbol
        st.session_state.risk_profile = risk
        st.session_state.analyzed = True

    else:

        st.warning("Please enter a stock or index.")

# ============================================================
# MAIN AREA — READY SCREEN
# ============================================================

if not st.session_state.analyzed:

    st.markdown("""
    <div class="ready-container">

        <div class="ready-icon">
            📈
        </div>

        <div class="ready-title">
            READY FOR ANALYSIS
        </div>

        <div class="ready-subtitle">
            Enter a stock or index in the left panel,
            select your risk profile, and click
            <b>Analyze</b> to view the F&O setup.
        </div>

    </div>
    """, unsafe_allow_html=True)

    st.stop()

# ============================================================
# SYMBOL
# ============================================================

symbol = st.session_state.selected_symbol
risk = st.session_state.risk_profile

# ============================================================
# DEMO / FALLBACK MARKET DATA
# ============================================================

# These values are used only as fallback data.
# Replace this section with live NSE / broker API data later.

market_data = {

    "NIFTY": {
        "spot": 25200,
        "pcr": 1.08,
        "oi_call": "25,300",
        "oi_put": "25,000",
        "rsi": 58,
        "momentum": "Positive",
        "trend": "Bullish",
        "volume": "Above Normal"
    },

    "BANKNIFTY": {
        "spot": 57500,
        "pcr": 1.02,
        "oi_call": "58,000",
        "oi_put": "57,000",
        "rsi": 55,
        "momentum": "Positive",
        "trend": "Bullish",
        "volume": "Normal"
    },

    "KOTAKBANK": {
        "spot": 420,
        "pcr": 0.96,
        "oi_call": "430",
        "oi_put": "410",
        "rsi": 56,
        "momentum": "Positive",
        "trend": "Bullish",
        "volume": "Above Normal"
    },

    "INDUSTOWER": {
        "spot": 382,
        "pcr": 1.04,
        "oi_call": "390",
        "oi_put": "375",
        "rsi": 54,
        "momentum": "Positive",
        "trend": "Bullish",
        "volume": "Normal"
    },

    "RELIANCE": {
        "spot": 1400,
        "pcr": 1.10,
        "oi_call": "1450",
        "oi_put": "1380",
        "rsi": 57,
        "momentum": "Positive",
        "trend": "Bullish",
        "volume": "Above Normal"
    },

    "HDFCBANK": {
        "spot": 1950,
        "pcr": 1.06,
        "oi_call": "2000",
        "oi_put": "1900",
        "rsi": 55,
        "momentum": "Positive",
        "trend": "Bullish",
        "volume": "Normal"
    },

    "ICICIBANK": {
        "spot": 1450,
        "pcr": 1.03,
        "oi_call": "1500",
        "oi_put": "1400",
        "rsi": 54,
        "momentum": "Positive",
        "trend": "Bullish",
        "volume": "Normal"
    },

    "SBIN": {
        "spot": 900,
        "pcr": 1.00,
        "oi_call": "920",
        "oi_put": "880",
        "rsi": 53,
        "momentum": "Neutral",
        "trend": "Sideways",
        "volume": "Normal"
    },

    "INFY": {
        "spot": 1500,
        "pcr": 0.98,
        "oi_call": "1550",
        "oi_put": "1470",
        "rsi": 52,
        "momentum": "Neutral",
        "trend": "Sideways",
        "volume": "Normal"
    },

    "TCS": {
        "spot": 3100,
        "pcr": 1.01,
        "oi_call": "3200",
        "oi_put": "3050",
        "rsi": 51,
        "momentum": "Neutral",
        "trend": "Sideways",
        "volume": "Normal"
    },

    "BHARTIARTL": {
        "spot": 1850,
        "pcr": 1.07,
        "oi_call": "1900",
        "oi_put": "1800",
        "rsi": 56,
        "momentum": "Positive",
        "trend": "Bullish",
        "volume": "Above Normal"
    }
}

# ============================================================
# DEFAULT DATA FOR UNKNOWN SYMBOL
# ============================================================

if symbol in market_data:

    data = market_data[symbol]

else:

    data = {
        "spot": 1000,
        "pcr": 1.00,
        "oi_call": "ATM + 50",
        "oi_put": "ATM - 50",
        "rsi": 50,
        "momentum": "Neutral",
        "trend": "Sideways",
        "volume": "Normal"
    }

# ============================================================
# SIMPLE SIGNAL ENGINE
# ============================================================

spot = float(data["spot"])
pcr = float(data["pcr"])
rsi = float(data["rsi"])

score = 0

if data["trend"] == "Bullish":
    score += 2

elif data["trend"] == "Bearish":
    score -= 2

if data["momentum"] == "Positive":
    score += 1

elif data["momentum"] == "Negative":
    score -= 1

if pcr > 1.05:
    score += 1

elif pcr < 0.95:
    score -= 1

if rsi >= 55:
    score += 1

elif rsi <= 45:
    score -= 1

# ============================================================
# ACTION
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
# ENTRY / SL / TARGET
# ============================================================

if action == "CALL BUY":

    strike = round(spot / 50) * 50

    entry = spot
    sl = spot * 0.985
    target = spot * 1.03

elif action == "PUT BUY":

    strike = round(spot / 50) * 50

    entry = spot
    sl = spot * 1.015
    target = spot * 0.97

else:

    strike = round(spot / 50) * 50

    entry = spot
    sl = spot
    target = spot

# ============================================================
# MAIN TITLE
# ============================================================

st.markdown(
    f"""
    <div class="section-title">
        📊 {symbol} — F&O Analysis
    </div>
    """,
    unsafe_allow_html=True
)

# ============================================================
# TOP STATUS
# ============================================================

if action == "CALL BUY":

    status_text = "Bullish setup detected"

elif action == "PUT BUY":

    status_text = "Bearish setup detected"

else:

    status_text = "Market conditions are not strong enough for a trade"

st.markdown(
    f"""
    <div class="status-box">
        <b>Market Bias:</b> {bias}
        &nbsp;&nbsp; | &nbsp;&nbsp;
        <b>Signal:</b> {status_text}
    </div>
    """,
    unsafe_allow_html=True
)

# ============================================================
# TRADE SIGNAL CARD
# ============================================================

st.markdown(
    f"""
    <div class="trade-card">

        <div class="trade-action">
            {action}
        </div>

        <div class="trade-description">
            Suggested setup based on the current analysis factors.
        </div>

    </div>
    """,
    unsafe_allow_html=True
)

# ============================================================
# KEY METRICS
# ============================================================

c1, c2, c3, c4, c5 = st.columns(5)

with c1:

    st.markdown(
        f"""
        <div class="info-card">
            <div class="metric-label">SPOT PRICE</div>
            <div class="metric-value">₹{spot:,.2f}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with c2:

    st.markdown(
        f"""
        <div class="info-card">
            <div class="metric-label">PCR</div>
            <div class="metric-value">{pcr:.2f}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with c3:

    st.markdown(
        f"""
        <div class="info-card">
            <div class="metric-label">RSI</div>
            <div class="metric-value">{rsi}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with c4:

    st.markdown(
        f"""
        <div class="info-card">
            <div class="metric-label">TREND</div>
            <div class="metric-value">{data["trend"]}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with c5:

    st.markdown(
        f"""
        <div class="info-card">
            <div class="metric-label">VOLUME</div>
            <div class="metric-value">{data["volume"]}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================
# TRADE PLAN
# ============================================================

st.markdown(
    '<div class="section-title">🎯 Trade Plan</div>',
    unsafe_allow_html=True
)

p1, p2, p3, p4 = st.columns(4)

with p1:

    st.metric(
        "Action",
        action
    )

with p2:

    st.metric(
        "Reference Price",
        f"₹{entry:,.2f}"
    )

with p3:

    if action == "CALL BUY":

        sl_display = f"₹{sl:,.2f}"

    elif action == "PUT BUY":

        sl_display = f"₹{sl:,.2f}"

    else:

        sl_display = "—"

    st.metric(
        "Stop Loss",
        sl_display
    )

with p4:

    if action in ["CALL BUY", "PUT BUY"]:

        target_display = f"₹{target:,.2f}"

    else:

        target_display = "—"

    st.metric(
        "Target",
        target_display
    )

# ============================================================
# OPTION CHAIN / MARKET ANALYSIS
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

    st.markdown("### Suggested Setup")

    if action == "NO TRADE":

        st.warning(
            "NO TRADE — Current conditions do not provide enough confirmation."
        )

    else:

        option_type = "CE" if action == "CALL BUY" else "PE"

        st.info(
            f"Potential setup: {symbol} {strike} {option_type}"
        )

        setup_df = pd.DataFrame(
            {
                "Parameter": [
                    "Instrument",
                    "Direction",
                    "Strike",
                    "Entry Reference",
                    "Stop Loss",
                    "Target",
                    "Risk Profile"
                ],
                "Value": [
                    symbol,
                    action,
                    strike,
                    f"₹{entry:,.2f}",
                    f"₹{sl:,.2f}",
                    f"₹{target:,.2f}",
                    risk
                ]
            }
        )

        st.dataframe(
            setup_df,
            use_container_width=True,
            hide_index=True
        )

# ============================================================
# TAB 2
# ============================================================

with tab2:

    st.markdown("### Option Chain Snapshot")

    strikes = [
        strike - 100,
        strike - 50,
        strike,
        strike + 50,
        strike + 100
    ]

    chain = pd.DataFrame(
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
        chain,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Option-chain values shown here are placeholder/fallback values until live market data is connected."
    )

# ============================================================
# TAB 3
# ============================================================

with tab3:

    st.markdown("### Market Analysis")

    analysis_df = pd.DataFrame(
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
                str(rsi),
                data["volume"],
                data["oi_call"],
                data["oi_put"]
            ]
        }
    )

    st.dataframe(
        analysis_df,
        use_container_width=True,
        hide_index=True
    )

# ============================================================
# TAB 4
# ============================================================

with tab4:

    st.markdown("### How the Engine Thinks")

    st.write(
        """
        The analysis combines multiple market factors instead of relying
        on a single indicator.
        """
    )

    st.markdown(
        """
        **Factors considered:**

        - Trend direction
        - Momentum
        - Put/Call Ratio (PCR)
        - RSI
        - Volume
        - Call Open Interest
        - Put Open Interest
        - Overall market bias
        """
    )

    st.info(
        "The engine is designed to avoid forcing a trade when the available "
        "signals are not sufficiently aligned."
    )

# ============================================================
# FOOTER
# ============================================================

st.markdown("<br><br>", unsafe_allow_html=True)

st.caption(
    "F&O Pro Trader Assistant • For educational and analytical purposes. "
    "Trade decisions should be independently verified."
)
