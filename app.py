import math
import gzip
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# ============================================================
# FO PRO TRADER ASSISTANT — LIVE UPSTOX VERSION
# Restored fuller trade-plan design:
# PoP, Entry, SL, Target 1, Target 2, Exit, Delta, IV,
# PCR, OI support/resistance, live option chain and analysis.
# ============================================================

st.set_page_config(
    page_title="FO PRO Trader Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "https://api.upstox.com"

st.markdown(
    """
<style>
.stApp { background:#f6f8fb; }
.block-container { padding-top:1rem; padding-bottom:2rem; max-width:1500px; }
.topbar {
    background:linear-gradient(100deg,#102a43,#1f4b73);
    padding:18px 24px; border-radius:14px; color:white; margin-bottom:18px;
}
.topbar-title {font-size:27px;font-weight:800;}
.topbar-sub {font-size:13px;opacity:.82;margin-top:3px;}
.status-pill {
    display:inline-block;padding:7px 12px;border-radius:20px;
    background:#1f9d55;color:white;font-size:12px;font-weight:700;
}
.card {
    background:white;border:1px solid #e7ebf0;border-radius:14px;
    padding:18px;margin-bottom:16px;box-shadow:0 2px 8px rgba(16,42,67,.04);
}
.section-title {font-size:20px;font-weight:800;color:#182230;margin-bottom:12px;}
.trade-call {
    background:#eaf8ef;border:1px solid #bde5c9;border-radius:12px;
    padding:14px 16px;font-weight:800;color:#147a3d;
}
.trade-put {
    background:#fff0f1;border:1px solid #f2c5c8;border-radius:12px;
    padding:14px 16px;font-weight:800;color:#b4232f;
}
.trade-neutral {
    background:#f2f4f7;border:1px solid #dfe3e8;border-radius:12px;
    padding:14px 16px;font-weight:800;color:#475467;
}
</style>
""",
    unsafe_allow_html=True,
)


class UpstoxError(RuntimeError):
    pass


def get_token():
    try:
        return str(st.secrets.get("UPSTOX_ACCESS_TOKEN", "")).strip()
    except Exception:
        return ""


TOKEN = get_token()

if not TOKEN:
    st.error(
        "Upstox access token is not configured. Add UPSTOX_ACCESS_TOKEN "
        "under Streamlit → App settings → Secrets, then reload the app."
    )
    st.stop()

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}


