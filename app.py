
import math
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="F&O Pro Trader Assistant — Demo",
    page_icon="📈",
    layout="wide",
)

# ============================================================
# F&O PRO TRADER ASSISTANT — DEMO ENGINE
# ============================================================
# IMPORTANT:
# This version uses SIMULATED market/option-chain data.
# It does NOT connect to Dhan and does NOT place orders.
# The scoring system is a rule-based prototype, not a profit guarantee.
# ============================================================

INDEX_SPOTS = {
    "NIFTY": 25200.0,
    "BANKNIFTY": 57500.0,
    "FINNIFTY": 26900.0,
    "MIDCPNIFTY": 13100.0,
}

STOCK_SPOTS = {
    "KOTAKBANK": 420.0,
    "INDUSTOWER": 382.0,
    "RELIANCE": 1410.0,
    "HDFCBANK": 1980.0,
    "ICICIBANK": 1450.0,
    "SBIN": 930.0,
    "AXISBANK": 1280.0,
    "INFY": 1550.0,
    "TCS": 4200.0,
    "BHARTIARTL": 1900.0,
}

LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
    "MIDCPNIFTY": 120,
    "KOTAKBANK": 2000,
    "INDUSTOWER": 1700,
    "RELIANCE": 500,
    "HDFCBANK": 550,
    "ICICIBANK": 700,
    "SBIN": 750,
    "AXISBANK": 625,
    "INFY": 400,
    "TCS": 175,
    "BHARTIARTL": 475,
}

INDEX_NAMES = set(INDEX_SPOTS)


def round_to_step(value, step):
    return round(value / step) * step


def fmt_price(x):
    if abs(x) >= 1000:
        return f"₹{x:,.0f}"
    return f"₹{x:,.2f}"


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


@st.cache_data
def generate_demo_chain(symbol, regime, seed):
    """Create deterministic, realistic-looking synthetic option-chain data."""
    rng = np.random.default_rng(seed)
    is_index = symbol in INDEX_NAMES
    base = (INDEX_SPOTS if is_index else STOCK_SPOTS)[symbol]

    step = 50 if symbol in {"NIFTY", "BANKNIFTY"} else (
        25 if symbol in {"FINNIFTY", "MIDCPNIFTY"} else
        (5 if base < 1000 else 10)
    )
    spot = base * (1 + rng.normal(0, 0.0025))

    if regime == "Strong Bullish":
        bias = 1.0
    elif regime == "Bullish":
        bias = 0.55
    elif regime == "Bearish":
        bias = -0.55
    elif regime == "Strong Bearish":
        bias = -1.0
    else:
        bias = 0.0

    atm = round_to_step(spot, step)
    strikes = np.arange(atm - 8 * step, atm + 9 * step, step)

    # Synthetic market metrics.
    rows = []
    max_dist = max(step * 8, 1)

    for k in strikes:
        dist = (k - spot) / max_dist
        atmness = math.exp(-0.5 * (dist * 2.2) ** 2)

        call_wall = max(0.15, 1.0 + dist * 0.20 - bias * 0.10)
        put_wall = max(0.15, 1.0 - dist * 0.20 + bias * 0.10)

        call_oi = int(max(
            5000,
            55000 * call_wall * (0.35 + 0.9 * math.exp(-((dist - 0.30) / 0.75) ** 2))
            * rng.uniform(0.82, 1.18)
        ))
        put_oi = int(max(
            5000,
            52000 * put_wall * (0.35 + 0.9 * math.exp(-((dist + 0.30) / 0.75) ** 2))
            * rng.uniform(0.82, 1.18)
        ))

        # OI change: bullish regime tends to build puts below and unwind calls,
        # bearish regime tends to do the reverse.
        call_change = int(call_oi * (
            0.10 - bias * 0.12 + rng.normal(0, 0.045)
        ))
        put_change = int(put_oi * (
            0.10 + bias * 0.12 + rng.normal(0, 0.045)
        ))

        iv_base = 14.0 + 5.0 * abs(dist) + (3.0 if regime in {"Strong Bullish", "Strong Bearish"} else 0)
        iv = max(8.0, iv_base + rng.normal(0, 0.6))

        days = 27
        intrinsic_call = max(spot - k, 0)
        intrinsic_put = max(k - spot, 0)

        time_value = max(0.5 * step, spot * (iv / 100) * math.sqrt(days / 365) * 0.18)
        ce_ltp = max(0.15, intrinsic_call + time_value * (0.55 + 0.75 * atmness))
        pe_ltp = max(0.15, intrinsic_put + time_value * (0.55 + 0.75 * atmness))

        # Approximate deltas.
        ce_delta = 0.5 + 0.45 * math.tanh((spot - k) / max(step * 2.2, 1))
        pe_delta = ce_delta - 1.0

        spread_ce = max(0.05, ce_ltp * 0.025)
        spread_pe = max(0.05, pe_ltp * 0.025)

        volume_ce = int(max(100, call_oi * rng.uniform(0.05, 0.35)))
        volume_pe = int(max(100, put_oi * rng.uniform(0.05, 0.35)))

        rows.append({
            "Strike": float(k),
            "CE LTP": round(ce_ltp, 2),
            "CE OI": call_oi,
            "CE Chg OI": call_change,
            "CE Volume": volume_ce,
            "CE IV": round(iv + rng.normal(0, 0.25), 2),
            "CE Delta": round(ce_delta, 3),
            "CE Bid": round(max(0.05, ce_ltp - spread_ce), 2),
            "CE Ask": round(ce_ltp + spread_ce, 2),
            "PE LTP": round(pe_ltp, 2),
            "PE OI": put_oi,
            "PE Chg OI": put_change,
            "PE Volume": volume_pe,
            "PE IV": round(iv + rng.normal(0, 0.25), 2),
            "PE Delta": round(pe_delta, 3),
            "PE Bid": round(max(0.05, pe_ltp - spread_pe), 2),
            "PE Ask": round(pe_ltp + spread_pe, 2),
        })

    df = pd.DataFrame(rows)

    # Create synthetic underlying technical metrics.
    momentum = np.clip(50 + bias * 27 + rng.normal(0, 4), 10, 90)
    trend_strength = np.clip(45 + abs(bias) * 38 + rng.normal(0, 5), 10, 95)
    volume_ratio = max(0.65, 1.0 + bias * 0.28 + rng.normal(0, 0.12))
    rsi = np.clip(52 + bias * 17 + rng.normal(0, 4), 20, 80)

    return {
        "spot": float(spot),
        "step": step,
        "chain": df,
        "momentum": float(momentum),
        "trend_strength": float(trend_strength),
        "volume_ratio": float(volume_ratio),
        "rsi": float(rsi),
        "regime": regime,
    }


