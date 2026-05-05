import streamlit as st
import time
import random
from datetime import datetime
import pandas as pd
import os

# ---------- API KEYS (optional, sirf real mode ke liye) ----------
try:
    API_KEY = st.secrets["APCA_API_KEY_ID"]
    SECRET_KEY = st.secrets["APCA_API_SECRET_KEY"]
except:
    from dotenv import load_dotenv
    load_dotenv()
    API_KEY = os.getenv("APCA_API_KEY_ID")
    SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")

st.set_page_config(page_title="Real-Time Dashboard", layout="wide")
st.title("📈 Real-Time Stock Dashboard")
st.markdown("### Live Prices | Alerts | Add Tickers")

# ---------- SESSION STATE ----------
if "symbols" not in st.session_state:
    st.session_state.symbols = ["AAPL","MSFT","GOOGL","AMZN","TSLA","META","NFLX","NVDA"]
if "prices" not in st.session_state:
    # Initialize with random prices so they show immediately
    st.session_state.prices = {s: round(random.uniform(90, 110), 2) for s in st.session_state.symbols}
if "alerts" not in st.session_state:
    st.session_state.alerts = {}
if "triggered" not in st.session_state:
    st.session_state.triggered = set()
if "history" not in st.session_state:
    st.session_state.history = []
if "streaming" not in st.session_state:
    st.session_state.streaming = False
if "last_update" not in st.session_state:
    st.session_state.last_update = time.time()
if "use_real" not in st.session_state:
    st.session_state.use_real = False

# ---------- SIDEBAR ----------
st.sidebar.header("🌐 Data Source")
st.session_state.use_real = st.sidebar.checkbox("Use Real Alpaca", value=False, disabled=not API_KEY)
if not API_KEY:
    st.sidebar.warning("No API keys - Demo only")

st.sidebar.header("➕ Add Ticker")
new_sym = st.sidebar.text_input("Symbol", "").upper()
if st.sidebar.button("Add") and new_sym and new_sym not in st.session_state.symbols:
    st.session_state.symbols.append(new_sym)
    st.session_state.prices[new_sym] = 100.0
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

# ---------- CONTROL BUTTONS ----------
col1, col2 = st.columns(2)
with col1:
    if st.button("▶️ START STREAMING", type="primary"):
        st.session_state.streaming = True
        st.session_state.last_update = time.time()
        st.rerun()
with col2:
    if st.button("⏹️ STOP STREAMING"):
        st.session_state.streaming = False
        st.rerun()

# ---------- UPDATE PRICES (NO THREADS) ----------
if st.session_state.streaming:
    now = time.time()
    if now - st.session_state.last_update >= 2.0:
        # Update each symbol with random walk (demo mode)
        # For real mode, you'd call an API here, but for now simple demo
        for sym in st.session_state.symbols:
            old = st.session_state.prices.get(sym, 100)
            change = random.uniform(-2, 2)
            new_price = round(max(50, min(200, old + change)), 2)
            st.session_state.prices[sym] = new_price
            
            # Alert check
            if sym in st.session_state.alerts and new_price > st.session_state.alerts[sym]:
                if sym not in st.session_state.triggered:
                    st.session_state.triggered.add(sym)
            
            # History
            st.session_state.history.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "symbol": sym,
                "price": new_price
            })
            if len(st.session_state.history) > 500:
                st.session_state.history = st.session_state.history[-500:]
        
        st.session_state.last_update = now
        st.rerun()  # Refresh UI after update

# ---------- UI DISPLAY ----------
cols = st.columns(4)
placeholders = {}
for i, sym in enumerate(st.session_state.symbols):
    placeholders[sym] = cols[i % 4].empty()

status_placeholder = st.empty()
alert_placeholder = st.empty()

if st.session_state.streaming:
    status_placeholder.success("🟢 STREAMING ACTIVE - Demo Mode (updates every 2 sec)")
    for sym, ph in placeholders.items():
        price = st.session_state.prices.get(sym, 0)
        icon = "🔔 " if sym in st.session_state.alerts else ""
        ph.metric(icon + sym, f"${price:.2f}")
    if st.session_state.triggered:
        alert_placeholder.warning(f"🔔 ALERT: {list(st.session_state.triggered)[-1]} crossed!")
else:
    status_placeholder.info("⚡ Click START STREAMING")
    for sym, ph in placeholders.items():
        price = st.session_state.prices.get(sym, 0)
        if price == 0:
            ph.metric(sym, "Paused")
        else:
            ph.metric(sym, f"${price:.2f}")

# Alert history expander
with st.expander("🔔 Alert History"):
    if st.session_state.triggered:
        for a in st.session_state.triggered:
            st.warning(f"{a} crossed threshold")
    else:
        st.info("No alerts yet")

with st.expander("📜 Export Data"):
    if st.button("Export CSV"):
        if st.session_state.history:
            df = pd.DataFrame(st.session_state.history)
            st.download_button("Download", df.to_csv(index=False), "prices.csv")
    st.dataframe(pd.DataFrame(st.session_state.history[-20:]) if st.session_state.history else pd.DataFrame())