def api_get(path, params=None, timeout=20):
    try:
        response = requests.get(
            f"{API_BASE}{path}",
            headers=HEADERS,
            params=params,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise UpstoxError(f"Network error while contacting Upstox: {exc}") from exc

    if response.status_code != 200:
        try:
            body = response.json()
            message = body.get("errors") or body.get("message") or body
        except Exception:
            message = response.text[:500]
        raise UpstoxError(f"Upstox API {response.status_code}: {message}")

    try:
        return response.json()
    except Exception as exc:
        raise UpstoxError("Upstox returned invalid JSON.") from exc


def fmt_price(value):
    try:
        x = float(value)
    except Exception:
        return "—"
    if np.isnan(x):
        return "—"
    return f"₹{x:,.2f}" if abs(x) < 1000 else f"₹{x:,.0f}"


def fmt_num(value):
    try:
        x = float(value)
    except Exception:
        return "—"
    if np.isnan(x):
        return "—"
    return f"{x:,.0f}"


def safe_float(value, default=np.nan):
    try:
        return float(value)
    except Exception:
        return default


def alias_symbol(symbol):
    s = symbol.strip().upper().replace(" ", "")
    aliases = {
        "NIFTY50": "NIFTY",
        "NIFTYBANK": "BANKNIFTY",
        "NIFTYFIN": "FINNIFTY",
        "MIDCAPNIFTY": "MIDCPNIFTY",
    }
    return aliases.get(s, s)


@st.cache_data(ttl=30, show_spinner=False)
def search_underlying(symbol):
    symbol = alias_symbol(symbol)
    results = []

    for segment in ["EQ", "INDEX"]:
        payload = api_get(
            "/v2/instruments/search",
            params={
                "query": symbol,
                "exchanges": "NSE",
                "segments": segment,
                "page_number": 1,
                "records": 30,
            },
        )
        results.extend(payload.get("data", []))

    if not results:
        raise UpstoxError(
            f"No NSE instrument found for '{symbol}'. "
            "Enter an NSE F&O stock symbol such as HDFCBANK or an index such as NIFTY."
        )

    exact = [
        item for item in results
        if str(item.get("trading_symbol", "")).upper() == symbol
    ]
    if exact:
        return exact[0]

    if symbol in {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}:
        indexes = [x for x in results if x.get("segment") == "NSE_INDEX"]
        if indexes:
            return indexes[0]

    equities = [x for x in results if x.get("segment") == "NSE_EQ"]
    return equities[0] if equities else results[0]


@st.cache_data(ttl=120, show_spinner=False)
def get_contracts(underlying_key):
    payload = api_get(
        "/v2/option/contract",
        params={"instrument_key": underlying_key},
        timeout=30,
    )
    contracts = payload.get("data", [])
    if not contracts:
        raise UpstoxError("Upstox returned no option contracts for this instrument.")
    return contracts


def available_expiries(contracts):
    today = date.today().isoformat()
    return sorted(
        {
            str(item.get("expiry"))
            for item in contracts
            if item.get("expiry") and str(item.get("expiry")) >= today
        }
    )


@st.cache_data(ttl=20, show_spinner=False)
def get_option_chain(underlying_key, expiry):
    payload = api_get(
        "/v2/option/chain",
        params={
            "instrument_key": underlying_key,
            "expiry_date": expiry,
        },
        timeout=30,
    )
    rows = payload.get("data", [])
    if not rows:
        raise UpstoxError(f"No option-chain data returned for expiry {expiry}.")
    return rows


@st.cache_data(ttl=20, show_spinner=False)
def get_quote(instrument_key):
    payload = api_get(
        "/v3/market-quote/quotes",
        params={"instrument_key": instrument_key},
    )
    data = payload.get("data", {})
    if not data:
        raise UpstoxError("No live quote returned by Upstox.")
    return next(iter(data.values()))


@st.cache_data(ttl=15, show_spinner=False)
def get_intraday_candles(instrument_key, minutes=5):
    path = (
        f"/v3/historical-candle/intraday/"
        f"{quote(instrument_key, safe='')}/minutes/{minutes}"
    )
    payload = api_get(path, timeout=30)
    candles = payload.get("data", {}).get("candles", [])
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(
        candles,
        columns=["timestamp", "open", "high", "low", "close", "volume", "oi"],
    )
    for column in ["open", "high", "low", "close", "volume", "oi"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True)


@st.cache_data(ttl=120, show_spinner=False)
def get_30min_candles(instrument_key):
    end_date = date.today()
    start_date = end_date - timedelta(days=90)
    path = (
        f"/v3/historical-candle/{quote(instrument_key, safe='')}"
        f"/minutes/30/{end_date.isoformat()}/{start_date.isoformat()}"
    )
    payload = api_get(path, timeout=30)
    candles = payload.get("data", {}).get("candles", [])
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(
        candles,
        columns=["timestamp", "open", "high", "low", "close", "volume", "oi"],
    )
    for column in ["open", "high", "low", "close", "volume", "oi"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def get_daily_candles(instrument_key):
    end_date = date.today()
    start_date = end_date - timedelta(days=160)

    path = (
        f"/v3/historical-candle/{quote(instrument_key, safe='')}"
        f"/days/1/{end_date.isoformat()}/{start_date.isoformat()}"
    )

    payload = api_get(path, timeout=30)
    candles = payload.get("data", {}).get("candles", [])

    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(
        candles,
        columns=["timestamp", "open", "high", "low", "close", "volume", "oi"],
    )

    for column in ["open", "high", "low", "close", "volume", "oi"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True)


def technicals(df, spot, label="Daily"):
    if df.empty or len(df) < 20:
        return {
            "label": label,
            "rsi": 50.0,
            "ema20": spot,
            "ema50": spot,
            "atr": spot * 0.01,
            "trend": "Unavailable",
            "momentum": 0.0,
            "volume_ratio": np.nan,
        }

    close = df["close"].astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - previous_close).abs(),
            (df["low"] - previous_close).abs(),
        ], axis=1,
    ).max(axis=1)
    atr = true_range.rolling(14, min_periods=14).mean()

    latest_rsi = safe_float(rsi.iloc[-1], 50.0)
    latest_ema20 = safe_float(ema20.iloc[-1], spot)
    latest_ema50 = safe_float(ema50.iloc[-1], spot)
    latest_atr = safe_float(atr.iloc[-1], spot * 0.01)
    lookback = min(10, len(close)-1)
    momentum = ((float(close.iloc[-1]) / float(close.iloc[-1-lookback])) - 1) * 100 if lookback > 0 else 0.0
    volume_ratio = np.nan
    if "volume" in df.columns and len(df) >= 20:
        avg_vol = df["volume"].rolling(20, min_periods=10).mean().iloc[-1]
        if np.isfinite(avg_vol) and avg_vol > 0:
            volume_ratio = float(df["volume"].iloc[-1] / avg_vol)

    if spot > latest_ema20 > latest_ema50 and latest_rsi >= 52:
        trend = "Bullish"
    elif spot < latest_ema20 < latest_ema50 and latest_rsi <= 48:
        trend = "Bearish"
    else:
        trend = "Sideways"

    return {
        "label": label,
        "rsi": latest_rsi,
        "ema20": latest_ema20,
        "ema50": latest_ema50,
        "atr": latest_atr,
        "trend": trend,
        "momentum": momentum,
        "volume_ratio": volume_ratio,
    }


def overall_trend(tf5, tf30, daily):
    vals=[tf5["trend"],tf30["trend"],daily["trend"]]
    bull=vals.count("Bullish"); bear=vals.count("Bearish")
    if bull>=2 and bull>bear: return "Bullish", bull
    if bear>=2 and bear>bull: return "Bearish", bear
    return "Sideways", max(bull,bear)

def normalize_chain(rows):
    records = []

    for item in rows:
        strike = safe_float(item.get("strike_price"))

        call = item.get("call_options") or {}
        put = item.get("put_options") or {}

        call_market = call.get("market_data") or {}
        call_greeks = call.get("option_greeks") or {}
        put_market = put.get("market_data") or {}
        put_greeks = put.get("option_greeks") or {}

        call_oi = safe_float(call_market.get("oi"), 0)
        put_oi = safe_float(put_market.get("oi"), 0)

        call_prev_oi = safe_float(call_market.get("prev_oi"), 0)
        put_prev_oi = safe_float(put_market.get("prev_oi"), 0)

        records.append(
            {
                "Strike": strike,
                "CE Key": call.get("instrument_key"),
                "CE LTP": safe_float(call_market.get("ltp")),
                "CE Bid": safe_float(call_market.get("bid_price")),
                "CE Ask": safe_float(call_market.get("ask_price")),
                "CE OI": call_oi,
                "CE Chg OI": call_oi - call_prev_oi,
                "CE Volume": safe_float(call_market.get("volume"), 0),
                "CE IV": safe_float(call_greeks.get("iv")),
                "CE Delta": safe_float(call_greeks.get("delta")),
                "CE Gamma": safe_float(call_greeks.get("gamma")),
                "CE Theta": safe_float(call_greeks.get("theta")),
                "CE Vega": safe_float(call_greeks.get("vega")),
                "CE PoP": safe_float(call_greeks.get("pop")),
                "PE Key": put.get("instrument_key"),
                "PE LTP": safe_float(put_market.get("ltp")),
                "PE Bid": safe_float(put_market.get("bid_price")),
                "PE Ask": safe_float(put_market.get("ask_price")),
                "PE OI": put_oi,
                "PE Chg OI": put_oi - put_prev_oi,
                "PE Volume": safe_float(put_market.get("volume"), 0),
                "PE IV": safe_float(put_greeks.get("iv")),
                "PE Delta": safe_float(put_greeks.get("delta")),
                "PE Gamma": safe_float(put_greeks.get("gamma")),
                "PE Theta": safe_float(put_greeks.get("theta")),
                "PE Vega": safe_float(put_greeks.get("vega")),
                "PE PoP": safe_float(put_greeks.get("pop")),
            }
        )

    return pd.DataFrame(records).sort_values("Strike").reset_index(drop=True)


