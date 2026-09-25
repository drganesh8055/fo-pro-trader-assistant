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
    """Normalize common index aliases while preserving company-name input."""
    raw = str(symbol or "").strip().upper()
    compact = "".join(ch for ch in raw if ch.isalnum())

    aliases = {
        "NIFTY50": "NIFTY",
        "NIFTYBANK": "BANKNIFTY",
        "NIFTYFIN": "FINNIFTY",
        "MIDCAPNIFTY": "MIDCPNIFTY",

        # Common company-name inputs -> NSE F&O trading symbols.
        # Upstox instrument search is not guaranteed to resolve a fully
        # concatenated company name such as KAYNESTECHNOLOGIES, so normalize
        # these to the actual NSE underlying before querying the API.
        "KAYNESTECHNOLOGIES": "KAYNES",
        "KAYNESTECHNOLOGY": "KAYNES",
        "KAYNESTECHNOLOGYINDIALTD": "KAYNES",
        "KAYNESTECHNOLOGIESINDIALTD": "KAYNES",
    }
    return aliases.get(compact, raw)


def _search_queries_for_symbol(symbol):
    """Build safe Upstox search variants so users need not know the exact NSE symbol."""
    raw = str(symbol or "").strip().upper()
    compact = "".join(ch for ch in raw if ch.isalnum())

    queries = []
    for value in (raw, compact):
        if value and value not in queries:
            queries.append(value[:50])

    # Upstox supports partial matching. For company-name input such as
    # KAYNESTECHNOLOGIES, searching the distinctive leading token KAYNES
    # can resolve the NSE trading symbol KAYNES.
    if len(compact) >= 6:
        for n in (10, 8, 6):
            prefix = compact[:n]
            if prefix not in queries:
                queries.append(prefix)

    # Common long company-name pattern: also try the first alphabetic word.
    words = [w for w in raw.replace("-", " ").split() if w]
    if words:
        first_word = "".join(ch for ch in words[0] if ch.isalnum())
        if len(first_word) >= 4 and first_word not in queries:
            queries.append(first_word[:50])

    return queries


def _instrument_rank(item, user_input):
    """Rank likely underlying matches without changing the existing UI."""
    user_raw = str(user_input or "").strip().upper()
    user_compact = "".join(ch for ch in user_raw if ch.isalnum())

    trading = str(item.get("trading_symbol") or "").upper()
    short_name = str(item.get("short_name") or "").upper()
    name = str(item.get("name") or "").upper()
    underlying = str(item.get("underlying_symbol") or "").upper()

    def compact(v):
        return "".join(ch for ch in v if ch.isalnum())

    tc, sc, nc, uc = map(compact, (trading, short_name, name, underlying))

    score = 0
    if tc == user_compact or uc == user_compact:
        score += 1000
    if tc.startswith(user_compact) or uc.startswith(user_compact):
        score += 500
    if user_compact and user_compact in tc:
        score += 350
    if user_compact and user_compact in sc:
        score += 300
    if user_compact and user_compact in nc:
        score += 250

    # Prefer a clean NSE equity/index underlying over an individual option/future.
    segment = str(item.get("segment") or "")
    if segment == "NSE_EQ":
        score += 100
    elif segment == "NSE_INDEX":
        score += 100
    elif segment == "NSE_FO":
        score += 50

    return score


