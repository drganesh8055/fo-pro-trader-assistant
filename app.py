import streamlit as st
import requests
import pandas as pd
from datetime import date

st.set_page_config(page_title="F&O Pro Trader Assistant", page_icon="📈", layout="wide")

BASE = "https://api.dhan.co/v2"
MASTER = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"

def dhan_headers():
    return {
        "access-token": st.secrets["DHAN_ACCESS_TOKEN"],
        "client-id": st.secrets["DHAN_CLIENT_ID"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def api_post(path, payload):
    r = requests.post(BASE + path, headers=dhan_headers(), json=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Dhan API error {r.status_code}: {r.text[:500]}")
    return r.json()

@st.cache_data(ttl=3600)
def load_master():
    df = pd.read_csv(MASTER, low_memory=False)
    return df

def find_underlying(master, symbol):
    symbol = symbol.upper().strip()
    # Prefer NSE cash equity row.
    candidates = master[
        (master["EXCH_ID"].astype(str).str.upper()=="NSE") &
        (master["SEGMENT"].astype(str).str.upper().isin(["E","EQUITY"])) &
        (master["SYMBOL_NAME"].astype(str).str.upper()==symbol)
    ]
    if not candidates.empty:
        return str(candidates.iloc[0]["SECURITY_ID"]), "NSE_EQ"
    # Fallback to derivative rows and their underlying security id.
    candidates = master[
        master["UNDERLYING_SYMBOL"].astype(str).str.upper().eq(symbol) &
        master["INSTRUMENT"].astype(str).str.upper().eq("OPTSTK")
    ]
    if not candidates.empty:
        return str(candidates.iloc[0]["UNDERLYING_SECURITY_ID"]), "NSE_EQ"
    raise ValueError(f"Could not find Dhan security ID for {symbol}")

def expiry_list(secid, seg):
    out = api_post("/optionchain/expirylist", {
        "UnderlyingScrip": int(secid),
        "UnderlyingSeg": seg
    })
    return out.get("data", [])

def option_chain(secid, seg, expiry):
    return api_post("/optionchain", {
        "UnderlyingScrip": int(secid),
        "UnderlyingSeg": seg,
        "Expiry": expiry
    })

def flatten_chain(resp):
    rows=[]
    data=resp.get("data", {})
    for strike, both in data.get("oc", {}).items():
        try: strike_f=float(strike)
        except: continue
        for side, item in [("CE", both.get("ce", {})), ("PE", both.get("pe", {}))]:
            if not item: continue
            g=item.get("greeks", {}) or {}
            rows.append({
                "Strike":strike_f, "Side":side,
                "LTP":item.get("last_price",0),
                "OI":item.get("oi",0),
                "Prev OI":item.get("previous_oi",0),
                "Volume":item.get("volume",0),
                "IV":item.get("implied_volatility",0),
                "Delta":g.get("delta",0),
                "Theta":g.get("theta",0),
                "Gamma":g.get("gamma",0),
                "Vega":g.get("vega",0),
                "Bid":item.get("top_bid_price",0),
                "Ask":item.get("top_ask_price",0),
                "Security ID":item.get("security_id","")
            })
    return pd.DataFrame(rows)

def analyze(symbol, expiry_choice):
    master=load_master()
    secid, seg=find_underlying(master, symbol)
    expiries=expiry_list(secid, seg)
    if not expiries: raise ValueError("Dhan returned no active expiries.")
    expiry=expiry_choice if expiry_choice in expiries else expiries[0]
    resp=option_chain(secid, seg, expiry)
    chain=flatten_chain(resp)
    spot=float(resp.get("data",{}).get("last_price",0))
    if chain.empty: raise ValueError("Empty option chain.")
    chain["OI Change"]=chain["OI"]-chain["Prev OI"]
    ce=chain[chain.Side=="CE"].copy()
    pe=chain[chain.Side=="PE"].copy()
    pcr=pe.OI.sum()/max(ce.OI.sum(),1)
    call_wall=float(ce.loc[ce.OI.idxmax(),"Strike"])
    put_wall=float(pe.loc[pe.OI.idxmax(),"Strike"])
    # ATM row and simple directional scoring, deliberately conservative.
    atm_idx=(chain.Strike-spot).abs().argsort().iloc[0]
    atm_strike=float(chain.iloc[atm_idx].Strike)
    atm_ce=ce[ce.Strike==atm_strike]
    atm_pe=pe[pe.Strike==atm_strike]
    ce_oi_chg=float(atm_ce["OI Change"].iloc[0]) if not atm_ce.empty else 0
    pe_oi_chg=float(atm_pe["OI Change"].iloc[0]) if not atm_pe.empty else 0
    if pcr > 1.15 and pe_oi_chg > 0: view="BULLISH"
    elif pcr < .85 and ce_oi_chg > 0: view="BEARISH"
    else: view="NEUTRAL / WAIT"
    return spot, expiry, pcr, call_wall, put_wall, view, chain

st.title("📈 F&O Pro Trader Assistant — Live Dhan")
st.caption("Live option-chain analysis. Recommendations remain decision support; automatic orders are disabled.")

if "DHAN_ACCESS_TOKEN" not in st.secrets or "DHAN_CLIENT_ID" not in st.secrets:
    st.error("Dhan credentials are not configured yet.")
    st.info("After replacing this app, add DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID in Streamlit App Settings → Secrets. Never put them in GitHub.")
    st.stop()

default_symbols=["NIFTY","BANKNIFTY","RELIANCE","HDFCBANK","ICICIBANK","KOTAKBANK","INFY","TCS"]
symbol=st.selectbox("Select underlying", default_symbols)
if st.button("🔄 READ LIVE OPTION CHAIN", type="primary"):
    try:
        master=load_master()
        secid, seg=find_underlying(master, symbol)
        expiries=expiry_list(secid, seg)
        if not expiries: raise ValueError("No expiry returned by Dhan.")
        expiry=st.selectbox("Expiry", expiries, index=0)
        spot, exp, pcr, call_wall, put_wall, view, chain=analyze(symbol, expiry)
        c1,c2,c3,c4,c5=st.columns(5)
        c1.metric("Spot", f"₹{spot:,.2f}")
        c2.metric("PCR", f"{pcr:.2f}")
        c3.metric("Call OI Wall", f"{call_wall:g}")
        c4.metric("Put OI Wall", f"{put_wall:g}")
        c5.metric("Engine View", view)
        st.subheader("Option Chain")
        st.dataframe(chain.sort_values(["Strike","Side"]), use_container_width=True, hide_index=True)
        st.warning("This first live build is a data-validation stage. It does NOT yet claim a statistically validated probability of profit.")
    except Exception as e:
        st.error(str(e))
else:
    st.info("Click the button to retrieve the live option chain from Dhan.")
    st.markdown("""
### What we are building next
1. Live F&O universe
2. Top gainers/losers
3. OI + change in OI
4. PCR + OI walls
5. Greeks + IV + liquidity
6. Price-action and technical signals
7. Historical backtesting
8. Calibrated target-before-SL probability
9. Paper trading
10. Broker execution only after validation
""")