def oi_levels(chain, spot):
    valid = chain.dropna(subset=["Strike"]).copy()
    if valid.empty:
        return np.nan, np.nan, np.nan, {"put_walls": pd.DataFrame(), "call_walls": pd.DataFrame()}
    window = valid[(valid["Strike"] >= spot*0.93) & (valid["Strike"] <= spot*1.07)]
    if window.empty: window = valid
    below = window[window["Strike"] <= spot]
    above = window[window["Strike"] >= spot]
    support_row = below.loc[below["PE OI"].idxmax()] if not below.empty else window.loc[window["PE OI"].idxmax()]
    resistance_row = above.loc[above["CE OI"].idxmax()] if not above.empty else window.loc[window["CE OI"].idxmax()]
    total_call_oi = valid["CE OI"].sum(); total_put_oi = valid["PE OI"].sum()
    pcr = total_put_oi/total_call_oi if total_call_oi else np.nan
    return float(support_row["Strike"]), float(resistance_row["Strike"]), pcr, {
        "put_walls": window.nlargest(3,"PE OI")[["Strike","PE OI","PE Chg OI"]],
        "call_walls": window.nlargest(3,"CE OI")[["Strike","CE OI","CE Chg OI"]],
    }

def nearest_row(chain, strike):
    if chain.empty:
        return None
    index = (chain["Strike"] - strike).abs().idxmin()
    return chain.loc[index]


def current_iv_percentile(chain, side, iv):
    vals = pd.to_numeric(chain[f"{side} IV"], errors="coerce").dropna()
    if not np.isfinite(iv) or len(vals) < 5:
        return np.nan
    return float((vals <= iv).mean()*100)


def spread_percent(row, side):
    bid=safe_float(row[f"{side} Bid"]); ask=safe_float(row[f"{side} Ask"])
    if not np.isfinite(bid) or not np.isfinite(ask) or bid<=0 or ask<=0: return np.nan
    mid=(bid+ask)/2
    return (ask-bid)/mid*100 if mid>0 else np.nan


def score_option(row, side, spot, pcr, tf5, tf30, daily, chain):
    direction="Bullish" if side=="CE" else "Bearish"
    trends=[tf5["trend"],tf30["trend"],daily["trend"]]
    alignment=sum(x==direction for x in trends)
    delta=safe_float(row[f"{side} Delta"]); pop=safe_float(row[f"{side} PoP"])
    iv=safe_float(row[f"{side} IV"]); chg_oi=safe_float(row[f"{side} Chg OI"],0)
    volume=safe_float(row[f"{side} Volume"],0); spread=spread_percent(row,side)
    iv_rank=current_iv_percentile(chain,side,iv)
    distance_pct=abs(float(row["Strike"])-spot)/max(spot,1)*100
    delta_points=12 if np.isfinite(delta) and .45<=abs(delta)<=.65 else 8 if np.isfinite(delta) and .35<=abs(delta)<=.75 else 4 if np.isfinite(delta) else 0
    pop_points=np.clip((pop-50)/30*10,0,10) if np.isfinite(pop) else 0
    spread_points=4 if np.isfinite(spread) and spread<=2 else 2 if np.isfinite(spread) and spread<=4 else 0
    liquidity_points=4 if volume>0 else 0
    iv_points=5 if np.isfinite(iv_rank) and 25<=iv_rank<=75 else 2 if np.isfinite(iv_rank) else 0
    distance_points=5 if distance_pct<=2 else 3 if distance_pct<=4 else 0
    trend_points={3:25,2:19,1:10,0:0}[alignment]
    avg_momentum=np.nanmean([tf5["momentum"],tf30["momentum"],daily["momentum"]])
    if side=="CE": momentum_points=float(np.clip(5+avg_momentum*2,0,10))
    else: momentum_points=float(np.clip(5-avg_momentum*2,0,10))
    if np.isfinite(pcr):
        pcr_points=(10 if pcr>=1 else 6 if pcr>=.85 else 0) if side=="CE" else (10 if pcr<=.85 else 6 if pcr<=1 else 0)
    else: pcr_points=0
    oi_points=5 if chg_oi>0 else 2 if chg_oi==0 else 1
    score=float(np.clip(trend_points+pcr_points+momentum_points+oi_points+delta_points+pop_points+spread_points+liquidity_points+iv_points+distance_points,0,100))
    return {"score":score,"premium":row[f"{side} LTP"],"delta":delta,"iv":iv,"pop":pop,"chg_oi":chg_oi,"volume":volume,"gamma":safe_float(row[f"{side} Gamma"]),"theta":safe_float(row[f"{side} Theta"]),"vega":safe_float(row[f"{side} Vega"]),"spread":spread,"iv_rank":iv_rank,"alignment":alignment,"avg_momentum":avg_momentum}


