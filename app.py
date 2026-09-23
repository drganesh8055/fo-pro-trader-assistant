# ============================================================
# PREMIUM TRADING TERMINAL UI
# LOGIC ABOVE THIS SECTION IS UNCHANGED
# ============================================================

market_now = datetime.now(ZoneInfo("Asia/Kolkata"))

market_open = (
    market_now.weekday() < 5
    and (market_now.hour, market_now.minute) >= (9, 15)
    and (market_now.hour, market_now.minute) < (15, 30)
)

# ============================================================
# PREMIUM UI CSS
# ============================================================

st.markdown(
    """
<style>

/* ============================================================
   GLOBAL
   ============================================================ */

.stApp {
    background:
        radial-gradient(circle at top right, rgba(35,82,125,.08), transparent 28%),
        #f4f7fb;
}

.block-container {
    max-width: 1540px;
    padding-top: 1rem;
    padding-bottom: 3rem;
}

[data-testid="stSidebar"] {
    background: #0d1b2a;
}

[data-testid="stSidebar"] > div:first-child {
    background: #0d1b2a;
}

[data-testid="stSidebar"] * {
    color: #e8eef5;
}

[data-testid="stSidebar"] .stCaption {
    color: #94a9bd !important;
}

[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,.10);
}

[data-testid="stSidebar"] input {
    background: #16293d !important;
    color: white !important;
    border: 1px solid #2b4259 !important;
}

[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #16293d !important;
    border-color: #2b4259 !important;
    color: white !important;
}


/* ============================================================
   HEADER
   ============================================================ */

.fo-header {
    background:
        linear-gradient(135deg,#071522 0%,#102a43 48%,#17456d 100%);
    border-radius: 18px;
    padding: 24px 28px;
    margin-bottom: 18px;
    color: white;
    box-shadow: 0 10px 30px rgba(8,27,45,.16);
    position: relative;
    overflow: hidden;
}

.fo-header:after {
    content: "";
    position: absolute;
    width: 260px;
    height: 260px;
    right: -100px;
    top: -120px;
    border-radius: 50%;
    border: 1px solid rgba(255,255,255,.08);
}

.fo-header-inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    position: relative;
    z-index: 1;
}

.fo-brand {
    display: flex;
    align-items: center;
    gap: 14px;
}

.fo-brand-icon {
    width: 48px;
    height: 48px;
    border-radius: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255,255,255,.10);
    border: 1px solid rgba(255,255,255,.12);
    font-size: 24px;
}

.fo-title {
    font-size: 25px;
    font-weight: 900;
    letter-spacing: -.5px;
}

.fo-subtitle {
    font-size: 12px;
    color: #a9bed2;
    margin-top: 4px;
}

.fo-live {
    padding: 10px 16px;
    border-radius: 30px;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: .6px;
    white-space: nowrap;
}

.fo-live-open {
    background: rgba(22,163,74,.18);
    border: 1px solid rgba(74,222,128,.35);
    color: #86efac;
}

.fo-live-closed {
    background: rgba(220,38,38,.18);
    border: 1px solid rgba(248,113,113,.35);
    color: #fca5a5;
}


/* ============================================================
   SYMBOL HERO
   ============================================================ */

.symbol-hero {
    background: white;
    border: 1px solid #e5eaf0;
    border-radius: 16px;
    padding: 19px 22px;
    margin-bottom: 18px;
    box-shadow: 0 4px 15px rgba(16,42,67,.045);
}

.symbol-name {
    font-size: 25px;
    font-weight: 900;
    color: #17212d;
}

.symbol-sub {
    font-size: 11px;
    color: #7b8794;
    margin-top: 4px;
}

.hero-price-label {
    color: #7b8794;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: .7px;
}

.hero-price {
    font-size: 29px;
    line-height: 1;
    font-weight: 900;
    color: #17212d;
    margin-top: 5px;
}

.hero-change {
    font-size: 11px;
    font-weight: 800;
    margin-top: 6px;
}

.hero-positive {
    color: #16803c;
}

.hero-negative {
    color: #c62835;
}

.expiry-box {
    text-align: right;
}

.expiry-label {
    color: #7b8794;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: .6px;
}

.expiry-value {
    color: #17212d;
    font-size: 15px;
    font-weight: 850;
    margin-top: 6px;
}


/* ============================================================
   SECTION TITLES
   ============================================================ */

.fo-section {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 22px 0 11px;
}

.fo-section-title {
    color: #17212d;
    font-size: 15px;
    font-weight: 900;
    letter-spacing: .35px;
}

.fo-section-line {
    flex: 1;
    height: 1px;
    background: #e3e8ee;
    margin-left: 14px;
}


/* ============================================================
   METRIC CARDS
   ============================================================ */

.metric-grid {
    display: grid;
    grid-template-columns: repeat(6,1fr);
    gap: 10px;
}

.metric-box {
    background: white;
    border: 1px solid #e4e9ef;
    border-radius: 13px;
    padding: 14px;
    min-height: 95px;
    box-shadow: 0 3px 12px rgba(16,42,67,.035);
}

.metric-label {
    color: #84909c;
    font-size: 9px;
    font-weight: 900;
    letter-spacing: .7px;
}

.metric-value {
    color: #17212d;
    font-size: 19px;
    font-weight: 900;
    margin-top: 8px;
}

.metric-note {
    color: #a0aab5;
    font-size: 9px;
    margin-top: 6px;
}

.metric-green .metric-value {
    color: #16803c;
}

.metric-red .metric-value {
    color: #c62835;
}

.metric-blue .metric-value {
    color: #2166a5;
}


/* ============================================================
   DECISION PANEL
   ============================================================ */

.decision-wrap {
    display: grid;
    grid-template-columns: 1.5fr 1fr;
    gap: 14px;
}

.decision-main-card {
    background: white;
    border: 1px solid #e1e7ed;
    border-radius: 17px;
    padding: 24px;
    box-shadow: 0 5px 20px rgba(16,42,67,.055);
}

.decision-call {
    border-top: 5px solid #16a34a;
}

.decision-put {
    border-top: 5px solid #dc2626;
}

.decision-neutral {
    border-top: 5px solid #98a2b3;
}

.decision-label {
    color: #8995a2;
    font-size: 9px;
    font-weight: 900;
    letter-spacing: 1px;
}

.decision-value {
    font-size: 34px;
    font-weight: 950;
    margin-top: 7px;
    letter-spacing: -.8px;
}

.decision-call .decision-value {
    color: #15803d;
}

.decision-put .decision-value {
    color: #c62835;
}

.decision-neutral .decision-value {
    color: #475467;
}

.decision-description {
    color: #667085;
    font-size: 12px;
    line-height: 1.55;
    margin-top: 7px;
}

.decision-mini-grid {
    display: grid;
    grid-template-columns: repeat(4,1fr);
    gap: 8px;
    margin-top: 19px;
}

.decision-mini {
    background: #f7f9fb;
    border: 1px solid #e8edf2;
    border-radius: 10px;
    padding: 10px;
    text-align: center;
}

.decision-mini span {
    display: block;
    color: #8a95a1;
    font-size: 8px;
    font-weight: 900;
    letter-spacing: .5px;
}

.decision-mini b {
    display: block;
    color: #17212d;
    font-size: 16px;
    margin-top: 5px;
}


/* ============================================================
   STATUS PANEL
   ============================================================ */

.status-card {
    background: #0d1b2a;
    color: white;
    border-radius: 17px;
    padding: 23px;
    box-shadow: 0 5px 20px rgba(8,27,45,.10);
}

.status-label {
    color: #8fa7bb;
    font-size: 9px;
    font-weight: 900;
    letter-spacing: 1px;
}

.status-title {
    font-size: 22px;
    font-weight: 950;
    margin-top: 8px;
}

.status-green {
    color: #6ee7a0;
}

.status-yellow {
    color: #f8cf67;
}

.status-red {
    color: #ff858d;
}

.status-info {
    color: #9db0c1;
    font-size: 11px;
    line-height: 1.55;
    margin-top: 9px;
}

.status-price-grid {
    display: grid;
    grid-template-columns: repeat(3,1fr);
    gap: 7px;
    margin-top: 18px;
}

.status-price {
    background: rgba(255,255,255,.06);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 9px;
    padding: 9px;
    text-align: center;
}

.status-price span {
    display: block;
    color: #7f97aa;
    font-size: 8px;
    font-weight: 800;
}

.status-price b {
    display: block;
    font-size: 14px;
    margin-top: 4px;
}


/* ============================================================
   CHECKLIST
   ============================================================ */

.check-card {
    background: white;
    border: 1px solid #e3e8ee;
    border-radius: 15px;
    overflow: hidden;
    box-shadow: 0 3px 12px rgba(16,42,67,.035);
}

.check-row {
    display: grid;
    grid-template-columns: 1.3fr .65fr 2fr;
    align-items: center;
    gap: 12px;
    padding: 12px 17px;
    border-bottom: 1px solid #edf0f3;
}

.check-name {
    color: #344054;
    font-size: 11px;
    font-weight: 850;
}

.check-state {
    font-size: 10px;
    font-weight: 900;
}

.check-detail {
    color: #8a95a1;
    font-size: 10px;
}

.check-pass {
    color: #16803c;
}

.check-wait {
    color: #a56b00;
}

.check-fail {
    color: #c62835;
}

.check-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 13px 17px;
    background: #fafbfc;
}

.check-footer span {
    color: #7d8995;
    font-size: 9px;
    font-weight: 900;
    letter-spacing: .6px;
}

.check-footer b {
    color: #17212d;
    font-size: 18px;
}


/* ============================================================
   TRADE PLAN
   ============================================================ */

.plan-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
}

.plan-card {
    background: white;
    border: 1px solid #e1e7ed;
    border-radius: 17px;
    overflow: hidden;
    box-shadow: 0 4px 16px rgba(16,42,67,.045);
}

.plan-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px 18px;
    border-bottom: 1px solid #edf0f3;
}

.plan-call {
    border-top: 4px solid #16a34a;
}

.plan-put {
    border-top: 4px solid #dc2626;
}

.plan-title {
    font-size: 14px;
    font-weight: 950;
}

.plan-call .plan-title {
    color: #15803d;
}

.plan-put .plan-title {
    color: #c62835;
}

.plan-badge {
    border-radius: 20px;
    padding: 5px 9px;
    font-size: 8px;
    font-weight: 900;
    letter-spacing: .5px;
}

.badge-active {
    background: #e9f8ee;
    color: #16803c;
}

.badge-candidate {
    background: #fff8e8;
    color: #9a6700;
}

.badge-watch {
    background: #f1f3f5;
    color: #667085;
}

.plan-body {
    padding: 18px;
}

.plan-strike {
    color: #17212d;
    font-size: 25px;
    font-weight: 950;
}

.plan-expiry {
    color: #8b96a2;
    font-size: 10px;
    margin-top: 2px;
}

.plan-status {
    border-radius: 8px;
    padding: 8px;
    text-align: center;
    font-size: 9px;
    font-weight: 900;
    margin: 13px 0;
}

.plan-ready {
    background: #edf9f1;
    color: #16803c;
}

.plan-wait {
    background: #fff8e8;
    color: #9a6700;
}

.plan-no {
    background: #fff0f1;
    color: #c62835;
}

.plan-metrics {
    display: grid;
    grid-template-columns: repeat(4,1fr);
    gap: 7px;
}

.plan-metric {
    background: #f7f9fb;
    border-radius: 9px;
    padding: 9px;
}

.plan-metric span {
    display: block;
    color: #8b96a2;
    font-size: 8px;
    font-weight: 850;
}

.plan-metric b {
    display: block;
    color: #17212d;
    font-size: 14px;
    margin-top: 5px;
}

.plan-trigger {
    margin-top: 12px;
    padding: 11px;
    border-radius: 9px;
    background: #f8fafc;
    border: 1px solid #e7ebef;
}

.plan-trigger span {
    display: block;
    color: #8b96a2;
    font-size: 8px;
    font-weight: 900;
    letter-spacing: .5px;
}

.plan-trigger b {
    display: block;
    color: #344054;
    font-size: 10px;
    line-height: 1.45;
    margin-top: 5px;
}


/* ============================================================
   ENTRY / EXIT
   ============================================================ */

.entry-grid {
    display: grid;
    grid-template-columns: repeat(5,1fr);
    gap: 9px;
}

.entry-box {
    background: white;
    border: 1px solid #e3e8ee;
    border-radius: 12px;
    padding: 13px;
}

.entry-box span {
    color: #8995a1;
    font-size: 8px;
    font-weight: 900;
    letter-spacing: .6px;
}

.entry-box b {
    display: block;
    color: #17212d;
    font-size: 18px;
    margin-top: 6px;
}

.entry-box small {
    display: block;
    color: #a0aab5;
    font-size: 9px;
    margin-top: 5px;
}

.exit-box {
    margin-top: 9px;
    background: #0d1b2a;
    color: white;
    border-radius: 12px;
    padding: 13px 16px;
}

.exit-box span {
    color: #91a7b9;
    font-size: 8px;
    font-weight: 900;
    letter-spacing: .7px;
}

.exit-box b {
    display: block;
    color: #e9eff5;
    font-size: 10px;
    margin-top: 5px;
    line-height: 1.5;
}


/* ============================================================
   WHY TRADE
   ============================================================ */

.why-card {
    background: white;
    border: 1px solid #e3e8ee;
    border-radius: 14px;
    overflow: hidden;
}

.why-row {
    padding: 11px 16px;
    border-bottom: 1px solid #edf0f3;
    color: #475467;
    font-size: 10px;
    line-height: 1.45;
}

.why-row:last-child {
    border-bottom: 0;
}

.why-warning {
    background: #fff8e8;
    color: #916200;
}


/* ============================================================
   SUPPORT / RESISTANCE
   ============================================================ */

.sr-card {
    display: grid;
    grid-template-columns: 1fr 1.2fr 1fr;
    background: white;
    border: 1px solid #e2e8ee;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 3px 12px rgba(16,42,67,.035);
}

.sr-block {
    padding: 22px;
    text-align: center;
}

.sr-resistance {
    background: #fff7f7;
}

.sr-support {
    background: #f4fbf6;
}

.sr-label {
    font-size: 9px;
    font-weight: 900;
    letter-spacing: .6px;
}

.sr-resistance .sr-label {
    color: #c62835;
}

.sr-support .sr-label {
    color: #16803c;
}

.sr-value {
    color: #17212d;
    font-size: 25px;
    font-weight: 950;
    margin-top: 7px;
}

.sr-note {
    color: #8b96a2;
    font-size: 9px;
    margin-top: 4px;
}

.sr-center {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    border-left: 1px dashed #dce2e8;
    border-right: 1px dashed #dce2e8;
}

.sr-current {
    background: #17212d;
    color: white;
    border-radius: 30px;
    padding: 9px 16px;
    font-size: 14px;
    font-weight: 900;
}

.sr-room {
    color: #98a2b3;
    font-size: 9px;
    font-weight: 800;
    margin: 7px;
}


/* ============================================================
   SCANNER TABLE
   ============================================================ */

.scanner-title {
    color: white;
    font-size: 15px;
    font-weight: 900;
}

.scanner-subtitle {
    color: #91a7b9;
    font-size: 10px;
    line-height: 1.45;
    margin-top: 4px;
}

.scanner-count {
    margin-top: 13px;
    padding: 8px 10px;
    background: rgba(22,163,74,.12);
    border: 1px solid rgba(74,222,128,.18);
    border-radius: 8px;
    color: #86efac;
    font-size: 9px;
    font-weight: 800;
}


/* ============================================================
   TABS
   ============================================================ */

.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: white;
    padding: 5px;
    border-radius: 12px;
    border: 1px solid #e2e8ee;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    font-size: 11px;
    font-weight: 800;
}

.stTabs [aria-selected="true"] {
    background: #102a43;
    color: white;
}

.tab-banner {
    border-radius: 11px;
    padding: 12px 15px;
    margin-bottom: 15px;
    font-size: 10px;
    line-height: 1.5;
}

.tab-danger {
    background: #fff5f5;
    border: 1px solid #f1c7ca;
    color: #b4232f;
}

.tab-positive {
    background: #f1faf4;
    border: 1px solid #bde5c9;
    color: #147a3d;
}


/* ============================================================
   FOOTER
   ============================================================ */

.fo-footer {
    text-align: center;
    padding: 20px 0 5px;
    color: #98a2b3;
    font-size: 9px;
}


/* ============================================================
   RESPONSIVE
   ============================================================ */

@media(max-width:1100px) {
    .metric-grid {
        grid-template-columns: repeat(3,1fr);
    }

    .decision-wrap {
        grid-template-columns: 1fr;
    }
}

@media(max-width:800px) {
    .metric-grid {
        grid-template-columns: repeat(2,1fr);
    }

    .plan-grid,
    .sr-card {
        grid-template-columns: 1fr;
    }

    .sr-center {
        padding: 15px;
        border-left: 0;
        border-right: 0;
        border-top: 1px dashed #dce2e8;
        border-bottom: 1px dashed #dce2e8;
    }

    .entry-grid {
        grid-template-columns: repeat(2,1fr);
    }

    .fo-header-inner {
        align-items: flex-start;
    }

    .fo-live {
        display: none;
    }
}

@media(max-width:600px) {
    .metric-grid,
    .entry-grid {
        grid-template-columns: 1fr 1fr;
    }

    .plan-metrics,
    .decision-mini-grid {
        grid-template-columns: 1fr 1fr;
    }

    .check-row {
        grid-template-columns: 1fr .8fr;
    }

    .check-detail {
        grid-column: 1 / -1;
    }

    .fo-title {
        font-size: 20px;
    }

    .decision-value {
        font-size: 27px;
    }
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# UI HELPERS
# ============================================================

def _num_or_dash(v, decimals=2):
    try:
        x = float(v)
        if not np.isfinite(x):
            return "—"
        return f"{x:.{decimals}f}"
    except Exception:
        return "—"


def _status_class(value):
    v = str(value).upper()

    if "READY" in v or "BUY" in v or "PASS" in v:
        return "status-green"

    if "WAIT" in v:
        return "status-yellow"

    if "NO TRADE" in v or "FAIL" in v:
        return "status-red"

    return "status-grey"


def _check_row(label, state, detail):
    if state == "PASS":
        icon = "●"
        css = "check-pass"
    elif state == "WAIT":
        icon = "●"
        css = "check-wait"
    else:
        icon = "●"
        css = "check-fail"

    return f"""
    <div class="check-row">
        <div class="check-name">{label}</div>
        <div class="check-state {css}">{icon} {state}</div>
        <div class="check-detail">{detail}</div>
    </div>
    """


# ============================================================
# HEADER
# ============================================================

live_class = "fo-live-open" if market_open else "fo-live-closed"
live_text = "● LIVE DATA" if market_open else "● MARKET CLOSED"

st.markdown(
    f"""
<div class="fo-header">
    <div class="fo-header-inner">

        <div class="fo-brand">
            <div class="fo-brand-icon">📊</div>

            <div>
                <div class="fo-title">FO PRO Trader Assistant</div>
                <div class="fo-subtitle">
                    Options Analysis • Multi-Timeframe Engine • Powered by Upstox
                </div>
            </div>
        </div>

        <div class="fo-live {live_class}">
            {live_text}
        </div>

    </div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SYMBOL HERO
# ============================================================

change_class = "hero-positive" if net_change >= 0 else "hero-negative"

st.markdown(
    f"""
<div class="symbol-hero">

    <div style="display:grid;grid-template-columns:1.7fr 1fr 1fr;gap:20px;align-items:center;">

        <div>
            <div class="symbol-name">{symbol} — F&O Analysis</div>
            <div class="symbol-sub">
                Live underlying • Option-chain analysis • Multi-timeframe confirmation
            </div>
        </div>

        <div>
            <div class="hero-price-label">LAST TRADED PRICE</div>
            <div class="hero-price">{fmt_price(spot)}</div>
            <div class="hero-change {change_class}">
                {net_change:+.2f} ({change_pct:+.2f}%)
            </div>
        </div>

        <div class="expiry-box">
            <div class="expiry-label">NEAREST EXPIRY</div>
            <div class="expiry-value">{selected_expiry}</div>
            <div class="symbol-sub">
                Updated {str(updated)[:19]}
            </div>
        </div>

    </div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SECTION HELPER
# ============================================================

def section_header(title):
    st.markdown(
        f"""
        <div class="fo-section">
            <div class="fo-section-title">{title}</div>
            <div class="fo-section-line"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# MARKET SNAPSHOT
# ============================================================

section_header("MARKET SNAPSHOT")

bias_class = (
    "metric-green"
    if tech["trend"] == "Bullish"
    else "metric-red"
    if tech["trend"] == "Bearish"
    else ""
)

pcr_display = f"{pcr:.2f}" if np.isfinite(pcr) else "—"

st.markdown(
    f"""
<div class="metric-grid">

    <div class="metric-box">
        <div class="metric-label">LAST PRICE</div>
        <div class="metric-value">{fmt_price(spot)}</div>
        <div class="metric-note">LIVE UNDERLYING</div>
    </div>

    <div class="metric-box {bias_class}">
        <div class="metric-label">MARKET BIAS</div>
        <div class="metric-value">{tech["trend"]}</div>
        <div class="metric-note">DAILY HEADLINE TREND</div>
    </div>

    <div class="metric-box">
        <div class="metric-label">PCR</div>
        <div class="metric-value">{pcr_display}</div>
        <div class="metric-note">PUT / CALL OI</div>
    </div>

    <div class="metric-box metric-green">
        <div class="metric-label">SUPPORT</div>
        <div class="metric-value">{fmt_price(support)}</div>
        <div class="metric-note">PUT OI WALL</div>
    </div>

    <div class="metric-box metric-red">
        <div class="metric-label">RESISTANCE</div>
        <div class="metric-value">{fmt_price(resistance)}</div>
        <div class="metric-note">CALL OI WALL</div>
    </div>

    <div class="metric-box">
        <div class="metric-label">RSI</div>
        <div class="metric-value">{tech["rsi"]:.1f}</div>
        <div class="metric-note">DAILY RSI 14</div>
    </div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# TRADE DECISION
# ============================================================

section_header("TRADE DECISION")

decision_icon = (
    "🟢"
    if decision == "CALL BUY"
    else "🔴"
    if decision == "PUT BUY"
    else "🟡"
    if "WAIT" in decision
    else "⚪"
)

decision_css = (
    "decision-call"
    if decision == "CALL BUY"
    else "decision-put"
    if decision == "PUT BUY"
    else "decision-neutral"
)

decision_sub = {
    "CALL BUY":
        "Bullish conditions are aligned. Follow the entry trigger and risk levels.",
    "PUT BUY":
        "Bearish conditions are aligned. Follow the entry trigger and risk levels.",
    "WAIT FOR TRIGGER":
        "The setup is developing. Wait for the underlying to reach the trigger.",
    "WAIT FOR CONFIRMATION":
        "The trigger has been reached, but confirmation conditions are incomplete.",
    "NO TRADE":
        "Current conditions do not satisfy the engine's quality gate.",
}.get(
    decision,
    "Review the current live conditions before taking action.",
)

st.markdown(
    f"""
<div class="decision-wrap">

    <div class="decision-main-card {decision_css}">

        <div class="decision-label">ENGINE DECISION</div>

        <div class="decision-value">
            {decision_icon} {decision}
        </div>

        <div class="decision-description">
            {decision_sub}
        </div>

        <div class="decision-mini-grid">

            <div class="decision-mini">
                <span>CALL SCORE</span>
                <b>{ce_score:.0f}</b>
            </div>

            <div class="decision-mini">
                <span>PUT SCORE</span>
                <b>{pe_score:.0f}</b>
            </div>

            <div class="decision-mini">
                <span>TREND</span>
                <b>{overall_direction}</b>
            </div>

            <div class="decision-mini">
                <span>CONFIDENCE</span>
                <b>{confidence}/100</b>
            </div>

        </div>

    </div>

    <div class="status-card">

        <div class="status-label">CURRENT TRADE STATUS</div>

        <div class="status-title {_status_class(decision)}">
            {decision}
        </div>

        <div class="status-info">
            The engine evaluates trend alignment, VWAP, OI structure,
            option liquidity, Delta, PoP, spread and breakout confirmation.
        </div>

        <div class="status-price-grid">

            <div class="status-price">
                <span>SPOT</span>
                <b>{fmt_price(spot)}</b>
            </div>

            <div class="status-price">
                <span>CE SCORE</span>
                <b>{ce_score:.0f}</b>
            </div>

            <div class="status-price">
                <span>PE SCORE</span>
                <b>{pe_score:.0f}</b>
            </div>

        </div>

    </div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# TRADE STATUS / TRIGGER
# ============================================================

section_header("TRADE STATUS")

status_plan = best_plan

if status_plan:

    actionable_decision = decision in {"CALL BUY", "PUT BUY"}

    if actionable_decision:
        status = decision
    elif decision == "WAIT FOR TRIGGER":
        status = "WAIT FOR TRIGGER"
    elif decision == "WAIT FOR CONFIRMATION":
        status = "WAIT FOR CONFIRMATION"
    else:
        status = "NO TRADE"

    trigger_distance = abs(
        spot - status_plan["trigger_level"]
    )

    if status == "NO TRADE":
        status_note = (
            f"Monitor the "
            f"{'CALL' if status_plan['side'] == 'CE' else 'PUT'} "
            f"candidate only. The trigger is "
            f"{fmt_price(status_plan['trigger_level'])}, "
            "but the quality gate is currently not satisfied."
        )
    else:
        status_note = status_plan["trigger"]

    status_class = _status_class(status)

    st.markdown(
        f"""
<div class="status-card">

    <div class="status-label">ENGINE STATUS</div>

    <div class="status-title {status_class}">
        {status}
    </div>

    <div class="status-info">
        {status_note}
    </div>

    <div class="status-price-grid">

        <div class="status-price">
            <span>CURRENT PRICE</span>
            <b>{fmt_price(spot)}</b>
        </div>

        <div class="status-price">
            <span>TRIGGER</span>
            <b>{fmt_price(status_plan["trigger_level"])}</b>
        </div>

        <div class="status-price">
            <span>DISTANCE</span>
            <b>{fmt_price(trigger_distance)}</b>
        </div>

    </div>

</div>
""",
        unsafe_allow_html=True,
    )

else:

    st.markdown(
        """
<div class="status-card">

    <div class="status-label">ENGINE STATUS</div>

    <div class="status-title status-red">
        NO VALID PLAN
    </div>

    <div class="status-info">
        No usable option contract was returned from the current live option chain.
        No trade should be considered.
    </div>

</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# TRADE CHECKLIST
# ============================================================

direction_pass = overall_direction in {"Bullish", "Bearish"}

mtf_pass = overall_alignment >= 2

oi_pass = (
    np.isfinite(support)
    and np.isfinite(resistance)
    and support < spot < resistance
)

vwap_value = safe_float(
    tf5.get("vwap"),
    spot,
)

if best_plan:

    if best_plan["side"] == "CE":
        vwap_pass = spot >= vwap_value * 0.997
    else:
        vwap_pass = spot <= vwap_value * 1.003

else:
    vwap_pass = False

breakout_state = (
    "PASS"
    if (
        best_plan
        and best_plan.get("trigger_hit")
        and best_plan.get("candle_confirmed")
        and best_plan.get("volume_confirmed")
    )
    else "WAIT"
)

check_overall = sum(
    [
        direction_pass,
        mtf_pass,
        oi_pass,
        vwap_pass,
        breakout_state == "PASS",
    ]
)

section_header("TRADE CHECKLIST")

check_html = (
    _check_row(
        "Market Direction",
        "PASS" if direction_pass else "FAIL",
        f"{overall_direction} market bias",
    )
    +
    _check_row(
        "Multi-Timeframe",
        "PASS" if mtf_pass else "FAIL",
        f"{overall_alignment}/3 timeframes aligned",
    )
    +
    _check_row(
        "OI Structure",
        "PASS" if oi_pass else "FAIL",
        f"Support {fmt_price(support)} • Resistance {fmt_price(resistance)}",
    )
    +
    _check_row(
        "VWAP",
        "PASS" if vwap_pass else "FAIL",
        f"5m VWAP {fmt_price(vwap_value)}",
    )
    +
    _check_row(
        "Breakout Confirmation",
        breakout_state,
        "Trigger + 5m momentum + volume",
    )
)

st.markdown(
    f"""
<div class="check-card">

    {check_html}

    <div class="check-footer">
        <span>OVERALL CHECKLIST</span>
        <b>{check_overall}/5</b>
    </div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# TRADE PLAN
# ============================================================

section_header("TRADE PLAN")

active_side = (
    "CE"
    if decision == "CALL BUY"
    else "PE"
    if decision == "PUT BUY"
    else None
)

candidate_side = best_plan["side"] if best_plan else None


def render_plan(plan, label, active=False, candidate=False):

    if not plan:

        st.markdown(
            f"""
            <div class="plan-card">
                <div class="plan-body">
                    <div class="plan-title">{label} BUY</div>
                    <div style="margin-top:12px;color:#98a2b3;font-size:10px;">
                        No valid option plan returned.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        return

    side = plan["side"]

    icon = "🟢" if side == "CE" else "🔴"

    contract = "CE" if side == "CE" else "PE"

    status = str(
        plan.get("readiness", "NO TRADE")
    )

    if status == "READY":
        status_class = "plan-ready"
    elif "WAIT" in status:
        status_class = "plan-wait"
    else:
        status_class = "plan-no"

    if active:
        badge = '<span class="plan-badge badge-active">★ ACTIVE TRADE</span>'
    elif candidate:
        badge = '<span class="plan-badge badge-candidate">◉ CANDIDATE ONLY</span>'
    else:
        badge = '<span class="plan-badge badge-watch">REFERENCE</span>'

    st.markdown(
        f"""
<div class="plan-card {'plan-call' if side == 'CE' else 'plan-put'}">

    <div class="plan-header">

        <div class="plan-title">
            {icon} {label} BUY
        </div>

        {badge}

    </div>

    <div class="plan-body">

        <div class="plan-strike">
            {plan["strike"]:.0f} {contract}
        </div>

        <div class="plan-expiry">
            Expiry {selected_expiry}
        </div>

        <div class="plan-status {status_class}">
            {status}
        </div>

        <div class="plan-metrics">

            <div class="plan-metric">
                <span>ENTRY</span>
                <b>{fmt_price(plan["entry"])}</b>
            </div>

            <div class="plan-metric">
                <span>STOP LOSS</span>
                <b>{fmt_price(plan["sl"])}</b>
            </div>

            <div class="plan-metric">
                <span>TARGET 1</span>
                <b>{fmt_price(plan["target1"])}</b>
            </div>

            <div class="plan-metric">
                <span>TARGET 2</span>
                <b>{fmt_price(plan["target2"])}</b>
            </div>

            <div class="plan-metric">
                <span>PoP</span>
                <b>{_num_or_dash(plan.get("pop"),1)}%</b>
            </div>

            <div class="plan-metric">
                <span>DELTA</span>
                <b>{_num_or_dash(plan.get("delta"),2)}</b>
            </div>

            <div class="plan-metric">
                <span>IV</span>
                <b>{_num_or_dash(plan.get("iv"),1)}%</b>
            </div>

            <div class="plan-metric">
                <span>R:R T2</span>
                <b>1:{_num_or_dash(plan.get("rr2"),2)}</b>
            </div>

        </div>

        <div class="plan-trigger">

            <span>ENTRY TRIGGER</span>

            <b>
                {plan["trigger"]}
            </b>

        </div>

    </div>

</div>
""",
        unsafe_allow_html=True,
    )


p1, p2 = st.columns(2)

with p1:
    render_plan(
        ce_plan,
        "CALL",
        active_side == "CE",
        candidate_side == "CE" and active_side is None,
    )

with p2:
    render_plan(
        pe_plan,
        "PUT",
        active_side == "PE",
        candidate_side == "PE" and active_side is None,
    )


# ============================================================
# ENTRY / EXIT
# ============================================================

section_header("ENTRY / EXIT")

if best_plan and decision in {"CALL BUY", "PUT BUY"}:

    entry_distance = abs(
        spot - best_plan["trigger_level"]
    )

    st.markdown(
        f"""
<div class="entry-grid">

    <div class="entry-box">
        <span>CURRENT PRICE</span>
        <b>{fmt_price(spot)}</b>
        <small>Underlying</small>
    </div>

    <div class="entry-box">
        <span>ENTRY TRIGGER</span>
        <b>{fmt_price(best_plan["trigger_level"])}</b>
        <small>Distance {fmt_price(entry_distance)}</small>
    </div>

    <div class="entry-box">
        <span>STOP LOSS</span>
        <b>{fmt_price(best_plan["sl"])}</b>
        <small>Option premium</small>
    </div>

    <div class="entry-box">
        <span>TARGET 1</span>
        <b>{fmt_price(best_plan["target1"])}</b>
        <small>Partial exit</small>
    </div>

    <div class="entry-box">
        <span>TARGET 2</span>
        <b>{fmt_price(best_plan["target2"])}</b>
        <small>Final target</small>
    </div>

</div>

<div class="exit-box">
    <span>EXIT / INVALIDATION RULE</span>
    <b>{best_plan["exit"]}</b>
</div>
""",
        unsafe_allow_html=True,
    )

else:

    st.warning(
        "NO TRADE: entry, stop-loss and targets are shown only as reference. "
        "Wait for CALL BUY or PUT BUY before entering."
    )


# ============================================================
# WHY TRADE / WHY NO TRADE
# ============================================================

section_title = (
    "WHY THIS TRADE?"
    if decision in {"CALL BUY", "PUT BUY"}
    else "WHY NO TRADE?"
)

section_header(section_title)

why_items = []

if best_plan:

    side_name = (
        "CALL"
        if best_plan["side"] == "CE"
        else "PUT"
    )

    if decision in {"CALL BUY", "PUT BUY"}:

        why_items = [
            f"{tf5['trend']} 5m trend supports the {side_name} direction.",
            f"{tf30['trend']} 30m trend and {daily_tech['trend']} daily trend are part of the confirmation framework.",
            f"5m VWAP is {fmt_price(vwap_value)} and price is {'above' if spot >= vwap_value else 'below'} it.",
            f"OI structure shows support at {fmt_price(support)} and resistance at {fmt_price(resistance)}.",
            f"Active option PoP is {_num_or_dash(best_plan['pop'],1)}% with Delta {_num_or_dash(best_plan['delta'],2)}.",
            f"Option spread is {_num_or_dash(best_plan['spread_pct'],1)}% with volume {fmt_num(best_plan['volume'])}.",
        ]

    else:

        why_items = [
            f"The {side_name} is the strongest current candidate, but it is NOT an approved entry.",
            f"Market direction is {overall_direction} with {overall_alignment}/3 timeframes aligned.",
            f"5m trend: {tf5['trend']} • 30m: {tf30['trend']} • Daily: {daily_tech['trend']}.",
            f"Price is {'above' if spot >= vwap_value else 'below'} the 5m VWAP at {fmt_price(vwap_value)}.",
            f"OI structure shows support at {fmt_price(support)} and resistance at {fmt_price(resistance)}.",
            f"Candidate PoP is {_num_or_dash(best_plan['pop'],1)}% with Delta {_num_or_dash(best_plan['delta'],2)}.",
        ]

    if best_plan["fail_reasons"]:
        why_items.append(
            "⚠ " + "; ".join(best_plan["fail_reasons"])
        )

else:

    why_items = [
        "No valid option plan is currently available."
    ]


why_html = ""

for item in why_items:

    warning = item.startswith("⚠")

    clean_item = item.lstrip("⚠ ")

    why_html += f"""
    <div class="why-row {'why-warning' if warning else ''}">
        {"⚠" if warning else "✓"} {clean_item}
    </div>
    """

st.markdown(
    f"""
<div class="why-card">
    {why_html}
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SUPPORT / RESISTANCE OI MAP
# ============================================================

section_header("SUPPORT / RESISTANCE + OI MAP")

put_row = nearest_row(chain, support)
call_row = nearest_row(chain, resistance)

put_oi = (
    put_row["PE OI"]
    if put_row is not None
    else np.nan
)

call_oi = (
    call_row["CE OI"]
    if call_row is not None
    else np.nan
)

support_room = (
    max((spot - support) / max(spot, 1) * 100, 0)
    if np.isfinite(support)
    else np.nan
)

resistance_room = (
    max((resistance - spot) / max(spot, 1) * 100, 0)
    if np.isfinite(resistance)
    else np.nan
)

st.markdown(
    f"""
<div class="sr-card">

    <div class="sr-block sr-resistance">

        <div class="sr-label">
            🔴 CALL OI WALL
        </div>

        <div class="sr-value">
            {fmt_price(resistance)}
        </div>

        <div class="sr-note">
            OI {fmt_num(call_oi)}
        </div>

    </div>


    <div class="sr-center">

        <div class="sr-room">
            +{_num_or_dash(resistance_room,2)}% room
        </div>

        <div class="sr-current">
            ● {fmt_price(spot)}
        </div>

        <div class="sr-room">
            -{_num_or_dash(support_room,2)}% room
        </div>

    </div>


    <div class="sr-block sr-support">

        <div class="sr-label">
            🟢 PUT OI WALL
        </div>

        <div class="sr-value">
            {fmt_price(support)}
        </div>

        <div class="sr-note">
            OI {fmt_num(put_oi)}
        </div>

    </div>

</div>
""",
    unsafe_allow_html=True,
)


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


# ============================================================
# TAB 1 — BEST TRADE
# ============================================================

with tab1:

    if decision == "NO TRADE":

        st.markdown(
            """
<div class="tab-banner tab-danger">
    <b>⚪ NO TRADE</b><br>
    Current conditions do not satisfy the quality gate.
    Wait for a new setup rather than forcing an entry.
</div>
""",
            unsafe_allow_html=True,
        )

    elif best_plan:

        tab_icon = (
            "🟢"
            if best_plan["side"] == "CE"
            else "🔴"
        )

        st.markdown(
            f"""
<div class="tab-banner tab-positive">
    <b>{tab_icon} {decision}</b><br>
    Strike {best_plan["strike"]:.0f}
    • Entry {fmt_price(best_plan["entry"])}
    • SL {fmt_price(best_plan["sl"])}
    • T1 {fmt_price(best_plan["target1"])}
    • T2 {fmt_price(best_plan["target2"])}
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("### Engine Summary")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "CALL SCORE",
        f"{ce_score:.0f}/100",
    )

    c2.metric(
        "PUT SCORE",
        f"{pe_score:.0f}/100",
    )

    c3.metric(
        "ALIGNMENT",
        f"{overall_alignment}/3",
    )

    c4.metric(
        "CHECKLIST",
        f"{check_overall}/5",
    )


# ============================================================
# TAB 2 — OPTION CHAIN
# ============================================================

with tab2:

    st.markdown(
        f"### Live Option Chain"
    )

    st.caption(
        f"{symbol} • Expiry {selected_expiry} • "
        "Closest 15 strikes to ATM"
    )

    view = chain.copy()

    display = pd.DataFrame(
        {
            "Strike":
                view["Strike"].round(0).astype(int),

            "CE LTP":
                view["CE LTP"].round(2),

            "CE OI":
                view["CE OI"].round(0).astype("int64"),

            "CE Chg OI":
                view["CE Chg OI"].round(0).astype("int64"),

            "CE IV":
                view["CE IV"].round(1),

            "CE Delta":
                view["CE Delta"].round(3),

            "CE PoP":
                view["CE PoP"].round(1),

            "PE LTP":
                view["PE LTP"].round(2),

            "PE OI":
                view["PE OI"].round(0).astype("int64"),

            "PE Chg OI":
                view["PE Chg OI"].round(0).astype("int64"),

            "PE IV":
                view["PE IV"].round(1),

            "PE Delta":
                view["PE Delta"].round(3),

            "PE PoP":
                view["PE PoP"].round(1),
        }
    )

    display["_distance"] = (
        display["Strike"] - spot
    ).abs()

    display = (
        display
        .sort_values("_distance")
        .drop(columns="_distance")
        .head(15)
    )

    def style_chain(row):

        styles = [
            ""
            for _ in row.index
        ]

        strike = row["Strike"]

        if strike == int(round(atm_strike)):
            styles = [
                "font-weight:700;"
                for _ in row.index
            ]

        if (
            best_plan
            and strike == int(round(best_plan["strike"]))
        ):
            styles = [
                "font-weight:900;"
                for _ in row.index
            ]

        return styles

    styled_chain = display.style.apply(
        style_chain,
        axis=1,
    )

    st.dataframe(
        styled_chain,
        use_container_width=True,
        hide_index=True,
        height=520,
    )

    st.caption(
        "ATM and selected strikes are emphasized. "
        "CE/PE LTP, OI, Change OI, IV, Delta and PoP "
        "remain available."
    )


# ============================================================
# TAB 3 — MARKET ANALYSIS
# ============================================================

with tab3:

    st.markdown("### Market Technicals")

    a1, a2, a3, a4 = st.columns(4)

    a1.metric(
        "EMA 20",
        fmt_price(daily_tech["ema20"]),
    )

    a2.metric(
        "EMA 50",
        fmt_price(daily_tech["ema50"]),
    )

    a3.metric(
        "ATR 14",
        fmt_price(daily_tech["atr"]),
    )

    a4.metric(
        "5m VWAP",
        fmt_price(tf5["vwap"]),
    )

    st.markdown("### Multi-Timeframe Confirmation")

    mtf = pd.DataFrame(
        [
            {
                "Timeframe": "5 Minute",
                "Trend": tf5["trend"],
                "RSI": round(tf5["rsi"],1),
                "ADX": round(tf5["adx"],1),
                "Momentum %": round(tf5["momentum"],2),
                "VWAP": fmt_price(tf5["vwap"]),
            },
            {
                "Timeframe": "30 Minute",
                "Trend": tf30["trend"],
                "RSI": round(tf30["rsi"],1),
                "ADX": round(tf30["adx"],1),
                "Momentum %": round(tf30["momentum"],2),
                "VWAP": fmt_price(tf30["vwap"]),
            },
            {
                "Timeframe": "Daily",
                "Trend": daily_tech["trend"],
                "RSI": round(daily_tech["rsi"],1),
                "ADX": round(daily_tech["adx"],1),
                "Momentum %": round(daily_tech["momentum"],2),
                "VWAP": fmt_price(daily_tech["vwap"]),
            },
        ]
    )

    st.dataframe(
        mtf,
        use_container_width=True,
        hide_index=True,
    )

    left, right = st.columns(2)

    with left:

        st.markdown("### 🟢 Support / Put OI")

        st.write(
            f"Major support: **{fmt_price(support)}**"
        )

        if put_row is not None:

            st.write(
                f"Put OI: **{fmt_num(put_row['PE OI'])}**"
            )

            st.write(
                f"Put Chg OI: **{fmt_num(put_row['PE Chg OI'])}**"
            )

    with right:

        st.markdown("### 🔴 Resistance / Call OI")

        st.write(
            f"Major resistance: **{fmt_price(resistance)}**"
        )

        if call_row is not None:

            st.write(
                f"Call OI: **{fmt_num(call_row['CE OI'])}**"
            )

            st.write(
                f"Call Chg OI: **{fmt_num(call_row['CE Chg OI'])}**"
            )

    if not candles.empty:

        st.markdown("### Price Trend")

        chart = (
            candles
            .set_index("timestamp")[["close"]]
            .tail(80)
        )

        st.line_chart(
            chart,
            use_container_width=True,
        )


# ============================================================
# TAB 4 — ENGINE
# ============================================================

with tab4:

    st.markdown("### Live-data decision framework")

    st.markdown(
        """
### 1. Market Direction

- Live underlying spot
- 5-minute trend
- 30-minute trend
- Daily trend
- EMA20 / EMA50
- RSI
- ADX
- Momentum
- Intraday VWAP

### 2. Option-Chain Structure

- Put OI
- Call OI
- Change in OI
- PCR
- OI-derived support
- OI-derived resistance

### 3. Option Quality

- LTP
- Bid / Ask spread
- Volume
- Open Interest
- IV
- Delta
- Upstox PoP

### 4. Trade Plan

- Entry trigger
- Entry price
- Stop Loss
- Target 1
- Target 2
- Exit / invalidation rule
- Risk / Reward

### 5. Quality Gate

- Minimum setup score: **72/100**
- At least **2 of 3 timeframes** must agree
- VWAP must confirm the intraday direction
- Short-term trend conflict blocks the setup
- Delta must remain within the configured range
- Option liquidity and spread are checked
- Upstox PoP must be at least **55%**
- Breakout requires 5m confirmation
- Volume confirmation is preferred/required by the readiness logic
- A close OI wall can block a setup
- Engine can return **READY**, **WAIT FOR TRIGGER**,
  **WAIT FOR CONFIRMATION**, or **NO TRADE**

> The score is a rule-based setup-quality measure.
> It is not a backtested win rate and does not guarantee profit.
"""
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.markdown(
    f"""
<div class="fo-footer">

    LIVE UPSTOX SNAPSHOT • {symbol} • EXPIRY {selected_expiry}
    • UPDATED {updated}

    <br>

    Educational / decision-support use only.
    Review live market conditions and risk before trading.

</div>
""",
    unsafe_allow_html=True,
)