def market_summary(data):
    df = data["chain"]
    spot = data["spot"]

    total_call_oi = df["CE OI"].sum()
    total_put_oi = df["PE OI"].sum()
    pcr = total_put_oi / max(total_call_oi, 1)

    call_wall_row = df.loc[df["CE OI"].idxmax()]
    put_wall_row = df.loc[df["PE OI"].idxmax()]

    # OI interpretation around spot.
    near = df[(df["Strike"] >= spot - 3 * data["step"]) &
              (df["Strike"] <= spot + 3 * data["step"])]

    call_chg = near["CE Chg OI"].sum()
    put_chg = near["PE Chg OI"].sum()

    if data["momentum"] >= 65 and pcr >= 0.95:
        direction = "BULLISH"
    elif data["momentum"] <= 35 and pcr <= 0.95:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL / WAIT"

    return {
        "pcr": pcr,
        "call_wall": float(call_wall_row["Strike"]),
        "put_wall": float(put_wall_row["Strike"]),
        "call_chg": int(call_chg),
        "put_chg": int(put_chg),
        "direction": direction,
    }


def score_candidate(data, option_type, strike, risk_profile):
    df = data["chain"]
    spot = data["spot"]
    row = df[df["Strike"] == strike].iloc[0]
    summary = market_summary(data)

    if option_type == "CE":
        premium = row["CE LTP"]
        delta = row["CE Delta"]
        iv = row["CE IV"]
        oi = row["CE OI"]
        chg_oi = row["CE Chg OI"]
        volume = row["CE Volume"]

        trend_score = np.interp(data["momentum"], [0, 100], [0, 30])
        pcr_score = np.interp(summary["pcr"], [0.65, 1.30], [0, 15])
        location_score = 15 if strike >= spot and strike <= spot + 2.5 * data["step"] else 8
        delta_score = np.interp(delta, [0.25, 0.75], [0, 15])
        volume_score = min(10, 10 * min(volume / max(oi * 0.18, 1), 1))
        oi_score = 8 if chg_oi < 0 else 4
        iv_score = 7 if iv <= df["CE IV"].median() * 1.12 else 3

        direction_penalty = 0 if data["momentum"] >= 50 else 18
    else:
        premium = row["PE LTP"]
        delta = abs(row["PE Delta"])
        iv = row["PE IV"]
        oi = row["PE OI"]
        chg_oi = row["PE Chg OI"]
        volume = row["PE Volume"]

        trend_score = np.interp(100 - data["momentum"], [0, 100], [0, 30])
        pcr_score = np.interp(1.30 - summary["pcr"], [0, 0.65], [0, 15])
        location_score = 15 if strike <= spot and strike >= spot - 2.5 * data["step"] else 8
        delta_score = np.interp(delta, [0.25, 0.75], [0, 15])
        volume_score = min(10, 10 * min(volume / max(oi * 0.18, 1), 1))
        oi_score = 8 if chg_oi < 0 else 4
        iv_score = 7 if iv <= df["PE IV"].median() * 1.12 else 3

        direction_penalty = 0 if data["momentum"] <= 50 else 18

    raw = trend_score + pcr_score + location_score + delta_score + volume_score + oi_score + iv_score - direction_penalty

    # Risk profile adjustment.
    if risk_profile == "Conservative":
        raw -= max(0, 0.45 - delta) * 10
    elif risk_profile == "Aggressive":
        raw += max(0, 0.45 - delta) * 4

    score = float(np.clip(raw, 0, 100))

    # Keep the demo target/SL practical and transparent.
    sl_pct = {"Conservative": 0.18, "Balanced": 0.22, "Aggressive": 0.28}[risk_profile]
    target_pct = {"Conservative": 0.30, "Balanced": 0.42, "Aggressive": 0.55}[risk_profile]

    entry_low = float(row[f"{option_type} Bid"])
    entry_high = float(row[f"{option_type} Ask"])
    entry = round((entry_low + entry_high) / 2, 2)
    sl = round(max(0.05, entry * (1 - sl_pct)), 2)
    target = round(entry * (1 + target_pct), 2)

    rr = (target - entry) / max(entry - sl, 0.01)

    if option_type == "CE":
        reasons = [
            "Underlying momentum supports the bullish side." if data["momentum"] >= 50
            else "Momentum is not supportive for a bullish option.",
            f"PCR is {summary['pcr']:.2f}.",
            f"Nearest call resistance / OI wall is around {fmt_price(summary['call_wall'])}.",
            "Strike has usable delta and synthetic liquidity.",
        ]
    else:
        reasons = [
            "Underlying momentum supports the bearish side." if data["momentum"] <= 50
            else "Momentum is not supportive for a bearish option.",
            f"PCR is {summary['pcr']:.2f}.",
            f"Nearest put support / OI wall is around {fmt_price(summary['put_wall'])}.",
            "Strike has usable delta and synthetic liquidity.",
        ]

    if score < 55:
        action = "NO TRADE"
    elif score < 68:
        action = "WATCH"
    else:
        action = "TRADE CANDIDATE"

    return {
        "symbol": "",
        "type": option_type,
        "strike": strike,
        "score": round(score, 1),
        "action": action,
        "entry": entry,
        "sl": sl,
        "target": target,
        "rr": round(rr, 2),
        "premium": premium,
        "delta": delta,
        "iv": iv,
        "oi": oi,
        "chg_oi": chg_oi,
        "volume": volume,
        "reasons": reasons,
    }