def build_plan(row, side, spot, support, resistance, pcr, tf5, tf30, daily, risk_profile, chain):
    if row is None: return None
    scored=score_option(row,side,spot,pcr,tf5,tf30,daily,chain)
    bid=safe_float(row[f"{side} Bid"]); ask=safe_float(row[f"{side} Ask"]); ltp=safe_float(row[f"{side} LTP"])
    current=(bid+ask)/2 if np.isfinite(bid) and np.isfinite(ask) and bid>0 and ask>0 else ltp
    if not np.isfinite(current) or current<=0: return None
    factors={"Conservative":(.78,1.28,1.55),"Balanced":(.72,1.42,1.85),"Aggressive":(.65,1.58,2.15)}
    slf,t1f,t2f=factors[risk_profile]
    sl=round(current*slf,2); t1=round(current*t1f,2); t2=round(current*t2f,2)
    rr1=(t1-current)/max(current-sl,.01); rr2=(t2-current)/max(current-sl,.01)
    trigger_level=resistance if side=="CE" else support
    triggered=spot>=trigger_level if side=="CE" else spot<=trigger_level
    trigger=(f"Spot is above/at resistance {fmt_price(trigger_level)}." if triggered and side=="CE" else f"Spot is below/at support {fmt_price(trigger_level)}." if triggered else (f"Wait for spot to break and sustain above {fmt_price(trigger_level)}." if side=="CE" else f"Wait for spot to break and sustain below {fmt_price(trigger_level)}."))
    direction="Bullish" if side=="CE" else "Bearish"
    overall,align=max((tf5["trend"],tf30["trend"],daily["trend"]),key=lambda x:0) if False else (None,None)
    trends=[tf5["trend"],tf30["trend"],daily["trend"]]
    alignment=sum(x==direction for x in trends)
    failures=[]
    if alignment<2: failures.append("multi-timeframe trend not aligned")
    if scored["score"]<68: failures.append("setup score below 68")
    if not np.isfinite(scored["spread"]) or scored["spread"]>4: failures.append("wide bid/ask spread")
    if scored["alignment"]<2: failures.append("insufficient timeframe confirmation")
    if not np.isfinite(scored["pop"]): failures.append("Upstox PoP unavailable")
    readiness="READY" if triggered and not failures else "WAIT FOR TRIGGER" if scored["score"]>=68 and alignment>=2 else "NO TRADE"
    if side=="CE": exit_rule=f"Exit if spot closes below support {fmt_price(support)} or option premium hits {fmt_price(sl)}. After T1, book partial profit and trail."
    else: exit_rule=f"Exit if spot closes above resistance {fmt_price(resistance)} or option premium hits {fmt_price(sl)}. After T1, book partial profit and trail."
    return {"side":side,"strike":float(row["Strike"]),"current_premium":float(current),"trigger_price":float(trigger_level),"triggered":triggered,"sl":sl,"target1":t1,"target2":t2,"pop":scored["pop"],"delta":scored["delta"],"iv":scored["iv"],"gamma":scored["gamma"],"theta":scored["theta"],"vega":scored["vega"],"score":scored["score"],"rr1":rr1,"rr2":rr2,"trigger":trigger,"exit":exit_rule,"oi":row[f"{side} OI"],"chg_oi":scored["chg_oi"],"volume":scored["volume"],"spread":scored["spread"],"iv_rank":scored["iv_rank"],"alignment":alignment,"failures":failures,"readiness":readiness}


# ============================================================
# FULL F&O MARKET PoP SCANNER — SIDEBAR ONLY
# ============================================================

FNO_MASTER_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"


@st.cache_data(ttl=3600, show_spinner=False)
def get_fno_underlyings():
    """Build the current NSE equity F&O universe from Upstox's BOD master."""
    try:
        response = requests.get(FNO_MASTER_URL, timeout=30)
        response.raise_for_status()
        raw = gzip.decompress(response.content)
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise UpstoxError(f"Unable to load the Upstox NSE F&O instrument list: {exc}") from exc

    if isinstance(payload, dict):
        records = payload.get("data", payload.get("instruments", []))
    else:
        records = payload

    today = date.today().isoformat()
    universe = {}

    for item in records:
        if not isinstance(item, dict):
            continue
        if item.get("segment") != "NSE_FO":
            continue
        if item.get("instrument_type") not in {"CE", "PE", "FUT"}:
            continue
        if item.get("underlying_type") != "EQUITY":
            continue

        expiry = str(item.get("expiry", ""))
        if not expiry:
            continue

        # Upstox BOD JSON normally supplies expiry as an epoch-millisecond value
        # for NSE_FO. Handle both epoch and YYYY-MM-DD formats safely.
        if expiry.isdigit():
            try:
                expiry_date = datetime.fromtimestamp(
                    int(expiry) / 1000, tz=ZoneInfo("Asia/Kolkata")
                ).date().isoformat()
            except Exception:
                continue
        else:
            expiry_date = expiry[:10]

        if expiry_date < today:
            continue

        underlying_key = item.get("underlying_key")
        symbol = str(item.get("underlying_symbol") or "").strip().upper()
        if not underlying_key or not symbol:
            continue

        current = universe.get(underlying_key)
        if current is None or expiry_date < current["expiry"]:
            universe[underlying_key] = {
                "symbol": symbol,
                "underlying_key": underlying_key,
                "expiry": expiry_date,
            }

    return sorted(universe.values(), key=lambda x: x["symbol"])


