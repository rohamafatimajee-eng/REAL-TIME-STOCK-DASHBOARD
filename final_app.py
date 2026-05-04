import streamlit as st
import time
import random
import asyncio
import threading
from datetime import datetime
import pandas as pd
from alpaca.data.live import StockDataStream
from alpaca.data.models import Trade
from dotenv import load_dotenv
import os

# Load API Keys from .env file
load_dotenv()
API_KEY = os.getenv("APCA_API_KEY_ID")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")

st.set_page_config(page_title="Real-Time Stock Dashboard", layout="wide")
st.title("📈 Real-Time Stock & Forex Price Dashboard")
st.markdown("### Live Real Market Data via Alpaca WebSocket | Price Alerts")

# --- Session State Initialization ---
if "symbols" not in st.session_state:
    st.session_state.symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NFLX", "NVDA"]
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
if "data_source" not in st.session_state:
    st.session_state.data_source = "Demo"  # 'Demo' or 'Real'

# --- Sidebar Controls ---
st.sidebar.header("🌐 Data Source")
use_real = st.sidebar.checkbox("Use Real Alpaca Market Data", value=True if API_KEY else False, disabled=not API_KEY)
if not API_KEY:
    st.sidebar.error("❌ API Keys Missing. Add them to .env file to use Real Data.")
    use_real = False

st.sidebar.header("➕ Add Ticker")
new_ticker = st.sidebar.text_input("Symbol", "").upper()
if st.sidebar.button("Add") and new_ticker and new_ticker not in st.session_state.symbols:
    st.session_state.symbols.append(new_ticker)
    st.session_state.prices[new_ticker] = 0.0
    st.rerun()
if st.sidebar.button("Remove Last") and len(st.session_state.symbols) > 1:
    removed = st.session_state.symbols.pop()
    st.session_state.prices.pop(removed, None)
    st.rerun()

st.sidebar.info(f"Active: {len(st.session_state.symbols)} tickers")

# --- Alerts ---
st.sidebar.header("🔔 Price Alerts")
alert_sym = st.sidebar.selectbox("Symbol", st.session_state.symbols)
alert_val = st.sidebar.number_input("Alert > $", 100.0, step=10.0)
if st.sidebar.button("Set Alert"):
    st.session_state.alerts[alert_sym] = alert_val
if st.sidebar.button("Clear All Alerts"):
    st.session_state.alerts.clear()
    st.session_state.triggered.clear()

# --- Tabs ---
col_start, col_stop = st.columns(2)
with col_start:
    start_clicked = st.button("▶️ START STREAMING", type="primary")
with col_stop:
    stop_clicked = st.button("⏹️ STOP STREAMING")

# --- Tabs for Data Views ---
tab1, tab2, tab3 = st.tabs(["📊 Live Prices", "🔔 Alert History", "📜 Export Data"])
with tab1:
    cols = st.columns(4)
    placeholders = {}
    for i, sym in enumerate(st.session_state.symbols):
        placeholders[sym] = cols[i % 4].empty()
    status_placeholder = st.empty()
    alert_placeholder = st.empty()
with tab2:
    alert_tab = st.empty()
with tab3:
    export_btn = st.button("Export History as CSV")
    st.dataframe(pd.DataFrame(st.session_state.history[-20:]) if st.session_state.history else pd.DataFrame())

# --- Alert Tab Update Function ---
def update_alert_tab():
    if st.session_state.triggered:
        alert_tab.warning("\n".join([f"⚠️ {a} crossed threshold!" for a in st.session_state.triggered]))
    else:
        alert_tab.info("No alerts triggered yet")

# --- Real Data Callback (Alpaca) ---
stock_stream = None