def build_candidates(data, symbol, risk_profile):
    spot = data["spot"]
    step = data["step"]
    df = data["chain"]

    # Candidate strikes are near ATM, avoiding far OTM lottery options.
    candidates = []
    for strike in df["Strike"]:
        if abs(strike - spot) <= 3 * step:
            candidates.append(score_candidate(data, "CE", float(strike), risk_profile))
            candidates.append(score_candidate(data, "PE", float(strike), risk_profile))

    for c in candidates:
        c["symbol"] = symbol

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Add a simple "quality gate": require direction alignment.
    if data["momentum"] >= 55:
        preferred = [c for c in candidates if c["type"] == "CE"]
    elif data["momentum"] <= 45:
        preferred = [c for c in candidates if c["type"] == "PE"]
    else:
        preferred = []

    if preferred:
        candidates = sorted(preferred, key=lambda x: x["score"], reverse=True) + [
            c for c in candidates if c not in preferred
        ]

    return candidates[:10]


def show_trade_card(c):
    title = f"{c['symbol']} {c['strike']:.0f} {c['type']}"
    if c["action"] == "TRADE CANDIDATE":
        st.success(f"### {title} — {c['score']}/100")
    elif c["action"] == "WATCH":
        st.warning(f"### {title} — {c['score']}/100")
    else:
        st.info(f"### {title} — {c['score']}/100")

    cols = st.columns(6)
    cols[0].metric("Action", c["action"])
    cols[1].metric("Entry", fmt_price(c["entry"]))
    cols[2].metric("Stop Loss", fmt_price(c["sl"]))
    cols[3].metric("Target", fmt_price(c["target"]))
    cols[4].metric("R:R", f"1:{c['rr']:.2f}")
    cols[5].metric("Delta", f"{c['delta']:.2f}")

    with st.expander("Why the engine likes / dislikes this setup"):
        for r in c["reasons"]:
            st.write("•", r)
        st.caption(
            f"OI: {c['oi']:,} | Chg OI: {c['chg_oi']:+,} | "
            f"Volume: {c['volume']:,} | IV: {c['iv']:.1f}%"
        )


