
import math, time
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Option Trade Assistant", page_icon="📈", layout="wide")

IST = timezone(timedelta(hours=5, minutes=30))
NSE = "https://www.nseindia.com"

COMMON = {
    "NIFTY":"NIFTY", "NIFTY50":"NIFTY", "BANKNIFTY":"BANKNIFTY",
    "FINNIFTY":"FINNIFTY", "MIDCPNIFTY":"MIDCPNIFTY",
    "KOTAKBANK":"KOTAKBANK", "KOTAK MAHINDRA BANK":"KOTAKBANK",
    "INDUSTOWER":"INDUSTOWER", "INDUS TOWERS":"INDUSTOWER",
    "RELIANCE":"RELIANCE", "HDFCBANK":"HDFCBANK", "ICICIBANK":"ICICIBANK",
    "SBIN":"SBIN", "AXISBANK":"AXISBANK", "INFY":"INFY", "TCS":"TCS",
    "BHARTIARTL":"BHARTIARTL", "ADANIENT":"ADANIENT", "ADANIPORTS":"ADANIPORTS",
    "TATAMOTORS":"TATAMOTORS", "TATASTEEL":"TATASTEEL", "MARUTI":"MARUTI",
    "BAJFINANCE":"BAJFINANCE", "SUNPHARMA":"SUNPHARMA", "LT":"LT",
    "HINDALCO":"HINDALCO", "COALINDIA":"COALINDIA", "BEL":"BEL",
    "TRENT":"TRENT", "HAL":"HAL", "M&M":"M&M"
}
INDEXES={"NIFTY","BANKNIFTY","FINNIFTY","MIDCPNIFTY"}

HEADERS={
 "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
 "Accept":"application/json,text/plain,*/*",
 "Accept-Language":"en-US,en;q=0.9",
 "Referer":"https://www.nseindia.com/"
}

@st.cache_resource
def nse_session():
    s=requests.Session()
    s.headers.update(HEADERS)
    s.get(NSE, timeout=10)
    return s

def get_json(path, params=None, tries=3):
    s=nse_session()
    url=NSE+path
    last=None
    for i in range(tries):
        try:
            r=s.get(url, params=params, timeout=12)
            if r.status_code==200:
                return r.json()
            last=f"HTTP {r.status_code}"
        except Exception as e:
            last=str(e)
        time.sleep(1.2*(i+1))
        try: s.get(NSE, timeout=8)
        except: pass
    raise RuntimeError(f"NSE data request failed: {last}")

def normalize_symbol(x):
    x=x.strip().upper()
    return COMMON.get(x,x.replace(" ",""))

def quote(symbol):
    if symbol in INDEXES:
        d=get_json("/api/allIndices")
        rows=d.get("data",[])
        for r in rows:
            if r.get("index","").upper() in {symbol, "NIFTY 50" if symbol=="NIFTY" else symbol}:
                return {"price":float(r.get("last",0) or r.get("lastPrice",0)),
                        "change":float(r.get("variation",0) or 0)}
        # fallback
        d=get_json("/api/option-chain-indices", {"symbol":symbol})
        return {"price":float(d["records"]["underlyingValue"]), "change":0.0}
    d=get_json("/api/quote-equity", {"symbol":symbol})
    p=d.get("priceInfo",{})
    return {"price":float(p.get("lastPrice",0)), "change":float(p.get("pChange",0))}

def chart_prices(symbol):
    # NSE's public chart endpoint is best-effort and may change.
    # It commonly returns intraday graph data for EQUITY symbols.
    try:
        d=get_json("/api/chart-databyindex", {"index":symbol+"EQN"})
        arr=d.get("grapthData") or d.get("graphData") or []
        vals=[float(x[1]) for x in arr if len(x)>=2 and x[1] is not None]
        return vals
    except Exception:
        return []