@st.cache_data(ttl=60, show_spinner=False)
def search_underlying(symbol):
    """Resolve an NSE F&O underlying from a trading symbol or company name.

    Upstox Instrument Search supports case-insensitive partial matching on
    symbol, name and short_name.  We deliberately search both NSE_EQ/NSE_INDEX
    and NSE_FO so inputs such as KAYNES, KAYNESTECHNOLOGIES and
    KAYNES TECHNOLOGY INDIA LTD can resolve to the underlying KAYNES.
    """
    original_input = str(symbol or "").strip()
    normalized = alias_symbol(original_input)

    if not original_input:
        raise UpstoxError(
            "Please enter an NSE F&O stock symbol or company name, such as HDFCBANK, KAYNES or NIFTY."
        )

    queries = _search_queries_for_symbol(normalized)
    all_equity = []
    fno_items = []

    def compact(value):
        return "".join(ch for ch in str(value or "").upper() if ch.isalnum())

    target = compact(normalized)

    def item_fields(item):
        return [
            compact(item.get("trading_symbol")),
            compact(item.get("short_name")),
            compact(item.get("name")),
            compact(item.get("underlying_symbol")),
        ]

    def rank_item(item, query):
        """Rank a result against the actual search query used for that result."""
        q = compact(query)
        fields = item_fields(item)
        score = 0

        if not q:
            return -1

        for field in fields:
            if not field:
                continue
            if field == q:
                score = max(score, 1000)
            elif field.startswith(q):
                score = max(score, 800)
            elif q in field:
                score = max(score, 650)
            elif field in q and len(field) >= 4:
                score = max(score, 550)

        segment = str(item.get("segment") or "")
        if segment in {"NSE_EQ", "NSE_INDEX"}:
            score += 100
        elif segment == "NSE_FO":
            score += 25
        return score

    def exact_target_match(items):
        matches = []
        for item in items:
            fields = item_fields(item)
            if target and target in fields:
                matches.append(item)
        return matches

    # ------------------------------------------------------------
    # 1. Search the actual NSE equity/index underlying first.
    # ------------------------------------------------------------
    for query in queries:
        for segment in ("EQ", "INDEX"):
            try:
                payload = api_get(
                    "/v2/instruments/search",
                    params={
                        "query": query,
                        "exchanges": "NSE",
                        "segments": segment,
                        "page_number": 1,
                        "records": 30,
                    },
                )
            except UpstoxError:
                continue

            items = payload.get("data", []) or []
            all_equity.extend(items)

            # Exact symbol/name match always wins.
            exact = exact_target_match(items)
            if exact:
                return sorted(
                    exact,
                    key=lambda x: rank_item(x, normalized),
                    reverse=True,
                )[0]

    # If no exact match was found, rank the equity/index results using the
    # search variants.  This handles company-name input without requiring the
    # user to know the NSE trading symbol.
    ranked_equity = []
    seen = set()
    for item in all_equity:
        key = item.get("instrument_key")
        if not key or key in seen:
            continue
        seen.add(key)
        best_score = max((rank_item(item, q) for q in queries), default=-1)
        if best_score > 100:
            ranked_equity.append((best_score, item))

    if ranked_equity:
        ranked_equity.sort(key=lambda x: x[0], reverse=True)
        return ranked_equity[0][1]

    # ------------------------------------------------------------
    # 2. Search NSE F&O as a second resolver.
    # ------------------------------------------------------------
    # F&O results contain underlying_key and underlying_symbol.  We map the
    # best matching F&O result back to the NSE equity/index underlying required
    # by the rest of the application.
    fno_by_underlying = {}
    for query in queries:
        try:
            payload = api_get(
                "/v2/instruments/search",
                params={
                    "query": query,
                    "exchanges": "NSE",
                    "segments": "FO",
                    "page_number": 1,
                    "records": 30,
                },
            )
        except UpstoxError:
            continue

        for item in payload.get("data", []) or []:
            if item.get("segment") != "NSE_FO":
                continue
            underlying_key = item.get("underlying_key")
            if not underlying_key:
                continue

            score = rank_item(item, query)
            current = fno_by_underlying.get(underlying_key)
            if current is None or score > current["score"]:
                fno_by_underlying[underlying_key] = {
                    "score": score,
                    "item": item,
                }

    if fno_by_underlying:
        candidates = []
        for data in fno_by_underlying.values():
            item = data["item"]
            score = data["score"]
            underlying_key = item.get("underlying_key")
            underlying_symbol = str(item.get("underlying_symbol") or "").strip().upper()
            if not underlying_key or not underlying_symbol:
                continue

            candidates.append(
                (
                    score,
                    {
                        "name": item.get("name", ""),
                        "segment": (
                            "NSE_EQ"
                            if item.get("underlying_type") == "EQUITY"
                            else "NSE_INDEX"
                        ),
                        "exchange": "NSE",
                        "instrument_key": underlying_key,
                        "trading_symbol": underlying_symbol,
                        "short_name": item.get("name", ""),
                        "underlying_symbol": underlying_symbol,
                    },
                )
            )

        candidates.sort(key=lambda x: x[0], reverse=True)
        if candidates and candidates[0][0] > 25:
            return candidates[0][1]

    raise UpstoxError(
        f"No NSE F&O instrument found for '{original_input}'. "
        "Enter an NSE F&O symbol such as KAYNES or HDFCBANK, "
        "or a company name such as Kaynes Technology."
    )


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