def scan_full_fno_pop_market(min_pop=75.0):
    """Scan the nearest expiry of every NSE equity F&O underlying and return top 5 unique stocks."""
    universe = get_fno_underlyings()
    candidates = []
    scanned = 0
    failed = 0

    progress = st.progress(0, text="Starting full F&O market scan...")

    for idx, item in enumerate(universe, start=1):
        try:
            rows = get_option_chain(item["underlying_key"], item["expiry"])
            if not rows:
                failed += 1
                continue

            # The option-chain response carries the underlying spot in its rows.
            spot_values = [
                safe_float(row.get("underlying_spot_price"))
                for row in rows
                if np.isfinite(safe_float(row.get("underlying_spot_price")))
            ]
            spot_value = spot_values[0] if spot_values else np.nan

            best_for_stock = None

            for raw in rows:
                strike = safe_float(raw.get("strike_price"))
                if not np.isfinite(strike):
                    continue

                for side, action in (("CE", "CALL BUY"), ("PE", "PUT BUY")):
                    option = raw.get("call_options" if side == "CE" else "put_options") or {}
                    market = option.get("market_data") or {}
                    greeks = option.get("option_greeks") or {}

                    pop = safe_float(greeks.get("pop"))
                    if not np.isfinite(pop) or pop <= min_pop:
                        continue

                    ltp = safe_float(market.get("ltp"))
                    ask = safe_float(market.get("ask_price"))
                    bid = safe_float(market.get("bid_price"))
                    volume = safe_float(market.get("volume"), 0)
                    oi = safe_float(market.get("oi"), 0)
                    delta = safe_float(greeks.get("delta"))
                    iv = safe_float(greeks.get("iv"))

                    entry = ask if np.isfinite(ask) and ask > 0 else ltp
                    if not np.isfinite(entry) or entry <= 0:
                        continue

                    distance = (
                        abs(strike - spot_value) / max(spot_value, 1)
                        if np.isfinite(spot_value)
                        else 999
                    )

                    # Use the same Balanced risk levels as the main analyzer
                    # so the scanner's SL/targets are consistent with the app.
                    sl = round(entry * 0.70, 2)
                    target1 = round(entry * 1.40, 2)
                    target2 = round(entry * 1.80, 2)
                    exit_rule = "Exit at SL or Target 2; trail after Target 1"

                    spread_pct = ((ask-bid)/((ask+bid)/2)*100) if np.isfinite(bid) and np.isfinite(ask) and bid>0 and ask>0 else 999
                    delta_pts = 12 if np.isfinite(delta) and 0.45 <= abs(delta) <= 0.65 else 8 if np.isfinite(delta) and 0.35 <= abs(delta) <= 0.75 else 3
                    pop_pts = float(np.clip((pop-50)/30*10,0,10))
                    spread_pts = 4 if spread_pct <= 2 else 2 if spread_pct <= 4 else 0
                    liq_pts = 4 if volume > 0 else 0
                    dist_pct = distance*100
                    dist_pts = 5 if dist_pct <= 2 else 3 if dist_pct <= 4 else 0
                    setup_score = float(np.clip(45 + pop_pts + delta_pts + spread_pts + liq_pts + dist_pts,0,100))
                    candidate = {
                        "Stock": item["symbol"], "Trade": action, "Strike": strike, "Expiry": item["expiry"],
                        "PoP": pop, "SetupScore": setup_score, "Entry": entry, "SL": sl, "Target1": target1, "Target2": target2,
                        "Exit": exit_rule, "LTP": ltp, "Bid": bid, "Ask": ask, "Delta": delta, "IV": iv, "Volume": volume, "OI": oi,
                        "distance": distance, "Spread": spread_pct,
                    }

                    # One highest-PoP opportunity per stock keeps the Top 5 diversified.
                    if best_for_stock is None or (
                        candidate["SetupScore"], candidate["PoP"], candidate["Volume"], -candidate["distance"]
                    ) > (
                        best_for_stock["SetupScore"], best_for_stock["PoP"], best_for_stock["Volume"], -best_for_stock["distance"]
                    ):
                        best_for_stock = candidate

            if best_for_stock is not None:
                candidates.append(best_for_stock)
            scanned += 1

        except Exception:
            failed += 1

        progress.progress(
            idx / max(len(universe), 1),
            text=f"Scanning F&O market: {idx}/{len(universe)} stocks",
        )

    progress.empty()

    candidates.sort(
        key=lambda x: (-x["SetupScore"], -x["PoP"], -x["Volume"], x["distance"])
    )

    return candidates[:5], len(universe), scanned, failed


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("### 🔥 Top 5 F&O Setup Scanner")
    st.caption("Scans the full NSE equity F&O market. PoP is a filter; Setup Score ranks quality.")

    scan_market = st.button(
        "🔎 Scan Full F&O Market",
        use_container_width=True,
        type="primary",
    )

    if scan_market:
        try:
            with st.spinner("Scanning the full F&O market..."):
                results, total, scanned, failed = scan_full_fno_pop_market(75.0)
            st.session_state["fno_pop_results"] = results
            st.session_state["fno_pop_scan_info"] = (total, scanned, failed)
            st.session_state["fno_pop_scan_time"] = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")
        except UpstoxError as exc:
            st.session_state["fno_pop_results"] = []
            st.error(str(exc))
        except Exception as exc:
            st.session_state["fno_pop_results"] = []
            st.error(f"F&O scan failed: {exc}")

    pop_results = st.session_state.get("fno_pop_results", [])
    scan_info = st.session_state.get("fno_pop_scan_info")
    scan_time = st.session_state.get("fno_pop_scan_time")

    if pop_results:
        st.success(f"Top {len(pop_results)} setups with Upstox PoP ≥ 75%")
        if scan_info:
            total, scanned, failed = scan_info
            st.caption(f"Scanned {scanned}/{total} F&O stocks • {failed} unavailable")
        if scan_time:
            st.caption(f"Last scan: {scan_time} IST")

        scanner_display = pd.DataFrame([
            {
                "Stock": row["Stock"],
                "Trade": row["Trade"],
                "Strike": int(row["Strike"]),
                "PoP": f"{row['PoP']:.1f}%",
                "Setup Score": f"{row['SetupScore']:.0f}/100",
                "Entry": fmt_price(row["Entry"]),
                "SL": fmt_price(row["SL"]),
                "Target1": fmt_price(row["Target1"]),
                "Target2": fmt_price(row["Target2"]),
                "Exit": row["Exit"],
            }
            for row in pop_results
        ])
        st.dataframe(
            scanner_display,
            use_container_width=True,
            hide_index=True,
            height=min(360, 58 + len(scanner_display) * 52),
        )
    elif "fno_pop_results" in st.session_state:
        st.info("No F&O stock currently has an option trade with PoP > 75%.")

    st.divider()
    st.markdown("### 🔎 Analyze Instrument")

    symbol_input = st.text_input(
        "Stock / Index",
        value=st.session_state.get("symbol", "KOTAKBANK"),
        placeholder="e.g. KOTAKBANK, HDFCBANK, NIFTY",
        label_visibility="collapsed",
    )

    risk_profile = st.selectbox(
        "Risk Profile",
        ["Conservative", "Balanced", "Aggressive"],
        index=1,
    )

    analyze = st.button(
        "🔍 Analyze",
        type="primary",
        use_container_width=True,
    )

    refresh = st.button(
        "↻ Refresh Live Data",
        use_container_width=True,
    )

    if st_autorefresh is not None:
        auto_refresh = st.checkbox(
            "Auto refresh every 30 seconds",
            value=True,
        )
        if auto_refresh:
            st_autorefresh(interval=30_000, key="upstox_live_refresh")

    st.divider()
    st.caption("LIVE DATA • Powered by Upstox")
    st.caption("No simulated market values are used.")