def trade_callback(trade: Trade):
    """Handle incoming trade data from Alpaca"""
    sym = trade.symbol
    price = round(trade.price, 2)
    st.session_state.prices[sym] = price
    
    # Check alerts
    if sym in st.session_state.alerts:
        if price > st.session_state.alerts[sym] and sym not in st.session_state.triggered:
            st.session_state.triggered.add(sym)
    
    # Store history
    st.session_state.history.append({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "symbol": sym,
        "price": price
    })
    if len(st.session_state.history) > 500:
        st.session_state.history = st.session_state.history[-500:]

def start_real_stream():
    """Initialize Alpaca WebSocket connection"""
    global stock_stream
    try:
        stock_stream = StockDataStream(api_key=API_KEY, secret_key=SECRET_KEY)
        for sym in st.session_state.symbols:
            stock_stream.subscribe_trades(trade_callback, sym)
        st.session_state.data_source = "Real"
        stock_stream.run()
    except Exception as e:
        st.error(f"Real data connection failed: {e}")
        st.session_state.data_source = "Demo"
        st.session_state.streaming = False

# --- DEMO Mode Function (Fallback/Standalone) ---
def demo_stream_thread():
    """Fallback demo mode if Real fails or is disabled"""
    while st.session_state.streaming and st.session_state.data_source == "Demo":
        for sym in st.session_state.symbols:
            old = st.session_state.prices.get(sym, 100)
            if old == 0:
                old = 100
            change = random.uniform(-2, 2)
            new_price = round(max(50, min(200, old + change)), 2)
            st.session_state.prices[sym] = new_price
            
            if sym in st.session_state.alerts:
                if new_price > st.session_state.alerts[sym] and sym not in st.session_state.triggered:
                    st.session_state.triggered.add(sym)
            
            st.session_state.history.append({
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "symbol": sym,
                "price": new_price
            })
            if len(st.session_state.history) > 500:
                st.session_state.history = st.session_state.history[-500:]
        time.sleep(2)

# --- Stream Control Logic ---
if start_clicked and not st.session_state.streaming:
    st.session_state.streaming = True
    st.session_state.triggered.clear()
    
    if use_real and API_KEY:
        try:
            st.session_state.data_source = "Real"
            # Start real Alpaca thread
            real_thread = threading.Thread(target=start_real_stream, daemon=True)
            real_thread.start()
            st.success("Real market data stream started!")
        except Exception as e:
            st.error(f"Could not start real stream: {e}. Falling back to demo.")
            st.session_state.data_source = "Demo"
            demo_thread = threading.Thread(target=demo_stream_thread, daemon=True)
            demo_thread.start()
    else:
        st.session_state.data_source = "Demo"
        demo_thread = threading.Thread(target=demo_stream_thread, daemon=True)
        demo_thread.start()
    
    st.rerun()

if stop_clicked and st.session_state.streaming:
    st.session_state.streaming = False
    st.session_state.data_source = "Demo"
    if stock_stream:
        try:
            stock_stream.stop()
        except:
            pass
    st.rerun()

# --- Display Updates (Runs every loop) ---
if st.session_state.streaming:
    source_text = "Real Alpaca Market Data" if st.session_state.data_source == "Real" else "Demo Mode (Simulated)"
    status_placeholder.success(f"🟢 STREAMING ACTIVE - Source: {source_text}")
    
    for sym, placeholder in placeholders.items():
        price = st.session_state.prices.get(sym, 0)
        if price > 0:
            icon = "🔔 " if sym in st.session_state.alerts else ""
            placeholder.metric(icon + sym, f"${price:.2f}", delta="live")
        else:
            placeholder.metric(sym, "Waiting...")
    
    if st.session_state.triggered:
        alert_placeholder.warning(f"🔔 ALERT: {list(st.session_state.triggered)[-1]} crossed threshold!")
else:
    status_placeholder.info("⚡ Click 'START STREAMING' to begin")
    for sym, placeholder in placeholders.items():
        placeholder.metric(sym, "Paused")

# Update Alert Tab dynamically
update_alert_tab()

# Auto-refresh for live updates
if st.session_state.streaming:
    time.sleep(1)
    st.rerun()