def option_chain(symbol):
    endpoint="/api/option-chain-indices" if symbol in INDEXES else "/api/option-chain-equities"
    return get_json(endpoint, {"symbol":symbol})

def nearest_expiry(chain):
    dates=chain.get("records",{}).get("expiryDates",[])
    if not dates: raise RuntimeError("No active option expiry returned by NSE.")
    today=datetime.now(IST).date()
    parsed=[]
    for x in dates:
        try:
            dt=datetime.strptime(x,"%d-%b-%Y").date()
        except:
            try: dt=datetime.strptime(x,"%Y-%m-%d").date()
            except: continue
        if dt>=today: parsed.append((dt,x))
    if not parsed: raise RuntimeError("No future expiry returned by NSE.")
    return sorted(parsed)[0][1]

def norm_chain(chain, expiry):
    records=chain.get("records",{})
    rows=[]
    for item in records.get("data",[]):
        if item.get("expiryDate")!=expiry: continue
        k=float(item.get("strikePrice"))
        ce=item.get("CE",{}) or {}
        pe=item.get("PE",{}) or {}
        rows.append({
          "strike":k,
          "ce_ltp":float(ce.get("lastPrice",0) or 0),
          "ce_oi":int(ce.get("openInterest",0) or 0),
          "ce_chg_oi":int(ce.get("changeinOpenInterest",0) or 0),
          "ce_vol":int(ce.get("totalTradedVolume",0) or 0),
          "ce_iv":float(ce.get("impliedVolatility",0) or 0),
          "ce_bid":float(ce.get("bidprice",0) or 0),
          "ce_ask":float(ce.get("askPrice",0) or 0),
          "pe_ltp":float(pe.get("lastPrice",0) or 0),
          "pe_oi":int(pe.get("openInterest",0) or 0),
          "pe_chg_oi":int(pe.get("changeinOpenInterest",0) or 0),
          "pe_vol":int(pe.get("totalTradedVolume",0) or 0),
          "pe_iv":float(pe.get("impliedVolatility",0) or 0),
          "pe_bid":float(pe.get("bidprice",0) or 0),
          "pe_ask":float(pe.get("askPrice",0) or 0),
        })
    return pd.DataFrame(rows)

def rsi(vals,n=14):
    if len(vals)<n+2: return 50.0
    s=pd.Series(vals,dtype=float)
    d=s.diff()
    up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    rs=up/dn.replace(0,np.nan)
    x=100-(100/(1+rs))
    return float(x.iloc[-1]) if np.isfinite(x.iloc[-1]) else 50.0

def ema(vals,n):
    if not vals:return 0
    return float(pd.Series(vals).ewm(span=n,adjust=False).mean().iloc[-1])

def bs_delta(spot,strike,iv,days,call=True):
    if iv<=0 or spot<=0 or strike<=0: return 0.5 if call else -0.5
    T=max(days/365,1/3650)
    sigma=max(iv/100,0.01)
    d1=(math.log(spot/strike)+(0.10+0.5*sigma*sigma)*T)/(sigma*math.sqrt(T))
    # normal CDF
    cdf=0.5*(1+math.erf(d1/math.sqrt(2)))
    return cdf if call else cdf-1

def step_for(symbol, spot):
    if symbol=="NIFTY": return 50
    if symbol in {"BANKNIFTY","MIDCPNIFTY"}: return 100
    if symbol=="FINNIFTY": return 50
    if spot<500:return 5
    if spot<1500:return 10
    return 20

