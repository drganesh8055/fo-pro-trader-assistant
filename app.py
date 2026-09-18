import math
import threading
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

try:
    import upstox_client
except Exception:
    upstox_client = None

# ============================================================
# F&O PRO TRADER ASSISTANT — LIVE UPSTOX V3
# Upgrade over the accepted baseline:
#   • Upstox Market Data Feed V3 WebSocket for live ticks
#   • REST fallback if the WebSocket is unavailable
#   • Upstox Intraday Candle V3 for current-day technicals
#   • REST option-chain snapshot retained for expiry/structure/PoP
#   • Full trade plan retained: PoP, Entry, SL, T1, T2, Exit,
#     Delta, IV, PCR, OI support/resistance, score and NO TRADE.
# ============================================================

st.set_page_config(
    page_title="FO PRO Trader Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "https://api.upstox.com"
IST = timezone(timedelta(hours=5, minutes=30))

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
.status-pill-warn {
    display:inline-block;padding:7px 12px;border-radius:20px;
    background:#b54708;color:white;font-size:12px;font-weight:700;
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
.small-note {font-size:12px;color:#667085;}
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
        if value is None or value == "":
            return default
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
            f"No NSE instrument found for '{symbol}'. Enter an NSE F&O stock "
            "symbol such as HDFCBANK or an index such as NIFTY."
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


@st.cache_data(ttl=10, show_spinner=False)
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


@st.cache_data(ttl=5, show_spinner=False)
def get_quote(instrument_key):
    payload = api_get(
        "/v3/market-quote/quotes",
        params={"instrument_key": instrument_key},
    )
    data = payload.get("data", {})
    if not data:
        raise UpstoxError("No live quote returned by Upstox.")
    return next(iter(data.values()))


@st.cache_data(ttl=10, show_spinner=False)
def get_intraday_candles(instrument_key, interval=5):
    path = (
        f"/v3/historical-candle/intraday/"
        f"{quote(instrument_key, safe='')}/minutes/{interval}"
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
    start_date = end_date - timedelta(days=180)
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


# ============================================================
# LIVE UPSTOX V3 WEBSOCKET
# ============================================================


def _dict_find(obj, names):
    """Find the first dict value whose key matches one of names."""
    wanted = {str(x).lower() for x in names}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in wanted:
                return value
        for value in obj.values():
            found = _dict_find(value, names)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _dict_find(value, names)
            if found is not None:
                return found
    return None


def _find_first_number(obj, names):
    value = _dict_find(obj, names)
    return safe_float(value)


class LiveMarketStream:
    """Small background manager around Upstox MarketDataStreamerV3.

    Streamlit reruns the script frequently. The WebSocket itself therefore
    lives in a background daemon thread and the latest decoded ticks are kept
    in memory. The UI only reads this state on each rerun.
    """

    def __init__(self):
        self.lock = threading.RLock()
        self.streamer = None
        self.thread = None
        self.keys = tuple()
        self.data = {}
        self.status = "NOT STARTED"
        self.last_error = ""
        self.started_at = None
        self.last_message_at = None

    def _on_open(self):
        with self.lock:
            self.status = "CONNECTED"
            self.last_error = ""

    def _on_close(self, *args):
        with self.lock:
            if self.status != "ERROR":
                self.status = "DISCONNECTED"

    def _on_error(self, error):
        with self.lock:
            self.status = "ERROR"
            self.last_error = str(error)

    def _on_message(self, message):
        now = datetime.now().astimezone()
        with self.lock:
            self.last_message_at = now
            if isinstance(message, dict):
                feeds = message.get("feeds") or {}
                for instrument_key, feed in feeds.items():
                    parsed = self._parse_feed(feed)
                    if parsed:
                        previous = self.data.get(instrument_key, {})
                        previous.update(parsed)
                        previous["received_at"] = now
                        self.data[instrument_key] = previous

    @staticmethod
    def _parse_feed(feed):
        # Full V3 messages can contain marketFF/indexFF under fullFeed.
        # Recursive lookup keeps this parser tolerant of SDK field nesting.
        ltpc = _dict_find(feed, ["ltpc"])
        greeks = _dict_find(feed, ["optionGreeks"])
        details = _dict_find(feed, ["eFeedDetails", "extendedFeedDetails"])
        quote = _dict_find(feed, ["bidAskQuote"])
        market_level = _dict_find(feed, ["marketLevel"])

        if quote is None and market_level is not None:
            quote = _dict_find(market_level, ["bidAskQuote"])

        parsed = {}

        ltp = _find_first_number(ltpc, ["ltp"]) if ltpc is not None else np.nan
        cp = _find_first_number(ltpc, ["cp"]) if ltpc is not None else np.nan
        ltt = _dict_find(ltpc, ["ltt"]) if ltpc is not None else None

        if np.isfinite(ltp):
            parsed["ltp"] = ltp
        if np.isfinite(cp):
            parsed["cp"] = cp
        if ltt is not None:
            parsed["ltt"] = ltt

        # Quote fields in the protobuf are bq/bp/aq/ap.
        if quote is not None:
            bid = _find_first_number(quote, ["bp", "bidPrice"])
            ask = _find_first_number(quote, ["ap", "askPrice"])
            bid_qty = _find_first_number(quote, ["bq", "bidQty"])
            ask_qty = _find_first_number(quote, ["aq", "askQty"])
            if np.isfinite(bid):
                parsed["bid"] = bid
            if np.isfinite(ask):
                parsed["ask"] = ask
            if np.isfinite(bid_qty):
                parsed["bid_qty"] = bid_qty
            if np.isfinite(ask_qty):
                parsed["ask_qty"] = ask_qty

        if details is not None:
            oi = _find_first_number(details, ["oi"])
            change_oi = _find_first_number(details, ["changeOi", "change_oi"])
            volume = _find_first_number(details, ["vtt", "volume"])
            if np.isfinite(oi):
                parsed["oi"] = oi
            if np.isfinite(change_oi):
                parsed["change_oi"] = change_oi
            if np.isfinite(volume):
                parsed["volume"] = volume

        if greeks is not None:
            for key, aliases in {
                "iv": ["iv"],
                "delta": ["delta"],
                "theta": ["theta"],
                "gamma": ["gamma"],
                "vega": ["vega"],
                "rho": ["rho"],
            }.items():
                value = _find_first_number(greeks, aliases)
                if np.isfinite(value):
                    parsed[key] = value

        return parsed

    def ensure(self, instrument_keys):
        keys = tuple(sorted({k for k in instrument_keys if k}))
        if not keys:
            return
        with self.lock:
            if keys == self.keys and self.thread is not None and self.thread.is_alive():
                return
            old = self.streamer
            self.streamer = None
            self.keys = keys
            self.data = {k: self.data.get(k, {}) for k in keys}
            self.status = "CONNECTING"
            self.last_error = ""
            if old is not None:
                try:
                    old.disconnect()
                except Exception:
                    pass

            if upstox_client is None:
                self.status = "ERROR"
                self.last_error = (
                    "upstox-python-sdk is not installed. Add it to requirements.txt."
                )
                return

            self.thread = threading.Thread(
                target=self._run_stream,
                args=(keys,),
                daemon=True,
                name="upstox-market-stream",
            )
            self.started_at = datetime.now().astimezone()
            self.thread.start()

    def _run_stream(self, keys):
        try:
            configuration = upstox_client.Configuration()
            configuration.access_token = TOKEN
            api_client = upstox_client.ApiClient(configuration)
            streamer = upstox_client.MarketDataStreamerV3(
                api_client,
                list(keys),
                "full",
            )

            streamer.on("open", self._on_open)
            streamer.on("message", self._on_message)
            streamer.on("error", self._on_error)
            streamer.on("close", self._on_close)
            try:
                streamer.auto_reconnect(True, 5, 20)
            except Exception:
                pass

            with self.lock:
                self.streamer = streamer

            streamer.connect()
        except Exception as exc:
            with self.lock:
                self.status = "ERROR"
                self.last_error = str(exc)

    def snapshot(self, keys=None):
        with self.lock:
            if keys is None:
                selected = self.data
            else:
                selected = {k: self.data.get(k, {}) for k in keys}
            return {
                "status": self.status,
                "last_error": self.last_error,
                "started_at": self.started_at,
                "last_message_at": self.last_message_at,
                "data": {k: dict(v) for k, v in selected.items()},
            }


@st.cache_resource(show_spinner=False)
def get_stream_manager():
    return LiveMarketStream()


# ============================================================
# TECHNICALS
# ============================================================


def technicals(intraday_df, daily_df, spot):
    source = intraday_df.copy() if not intraday_df.empty else daily_df.copy()
    source_label = "Intraday V3" if not intraday_df.empty else "Daily fallback"
    interval_label = "5-min" if not intraday_df.empty else "Daily"

    if source.empty or len(source) < 14:
        return {
            "rsi": 50.0,
            "ema20": spot,
            "ema50": spot,
            "atr": spot * 0.01,
            "trend": "Unavailable",
            "source": source_label,
            "interval": interval_label,
        }

    close = source["close"].astype(float)
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
            source["high"] - source["low"],
            (source["high"] - previous_close).abs(),
            (source["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.rolling(14, min_periods=14).mean()

    latest_rsi = safe_float(rsi.iloc[-1], 50.0)
    latest_ema20 = safe_float(ema20.iloc[-1], spot)
    latest_ema50 = safe_float(ema50.iloc[-1], spot)
    latest_atr = safe_float(atr.iloc[-1], spot * 0.01)

    if spot > latest_ema20 > latest_ema50:
        trend = "Bullish"
    elif spot < latest_ema20 < latest_ema50:
        trend = "Bearish"
    else:
        trend = "Sideways"

    return {
        "rsi": latest_rsi,
        "ema20": latest_ema20,
        "ema50": latest_ema50,
        "atr": latest_atr,
        "trend": trend,
        "source": source_label,
        "interval": interval_label,
    }


# ============================================================
# OPTION CHAIN + ENGINE
# ============================================================


def normalize_chain(rows, live_map=None):
    live_map = live_map or {}
    records = []

    for item in rows:
        strike = safe_float(item.get("strike_price"))
        call = item.get("call_options") or {}
        put = item.get("put_options") or {}

        call_market = call.get("market_data") or {}
        call_greeks = call.get("option_greeks") or {}
        put_market = put.get("market_data") or {}
        put_greeks = put.get("option_greeks") or {}

        ce_key = call.get("instrument_key")
        pe_key = put.get("instrument_key")
        ce_live = live_map.get(ce_key, {})
        pe_live = live_map.get(pe_key, {})

        def choose(key, market, live, default=np.nan):
            live_value = safe_float(live.get(key), np.nan)
            if np.isfinite(live_value):
                return live_value
            return safe_float(market.get(key), default)

        def choose_greek(key, greeks, live):
            live_value = safe_float(live.get(key), np.nan)
            if np.isfinite(live_value):
                return live_value
            return safe_float(greeks.get(key))

        call_oi = choose("oi", call_market, ce_live, 0)
        put_oi = choose("oi", put_market, pe_live, 0)
        call_prev_oi = safe_float(call_market.get("prev_oi"), 0)
        put_prev_oi = safe_float(put_market.get("prev_oi"), 0)

        ce_change = safe_float(ce_live.get("change_oi"), np.nan)
        pe_change = safe_float(pe_live.get("change_oi"), np.nan)
        if not np.isfinite(ce_change):
            ce_change = call_oi - call_prev_oi
        if not np.isfinite(pe_change):
            pe_change = put_oi - put_prev_oi

        records.append(
            {
                "Strike": strike,
                "CE Key": ce_key,
                "CE LTP": choose("ltp", call_market, ce_live),
                "CE Bid": choose("bid", call_market, ce_live),
                "CE Ask": choose("ask", call_market, ce_live),
                "CE OI": call_oi,
                "CE Chg OI": ce_change,
                "CE Volume": choose("volume", call_market, ce_live, 0),
                "CE IV": choose_greek("iv", call_greeks, ce_live),
                "CE Delta": choose_greek("delta", call_greeks, ce_live),
                "CE PoP": safe_float(call_greeks.get("pop")),
                "PE Key": pe_key,
                "PE LTP": choose("ltp", put_market, pe_live),
                "PE Bid": choose("bid", put_market, pe_live),
                "PE Ask": choose("ask", put_market, pe_live),
                "PE OI": put_oi,
                "PE Chg OI": pe_change,
                "PE Volume": choose("volume", put_market, pe_live, 0),
                "PE IV": choose_greek("iv", put_greeks, pe_live),
                "PE Delta": choose_greek("delta", put_greeks, pe_live),
                "PE PoP": safe_float(put_greeks.get("pop")),
            }
        )

    return pd.DataFrame(records).sort_values("Strike").reset_index(drop=True)


def oi_levels(chain, spot):
    valid = chain.dropna(subset=["Strike"]).copy()
    if valid.empty:
        return np.nan, np.nan, np.nan

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

    return float(support_row["Strike"]), float(resistance_row["Strike"]), pcr


def nearest_row(chain, strike):
    if chain.empty or not np.isfinite(strike):
        return None
    index = (chain["Strike"] - strike).abs().idxmin()
    return chain.loc[index]


def score_option(row, side, spot, pcr, tech):
    if side == "CE":
        delta = row["CE Delta"]
        iv = row["CE IV"]
        pop = row["CE PoP"]
        chg_oi = row["CE Chg OI"]
        volume = row["CE Volume"]
        directional = 25 if tech["trend"] == "Bullish" else 10 if tech["trend"] == "Sideways" else 0
        pcr_score = 10 if pcr >= 0.90 else 5 if pcr >= 0.75 else 0
    else:
        delta = row["PE Delta"]
        iv = row["PE IV"]
        pop = row["PE PoP"]
        chg_oi = row["PE Chg OI"]
        volume = row["PE Volume"]
        directional = 25 if tech["trend"] == "Bearish" else 10 if tech["trend"] == "Sideways" else 0
        pcr_score = 10 if pcr <= 1.10 else 5 if pcr <= 1.30 else 0

    distance_pct = abs(float(row["Strike"]) - spot) / max(spot, 1)
    distance_score = max(0, 15 - distance_pct * 500)

    delta_score = (
        np.clip((abs(delta) - 0.30) / 0.45 * 20, 0, 20)
        if np.isfinite(delta) else 0
    )
    pop_score = (
        np.clip((pop - 40) / 30 * 20, 0, 20)
        if np.isfinite(pop) else 0
    )
    liquidity_score = 10 if volume > 0 else 0
    oi_score = 5 if chg_oi < 0 else 2

    score = float(
        np.clip(
            directional + pcr_score + distance_score + delta_score + pop_score
            + liquidity_score + oi_score,
            0,
            100,
        )
    )

    return {
        "score": score,
        "premium": row[f"{side} LTP"],
        "delta": delta,
        "iv": iv,
        "pop": pop,
        "chg_oi": chg_oi,
        "volume": volume,
    }


def build_plan(row, side, spot, support, resistance, pcr, tech, risk_profile):
    if row is None:
        return None

    scored = score_option(row, side, spot, pcr, tech)
    entry = row[f"{side} Ask"]
    if not np.isfinite(entry) or entry <= 0:
        entry = row[f"{side} LTP"]
    if not np.isfinite(entry) or entry <= 0:
        return None

    risk_settings = {
        "Conservative": (0.75, 1.30, 1.60),
        "Balanced": (0.70, 1.40, 1.80),
        "Aggressive": (0.65, 1.55, 2.10),
    }
    sl_factor, target1_factor, target2_factor = risk_settings[risk_profile]
    sl = round(entry * sl_factor, 2)
    target1 = round(entry * target1_factor, 2)
    target2 = round(entry * target2_factor, 2)
    rr1 = (target1 - entry) / max(entry - sl, 0.01)
    rr2 = (target2 - entry) / max(entry - sl, 0.01)

    if side == "CE":
        trigger = f"Enter only after spot sustains above resistance/trigger around {fmt_price(resistance)}."
        exit_rule = (
            f"Exit if spot closes below support {fmt_price(support)} or option premium hits {fmt_price(sl)}. "
            "After Target 1, book partial profit and trail the balance."
        )
    else:
        trigger = f"Enter only after spot breaks and sustains below support/trigger around {fmt_price(support)}."
        exit_rule = (
            f"Exit if spot closes above resistance {fmt_price(resistance)} or option premium hits {fmt_price(sl)}. "
            "After Target 1, book partial profit and trail the balance."
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
        "exit": exit_rule,
        "oi": row[f"{side} OI"],
        "chg_oi": scored["chg_oi"],
        "volume": scored["volume"],
    }


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
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

    analyze = st.button("🔍 Analyze", type="primary", use_container_width=True)
    refresh = st.button("↻ Refresh Live Data", use_container_width=True)

    st.divider()
    st.markdown("### 🔔 PoP Alert Monitor")
    monitor_enabled = st.toggle(
        "Monitor ON / OFF",
        value=st.session_state.get("pop_monitor_enabled", False),
        help="When ON, the app refreshes the live option chain every 5 seconds and lists every option contract whose Upstox PoP meets the selected threshold.",
    )
    st.session_state["pop_monitor_enabled"] = monitor_enabled

    pop_threshold = st.slider(
        "Minimum PoP",
        min_value=50,
        max_value=90,
        value=60,
        step=5,
        format="%d%%",
    )
    st.session_state["pop_alert_threshold"] = float(pop_threshold)

    # The monitor itself controls the refresh cycle. This keeps the right-hand
    # dashboard unchanged while the left-side scanner continuously refreshes
    # when the user turns monitoring ON.
    if monitor_enabled and st_autorefresh is not None:
        st_autorefresh(interval=5_000, key="pop_background_monitor")
        st.caption("🟢 Monitoring every 5 seconds")
    elif monitor_enabled:
        st.caption("🟢 Monitoring ON — refresh the page manually if auto-refresh is unavailable")
    else:
        st.caption("⚪ Monitoring OFF")

    st.divider()
    st.caption("LIVE DATA • Upstox V3 WebSocket + REST")
    st.caption("No simulated market values are used.")

if analyze:
    st.session_state["symbol"] = alias_symbol(symbol_input)
    st.rerun()

if refresh:
    st.cache_data.clear()
    st.rerun()

symbol = alias_symbol(st.session_state.get("symbol", symbol_input or "KOTAKBANK"))

# ============================================================
# REST SNAPSHOT + INTRADAY TECHNICALS
# ============================================================

try:
    with st.spinner(f"Fetching live Upstox V3 data for {symbol}..."):
        underlying = search_underlying(symbol)
        underlying_key = underlying["instrument_key"]

        contracts = get_contracts(underlying_key)
        expiries = available_expiries(contracts)
        if not expiries:
            raise UpstoxError("Upstox did not return an upcoming F&O expiry for this instrument.")

        selected_expiry = expiries[0]
        raw_chain = get_option_chain(underlying_key, selected_expiry)

        # Start/refresh the background WebSocket with the underlying and all
        # option contracts returned by the selected expiry.
        stream_keys = [underlying_key]
        for item in raw_chain:
            call_key = (item.get("call_options") or {}).get("instrument_key")
            put_key = (item.get("put_options") or {}).get("instrument_key")
            if call_key:
                stream_keys.append(call_key)
            if put_key:
                stream_keys.append(put_key)

        stream_manager = get_stream_manager()
        stream_manager.ensure(stream_keys)
        stream_snapshot = stream_manager.snapshot(stream_keys)
        live_map = stream_snapshot["data"]

        # REST quote is kept as a reliable fallback / initial snapshot.
        quote_data = get_quote(underlying_key)
        stream_underlying = live_map.get(underlying_key, {})

        spot = safe_float(stream_underlying.get("ltp"))
        if not np.isfinite(spot):
            spot = safe_float(quote_data.get("last_price"))

        previous_close = safe_float(stream_underlying.get("cp"), np.nan)
        if not np.isfinite(previous_close):
            previous_close = safe_float(quote_data.get("prev_close_price"), spot)

        net_change = spot - previous_close if np.isfinite(previous_close) else safe_float(quote_data.get("net_change"), 0)
        change_pct = net_change / previous_close * 100 if previous_close else 0

        chain = normalize_chain(raw_chain, live_map)

        intraday = get_intraday_candles(underlying_key, interval=5)
        daily = get_daily_candles(underlying_key)
        tech = technicals(intraday, daily, spot)

except UpstoxError as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:
    st.error(f"Unexpected error while loading live data: {exc}")
    st.stop()

support, resistance, pcr = oi_levels(chain, spot)
atm_index = (chain["Strike"] - spot).abs().idxmin()
atm_strike = float(chain.loc[atm_index, "Strike"])
candidate_rows = chain.iloc[max(0, atm_index - 3): min(len(chain), atm_index + 4)]

ce_scores = []
pe_scores = []
for _, row in candidate_rows.iterrows():
    ce_scores.append((score_option(row, "CE", spot, pcr, tech)["score"], float(row["Strike"])))
    pe_scores.append((score_option(row, "PE", spot, pcr, tech)["score"], float(row["Strike"])))

best_ce_strike = max(ce_scores, default=(0, atm_strike))[1]
best_pe_strike = max(pe_scores, default=(0, atm_strike))[1]

ce_plan = build_plan(nearest_row(chain, best_ce_strike), "CE", spot, support, resistance, pcr, tech, risk_profile)
pe_plan = build_plan(nearest_row(chain, best_pe_strike), "PE", spot, support, resistance, pcr, tech, risk_profile)

ce_score = ce_plan["score"] if ce_plan else 0
pe_score = pe_plan["score"] if pe_plan else 0

if ce_plan and ce_score >= 60 and ce_score >= pe_score + 5 and tech["trend"] == "Bullish":
    decision = "CALL BUY"
    decision_class = "trade-call"
    best_plan = ce_plan
elif pe_plan and pe_score >= 60 and pe_score >= ce_score + 5 and tech["trend"] == "Bearish":
    decision = "PUT BUY"
    decision_class = "trade-put"
    best_plan = pe_plan
else:
    decision = "NO TRADE"
    decision_class = "trade-neutral"
    best_plan = ce_plan if ce_score >= pe_score else pe_plan

# ============================================================
# PoP ALERT MONITOR
# ============================================================
# This is a scanner only. It does not alter the existing trade decision or
# Trade Plan shown on the right side. When enabled, every CE/PE contract in
# the selected live option chain is checked against the configured PoP floor.

monitor_enabled = bool(st.session_state.get("pop_monitor_enabled", False))
pop_threshold = float(st.session_state.get("pop_alert_threshold", 60))

qualifying_pop_trades = []

if monitor_enabled:
    for _, row in chain.iterrows():
        strike = safe_float(row.get("Strike"))
        if not np.isfinite(strike):
            continue

        for side, action in (("CE", "CALL BUY"), ("PE", "PUT BUY")):
            pop = safe_float(row.get(f"{side} PoP"))
            ltp = safe_float(row.get(f"{side} LTP"))
            ask = safe_float(row.get(f"{side} Ask"))
            delta = safe_float(row.get(f"{side} Delta"))
            iv = safe_float(row.get(f"{side} IV"))
            volume = safe_float(row.get(f"{side} Volume"))

            if not np.isfinite(pop) or pop < pop_threshold:
                continue

            entry = ask if np.isfinite(ask) and ask > 0 else ltp
            if not np.isfinite(entry) or entry <= 0:
                continue

            plan = build_plan(
                row, side, spot, support, resistance, pcr, tech, risk_profile
            )
            if plan is None:
                continue

            qualifying_pop_trades.append(
                {
                    "Action": action,
                    "Strike": strike,
                    "PoP": pop,
                    "Entry": plan["entry"],
                    "SL": plan["sl"],
                    "T1": plan["target1"],
                    "T2": plan["target2"],
                    "Delta": delta,
                    "IV": iv,
                    "Volume": volume,
                }
            )

    qualifying_pop_trades.sort(key=lambda x: (-x["PoP"], abs(x["Strike"] - spot)))

# Render ONLY inside the sidebar so the main/right dashboard is untouched.
with st.sidebar:
    st.markdown("### 📋 Options Meeting PoP Criteria")

    if not monitor_enabled:
        st.caption("Turn Monitor ON to scan the live option chain.")
    elif qualifying_pop_trades:
        st.success(
            f"{len(qualifying_pop_trades)} option trade(s) found with PoP ≥ {pop_threshold:.0f}%"
        )

        pop_view = pd.DataFrame(qualifying_pop_trades)
        pop_view["Strike"] = pop_view["Strike"].map(lambda x: f"{x:,.0f}")
        pop_view["PoP"] = pop_view["PoP"].map(lambda x: f"{x:.1f}%")
        pop_view["Entry"] = pop_view["Entry"].map(fmt_price)
        pop_view["SL"] = pop_view["SL"].map(fmt_price)
        pop_view["T1"] = pop_view["T1"].map(fmt_price)
        pop_view["T2"] = pop_view["T2"].map(fmt_price)
        pop_view["Delta"] = pop_view["Delta"].map(
            lambda x: f"{x:.2f}" if np.isfinite(x) else "—"
        )
        pop_view["IV"] = pop_view["IV"].map(
            lambda x: f"{x:.1f}%" if np.isfinite(x) else "—"
        )

        st.dataframe(
            pop_view[
                ["Action", "Strike", "PoP", "Entry", "SL", "T1", "T2", "Delta", "IV"]
            ],
            use_container_width=True,
            hide_index=True,
            height=min(520, 95 + len(pop_view) * 35),
        )
        st.caption(
            "Sorted by highest PoP. These are qualifying option contracts from the current selected expiry. "
            "PoP is an estimate from Upstox, not a guarantee of profit."
        )
    else:
        st.info(
            f"No option contract in the current expiry has PoP ≥ {pop_threshold:.0f}% right now."
        )

ws_last = stream_snapshot.get("last_message_at")
ws_status = stream_snapshot.get("status", "NOT STARTED")
if ws_last:
    ws_age = max(0.0, (datetime.now().astimezone() - ws_last).total_seconds())
else:
    ws_age = None

updated = quote_data.get("timestamp", datetime.now().astimezone().isoformat())

# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
<div class="topbar">
    <div class="topbar-title">📊 FO PRO Trader Assistant</div>
    <div class="topbar-sub">Options Analysis • Upstox V3 • WebSocket live market stream + intraday technicals</div>
</div>
""",
    unsafe_allow_html=True,
)

h1, h2, h3 = st.columns([2.2, 1.2, 1.0])
with h1:
    st.markdown(f"## {symbol} — F&O Options Analysis")
with h2:
    st.markdown("**Last Traded**")
    st.markdown(f"<span style='font-size:25px;font-weight:800'>{fmt_price(spot)}</span>", unsafe_allow_html=True)
    st.caption(f"{net_change:+.2f} ({change_pct:+.2f}%)")
with h3:
    st.markdown("**Data Status**")
    if ws_status == "CONNECTED" and ws_age is not None and ws_age < 15:
        st.markdown('<span class="status-pill">● LIVE WEBSOCKET</span>', unsafe_allow_html=True)
        st.caption(f"Last tick ~{ws_age:.1f}s ago")
    else:
        st.markdown('<span class="status-pill-warn">● REST FALLBACK / CONNECTING</span>', unsafe_allow_html=True)
        if ws_age is not None:
            st.caption(f"Last WS tick ~{ws_age:.1f}s ago")
        else:
            st.caption("WebSocket warming up")
    st.caption(f"Expiry: {selected_expiry}")

# ============================================================
# MARKET SNAPSHOT
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 Market Snapshot</div>', unsafe_allow_html=True)
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Live Price", fmt_price(spot), f"{net_change:+.2f} ({change_pct:+.2f}%)")
m2.metric("Bias", tech["trend"])
m3.metric("PCR", f"{pcr:.2f}" if np.isfinite(pcr) else "—")
m4.metric("Support", fmt_price(support))
m5.metric("Resistance", fmt_price(resistance))
m6.metric("RSI", f"{tech['rsi']:.1f}")
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TRADE DECISION
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🎯 Trade Decision</div>', unsafe_allow_html=True)
st.markdown(f'<div class="{decision_class}">Decision: {decision}</div>', unsafe_allow_html=True)
d1, d2, d3, d4 = st.columns(4)
d1.metric("Bull Score", f"{ce_score:.0f}/100")
d2.metric("Bear Score", f"{pe_score:.0f}/100")
d3.metric("Trend", tech["trend"])
d4.metric("ATR", fmt_price(tech["atr"]))
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TRADE PLAN
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">🎯 Trade Plan</div>', unsafe_allow_html=True)
plan_rows = []
for label, plan in [("CALL", ce_plan), ("PUT", pe_plan)]:
    if plan:
        plan_rows.append(
            {
                "Side": label,
                "Strike": int(plan["strike"]),
                "Entry (₹)": round(plan["entry"], 2),
                "SL (₹)": round(plan["sl"], 2),
                "Target 1 (₹)": round(plan["target1"], 2),
                "Target 2 (₹)": round(plan["target2"], 2),
                "PoP": f"{plan['pop']:.1f}%" if np.isfinite(plan["pop"]) else "—",
                "Delta": round(plan["delta"], 3) if np.isfinite(plan["delta"]) else "—",
                "IV": f"{plan['iv']:.1f}%" if np.isfinite(plan["iv"]) else "—",
                "R:R T1": f"1:{plan['rr1']:.2f}",
            }
        )

if plan_rows:
    st.dataframe(pd.DataFrame(plan_rows), use_container_width=True, hide_index=True)

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
        st.write(f"{fmt_price(best_plan['target1'])} / {fmt_price(best_plan['target2'])}")
    with e2:
        st.markdown("**Exit Rule**")
        st.write(best_plan["exit"])
        st.markdown("**PoP**")
        st.write(f"{best_plan['pop']:.1f}%" if np.isfinite(best_plan["pop"]) else "Not returned by Upstox")
        st.markdown("**Risk / Reward**")
        st.write(f"Target 1: 1:{best_plan['rr1']:.2f} | Target 2: 1:{best_plan['rr2']:.2f}")

st.caption(
    "PoP is the Probability of Profit returned by Upstox for the option contract; "
    "it is not a guarantee of profit. Entry/SL/targets are engine-derived levels, not guaranteed executions."
)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "🏆 Best Trade",
    "🔎 Live Option Chain",
    "📊 Market Analysis",
    "🧠 How Engine Thinks",
])

with tab1:
    if decision == "NO TRADE":
        st.info(
            "NO TRADE: the live conditions do not currently meet the directional quality gate. "
            "Wait for the entry trigger instead of forcing an option position."
        )
    elif best_plan:
        st.success(
            f"{decision} | Strike {best_plan['strike']:.0f} | Entry {fmt_price(best_plan['entry'])} | "
            f"SL {fmt_price(best_plan['sl'])} | T1 {fmt_price(best_plan['target1'])} | T2 {fmt_price(best_plan['target2'])}"
        )

    st.markdown("### Why the Engine Says This")
    reasons = [
        f"Live spot is {fmt_price(spot)}; nearest ATM strike is {atm_strike:.0f}.",
        f"Technical source: {tech['source']} ({tech['interval']}). Trend is {tech['trend']}.",
        f"RSI is {tech['rsi']:.1f}; EMA20 is {fmt_price(tech['ema20'])}; EMA50 is {fmt_price(tech['ema50'])}.",
        f"PCR is {pcr:.2f}." if np.isfinite(pcr) else "PCR is unavailable.",
        f"OI support is {fmt_price(support)} and resistance is {fmt_price(resistance)}.",
    ]
    if best_plan and np.isfinite(best_plan["pop"]):
        reasons.append(f"Selected option PoP from Upstox is {best_plan['pop']:.1f}%.")
    for reason in reasons:
        st.write("✓", reason)

with tab2:
    st.markdown(f"### Live Option Chain — {selected_expiry}")
    view = chain.copy()
    display = pd.DataFrame(
        {
            "Strike": view["Strike"].round(0).astype(int),
            "CE LTP": view["CE LTP"].round(2),
            "CE Bid": view["CE Bid"].round(2),
            "CE Ask": view["CE Ask"].round(2),
            "CE OI": view["CE OI"].round(0).astype("int64"),
            "CE Chg OI": view["CE Chg OI"].round(0).astype("int64"),
            "CE IV": view["CE IV"].round(1),
            "CE Delta": view["CE Delta"].round(3),
            "CE PoP": view["CE PoP"].round(1),
            "PE LTP": view["PE LTP"].round(2),
            "PE Bid": view["PE Bid"].round(2),
            "PE Ask": view["PE Ask"].round(2),
            "PE OI": view["PE OI"].round(0).astype("int64"),
            "PE Chg OI": view["PE Chg OI"].round(0).astype("int64"),
            "PE IV": view["PE IV"].round(1),
            "PE Delta": view["PE Delta"].round(3),
            "PE PoP": view["PE PoP"].round(1),
        }
    )
    display["_distance"] = (display["Strike"] - spot).abs()
    display = display.sort_values("_distance").drop(columns="_distance").head(15)
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.caption("LTP/bid/ask/OI/volume/Greeks are refreshed from the live stream when available; PoP is retained from the Upstox option-chain response.")

with tab3:
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("EMA 20", fmt_price(tech["ema20"]))
    a2.metric("EMA 50", fmt_price(tech["ema50"]))
    a3.metric("ATR 14", fmt_price(tech["atr"]))
    a4.metric("Tech Data", tech["interval"])

    left, right = st.columns(2)
    with left:
        st.markdown("### 🟢 Support / Put OI")
        st.write(f"Major support from Put OI: **{fmt_price(support)}**")
        support_row = nearest_row(chain, support)
        if support_row is not None:
            st.write(f"Put OI: **{fmt_num(support_row['PE OI'])}**")
            st.write(f"Put Chg OI: **{fmt_num(support_row['PE Chg OI'])}**")
    with right:
        st.markdown("### 🔴 Resistance / Call OI")
        st.write(f"Major resistance from Call OI: **{fmt_price(resistance)}**")
        resistance_row = nearest_row(chain, resistance)
        if resistance_row is not None:
            st.write(f"Call OI: **{fmt_num(resistance_row['CE OI'])}**")
            st.write(f"Call Chg OI: **{fmt_num(resistance_row['CE Chg OI'])}**")

    if not intraday.empty:
        chart = intraday.set_index("timestamp")[["close"]].tail(120)
        st.markdown("### 5-minute Intraday Price")
        st.line_chart(chart, use_container_width=True)
    elif not daily.empty:
        chart = daily.set_index("timestamp")[["close"]].tail(80)
        st.markdown("### Daily Price — fallback")
        st.line_chart(chart, use_container_width=True)

with tab4:
    st.markdown(
        """
### Live-data decision framework

**1. Live market stream**
- Upstox Market Data Feed V3 WebSocket
- Live underlying LTP and previous close
- Live option LTP, bid/ask, OI, volume and available Greeks
- Automatic reconnect is enabled
- REST quote remains as a fallback if the stream is warming up/unavailable

**2. Intraday technical analysis**
- Upstox Intraday Candle V3
- Current-day 5-minute OHLC
- RSI 14
- EMA 20 / EMA 50
- ATR 14
- Daily candles remain available as a fallback

**3. Option-chain structure**
- Put OI / Change in OI
- Call OI / Change in OI
- PCR
- OI-derived support and resistance
- Upstox PoP, IV and Delta

**4. Trade plan**
- Entry trigger
- Entry price
- Stop Loss
- Target 1
- Target 2
- Exit / invalidation rule
- Risk / Reward

**5. Quality gate**
- The app can return **NO TRADE** when evidence is mixed.
- It does not manufacture a trade simply because an instrument was entered.
"""
    )

    if stream_snapshot.get("last_error"):
        st.warning(f"WebSocket status: {stream_snapshot['last_error']}")

st.divider()

if ws_status == "CONNECTED" and ws_age is not None:
    data_note = f"WebSocket last message ~{ws_age:.1f}s ago"
else:
    data_note = "REST snapshot used while WebSocket connects/reconnects"

st.caption(
    f"Live Upstox V3 • {symbol} • Expiry {selected_expiry} • {data_note} • "
    f"Intraday technicals: {tech['interval']}. Updated {updated}. "
    "For educational/decision-support use; review live market conditions before trading."
)
