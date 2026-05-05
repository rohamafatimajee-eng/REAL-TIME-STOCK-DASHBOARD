import streamlit as st
import time
import random
from datetime import datetime
import pandas as pd
import os

st.set_page_config(page_title="Real-Time Dashboard", layout="wide")
st.title("📈 Real-Time Stock Dashboard")
st.markdown("### Live Prices | Alerts | Add Tickers")

# ---------- SESSION STATE ----------
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

# ---------- SIDEBAR ----------
st.sidebar.header("➕ Add Ticker")
new_sym = st.sidebar.text_input("Symbol", "").upper()
if st.sidebar.button("Add") and new_sym and new_sym not in st.session_state.symbols:
    st.session_state.symbols.append(new_sym)
    st.session_state.prices[new_sym] = random.uniform(90,110)
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
        st.rerun()
with col2:
    if st.button("⏹️ STOP STREAMING"):
        st.session_state.streaming = False
        st.rerun()

# ---------- PRICE UPDATE LOOP (inside main thread) ----------
if st.session_state.streaming:
    # Update prices every 2 seconds
    for sym in st.session_state.symbols:
        old = st.session_state.prices.get(sym, 100)
        if old == 0:
            old = 100
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
    
    # Show status and prices
    st.success("🟢 STREAMING ACTIVE - Demo Mode (prices updating...)")
    
    # Display price cards
    cols = st.columns(4)
    for i, sym in enumerate(st.session_state.symbols):
        price = st.session_state.prices.get(sym, 0)
        icon = "🔔 " if sym in st.session_state.alerts else ""
        cols[i % 4].metric(icon + sym, f"${price:.2f}")
    
    if st.session_state.triggered:
        st.warning(f"🔔 Alert: {list(st.session_state.triggered)[-1]} crossed threshold!")
    
    # Wait 2 seconds then refresh
    time.sleep(2)
    st.rerun()
else:
    st.info("⚡ Click START STREAMING to see live prices")
    cols = st.columns(4)
    for i, sym in enumerate(st.session_state.symbols):
        cols[i % 4].metric(sym, "Paused")

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