def analyze(symbol):
    q=quote(symbol)
    spot=q["price"]
    prices=chart_prices(symbol) if symbol not in INDEXES else []
    chain=option_chain(symbol)
    expiry=nearest_expiry(chain)
    df=norm_chain(chain,expiry)
    if df.empty: raise RuntimeError("NSE returned no option-chain rows for the nearest expiry.")

    step=step_for(symbol,spot)
    atm=float(df.iloc[(df["strike"]-spot).abs().argsort()[:1].iloc[0]]["strike"])
    near=df[(df.strike>=spot-5*step)&(df.strike<=spot+5*step)].copy()
    if near.empty: near=df.copy()

    total_call=near.ce_oi.sum(); total_put=near.pe_oi.sum()
    pcr=total_put/max(total_call,1)
    call_wall=float(near.loc[near.ce_oi.idxmax(),"strike"])
    put_wall=float(near.loc[near.pe_oi.idxmax(),"strike"])

    if prices:
        last=prices[-1]
        e20=ema(prices,20); e50=ema(prices,50)
        rv=float(np.std(np.diff(np.log(np.maximum(prices,1))))*math.sqrt(max(len(prices),1))*100)
        r=rsi(prices)
        momentum=float(np.clip(50+(last/e20-1)*1800,0,100))
        trend= "BULLISH" if last>e20 and e20>=e50 else ("BEARISH" if last<e20 and e20<=e50 else "NEUTRAL")
        recent=prices[-min(80,len(prices)):]
        support=float(min(recent)); resistance=float(max(recent))
    else:
        # Option-chain-only fallback when chart endpoint is unavailable.
        r=50.0; momentum=50.0
        trend="BULLISH" if pcr>=1.05 else ("BEARISH" if pcr<=0.85 else "NEUTRAL")
        support=put_wall; resistance=call_wall; rv=0

    # Combine price trend, PCR and OI changes.
    near3=near[(near.strike>=spot-3*step)&(near.strike<=spot+3*step)]
    call_chg=float(near3.ce_chg_oi.sum()); put_chg=float(near3.pe_chg_oi.sum())
    oi_bull = (put_chg>0 and call_chg<0)
    oi_bear = (call_chg>0 and put_chg<0)

    bull=0; bear=0
    bull += 30 if trend=="BULLISH" else (12 if trend=="NEUTRAL" else 0)
    bear += 30 if trend=="BEARISH" else (12 if trend=="NEUTRAL" else 0)
    bull += float(np.clip((pcr-0.8)*35,0,25))
    bear += float(np.clip((1.05-pcr)*45,0,25))
    bull += 20 if oi_bull else (7 if put_chg>0 else 0)
    bear += 20 if oi_bear else (7 if call_chg>0 else 0)
    bull += 15 if r>=55 else 5
    bear += 15 if r<=45 else 5
    bull=min(100,bull); bear=min(100,bear)

    side="CE" if bull>=bear else "PE"
    strength=max(bull,bear)
    # Quality gate: do not force a trade.
    action="NO TRADE"
    if strength>=68 and abs(bull-bear)>=12: action="TRADE"
    elif strength>=55: action="WAIT"

    target_strike = atm + (step if side=="CE" else -step)
    if side=="CE":
        candidates=near[(near.strike>=atm)&(near.strike<=atm+2*step)].copy()
        if candidates.empty: candidates=near.copy()
        row=candidates.iloc[(candidates.ce_ltp.replace(0,np.nan).fillna(1e9)).abs().argsort()[:1].iloc[0]]
        premium=float(row.ce_ltp); iv=float(row.ce_iv); delta=bs_delta(spot,float(row.strike),iv,max(1,(datetime.strptime(expiry,"%d-%b-%Y").date()-datetime.now(IST).date()).days),True)
        opt_oi=int(row.ce_oi); opt_chg=int(row.ce_chg_oi); vol=int(row.ce_vol)
        bid=float(row.ce_bid); ask=float(row.ce_ask)
    else:
        candidates=near[(near.strike<=atm)&(near.strike>=atm-2*step)].copy()
        if candidates.empty: candidates=near.copy()
        row=candidates.iloc[(candidates.pe_ltp.replace(0,np.nan).fillna(1e9)).abs().argsort()[:1].iloc[0]]
        premium=float(row.pe_ltp); iv=float(row.pe_iv); delta=abs(bs_delta(spot,float(row.strike),iv,max(1,(datetime.strptime(expiry,"%d-%b-%Y").date()-datetime.now(IST).date()).days),False))
        opt_oi=int(row.pe_oi); opt_chg=int(row.pe_chg_oi); vol=int(row.pe_vol)
        bid=float(row.pe_bid); ask=float(row.pe_ask)

    if premium<=0: action="NO TRADE"
    entry=max(premium,(bid+ask)/2 if bid>0 and ask>0 else premium)
    # Premium risk levels. Use a tighter stop for liquid ATM/near-ATM options.
    sl=round(entry*0.72,2)
    t1=round(entry*1.35,2)
    t2=round(entry*1.65,2)

    trigger = resistance if side=="CE" else support
    if prices:
        trigger = resistance if side=="CE" else support
        # Avoid requiring an impossible trigger far from current price.
        if side=="CE" and trigger<=spot: trigger=spot*(1+0.0015)
        if side=="PE" and trigger>=spot: trigger=spot*(1-0.0015)
    else:
        trigger=spot + step*0.15 if side=="CE" else spot-step*0.15

    reasons=[]
    reasons.append(f"Trend: {trend}. RSI: {r:.0f}.")
    reasons.append(f"PCR: {pcr:.2f}. Put OI wall {put_wall:.0f}; Call OI wall {call_wall:.0f}.")
    reasons.append("Put OI building / Call OI unwinding supports CE." if oi_bull else
                   "Call OI building / Put OI unwinding supports PE." if oi_bear else
                   "OI change is mixed; confirmation is required.")
    reasons.append(f"Selected {side} has delta ~{delta:.2f}, IV {iv:.1f}%, volume {vol:,}.")
    if action=="TRADE":
        reasons.append("Multiple independent factors align; wait for the stated underlying trigger.")
    elif action=="WAIT":
        reasons.append("Signal is not strong enough yet; do not enter until confirmation.")
    else:
        reasons.append("Signals are conflicting or weak; the correct action is NO TRADE.")

    return {
      "symbol":symbol,"spot":spot,"change":q["change"],"expiry":expiry,"atm":atm,
      "pcr":pcr,"put_wall":put_wall,"call_wall":call_wall,"support":support,
      "resistance":resistance,"rsi":r,"trend":trend,"bull":bull,"bear":bear,
      "action":action,"side":side,"strike":float(row.strike),"premium":premium,
      "entry":entry,"sl":sl,"t1":t1,"t2":t2,"delta":delta,"iv":iv,
      "oi":opt_oi,"chg_oi":opt_chg,"volume":vol,"trigger":trigger,"reasons":reasons,
      "rows":near
    }

