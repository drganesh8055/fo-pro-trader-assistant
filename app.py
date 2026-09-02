import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="F&O Pro Trader Assistant", page_icon="📈", layout="wide")

def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, float(x)))

def score_trade(row, market):
    direction = str(row.direction).upper()
    spot, strike, ltp = float(row.spot), float(row.strike), float(row.option_ltp)
    trend = float(market.get("trend_score", 50))
    momentum = float(market.get("momentum_score", 50))
    support = float(market.get("support", spot))
    resistance = float(market.get("resistance", spot))
    oi_chg = float(row.oi_change_pct)
    iv = float(row.iv)
    delta = abs(float(row.delta))
    vol_ratio = float(row.volume_ratio)
    spread = float(row.spread_pct)
    oi_support = float(row.supportive_oi_score)

    score = 0
    reasons, warnings = [], []

    # Trend 15
    good = trend >= 65 if direction == "CE" else trend <= 35
    mid = trend >= 55 if direction == "CE" else trend <= 45
    pts = 15 if good else 9 if mid else 3
    score += pts
    if pts >= 9: reasons.append("Underlying trend aligns with the option direction.")
    else: warnings.append("Trend is not strongly aligned.")

    # Support/resistance 15
    room = (resistance - spot) if direction == "CE" else (spot - support)
    pts = 15 if room >= max(spot*0.012, 1) else 8 if room > 0 else 2
    score += pts

    # OI structure 15
    score += clamp(oi_support * 0.15)
    if oi_support >= 70: reasons.append("Option-chain OI structure supports the setup.")

    # OI change 10
    pts = 10 if oi_chg > 8 else 7 if oi_chg > 2 else 4 if oi_chg > -2 else 1
    score += pts

    # Volume 10
    pts = 10 if vol_ratio >= 2 else 8 if vol_ratio >= 1.3 else 5 if vol_ratio >= .8 else 2
    score += pts
    if pts >= 8: reasons.append("Option volume is healthy.")

    # Momentum 10
    good = momentum >= 65 if direction == "CE" else momentum <= 35
    mid = momentum >= 55 if direction == "CE" else momentum <= 45
    pts = 10 if good else 6 if mid else 2
    score += pts

    # IV 10
    pts = 10 if iv <= 22 else 8 if iv <= 30 else 5 if iv <= 40 else 2
    score += pts
    if iv > 40: warnings.append("IV is high; premium can contract even when direction is correct.")

    # Liquidity 5
    pts = 5 if spread <= 1 else 4 if spread <= 2 else 2 if spread <= 4 else 0
    score += pts
    if pts < 3: warnings.append("Bid/ask spread is wide.")

    # Risk/reward 10
    stop = ltp * .72
    target = ltp * 1.55
    rr = (target-ltp)/max(ltp-stop, .01)
    pts = 10 if rr >= 2.5 else 8 if rr >= 2 else 5 if rr >= 1.5 else 1
    score += pts

    if delta < .30: warnings.append("Low delta option may need a large underlying move.")
    elif delta >= .45: reasons.append("Delta is reasonably responsive for a directional trade.")

    score = round(clamp(score), 1)
    grade = "A+" if score >= 85 else "A" if score >= 78 else "B" if score >= 68 else "C" if score >= 55 else "NO TRADE"
    return score, grade, reasons, warnings, rr

def demo():
    data = [
        ["RELIANCE","CE",1512,1510,12.5,185000,14.2,21,0.62,1.7,78,1.0],
        ["RELIANCE","PE",1512,1510,11.0,155000,2.0,25,0.48,1.1,42,1.5],
        ["HDFCBANK","CE",1725,1725,18.0,160000,4.5,24,0.55,1.4,70,1.1],
        ["KOTAKBANK","CE",422,420,10.3,4235000,-1.1,20.4,0.57,1.3,68,1.0],
        ["INFY","CE",1585,1590,14.0,140000,9.5,23,0.60,2.1,82,0.8],
        ["ICICIBANK","PE",1480,1480,13.5,175000,12.0,22,0.52,1.8,76,0.9],
    ]
    df = pd.DataFrame(data, columns=["symbol","direction","spot","strike","option_ltp","oi","oi_change_pct","iv","delta","volume_ratio","supportive_oi_score","spread_pct"])
    markets = {
        "RELIANCE":{"support":1490,"resistance":1540,"trend_score":67,"momentum_score":66},
        "HDFCBANK":{"support":1700,"resistance":1755,"trend_score":58,"momentum_score":55},
        "KOTAKBANK":{"support":415,"resistance":430,"trend_score":54,"momentum_score":48},
        "INFY":{"support":1560,"resistance":1610,"trend_score":63,"momentum_score":64},
        "ICICIBANK":{"support":1455,"resistance":1505,"trend_score":70,"momentum_score":68},
    }
    return df, markets