if analyze:
    st.session_state["symbol"] = alias_symbol(symbol_input)
    st.rerun()

if refresh:
    st.cache_data.clear()
    st.rerun()

symbol = alias_symbol(
    st.session_state.get("symbol", symbol_input or "KOTAKBANK")
)

# ============================================================
# LIVE DATA + MULTI-TIMEFRAME ENGINE
# ============================================================
try:
    with st.spinner(f"Fetching live Upstox data for {symbol}..."):
        underlying=search_underlying(symbol); underlying_key=underlying["instrument_key"]
        contracts=get_contracts(underlying_key); expiries=available_expiries(contracts)
        if not expiries: raise UpstoxError("Upstox did not return an upcoming F&O expiry for this instrument.")
        selected_expiry=expiries[0]
        raw_chain=get_option_chain(underlying_key,selected_expiry); chain=normalize_chain(raw_chain)
        quote_data=get_quote(underlying_key)
        spot=safe_float(quote_data.get("last_price"))
        previous_close=safe_float(quote_data.get("prev_close_price"),spot)
        net_change=safe_float(quote_data.get("net_change"),spot-previous_close)
        change_pct=net_change/previous_close*100 if previous_close else 0
        if not np.isfinite(spot): raise UpstoxError("Upstox did not return a valid live price.")
        intraday5=get_intraday_candles(underlying_key,5)
        candles30=get_30min_candles(underlying_key)
        daily=get_daily_candles(underlying_key)
        tf5=technicals(intraday5,spot,"5-min")
        tf30=technicals(candles30,spot,"30-min")
        tfd=technicals(daily,spot,"Daily")
        overall,bias_alignment=overall_trend(tf5,tf30,tfd)
        support,resistance,pcr,walls=oi_levels(chain,spot)
except UpstoxError as exc:
    st.error(str(exc)); st.stop()
except Exception as exc:
    st.error(f"Unexpected error while loading live data: {exc}"); st.stop()

atm_index=(chain["Strike"]-spot).abs().idxmin(); atm_strike=float(chain.loc[atm_index,"Strike"])
candidate_rows=chain.iloc[max(0,atm_index-4):min(len(chain),atm_index+5)]
candidates=[]
for _,row in candidate_rows.iterrows():
    for side in ("CE","PE"):
        p=build_plan(row,side,spot,support,resistance,pcr,tf5,tf30,tfd,risk_profile,chain)
        if p: candidates.append(p)
candidates.sort(key=lambda x:x["score"],reverse=True)
best_ce=max([x for x in candidates if x["side"]=="CE"],key=lambda x:x["score"],default=None)
best_pe=max([x for x in candidates if x["side"]=="PE"],key=lambda x:x["score"],default=None)
best=best_ce if overall=="Bullish" else best_pe if overall=="Bearish" else candidates[0] if candidates else None
if best is None or best["readiness"]=="NO TRADE": decision="NO TRADE"; decision_class="trade-neutral"
elif best["readiness"]=="WAIT FOR TRIGGER": decision=("CALL BUY — WAIT FOR TRIGGER" if best["side"]=="CE" else "PUT BUY — WAIT FOR TRIGGER"); decision_class="trade-call" if best["side"]=="CE" else "trade-put"
else: decision="CALL BUY" if best["side"]=="CE" else "PUT BUY"; decision_class="trade-call" if best["side"]=="CE" else "trade-put"
updated = quote_data.get(
    "timestamp",
    datetime.now().astimezone().isoformat(),
)

# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
<div class="topbar">
    <div class="topbar-title">📊 FO PRO Trader Assistant</div>
    <div class="topbar-sub">
        Options Analysis • Powered by Upstox • Live market data
    </div>