def money(x): return f"₹{x:,.2f}" if x<1000 else f"₹{x:,.0f}"

st.title("📈 Option Trade Assistant")
st.caption("Live NSE public-data connector • analysis only • no order placement")

with st.container(border=True):
    c1,c2=st.columns([4,1])
    with c1:
        symbol_input=st.text_input("Enter F&O stock / index", placeholder="KOTAKBANK, RELIANCE, NIFTY...")
    with c2:
        risk=st.selectbox("Risk",["Conservative","Balanced","Aggressive"],index=1)

    go=st.button("🔎 ANALYZE", type="primary", use_container_width=True)

if go:
    symbol=normalize_symbol(symbol_input)
    if not symbol:
        st.error("Enter a stock/index symbol.")
        st.stop()
    with st.spinner(f"Fetching live NSE data for {symbol}..."):
        try:
            a=analyze(symbol)
        except Exception as e:
            st.error("Live data could not be fetched right now.")
            st.code(str(e))
            st.info("NSE public endpoints can rate-limit or block automated requests. Try again after a short interval.")
            st.stop()

    st.success(f"Data received from NSE • {datetime.now(IST).strftime('%d-%b-%Y %H:%M:%S IST')}")

    top=st.columns(6)
    top[0].metric("Live price",money(a["spot"]),f"{a['change']:.2f}%")
    top[1].metric("Bias",a["trend"])
    top[2].metric("PCR",f"{a['pcr']:.2f}")
    top[3].metric("Put OI wall",money(a["put_wall"]))
    top[4].metric("Call OI wall",money(a["call_wall"]))
    top[5].metric("RSI",f"{a['rsi']:.0f}")

    st.divider()
    if a["action"]=="TRADE":
        st.success(f"## 🟢 BUY {a['side']} — {a['strike']:.0f} {a['side']}  | Score {max(a['bull'],a['bear']):.0f}/100")
    elif a["action"]=="WAIT":
        st.warning(f"## 🟡 WAIT — {a['side']} setup is developing")
    else:
        st.error("## 🔴 NO TRADE")

    if a["action"]!="NO TRADE":
        x=st.columns(6)
        x[0].metric("Option",f"{a['strike']:.0f} {a['side']}")
        x[1].metric("Entry",money(a["entry"]))
        x[2].metric("Stop Loss",money(a["sl"]))
        x[3].metric("Target 1",money(a["t1"]))
        x[4].metric("Target 2",money(a["t2"]))
        x[5].metric("Delta",f"{a['delta']:.2f}")

        st.markdown(f"### Entry trigger")
        if a["side"]=="CE":
            st.info(f"Enter only after the underlying sustains above **{money(a['trigger'])}** with volume/price confirmation.")
        else:
            st.info(f"Enter only after the underlying sustains below **{money(a['trigger'])}** with volume/price confirmation.")

        st.markdown("### Exit plan")
        st.write(f"1. **SL:** exit if option premium falls to **{money(a['sl'])}**.")
        st.write(f"2. **Target 1:** book partial profit around **{money(a['t1'])}**.")
        st.write(f"3. **Target 2:** exit the balance around **{money(a['t2'])}**.")
        st.write("4. If the underlying invalidates the breakout/breakdown or the bias flips, exit even if the premium target has not been reached.")
        st.write(f"5. Avoid carrying the trade into expiry just because the target was not hit.")

    st.divider()
    st.subheader("Why the engine says this")
    for r in a["reasons"]: st.write("•",r)

    with st.expander("Detailed live option-chain snapshot"):
        d=a["rows"].copy()
        show=d[["strike","ce_ltp","ce_oi","ce_chg_oi","ce_vol","ce_iv","pe_ltp","pe_oi","pe_chg_oi","pe_vol","pe_iv"]]
        show.columns=["Strike","CE LTP","CE OI","CE Chg OI","CE Vol","CE IV","PE LTP","PE OI","PE Chg OI","PE Vol","PE IV"]
        st.dataframe(show, use_container_width=True, hide_index=True)

    st.caption("This is a rule-based decision aid, not a guarantee of profit. Option prices can move sharply; verify the quote and liquidity in your broker before trading.")

else:
    st.info("Enter a stock such as KOTAKBANK or RELIANCE and click ANALYZE.")
    st.markdown("""
### What this app does
- Fetches the latest available NSE public quote and option chain.
- Chooses the nearest active expiry.
- Calculates PCR, OI walls, OI-change pressure, RSI/EMA when intraday chart data is available.
- Estimates option delta from spot, strike, IV and time to expiry.
- Ranks **CE vs PE** and can return **TRADE / WAIT / NO TRADE**.
- Gives an entry trigger, option SL, two targets and an exit plan.

### Important data limitation
This build intentionally avoids a paid market-data subscription. NSE's public website exposes an option-chain page and live/streaming market information, but NSE also states that its site is governed by its Terms of Use and prohibits aggregation/copying of site content. Public endpoints can also be rate-limited or blocked. Therefore this is a best-effort personal-use connector, not a guaranteed institutional-grade feed.
""")
