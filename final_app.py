# final_app.py
import streamlit as st
import asyncio
import threading
import json
import os
import time
import random
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

st.set_page_config(page_title="Real-Time Stock Dashboard", layout="wide", page_icon="📈")
st.title("📈 Real-Time Stock & Forex Price Dashboard")
st.markdown("### Live data via WebSockets | Price Alerts | 50+ Tickers Support")

# Session state initialization
if "prices" not in st.session_state:
    st.session_state.prices = {}
if "alerts" not in st.session_state:
    st.session_state.alerts = {}
if "triggered" not in st.session_state:
    st.session_state.triggered = set()
if "history" not in st.session_state:
    st.session_state.history = []

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Live Prices", "🔔 Set Alerts", "📜 History & About"])

# Tab 1: Live Prices
with tab1:
    cols = st.columns(4)
    placeholders = {}
    # Default symbols
    default_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NFLX", "NVDA"]
    for i, sym in enumerate(default_symbols):
        col = cols[i % 4]
        placeholders[sym] = col.empty()
        st.session_state.prices[sym] = 0.0

# Tab 2: Alerts
with tab2:
    st.subheader("Set Price Alerts")
    alert_sym = st.selectbox("Select Symbol", default_symbols)
    alert_thresh = st.number_input("Alert when price > ($)", value=100.0, step=10.0)
    if st.button("Set Alert"):
        st.session_state.alerts[alert_sym] = alert_thresh
        st.success(f"Alert set for {alert_sym} at ${alert_thresh}")
    
    st.subheader("Active Alerts")
    for sym, thresh in st.session_state.alerts.items():
        st.write(f"🔔 {sym} > ${thresh}")

# Tab 3: History
with tab3:
    if st.button("Export History as CSV"):
        df = pd.DataFrame(st.session_state.history)
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, "price_history.csv", "text/csv")
    st.write("Last 20 price updates:")
    st.dataframe(pd.DataFrame(st.session_state.history[-20:]))

# WebSocket simulation (real API ke liye replace with actual Alpaca code)
def simulate_websocket():
    """Demo ke liye random prices. Real mein Alpaca WebSocket use karo."""
    while True:
        for sym in default_symbols:
            price = 100 + random.uniform(-10, 10)
            st.session_state.prices[sym] = round(price, 2)
            
            # Alert check
            if sym in st.session_state.alerts:
                if price > st.session_state.alerts[sym] and sym not in st.session_state.triggered:
                    st.session_state.triggered.add(sym)
                    st.toast(f"⚠️ {sym} crossed ${st.session_state.alerts[sym]}! Now ${price}", icon="🔔")
            
            # History
            st.session_state.history.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": sym,
                "price": price
            })
            if len(st.session_state.history) > 100:
                st.session_state.history = st.session_state.history[-100:]
        time.sleep(2)

# Background thread
if "websocket_thread" not in st.session_state:
    thread = threading.Thread(target=simulate_websocket, daemon=True)
    thread.start()
    st.session_state.websocket_thread = True

# Update placeholders
for sym, placeholder in placeholders.items():
    price = st.session_state.prices.get(sym, 0)
    if price > 0:
        placeholder.metric(sym, f"${price:.2f}")
    else:
        placeholder.metric(sym, "Loading...")

# Auto-refresh
time.sleep(1)
st.rerun()