</div>
""",
    unsafe_allow_html=True,
)

h1, h2, h3 = st.columns([2.2, 1.2, 1.0])

with h1:
    st.markdown(f"## {symbol} — F&O Options Analysis")

with h2:
    st.markdown("**Last Traded**")
    st.markdown(
        f"<span style='font-size:25px;font-weight:800'>{fmt_price(spot)}</span>",
        unsafe_allow_html=True,
    )
    st.caption(f"{net_change:+.2f} ({change_pct:+.2f}%)")

with h3:
    st.markdown("**Data Status**")
    market_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    market_open = (
        market_now.weekday() < 5
        and (market_now.hour, market_now.minute) >= (9, 15)
        and (market_now.hour, market_now.minute) < (15, 30)
    )
    if market_open:
        st.markdown("**● LIVE DATA**")
    else:
        st.markdown("**● MARKET CLOSED**")
    st.caption(f"Expiry: {selected_expiry}")

# ============================================================
# MARKET SNAPSHOT
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(
    '<div class="section-title">📊 Market Snapshot</div>',
    unsafe_allow_html=True,
)

m1, m2, m3, m4, m5, m6, m7 = st.columns(7)

m1.metric(
    "Live Price",
    fmt_price(spot),
    f"{net_change:+.2f} ({change_pct:+.2f}%)",
)

m2.metric("Bias", overall)
m3.metric(
    "PCR",
    f"{pcr:.2f}" if not np.isnan(pcr) else "—",
)
m4.metric("Support", fmt_price(support))
m5.metric("Resistance", fmt_price(resistance))
m6.metric("5m RSI", f"{tf5['rsi']:.1f}")
m7.metric("Trend Align", f"{bias_alignment}/3")

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TRADE DECISION
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)

st.markdown(
    '<div class="section-title">🎯 Trade Decision</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="{decision_class}">Decision: {decision}</div>',
    unsafe_allow_html=True,
)

d1, d2, d3, d4, d5, d6 = st.columns(6)
d1.metric("Setup Score", f"{best['score']:.0f}/100" if best else "—")
d2.metric("Upstox PoP", f"{best['pop']:.1f}%" if best and np.isfinite(best['pop']) else "—")
d3.metric("Trend", overall)
d4.metric("5m RSI", f"{tf5['rsi']:.1f}")
d5.metric("R:R T1", f"1:{best['rr1']:.2f}" if best else "—")
d6.metric("TF Align", f"{best['alignment']}/3" if best else "—")

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TRADE PLAN
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)

st.markdown(
    '<div class="section-title">🎯 Trade Plan</div>',
    unsafe_allow_html=True,
)

if best:
    st.markdown(f"### {best['side'] == 'CE' and 'CALL BUY' or 'PUT BUY'} • Strike {best['strike']:.0f} • Setup Score {best['score']:.0f}/100")
    cols=st.columns(7)
    cols[0].metric("Current Premium",fmt_price(best["current_premium"]))
    cols[1].metric("Trigger",fmt_price(best["trigger_price"]))
    cols[2].metric("Stop Loss",fmt_price(best["sl"]))
    cols[3].metric("Target 1",fmt_price(best["target1"]))
    cols[4].metric("Target 2",fmt_price(best["target2"]))
    cols[5].metric("PoP",f"{best['pop']:.1f}%" if np.isfinite(best["pop"]) else "—")
    cols[6].metric("R:R T1",f"1:{best['rr1']:.2f}")
    if best["readiness"]=="READY": st.success("🟢 ENTRY TRIGGER ACTIVE — verify live bid/ask before execution.")
    elif best["readiness"]=="WAIT FOR TRIGGER": st.warning("🟡 WAIT FOR TRIGGER. The current premium is NOT the future trigger-entry premium; recalculate after the trigger occurs.")
    else: st.info("⚪ NO TRADE — setup quality or confirmation is insufficient.")
    e1,e2=st.columns(2)
    with e1:
        st.markdown("**Entry Trigger**"); st.write(best["trigger"])
        st.markdown("**Current premium**"); st.write(fmt_price(best["current_premium"]))
        st.markdown("**Stop Loss**"); st.write(fmt_price(best["sl"]))
        st.markdown("**Target 1 / Target 2**"); st.write(f"{fmt_price(best['target1'])} / {fmt_price(best['target2'])}")
    with e2:
        st.markdown("**Exit Rule**"); st.write(best["exit"])
        st.markdown("**Risk / Reward**"); st.write(f"Target 1: 1:{best['rr1']:.2f} | Target 2: 1:{best['rr2']:.2f}")
        st.markdown("**Option Greeks**"); st.write(f"Delta {best['delta']:.3f} | Gamma {best['gamma']:.5f} | Theta {best['theta']:.3f} | Vega {best['vega']:.3f}")
    st.markdown("### ⚠ Risk checks")
    risks=[]
    if best["trigger_price"] and np.isfinite(best["trigger_price"]):
        dist=abs(best["trigger_price"]-spot)/max(spot,1)*100
        if dist>3: risks.append(f"Trigger is {dist:.1f}% away from current spot.")
    if np.isfinite(best["iv_rank"]) and best["iv_rank"]>80: risks.append("IV is high relative to the current expiry chain.")
    if np.isfinite(best["spread"]) and best["spread"]>2: risks.append(f"Bid/ask spread is {best['spread']:.1f}%.")
    if np.isfinite(best["theta"]) and abs(best["theta"])>1: risks.append("Theta decay is material; option buyers need timely movement.")
    if not risks: risks.append("No major automated flag beyond normal option-trading risk.")
    for r in risks: st.write("⚠",r)
else:
    st.info("No valid option candidate was found in the near-ATM range.")
st.caption("Upstox PoP is an option-model input, not the historical win probability of this complete strategy. Entry/SL/targets are engine-derived levels and are not guaranteed executions.")

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🏆 Best Trade",
        "🔎 Live Option Chain",
        "📊 Market Analysis",
        "🧠 How Engine Thinks",
    ]
)

with tab1:
    if best:
        if best["readiness"]=="READY": st.success(f"{decision} | Strike {best['strike']:.0f} | Setup Score {best['score']:.0f}/100")
        elif best["readiness"]=="WAIT FOR TRIGGER": st.warning(f"{decision} — WAIT FOR TRIGGER | Strike {best['strike']:.0f} | Score {best['score']:.0f}/100")
        else: st.info("NO TRADE")
        st.markdown("### Why the Engine Says This")
        st.write(f"✓ 5m trend: {tf5['trend']} | 30m trend: {tf30['trend']} | Daily trend: {tfd['trend']}.")
        st.write(f"✓ {best['alignment']}/3 major timeframes align with the selected direction.")
        st.write(f"✓ Live spot is {fmt_price(spot)}; ATM strike is {atm_strike:.0f}.")
        st.write(f"✓ PCR is {pcr:.2f}." if np.isfinite(pcr) else "✓ PCR unavailable.")
        st.write(f"✓ OI support is {fmt_price(support)} and resistance is {fmt_price(resistance)}.")
        st.write(f"✓ Selected option PoP from Upstox is {best['pop']:.1f}%." if np.isfinite(best['pop']) else "✓ Upstox PoP unavailable.")
        if np.isfinite(best['spread']): st.write(f"✓ Bid/ask spread is approximately {best['spread']:.1f}%.")
        if np.isfinite(best['iv_rank']): st.write(f"✓ Current-expiry IV percentile across strikes is {best['iv_rank']:.0f}th percentile.")
        if best["failures"]:
            for f in best["failures"]: st.write("⚠",f)
    else:
        st.info("No candidate setup.")

with tab2:
    st.markdown(
        f"### Live Option Chain — {selected_expiry}"
    )

    view = chain.copy()

    display = pd.DataFrame(
        {
            "Strike": view["Strike"].round(0).astype(int),
            "CE LTP": view["CE LTP"].round(2),
            "CE OI": view["CE OI"].round(0).astype("int64"),
            "CE Chg OI": view["CE Chg OI"].round(0).astype("int64"),
            "CE IV": view["CE IV"].round(1),
            "CE Delta": view["CE Delta"].round(3),
            "CE Gamma": view["CE Gamma"].round(5),
            "CE Theta": view["CE Theta"].round(3),
            "CE Vega": view["CE Vega"].round(3),
            "CE PoP": view["CE PoP"].round(1),
            "PE LTP": view["PE LTP"].round(2),
            "PE OI": view["PE OI"].round(0).astype("int64"),
            "PE Chg OI": view["PE Chg OI"].round(0).astype("int64"),
            "PE IV": view["PE IV"].round(1),
            "PE Delta": view["PE Delta"].round(3),
            "PE Gamma": view["PE Gamma"].round(5),
            "PE Theta": view["PE Theta"].round(3),
            "PE Vega": view["PE Vega"].round(3),
            "PE PoP": view["PE PoP"].round(1),
        }
    )

    display["_distance"] = (
        display["Strike"] - spot
    ).abs()

    display = (
        display
        .sort_values("_distance")
        .drop(columns="_distance")
        .head(11)
    )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )

with tab3:
    a1,a2,a3,a4,a5,a6=st.columns(6)
    a1.metric("5m RSI",f"{tf5['rsi']:.1f}"); a2.metric("30m RSI",f"{tf30['rsi']:.1f}"); a3.metric("Daily RSI",f"{tfd['rsi']:.1f}")
    a4.metric("5m ATR",fmt_price(tf5["atr"])); a5.metric("30m ATR",fmt_price(tf30["atr"])); a6.metric("Daily ATR",fmt_price(tfd["atr"]))
    st.markdown("### 🕒 Multi-timeframe price confirmation")
    tf_display=pd.DataFrame([
        {"Timeframe":"5 min","Trend":tf5["trend"],"RSI":round(tf5["rsi"],1),"EMA20":fmt_price(tf5["ema20"]),"EMA50":fmt_price(tf5["ema50"]),"Momentum":f"{tf5['momentum']:+.2f}%"},
        {"Timeframe":"30 min","Trend":tf30["trend"],"RSI":round(tf30["rsi"],1),"EMA20":fmt_price(tf30["ema20"]),"EMA50":fmt_price(tf30["ema50"]),"Momentum":f"{tf30['momentum']:+.2f}%"},
        {"Timeframe":"Daily","Trend":tfd["trend"],"RSI":round(tfd["rsi"],1),"EMA20":fmt_price(tfd["ema20"]),"EMA50":fmt_price(tfd["ema50"]),"Momentum":f"{tfd['momentum']:+.2f}%"},
    ])
    st.dataframe(tf_display,use_container_width=True,hide_index=True)
    left,right=st.columns(2)
    with left:
        st.markdown("### 🟢 Put OI / Support")
        st.write(f"Major support: **{fmt_price(support)}**")
        sr=nearest_row(chain,support)
        if sr is not None: st.write(f"Put OI: **{fmt_num(sr['PE OI'])}** | Chg OI: **{fmt_num(sr['PE Chg OI'])}**")
        st.dataframe(walls["put_walls"],use_container_width=True,hide_index=True)
    with right:
        st.markdown("### 🔴 Call OI / Resistance")
        st.write(f"Major resistance: **{fmt_price(resistance)}**")
        rr=nearest_row(chain,resistance)
        if rr is not None: st.write(f"Call OI: **{fmt_num(rr['CE OI'])}** | Chg OI: **{fmt_num(rr['CE Chg OI'])}**")
        st.dataframe(walls["call_walls"],use_container_width=True,hide_index=True)
    if not intraday5.empty:
        st.markdown("### 5-minute price")
        st.line_chart(intraday5.set_index("timestamp")[["close"]].tail(150),use_container_width=True)
    if not daily.empty:
        st.markdown("### Daily price")
        st.line_chart(daily.set_index("timestamp")[["close"]].tail(120),use_container_width=True)

with tab4:
    st.markdown("""