@st.cache_data(ttl=60, show_spinner=False)
def get_intraday_candles(instrument_key, interval=5):
    """Current-session intraday candles used for entry timing."""
    path = (
        f"/v3/historical-candle/intraday/{quote(instrument_key, safe='')}"
        f"/minutes/{interval}"
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


@st.cache_data(ttl=180, show_spinner=False)
def get_30m_candles(instrument_key):
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
    start_date = end_date - timedelta(days=220)
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


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def technicals(df, spot):
    """Trend/volatility features for one timeframe."""
    if df.empty or len(df) < 20:
        return {
            "rsi": 50.0, "ema20": spot, "ema50": spot, "atr": spot * 0.01,
            "trend": "Unavailable", "adx": 0.0, "momentum": 0.0,
            "volume_ratio": 1.0, "vwap": spot
        }

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].fillna(0).astype(float)

    rsi = _rsi(close)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    prev_close = close.shift(1)
    tr = pd.concat(
        [(high-low), (high-prev_close).abs(), (low-prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1/14, adjust=False).mean()

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index
    )
    atr_safe = atr.replace(0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe
    minus_di = 100 * minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr_safe
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/14, adjust=False).mean()

    typical = (high + low + close) / 3
    if volume.sum() > 0:
        vwap = (typical * volume).cumsum() / volume.cumsum().replace(0, np.nan)
        latest_vwap = safe_float(vwap.iloc[-1], spot)
    else:
        latest_vwap = spot

    lookback = min(10, len(close)-1)
    momentum = (
        (close.iloc[-1] / close.iloc[-1-lookback] - 1) * 100
        if lookback > 0 and close.iloc[-1-lookback] else 0.0
    )
    vol_base = volume.rolling(20).median().iloc[-1]
    volume_ratio = volume.iloc[-1] / vol_base if vol_base and np.isfinite(vol_base) else 1.0

    e20 = safe_float(ema20.iloc[-1], spot)
    e50 = safe_float(ema50.iloc[-1], spot)
    r = safe_float(rsi.iloc[-1], 50.0)
    a = safe_float(atr.iloc[-1], spot * 0.01)
    adx_v = safe_float(adx.iloc[-1], 0.0)

    bullish = spot > e20 > e50
    bearish = spot < e20 < e50

    if bullish:
        trend = "Bullish"
    elif bearish:
        trend = "Bearish"
    else:
        trend = "Sideways"

    return {
        "rsi": r, "ema20": e20, "ema50": e50, "atr": max(a, spot*0.001),
        "trend": trend, "adx": adx_v, "momentum": momentum,
        "volume_ratio": volume_ratio, "vwap": latest_vwap
    }


def overall_trend(tf5, tf30, daily):
    trends = [tf5.get("trend"), tf30.get("trend"), daily.get("trend")]
    bullish = trends.count("Bullish")
    bearish = trends.count("Bearish")
    if bullish >= 2 and bearish == 0:
        return "Bullish", bullish
    if bearish >= 2 and bullish == 0:
        return "Bearish", bearish
    return "Mixed", max(bullish, bearish)


def timeframe_score(side, tf5, tf30, daily):
    desired = "Bullish" if side == "CE" else "Bearish"
    opposite = "Bearish" if side == "CE" else "Bullish"
    values = [tf5, tf30, daily]
    score = 0
    alignment = 0
    for tf in values:
        if tf.get("trend") == desired:
            score += 10
            alignment += 1
        elif tf.get("trend") == "Sideways":
            score += 3
        elif tf.get("trend") == opposite:
            score -= 8
    return float(np.clip(score, 0, 30)), alignment


def oi_levels(chain, spot):
    valid = chain.dropna(subset=["Strike"]).copy()
    if valid.empty:
        return spot, spot, np.nan, {"put_walls": [], "call_walls": []}

    # Do not allow a distant strike to become a misleading support/resistance.
    band = valid[
        (valid["Strike"] >= spot * 0.90) &
        (valid["Strike"] <= spot * 1.10)
    ].copy()
    if band.empty:
        band = valid

    below = band[band["Strike"] <= spot]
    above = band[band["Strike"] >= spot]

    support_row = (
        below.loc[below["PE OI"].fillna(0).idxmax()]
        if not below.empty else band.loc[band["PE OI"].fillna(0).idxmax()]
    )
    resistance_row = (
        above.loc[above["CE OI"].fillna(0).idxmax()]
        if not above.empty else band.loc[band["CE OI"].fillna(0).idxmax()]
    )

    total_call_oi = band["CE OI"].fillna(0).sum()
    total_put_oi = band["PE OI"].fillna(0).sum()
    pcr = total_put_oi / total_call_oi if total_call_oi else np.nan

    put_walls = band.nlargest(3, "PE OI")[["Strike", "PE OI", "PE Chg OI"]].to_dict("records")
    call_walls = band.nlargest(3, "CE OI")[["Strike", "CE OI", "CE Chg OI"]].to_dict("records")

    return (
        float(support_row["Strike"]),
        float(resistance_row["Strike"]),
        pcr,
        {"put_walls": put_walls, "call_walls": call_walls},
    )


def nearest_row(chain, strike):
    if chain.empty:
        return None
    index = (chain["Strike"] - strike).abs().idxmin()
    return chain.loc[index]

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
                "PE PoP": safe_float(put_greeks.get("pop")),
            }
        )

    return pd.DataFrame(records).sort_values("Strike").reset_index(drop=True)


def oi_levels(chain, spot):
    valid = chain.dropna(subset=["Strike"]).copy()

    below = valid[valid["Strike"] <= spot]
    above = valid[valid["Strike"] >= spot]

    support_row = (
        below.loc[below["PE OI"].idxmax()]
        if not below.empty
        else valid.loc[valid["PE OI"].idxmax()]
    )

    resistance_row = (
        above.loc[above["CE OI"].idxmax()]
        if not above.empty
        else valid.loc[valid["CE OI"].idxmax()]
    )

    total_call_oi = valid["CE OI"].sum()
    total_put_oi = valid["PE OI"].sum()
    pcr = total_put_oi / total_call_oi if total_call_oi else np.nan

    return (
        float(support_row["Strike"]),
        float(resistance_row["Strike"]),
        pcr,
    )


