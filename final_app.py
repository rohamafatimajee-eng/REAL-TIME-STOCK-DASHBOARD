import streamlit as st
import time
import random
import threading
import queue
import asyncio
from datetime import datetime
import pandas as pd
import os

# ---------- API KEYS (Cloud first, then .env) ----------
try:
    API_KEY = st.secrets["APCA_API_KEY_ID"]
    SECRET_KEY = st.secrets["APCA_API_SECRET_KEY"]
    st.sidebar.success("✅ Using Streamlit Secrets")
except:
    from dotenv import load_dotenv
    load_dotenv()
    API_KEY = os.getenv("APCA_API_KEY_ID")
    SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
    if API_KEY:
        st.sidebar.success("✅ Using .env file")
    else:
        st.sidebar.error("❌ No API keys found")

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
if "source" not in st.session_state:
    st.session_state.source = "Demo"

# Queue for thread-safe updates
data_queue = queue.Queue()

# ---------- SIDEBAR ----------
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

# ---------- REAL ALPACA THREAD (async callback) ----------
def real_worker(symbols_copy):
    """Background thread for Alpaca WebSocket"""
    async def trade_callback(trade):
        # This runs in asyncio event loop, push to queue
        data_queue.put(("real", trade.symbol, trade.price))
    
    try:
        from alpaca.data.live import StockDataStream
        stream = StockDataStream(api_key=API_KEY, secret_key=SECRET_KEY)
        for sym in symbols_copy:
            stream.subscribe_trades(trade_callback, sym)
        data_queue.put(("status", "real_connected"))
        # Run the stream (blocking)
        stream.run()
    except Exception as e:
        data_queue.put(("error", str(e)))

# ---------- DEMO THREAD (no async, just random) ----------
def demo_worker(symbols_copy):
    """Generates random prices and pushes to queue"""
    # Start with base prices
    prices = {sym: 100.0 for sym in symbols_copy}
    while True:
        # Check if streaming flag is still True (read from shared variable? but thread-safe)
        # We'll read from a global flag; to avoid conflict, we can check a simple variable
        # Since we can't access session_state, we'll use a module-level flag set by main thread
        if not getattr(demo_worker, "running", False):
            break
        for sym in symbols_copy:
            change = random.uniform(-2, 2)
            prices[sym] = max(50, min(200, prices[sym] + change))
            data_queue.put(("demo", sym, round(prices[sym], 2)))
        time.sleep(2)

# ---------- START / STOP BUTTONS ----------
col1, col2 = st.columns(2)
with col1:
    start_clicked = st.button("▶️ START STREAMING", type="primary")
with col2:
    stop_clicked = st.button("⏹️ STOP STREAMING")

if start_clicked and not st.session_state.streaming:
    st.session_state.streaming = True
    st.session_state.triggered.clear()
    st.session_state.source = "Demo"
    # Clear old queue
    while not data_queue.empty():
        try: data_queue.get_nowait()
        except: pass
    
    # Decide real or demo
    use_real = st.sidebar.checkbox("Use Real Alpaca", value=bool(API_KEY), key="real_toggle")
    if use_real and API_KEY:
        # Start real thread
        t = threading.Thread(target=real_worker, args=(st.session_state.symbols.copy(),), daemon=True)
        t.start()
    else:
        # Start demo thread with a running flag
        demo_worker.running = True
        t = threading.Thread(target=demo_worker, args=(st.session_state.symbols.copy(),), daemon=True)
        t.start()
    st.rerun()

if stop_clicked and st.session_state.streaming:
    st.session_state.streaming = False
    # Signal demo thread to stop
    if hasattr(demo_worker, "running"):
        demo_worker.running = False
    st.rerun()

# ---------- PROCESS QUEUE (main thread) ----------
if st.session_state.streaming:
    # Process up to 200 messages per refresh
    for _ in range(200):
        try:
            typ, *vals = data_queue.get_nowait()
            if typ == "real":
                _, sym, price = typ, vals[0], vals[1]
                price = round(price, 2)
                st.session_state.prices[sym] = price
                st.session_state.source = "Real"
                # alert check
                if sym in st.session_state.alerts and price > st.session_state.alerts[sym]:
                    if sym not in st.session_state.triggered:
                        st.session_state.triggered.add(sym)
                # history
                st.session_state.history.append({
                    "t": datetime.now().strftime("%H:%M:%S"),
                    "s": sym,
                    "p": price
                })
                if len(st.session_state.history) > 500:
                    st.session_state.history = st.session_state.history[-500:]
            elif typ == "demo":
                _, sym, price = typ, vals[0], vals[1]
                st.session_state.prices[sym] = price
                if sym in st.session_state.alerts and price > st.session_state.alerts[sym]:
                    if sym not in st.session_state.triggered:
                        st.session_state.triggered.add(sym)
                st.session_state.history.append({
                    "t": datetime.now().strftime("%H:%M:%S"),
                    "s": sym,
                    "p": price
                })
                if len(st.session_state.history) > 500:
                    st.session_state.history = st.session_state.history[-500:]
            elif typ == "status":
                if vals[0] == "real_connected":
                    st.session_state.source = "Real"
            elif typ == "error":
                st.error(f"Alpaca error: {vals[0]}")
                st.session_state.source = "Demo"
        except queue.Empty:
            break

# ---------- UI DISPLAY ----------
# Create dynamic columns
cols = st.columns(4)
placeholders = {}
for i, sym in enumerate(st.session_state.symbols):
    placeholders[sym] = cols[i % 4].empty()

status_placeholder = st.empty()
alert_placeholder = st.empty()

if st.session_state.streaming:
    source_text = "Real Alpaca" if st.session_state.source == "Real" else "Demo (random)"
    status_placeholder.success(f"🟢 STREAMING ACTIVE - Source: {source_text}")
    for sym, ph in placeholders.items():
        price = st.session_state.prices.get(sym, 0)
        if price > 0:
            icon = "🔔 " if sym in st.session_state.alerts else ""
            ph.metric(icon + sym, f"${price:.2f}")
        else:
            ph.metric(sym, "Waiting...")
    if st.session_state.triggered:
        alert_placeholder.warning(f"🔔 Alert: {list(st.session_state.triggered)[-1]} crossed threshold!")
else:
    status_placeholder.info("⚡ Click START STREAMING")
    for sym, ph in placeholders.items():
        ph.metric(sym, "Paused")

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

# Auto-rerun every 1 second while streaming
if st.session_state.streaming:
    time.sleep(1)
    st.rerun()