### 🧠 How the improved engine thinks

**1. Direction**
- 5-minute, 30-minute and Daily trend
- RSI, EMA20/EMA50, ATR and momentum
- At least 2 of 3 timeframes should align for a high-quality setup

**2. Option-chain structure**
- Put OI / Change in OI
- Call OI / Change in OI
- PCR
- Nearby OI walls for support/resistance

**3. Option quality**
- Upstox PoP
- Delta
- IV
- Gamma / Theta / Vega
- Volume
- Bid/ask spread
- Distance from ATM

**4. Setup Score — 0 to 100**
The score combines the above factors. It is a **setup-quality score**, not a probability.

**5. Entry discipline**
The app now separates **Current Premium** from the **Underlying Trigger**. If the trigger has not happened, the result is **WAIT FOR TRIGGER** and the premium must be recalculated after the trigger.

**6. NO TRADE**
The engine can reject the setup when timeframes conflict, score is weak, liquidity is poor, spread is wide, or the trigger/option quality is insufficient.

**7. Scanner**
The Top 5 scanner is no longer ranked by PoP alone. It uses PoP as one input and ranks by Setup Score, with the PoP threshold still acting as a minimum filter.

### What is NOT claimed
- Upstox PoP is not the historical win rate of this strategy.
- No fake backtest results are displayed.
- OI is not treated as a guarantee.
- No guaranteed profit is claimed.
""")


st.divider()

st.caption(
    f"Live Upstox snapshot • {symbol} • Expiry {selected_expiry} • "
    f"Updated {updated}. "
    "For educational/decision-support use; review live market conditions before trading."
)