def normalize(df):
    aliases = {
        "symbol":["symbol","stock","underlying","scrip"],
        "direction":["direction","option_type","type","ce_pe"],
        "spot":["spot","underlying_price","underlying_ltp"],
        "strike":["strike","strike_price"],
        "option_ltp":["option_ltp","ltp","last_price","option_price"],
        "oi":["oi","open_interest"],
        "oi_change_pct":["oi_change_pct","change_oi_pct","oi_change_percent"],
        "iv":["iv","implied_volatility"],
        "delta":["delta"],
        "volume_ratio":["volume_ratio"],
        "spread_pct":["spread_pct"],
        "supportive_oi_score":["supportive_oi_score"],
    }
    cols = {c.lower().strip(): c for c in df.columns}
    out = pd.DataFrame()
    for target, names in aliases.items():
        src = next((cols[n] for n in names if n in cols), None)
        if src: out[target] = df[src]
    required = ["symbol","direction","spot","strike","option_ltp","oi"]
    missing = [x for x in required if x not in out.columns]
    if missing: raise ValueError("Missing columns: " + ", ".join(missing))
    defaults = {"oi_change_pct":0,"iv":25,"delta":.5,"volume_ratio":1,"spread_pct":1,"supportive_oi_score":60}
    for c,v in defaults.items():
        if c not in out.columns: out[c] = v
    for c in out.columns:
        if c not in ["symbol","direction"]:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)
    out.direction = out.direction.astype(str).str.upper().replace({"CALL":"CE","PUT":"PE"})
    return out

st.title("📈 F&O Pro Trader Assistant")
st.caption("Non-technical trader dashboard • setup scoring • strict NO-TRADE filter")

with st.sidebar:
    mode = st.radio("Data mode", ["Demo / Test","Upload option-chain CSV"])
    minimum = st.slider("Minimum setup score", 50, 95, 75)
    count = st.slider("Top setups", 1, 10, 5)
    st.warning("Scores are decision support, NOT guaranteed profit probabilities.")

if mode == "Demo / Test":
    df, markets = demo()
else:
    file = st.file_uploader("Upload option-chain CSV", type=["csv"])
    if file is None:
        st.info("Upload a CSV with symbol, CE/PE, spot, strike, option LTP and OI.")
        st.stop()
    try:
        df = normalize(pd.read_csv(file))
        markets = {}
        for s in df.symbol.unique():
            spot = float(df[df.symbol==s].spot.iloc[0])
            markets[s] = {"support":spot*.985,"resistance":spot*1.015,"trend_score":50,"momentum_score":50}
    except Exception as e:
        st.error(str(e)); st.stop()

rows=[]
for _, r in df.iterrows():
    score, grade, reasons, warnings, rr = score_trade(r, markets.get(r.symbol, {}))
    rows.append({
        "Stock":r.symbol,"Trade":"BUY "+r.direction,"Strike":r.strike,
        "Spot":round(r.spot,2),"Premium":round(r.option_ltp,2),
        "Score":score,"Grade":grade,"SL":round(r.option_ltp*.72,2),
        "Target":round(r.option_ltp*1.55,2),"R:R":round(rr,2),
        "OI":int(r.oi),"OI Chg %":round(r.oi_change_pct,2),"IV":round(r.iv,2)
    })

result = pd.DataFrame(rows).sort_values("Score", ascending=False)
top = result[result.Score >= minimum].head(count)

a,b,c,d = st.columns(4)
a.metric("Stocks scanned", result.Stock.nunique())
b.metric("Qualified setups", len(top))
c.metric("Best score", f"{result.Score.max():.0f}/100")
d.metric("Mode", "Selective")

st.subheader("🏆 Highest-scoring setups")
if top.empty:
    st.error("NO TRADE — nothing meets your selected threshold.")
else:
    st.dataframe(top, use_container_width=True, hide_index=True)

st.subheader("🔎 Setup explanation")
labels = [f"{r.Stock} | {r.Trade} | {r.Strike}" for _,r in result.iterrows()]
choice = st.selectbox("Select a setup", labels)
idx = labels.index(choice)
r = result.iloc[idx]
st.write(f"**{choice}** — Score **{r.Score}/100 ({r.Grade})**")
st.write(f"Entry ~ ₹{r.Premium} | Stop ₹{r.SL} | Target ₹{r.Target} | R:R {r['R:R']}")

st.divider()
st.caption("The production version should use live licensed market data and historical calibration. Options can lose the full premium.")
