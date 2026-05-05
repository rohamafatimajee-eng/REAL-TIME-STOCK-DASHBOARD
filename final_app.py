import streamlit as st
import time
import random
import requests
from datetime import datetime
import pandas as pd
import os

# ---------- API KEYS ----------
try:
    API_KEY = st.secrets["APCA_API_KEY_ID"]
    SECRET_KEY = st.secrets["APCA_API_SECRET_KEY"]
    USE_REAL = True
except:
    from dotenv import load_dotenv
    load_dotenv()
    API_KEY = os.getenv("APCA_API_KEY_ID")
    SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
    USE_REAL = bool(API_KEY)

st.set_page_config(page_title="Real-Time Dashboard", layout="wide")
st.title("📈 Real-Time Stock Dashboard")

# ---------- SESSION ----------
if "symbols" not in st.session_state:
    st.session_state.symbols = ["AAPL","MSFT","GOOGL","AMZN","TSLA","META","NFLX","NVDA"]
if "prices" not in st.session_state:
    st.session_state.prices = {s: 0.0 for s in st.session_state.symbols}
if "alerts" not in st.session_state:
    st.session_state.alerts = {}
if "triggered" not in st.session_state:
    st.session_state.triggered = set()
if "history" not in st.session_state:
    st.session_state.history = []
if "streaming" not in st.session_state:
    st.session_state.streaming = False
if "use_real" not in st.session_state:
    st.session_state.use_real = USE_REAL

# ---------- FUNCTION TO FETCH REAL PRICES (REST API) ----------
@st.cache_data(ttl=5)
def fetch_alpaca_prices(symbols):
    """Fetch latest trade prices from Alpaca (REST, no WebSocket)"""
    headers = {"APCA-API-KEY-ID": API_KEY, "APCA-API-SECRET-KEY": SECRET_KEY}
    prices = {}
    for sym in symbols:
        try:
            url = f"https://data.alpaca.markets/v2/stocks/{sym}/trades/latest"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                prices[sym] = round(data["trade"]["p"], 2)
            else:
                prices[sym] = None
        except:
            prices[sym] = None
    return prices

# ---------- SIDEBAR ----------
st.sidebar.header("🌐 Data Source")
use_real_check = st.sidebar.checkbox("Use Real Alpaca Data", value=st.session_state.use_real, disabled=not USE_REAL)
st.session_state.use_real = use_real_check and USE_REAL

st.sidebar.header("➕ Add Ticker")
new_sym = st.sidebar.text_input("Symbol", "").upper()
if st.sidebar.button("Add") and new_sym and new_sym not in st.session_state.symbols:
    st.session_state.symbols.append(new_sym)
    st.session_state.prices[new_sym] = 0.0
    st.rerun()
if st.sidebar.button("Remove Last") and len(st.session_state.symbols) > 1:
    removed = st.session_state.symbols.pop()
    st.session_state.prices.pop(removed, None)
    st.rerun()

st.sidebar.header("🔔 Alerts")
alert_sym = st.sidebar.selectbox("Symbol", st.session_state.symbols)
alert_val = st.sidebar.number_input("Price > $", 100.0, step=10.0)
if st.sidebar.button("Set Alert"):
    st.session_state.alerts[alert_sym] = alert_val
if st.sidebar.button("Clear Alerts"):
    st.session_state.alerts.clear()
    st.session_state.triggered.clear()

# ---------- START/STOP ----------
col1, col2 = st.columns(2)
with col1:
    if st.button("▶️ START STREAMING"):
        st.session_state.streaming = True
        st.session_state.last_update = time.time()
        st.rerun()
with col2:
    if st.button("⏹️ STOP STREAMING"):
        st.session_state.streaming = False
        st.rerun()

# ---------- UPDATE PRICES ----------
if st.session_state.streaming:
    now = time.time()
    if now - st.session_state.get("last_update", 0) >= 3:
        if st.session_state.use_real:
            # Real API fetch
            real_prices = fetch_alpaca_prices(st.session_state.symbols)
            for sym, price in real_prices.items():
                if price is not None:
                    st.session_state.prices[sym] = price
        else:
            # Demo mode
            for sym in st.session_state.symbols:
                old = st.session_state.prices.get(sym, 100)
                if old == 0: old = 100
                change = random.uniform(-2, 2)
                new_price = round(max(50, min(200, old + change)), 2)
                st.session_state.prices[sym] = new_price
        
        # Alert check
        for sym, price in st.session_state.prices.items():
            if sym in st.session_state.alerts and price > st.session_state.alerts[sym]:
                if sym not in st.session_state.triggered:
                    st.session_state.triggered.add(sym)
        
        # History
        st.session_state.history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "symbols": st.session_state.prices.copy()
        })
        if len(st.session_state.history) > 100:
            st.session_state.history = st.session_state.history[-100:]
        
        st.session_state.last_update = now
        st.rerun()
    
    # Display
    source = "Real Alpaca" if st.session_state.use_real else "Demo (random)"
    st.success(f"🟢 STREAMING ACTIVE - Source: {source}")
    cols = st.columns(4)
    for i, sym in enumerate(st.session_state.symbols):
        price = st.session_state.prices.get(sym, 0)
        icon = "🔔 " if sym in st.session_state.alerts else ""
        cols[i % 4].metric(icon + sym, f"${price:.2f}" if price > 0 else "Loading...")
    
    if st.session_state.triggered:
        st.warning(f"🔔 Alert: {list(st.session_state.triggered)[-1]} crossed threshold!")
    
    time.sleep(1)
    st.rerun()
else:
    st.info("⚡ Click START STREAMING")
    cols = st.columns(4)
    for i, sym in enumerate(st.session_state.symbols):
        cols[i % 4].metric(sym, "Paused")

# Expanders
with st.expander("🔔 Alert History"):
    for a in st.session_state.triggered:
        st.warning(a)
    if not st.session_state.triggered:
        st.info("No alerts")
with st.expander("📜 Export"):
    if st.button("Export CSV"):
        df = pd.DataFrame(st.session_state.history)
        st.download_button("Download", df.to_csv(index=False), "prices.csv")