# ============================================================
# UI
# ============================================================

st.title("📈 F&O Pro Trader Assistant — DEMO")
st.caption("SIMULATED DATA MODE • No Dhan connection • No automatic orders")

st.warning(
    "⚠️ DEMO ONLY: Every market/option-chain value on this page is simulated. "
    "Do not use these numbers to place a real trade. The 0–100 score is a rule-based "
    "setup score, NOT a guaranteed probability of profit."
)

with st.sidebar:
    st.header("🎛️ Demo Controls")

    universe = st.selectbox(
        "Select instrument",
        list(INDEX_SPOTS.keys()) + list(STOCK_SPOTS.keys()),
        index=0,
    )

    regime = st.selectbox(
        "Simulated market regime",
        ["Strong Bullish", "Bullish", "Sideways", "Bearish", "Strong Bearish"],
        index=1,
    )

    risk_profile = st.selectbox(
        "Risk profile",
        ["Conservative", "Balanced", "Aggressive"],
        index=1,
    )

    seed = st.slider(
        "Demo scenario",
        min_value=1,
        max_value=50,
        value=7,
        help="Change this to generate a different synthetic market scenario.",
    )

    st.divider()
    st.write("**What this demo is designed to become:**")
    st.write("1. Scan F&O stocks")
    st.write("2. Read OI + Chg OI")
    st.write("3. Detect support/resistance")
    st.write("4. Identify bullish/bearish setups")
    st.write("5. Rank option strikes")
    st.write("6. Give Entry / SL / Target")
    st.write("7. Reject weak setups with NO TRADE")
    st.write("8. Later connect to Dhan live data")

data = generate_demo_chain(universe, regime, seed)
summary = market_summary(data)
candidates = build_candidates(data, universe, risk_profile)

# Top dashboard
st.subheader("1️⃣ Market Dashboard")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Spot", fmt_price(data["spot"]))
c2.metric("Market Bias", summary["direction"])
c3.metric("PCR", f"{summary['pcr']:.2f}")
c4.metric("Put OI Wall", fmt_price(summary["put_wall"]))
c5.metric("Call OI Wall", fmt_price(summary["call_wall"]))
c6.metric("RSI", f"{data['rsi']:.0f}")

c7, c8, c9 = st.columns(3)
c7.metric("Momentum", f"{data['momentum']:.0f}/100")
c8.metric("Trend Strength", f"{data['trend_strength']:.0f}/100")
c9.metric("Volume vs Normal", f"{data['volume_ratio']:.2f}x")

st.divider()

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🏆 Best Trades",
    "🔎 Option Chain",
    "📊 Market Analysis",
    "🧠 How the Engine Thinks",
])

with tab1:
    st.subheader("🏆 Ranked Trade Candidates")

    top = candidates[0] if candidates else None
    if top:
        st.markdown("### ⭐ #1 Setup")
        show_trade_card(top)

    st.markdown("### Other Candidates")
    for c in candidates[1:6]:
        show_trade_card(c)

    st.info(
        "Professional-style rule: if no setup crosses the quality threshold, "
        "the correct answer is NO TRADE. The app is intentionally designed not "
        "to force a trade every time."
    )

