import gzip
import json
import html
import math
import os
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests
import streamlit as st
import threading
import time

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# ============================================================
# FO PRO TRADER ASSISTANT — LIVE UPSTOX VERSION
# Restored fuller trade-plan design:
# PoP, Entry, SL, Target 1-4, Exit, Delta, IV,
# PCR, OI support/resistance, live option chain and analysis.
# ============================================================

st.set_page_config(
    page_title="FO PRO Trader Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# App password login removed at the user's request.

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
.topbar-title {font-size:30px;font-weight:800;}
.topbar-sub {font-size:16px;opacity:.82;margin-top:3px;}
.status-pill {
    display:inline-block;padding:7px 12px;border-radius:20px;
    background:#1f9d55;color:white;font-size:15px;font-weight:700;
}
.card {
    background:white;border:1px solid #e7ebf0;border-radius:14px;
    padding:18px;margin-bottom:16px;box-shadow:0 2px 8px rgba(16,42,67,.04);
}
.section-title {font-size:23px;font-weight:800;color:#182230;margin-bottom:12px;}
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

/* ============================================================
   REDESIGNED DASHBOARD VISUAL SYSTEM
   ============================================================ */
.topbar-dashboard {
    display:flex;align-items:center;justify-content:space-between;gap:18px;
}
.header-live,.live-block,.closed-block {
    color:#fff;padding:10px 16px;border-radius:9px;font-size:16px;
    font-weight:800;letter-spacing:.2px;text-align:center;white-space:nowrap;
}
.header-live { background:rgba(255,255,255,.14); }
.live-block { background:#16a34a; }
.closed-block { background:#dc2626; }
.hero-price {font-size:32px;font-weight:850;line-height:1.05;color:#182230;}
.section-heading {
    font-size:22px;font-weight:850;color:#182230;margin:20px 0 10px;
    letter-spacing:.15px;
}
.metric-card,.entry-card {
    background:#fff;border:1px solid #e7ebf0;border-radius:13px;
    padding:15px 14px;min-height:105px;box-shadow:0 2px 8px rgba(16,42,67,.035);
}
.metric-card span,.entry-card span,.decision-stats span,.status-grid span,