def nearest_row(chain, strike):
    if chain.empty:
        return None
    index = (chain["Strike"] - strike).abs().idxmin()
    return chain.loc[index]


def score_option(row, side, spot, pcr, tf5, tf30, daily, chain):
    """Conservative 100-point option-quality score.

    This is a decision-support score, not a statistical probability of winning.
    """
    if side == "CE":
        premium = safe_float(row["CE LTP"])
        delta = safe_float(row["CE Delta"])
        iv = safe_float(row["CE IV"])
        pop = safe_float(row["CE PoP"])
        chg_oi = safe_float(row["CE Chg OI"], 0)
        volume = safe_float(row["CE Volume"], 0)
        bid = safe_float(row["CE Bid"])
        ask = safe_float(row["CE Ask"])
    else:
        premium = safe_float(row["PE LTP"])
        delta = safe_float(row["PE Delta"])
        iv = safe_float(row["PE IV"])
        pop = safe_float(row["PE PoP"])
        chg_oi = safe_float(row["PE Chg OI"], 0)
        volume = safe_float(row["PE Volume"], 0)
        bid = safe_float(row["PE Bid"])
        ask = safe_float(row["PE Ask"])

    desired = "Bullish" if side == "CE" else "Bearish"
    opposite = "Bearish" if side == "CE" else "Bullish"

    # 30 points: multi-timeframe agreement.
    tf_points, alignment = timeframe_score(side, tf5, tf30, daily)

    # 15 points: price/momentum confirmation.
    tf = tf5
    momentum_points = 0
    if tf.get("trend") == desired:
        momentum_points += 6
    if tf.get("rsi", 50) >= 52 and side == "CE":
        momentum_points += 3
    if tf.get("rsi", 50) <= 48 and side == "PE":
        momentum_points += 3
    if side == "CE" and tf.get("momentum", 0) > 0:
        momentum_points += 3
    if side == "PE" and tf.get("momentum", 0) < 0:
        momentum_points += 3
    if tf.get("adx", 0) >= 20:
        momentum_points += 3
    momentum_points = min(momentum_points, 15)

    # 15 points: PCR is confirmation only, never the main signal.
    pcr_points = 0
    if np.isfinite(pcr):
        if side == "CE":
            pcr_points = 7 if 0.90 <= pcr <= 1.35 else 3 if 0.75 <= pcr < 0.90 else 0
        else:
            pcr_points = 7 if 0.65 <= pcr <= 1.10 else 3 if 1.10 < pcr <= 1.30 else 0

    # OI change is deliberately a small component because this endpoint exposes
    # current OI versus previous OI, not a full intraday OI history.
    if side == "CE":
        oi_points = 4 if chg_oi <= 0 else 2
    else:
        oi_points = 4 if chg_oi <= 0 else 2

    # Option quality: 25 points.
    quality = 0
    abs_delta = abs(delta) if np.isfinite(delta) else np.nan
    if np.isfinite(abs_delta):
        if 0.45 <= abs_delta <= 0.70:
            quality += 8
        elif 0.35 <= abs_delta < 0.45 or 0.70 < abs_delta <= 0.80:
            quality += 5

    spread_pct = (
        max(ask - bid, 0) / max((ask + bid) / 2, 0.01) * 100
        if np.isfinite(ask) and np.isfinite(bid) and ask > 0 and bid > 0
        else 999
    )
    if spread_pct <= 1.5:
        quality += 6
    elif spread_pct <= 2.5:
        quality += 4
    elif spread_pct <= 4:
        quality += 2

    if volume > 0:
        quality += 4
    if np.isfinite(iv):
        iv_values = chain[f"{side} IV"].replace([np.inf, -np.inf], np.nan).dropna()
        if len(iv_values) >= 5:
            iv_rank = float((iv_values <= iv).mean())
            if 0.15 <= iv_rank <= 0.75:
                quality += 4
            elif iv_rank < 0.90:
                quality += 2
        else:
            quality += 2

    # Near-ATM strikes are preferred; avoid deep OTM lottery tickets.
    distance_pct = abs(float(row["Strike"]) - spot) / max(spot, 1)
    if distance_pct <= 0.015:
        distance_points = 5
    elif distance_pct <= 0.03:
        distance_points = 3
    else:
        distance_points = 0

    pop_points = (
        float(np.clip((pop - 50) / 2.5, 0, 10))
        if np.isfinite(pop) else 0
    )

    score = float(np.clip(
        tf_points + momentum_points + pcr_points + oi_points +
        quality + distance_points + pop_points,
        0, 100
    ))

    return {
        "score": score,
        "premium": premium,
        "delta": delta,
        "iv": iv,
        "pop": pop,
        "chg_oi": chg_oi,
        "volume": volume,
        "spread_pct": spread_pct,
        "alignment": alignment,
        "distance_pct": distance_pct,
        "quality": quality,
    }