with tab2:
    st.subheader("🔎 Simulated Option Chain")

    display = data["chain"].copy()
    display["Strike"] = display["Strike"].map(lambda x: f"{x:,.0f}")

    st.dataframe(
        display[
            [
                "Strike",
                "CE LTP", "CE OI", "CE Chg OI", "CE Volume", "CE IV", "CE Delta",
                "PE LTP", "PE OI", "PE Chg OI", "PE Volume", "PE IV", "PE Delta",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "In a future Dhan-live version, these fields will come from Dhan's option-chain "
        "feed. Dhan's documented option chain includes OI, previous OI, Greeks, volume, "
        "LTP, bid/ask and IV."
    )

with tab3:
    st.subheader("📊 Support / Resistance & OI Interpretation")

    left, right = st.columns(2)

    with left:
        st.markdown("### 🟢 Put Side")
        st.write(f"**Largest Put OI:** {fmt_price(summary['put_wall'])}")
        st.write(f"**Near-spot Put OI change:** {summary['put_chg']:+,}")
        if summary["put_chg"] > 0:
            st.success("Synthetic put OI is building near spot → possible support.")
        else:
            st.warning("Synthetic put OI is not strongly building → support is weaker.")

    with right:
        st.markdown("### 🔴 Call Side")
        st.write(f"**Largest Call OI:** {fmt_price(summary['call_wall'])}")
        st.write(f"**Near-spot Call OI change:** {summary['call_chg']:+,}")
        if summary["call_chg"] > 0:
            st.warning("Synthetic call OI is building near spot → possible resistance.")
        else:
            st.success("Synthetic call OI is not strongly building → resistance is weaker.")

    st.markdown("### Underlying Momentum")
    momentum_df = pd.DataFrame(
        {
            "Metric": ["Momentum", "Trend Strength", "RSI"],
            "Value": [
                round(data["momentum"], 1),
                round(data["trend_strength"], 1),
                round(data["rsi"], 1),
            ],
        }
    )
    st.bar_chart(momentum_df.set_index("Metric"))

    st.markdown("### Engine conclusion")
    if summary["direction"] == "BULLISH":
        st.success(
            f"BULLISH bias: the engine will prefer CE candidates, especially strikes "
            f"near the money with usable delta and liquidity."
        )
    elif summary["direction"] == "BEARISH":
        st.error(
            f"BEARISH bias: the engine will prefer PE candidates, especially strikes "
            f"near the money with usable delta and liquidity."
        )
    else:
        st.warning(
            "NEUTRAL: conditions are mixed. A professional approach is to wait for "
            "confirmation rather than forcing a trade."
        )

with tab4:
    st.subheader("🧠 How the Pro Trader Engine Works")

    st.markdown("""
### The demo score is built from multiple factors

**1. Direction**
- Underlying momentum
- RSI
- Trend strength

**2. Option-chain structure**
- Put OI
- Call OI
- Change in OI
- Put/Call Ratio (PCR)
- OI walls around the current price

**3. Option quality**
- Delta
- IV
- Volume
- Distance from spot
- Bid/ask spread

**4. Risk/reward**
- Entry
- Stop loss
- Target
- R:R

**5. Final decision**
- **68–100:** Trade Candidate
- **55–67:** Watch
- **Below 55:** No Trade

These thresholds are prototype rules. They must be validated and recalibrated using
historical market data before the system can make statistically meaningful claims
about probability of profit.
""")

    st.markdown("### 🚫 What the app deliberately does NOT do")
    st.write("• It does not guarantee profit.")
    st.write("• It does not claim that OI alone predicts price.")
    st.write("• It does not place real orders.")
    st.write("• It does not pretend simulated data is live market data.")
    st.write("• It does not call a score a 'probability' without backtesting.")

    st.markdown("### 🚀 Next production stages")
    st.write("**Stage 1 — Demo:** rule engine + UI + simulated chain")
    st.write("**Stage 2 — Historical backtest:** test the rules across past F&O sessions")
    st.write("**Stage 3 — Live Dhan data:** replace simulated chain with live Dhan data")
    st.write("**Stage 4 — Paper trading:** track signals without real money")
    st.write("**Stage 5 — Optional broker execution:** only after validation and safeguards")

st.divider()
st.caption(
    "F&O Pro Trader Assistant — Demo build. Synthetic data only. "
    "For education and strategy development, not a recommendation to buy or sell."
)