def build_plan(row, side, spot, support, resistance, pcr, tf5, tf30, daily,
               risk_profile, chain):
    if row is None:
        return None

    scored = score_option(row, side, spot, pcr, tf5, tf30, daily, chain)

    ask = safe_float(row[f"{side} Ask"])
    ltp = safe_float(row[f"{side} LTP"])
    entry = ask if np.isfinite(ask) and ask > 0 else ltp
    if not np.isfinite(entry) or entry <= 0:
        return None

    # Conservative premium-risk model. Underlying invalidation remains the
    # primary exit condition; premium SL is a secondary protection.
    risk_settings = {
        "Conservative": (0.72, 1.25, 1.55),
        "Balanced": (0.70, 1.35, 1.75),
        "Aggressive": (0.65, 1.50, 2.00),
    }
    sl_factor, target1_factor, target2_factor = risk_settings[risk_profile]
    sl = round(entry * sl_factor, 2)
    target1 = round(entry * target1_factor, 2)
    target2 = round(entry * target2_factor, 2)
    rr1 = (target1 - entry) / max(entry - sl, 0.01)
    rr2 = (target2 - entry) / max(entry - sl, 0.01)

    atr = max(tf5.get("atr", spot*0.01), spot*0.001)
    trigger_buffer = max(atr * 0.15, spot * 0.0015)

    if side == "CE":
        trigger_level = resistance + trigger_buffer
        trigger_hit = spot >= trigger_level
        trigger = (
            f"Enter only after spot breaks and sustains above "
            f"{fmt_price(trigger_level)}."
        )
        exit_rule = (
            f"Exit if spot loses support {fmt_price(support)} or premium hits "
            f"{fmt_price(sl)}. After Target 1, book partial profit and trail."
        )
    else:
        trigger_level = support - trigger_buffer
        trigger_hit = spot <= trigger_level
        trigger = (
            f"Enter only after spot breaks and sustains below "
            f"{fmt_price(trigger_level)}."
        )
        exit_rule = (
            f"Exit if spot reclaims resistance {fmt_price(resistance)} or premium "
            f"hits {fmt_price(sl)}. After Target 1, book partial profit and trail."
        )

    desired = "Bullish" if side == "CE" else "Bearish"
    opposite = "Bearish" if side == "CE" else "Bullish"

    # Hard quality gates intentionally bias toward NO TRADE.
    hard_fail = []
    if scored["score"] < 72:
        hard_fail.append("setup score below 72")
    if scored["alignment"] < 2:
        hard_fail.append("fewer than 2 aligned timeframes")
    if tf5.get("trend") == opposite or tf30.get("trend") == opposite:
        hard_fail.append("short-term trend conflict")
    if scored["spread_pct"] > 4:
        hard_fail.append("wide option spread")
    if not np.isfinite(scored["delta"]) or not (0.35 <= abs(scored["delta"]) <= 0.80):
        hard_fail.append("poor delta")
    if not np.isfinite(scored["pop"]) or scored["pop"] < 55:
        hard_fail.append("low Upstox PoP")
    if scored["volume"] <= 0:
        hard_fail.append("no option volume")

    readiness = "READY" if not hard_fail and trigger_hit else (
        "WAIT FOR TRIGGER" if not hard_fail else "NO TRADE"
    )

    return {
        "side": side,
        "strike": float(row["Strike"]),
        "entry": float(entry),
        "sl": sl,
        "target1": target1,
        "target2": target2,
        "pop": scored["pop"],
        "delta": scored["delta"],
        "iv": scored["iv"],
        "score": scored["score"],
        "rr1": rr1,
        "rr2": rr2,
        "trigger": trigger,
        "trigger_level": trigger_level,
        "trigger_hit": trigger_hit,
        "readiness": readiness,
        "fail_reasons": hard_fail,
        "exit": exit_rule,
        "oi": row[f"{side} OI"],
        "chg_oi": scored["chg_oi"],
        "volume": scored["volume"],
        "spread_pct": scored["spread_pct"],
        "alignment": scored["alignment"],
    }


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

                    candidate = {
                        "Stock": item["symbol"],
                        "Trade": action,
                        "Strike": strike,
                        "Expiry": item["expiry"],
                        "PoP": pop,
                        "Entry": entry,
                        "SL": sl,
                        "Target1": target1,
                        "Target2": target2,
                        "Exit": exit_rule,
                        "LTP": ltp,
                        "Bid": bid,
                        "Ask": ask,
                        "Delta": delta,
                        "IV": iv,
                        "Volume": volume,
                        "OI": oi,
                        "distance": distance,
                    }

                    # One highest-PoP opportunity per stock keeps the Top 5 diversified.
                    if best_for_stock is None or (
                        candidate["PoP"], candidate["Volume"], -candidate["distance"]
                    ) > (
                        best_for_stock["PoP"], best_for_stock["Volume"], -best_for_stock["distance"]
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
        key=lambda x: (-x["PoP"], -x["Volume"], x["distance"])
    )

    return candidates[:5], len(universe), scanned, failed



# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("### 🔥 Top 5 F&O PoP Scanner")
    st.caption("Scans the full NSE equity F&O market for trades with PoP > 75%.")

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
        st.success(f"Top {len(pop_results)} trades with PoP > 75%")
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

    symbol_label = "Stock / Index"
    symbol_default = st.session_state.get("symbol", "KOTAKBANK")
    symbol_placeholder = "e.g. KOTAKBANK, HDFCBANK, NIFTY"

    symbol_input = st.text_input(
        symbol_label,
        value=symbol_default,
        placeholder=symbol_placeholder,
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
# LIVE DATA
# ============================================================

try:
    with st.spinner(f"Fetching live Upstox data for {symbol}..."):
        underlying = search_underlying(symbol)
        underlying_key = underlying["instrument_key"]

        contracts = get_contracts(underlying_key)
        expiries = available_expiries(contracts)

        if not expiries:
            raise UpstoxError(
                "Upstox did not return an upcoming F&O expiry for this instrument."
            )

        selected_expiry = expiries[0]

        raw_chain = get_option_chain(
            underlying_key,
            selected_expiry,
        )

        chain = normalize_chain(raw_chain)

        quote_data = get_quote(underlying_key)

        spot = safe_float(quote_data.get("last_price"))
        previous_close = safe_float(
            quote_data.get("prev_close_price"),
            spot,
        )

        net_change = safe_float(
            quote_data.get("net_change"),
            spot - previous_close,
        )

        change_pct = (
            net_change / previous_close * 100
            if previous_close
            else 0
        )

        candles = get_daily_candles(underlying_key)
        candles_30m = get_30m_candles(underlying_key)
        candles_5m = get_intraday_candles(underlying_key, 5)

        daily_tech = technicals(candles, spot)
        tf30 = technicals(candles_30m, spot)
        tf5 = technicals(candles_5m, spot)

        # Keep the existing UI terminology while using the stronger daily trend
        # as the headline bias.
        tech = daily_tech

except UpstoxError as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:
    st.error(f"Unexpected error while loading live data: {exc}")
    st.stop()

support, resistance, pcr, oi_wall_info = oi_levels(chain, spot)

atm_index = (chain["Strike"] - spot).abs().idxmin()
atm_strike = float(chain.loc[atm_index, "Strike"])

# Evaluate a slightly wider ATM band, then choose the option with the
# strongest quality score rather than simply choosing the highest PoP.
candidate_rows = chain.iloc[
    max(0, atm_index - 5): min(len(chain), atm_index + 6)
]

ce_candidates = []
pe_candidates = []

for _, row in candidate_rows.iterrows():
    ce_candidates.append(
        (score_option(row, "CE", spot, pcr, tf5, tf30, daily_tech, chain)["score"], row)
    )
    pe_candidates.append(
        (score_option(row, "PE", spot, pcr, tf5, tf30, daily_tech, chain)["score"], row)
    )

best_ce_row = max(ce_candidates, key=lambda x: x[0], default=(0, None))[1]
best_pe_row = max(pe_candidates, key=lambda x: x[0], default=(0, None))[1]

ce_plan = build_plan(
    best_ce_row, "CE", spot, support, resistance, pcr,
    tf5, tf30, daily_tech, risk_profile, chain
)
pe_plan = build_plan(
    best_pe_row, "PE", spot, support, resistance, pcr,
    tf5, tf30, daily_tech, risk_profile, chain
)

ce_score = ce_plan["score"] if ce_plan else 0
pe_score = pe_plan["score"] if pe_plan else 0

# High-accuracy mode: disagreement or an unconfirmed breakout produces
# WAIT/NO TRADE instead of forcing a position.
overall_direction, overall_alignment = overall_trend(tf5, tf30, daily_tech)

if ce_plan and ce_score >= 72 and ce_score >= pe_score + 8 and         overall_direction == "Bullish" and ce_plan["readiness"] in {"READY", "WAIT FOR TRIGGER"}:
    decision = "CALL BUY" if ce_plan["readiness"] == "READY" else "WAIT FOR TRIGGER"
    decision_class = "trade-call" if decision == "CALL BUY" else "trade-neutral"
    best_plan = ce_plan
elif pe_plan and pe_score >= 72 and pe_score >= ce_score + 8 and         overall_direction == "Bearish" and pe_plan["readiness"] in {"READY", "WAIT FOR TRIGGER"}:
    decision = "PUT BUY" if pe_plan["readiness"] == "READY" else "WAIT FOR TRIGGER"
    decision_class = "trade-put" if decision == "PUT BUY" else "trade-neutral"
    best_plan = pe_plan
else:
    decision = "NO TRADE"
    decision_class = "trade-neutral"
    best_plan = ce_plan if ce_score >= pe_score else pe_plan

# Confidence is intentionally a separate descriptive measure.
best_score = best_plan["score"] if best_plan else 0
best_alignment = best_plan["alignment"] if best_plan else 0
confidence = int(np.clip(
    best_score * 0.70 + (best_alignment / 3) * 20 +
    (5 if overall_direction in {"Bullish", "Bearish"} else 0), 0, 100
))

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
        st.markdown(
            """
            <div style="
                background:#16a34a;
                color:#ffffff;
                padding:10px 16px;
                border-radius:8px;
                font-weight:700;
                font-size:15px;
                text-align:center;
                width:100%;
                box-sizing:border-box;
                margin:6px 0 10px 0;
            ">
                ● LIVE DATA
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="
                background:#dc2626;
                color:#ffffff;
                padding:10px 16px;
                border-radius:8px;
                font-weight:700;
                font-size:15px;
                text-align:center;
                width:100%;
                box-sizing:border-box;
                margin:6px 0 10px 0;
            ">
                ● MARKET CLOSED
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.caption(f"Expiry: {selected_expiry}")

# ============================================================
# MARKET SNAPSHOT
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(
    '<div class="section-title">📊 Market Snapshot</div>',
    unsafe_allow_html=True,
)

m1, m2, m3, m4, m5, m6 = st.columns(6)

m1.metric(
    "Live Price",
    fmt_price(spot),
    f"{net_change:+.2f} ({change_pct:+.2f}%)",
)

m2.metric("Bias", tech["trend"])
m3.metric(
    "PCR",
    f"{pcr:.2f}" if not np.isnan(pcr) else "—",
)
m4.metric("Support", fmt_price(support))
m5.metric("Resistance", fmt_price(resistance))
m6.metric("RSI", f"{tech['rsi']:.1f}")

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

d1, d2, d3, d4 = st.columns(4)

d1.metric("Bull Score", f"{ce_score:.0f}/100")
d2.metric("Bear Score", f"{pe_score:.0f}/100")
d3.metric("Trend", overall_direction)
d4.metric("Confidence", f"{confidence}/100")

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TRADE PLAN
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)

st.markdown(
    '<div class="section-title">🎯 Trade Plan</div>',
    unsafe_allow_html=True,
)

plan_rows = []

for label, plan in [
    ("CALL", ce_plan),
    ("PUT", pe_plan),
]:
    if plan:
        plan_rows.append(
            {
                "Side": label,
                "Strike": int(plan["strike"]),
                "Entry (₹)": round(plan["entry"], 2),
                "SL (₹)": round(plan["sl"], 2),
                "Target 1 (₹)": round(plan["target1"], 2),
                "Target 2 (₹)": round(plan["target2"], 2),
                "PoP": (
                    f"{plan['pop']:.1f}%"
                    if not np.isnan(plan["pop"])
                    else "—"
                ),
                "Delta": (
                    round(plan["delta"], 3)
                    if not np.isnan(plan["delta"])
                    else "—"
                ),
                "IV": (
                    f"{plan['iv']:.1f}%"
                    if not np.isnan(plan["iv"])
                    else "—"
                ),
                "R:R T1": f"1:{plan['rr1']:.2f}",
                "Readiness": plan["readiness"],
            }
        )

if plan_rows:
    st.dataframe(
        pd.DataFrame(plan_rows),
        use_container_width=True,
        hide_index=True,
    )

if best_plan:
    st.markdown("### Entry / Exit Rules")

    e1, e2 = st.columns(2)

    with e1:
        st.markdown("**Entry Trigger**")
        st.write(best_plan["trigger"])

        st.markdown("**Entry**")
        st.write(fmt_price(best_plan["entry"]))

        st.markdown("**Stop Loss**")
        st.write(fmt_price(best_plan["sl"]))

        st.markdown("**Target 1 / Target 2**")
        st.write(
            f"{fmt_price(best_plan['target1'])} / "
            f"{fmt_price(best_plan['target2'])}"
        )

    with e2:
        st.markdown("**Exit Rule**")
        st.write(best_plan["exit"])

        st.markdown("**PoP**")
        st.write(
            f"{best_plan['pop']:.1f}%"
            if not np.isnan(best_plan["pop"])
            else "Not returned by Upstox"
        )

        st.markdown("**Risk / Reward**")
        st.write(
            f"Target 1: 1:{best_plan['rr1']:.2f} | "
            f"Target 2: 1:{best_plan['rr2']:.2f}"
        )

st.caption(
    "PoP is the Probability of Profit returned by Upstox for the option contract; "
    "it is not a guarantee of profit."
)

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
    if decision == "NO TRADE":
        st.info(
            "NO TRADE: the live conditions do not currently meet the "
            "directional quality gate. Wait for the entry trigger instead "
            "of forcing an option position."
        )
    elif best_plan:
        st.success(
            f"{decision} | Strike {best_plan['strike']:.0f} | "
            f"Entry {fmt_price(best_plan['entry'])} | "
            f"SL {fmt_price(best_plan['sl'])} | "
            f"T1 {fmt_price(best_plan['target1'])} | "
            f"T2 {fmt_price(best_plan['target2'])}"
        )

    st.markdown("### Why the Engine Says This")

    reasons = [
        f"Live spot is {fmt_price(spot)}; nearest ATM strike is {atm_strike:.0f}.",
        f"5-minute trend: {tf5['trend']} | 30-minute trend: {tf30['trend']} | Daily trend: {daily_tech['trend']}.",
        f"RSI: 5m {tf5['rsi']:.1f} | 30m {tf30['rsi']:.1f} | Daily {daily_tech['rsi']:.1f}.",
        f"PCR is {pcr:.2f}.",
        f"OI support is {fmt_price(support)} and resistance is {fmt_price(resistance)}.",
        f"Overall direction: {overall_direction} with {overall_alignment}/3 timeframes aligned.",
        f"Engine confidence: {confidence}/100. The score is a rule-based quality measure, not a historical win probability.",
    ]

    if best_plan and not np.isnan(best_plan["pop"]):
        reasons.append(
            f"Selected option PoP from Upstox is {best_plan['pop']:.1f}%."
        )

    for reason in reasons:
        st.write("✓", reason)

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
            "CE PoP": view["CE PoP"].round(1),
            "PE LTP": view["PE LTP"].round(2),
            "PE OI": view["PE OI"].round(0).astype("int64"),
            "PE Chg OI": view["PE Chg OI"].round(0).astype("int64"),
            "PE IV": view["PE IV"].round(1),
            "PE Delta": view["PE Delta"].round(3),
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
    a1, a2, a3 = st.columns(3)

    a1.metric("EMA 20", fmt_price(daily_tech["ema20"]))
    a2.metric("EMA 50", fmt_price(daily_tech["ema50"]))
    a3.metric("ATR 14", fmt_price(daily_tech["atr"]))

    st.markdown("### Multi-Timeframe Confirmation")
    mtf = pd.DataFrame([
        {"Timeframe": "5 Minute", "Trend": tf5["trend"], "RSI": round(tf5["rsi"], 1),
         "ADX": round(tf5["adx"], 1), "Momentum %": round(tf5["momentum"], 2)},
        {"Timeframe": "30 Minute", "Trend": tf30["trend"], "RSI": round(tf30["rsi"], 1),
         "ADX": round(tf30["adx"], 1), "Momentum %": round(tf30["momentum"], 2)},
        {"Timeframe": "Daily", "Trend": daily_tech["trend"], "RSI": round(daily_tech["rsi"], 1),
         "ADX": round(daily_tech["adx"], 1), "Momentum %": round(daily_tech["momentum"], 2)},
    ])
    st.dataframe(mtf, use_container_width=True, hide_index=True)

    left, right = st.columns(2)

    with left:
        st.markdown("### 🟢 Support / Put OI")

        st.write(
            f"Major support from Put OI: **{fmt_price(support)}**"
        )

        support_row = nearest_row(chain, support)

        if support_row is not None:
            st.write(
                f"Put OI: **{fmt_num(support_row['PE OI'])}**"
            )
            st.write(
                f"Put Chg OI: **{fmt_num(support_row['PE Chg OI'])}**"
            )

    with right:
        st.markdown("### 🔴 Resistance / Call OI")

        st.write(
            f"Major resistance from Call OI: **{fmt_price(resistance)}**"
        )

        resistance_row = nearest_row(chain, resistance)

        if resistance_row is not None:
            st.write(
                f"Call OI: **{fmt_num(resistance_row['CE OI'])}**"
            )
            st.write(
                f"Call Chg OI: **{fmt_num(resistance_row['CE Chg OI'])}**"
            )

    if not candles.empty:
        chart = candles.set_index("timestamp")[["close"]].tail(80)
        st.line_chart(chart, use_container_width=True)

with tab4:
    st.markdown(
        """
### Live-data decision framework

**1. Market direction**
- Live spot
- 5-minute + 30-minute + Daily trend alignment
- EMA20 / EMA50
- RSI
- ADX / momentum
- Intraday VWAP where volume is available

**2. Option-chain structure**
- Put OI / Change in OI
- Call OI / Change in OI
- PCR
- OI-derived support and resistance

**3. Option quality**
- LTP
- Bid / Ask
- Volume
- IV
- Delta
- Upstox PoP

**4. Trade plan**
- Entry trigger
- Entry price
- Stop Loss
- Target 1
- Target 2
- Exit / invalidation rule
- Risk / Reward

**5. High-accuracy quality gate**
- Minimum setup score: 72/100
- At least 2 of 3 timeframes must agree
- Short-term trend conflict blocks the trade
- Delta, liquidity and bid/ask spread are checked
- Upstox PoP must be at least 55%
- The underlying breakout trigger must occur before a BUY signal
- Otherwise the engine returns **WAIT FOR TRIGGER** or **NO TRADE**
- The score is not a backtested win rate and does not guarantee profit.
"""
    )

st.divider()

st.caption(
    f"Live Upstox snapshot • {symbol} • Expiry {selected_expiry} • "
    f"Updated {updated}. "
    "For educational/decision-support use; review live market conditions before trading."
)
