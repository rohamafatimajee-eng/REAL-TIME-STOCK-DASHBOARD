import streamlit as st
import time
import random
import threading
import queue
from datetime import datetime
import pandas as pd
import os

# ---------- LOAD API KEYS (Cloud + Local) ----------
try:
    API_KEY = st.secrets["APCA_API_KEY_ID"]
    SECRET_KEY = st.secrets["APCA_API_SECRET_KEY"]
    st.info("🔑 Using Streamlit Secrets (Cloud mode)")
except Exception:
    from dotenv import load_dotenv
    load_dotenv()
    API_KEY = os.getenv("APCA_API_KEY_ID")
    SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
    st.info("📁 Using .env file (Local mode)")

st.set_page_config(page_title="Real-Time Stock Dashboard", layout="wide")
st.title("📈 Real-Time Stock & Forex Price Dashboard")
st.markdown("### Live Real Market Data via Alpaca WebSocket | Price Alerts")

# ---------- SESSION STATE ----------
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
    st.session_state.data_source = "Demo"
if "last_trade" not in st.session_state:
    st.session_state.last_trade = None

# Queue for thread-safe updates
update_queue = queue.Queue()

# ---------- SIDEBAR ----------
st.sidebar.header("🌐 Data Source")
use_real = st.sidebar.checkbox("Use Real Alpaca Market Data", value=bool(API_KEY), disabled=not API_KEY)
if not API_KEY:
    st.sidebar.error("❌ API Keys Missing. Add to Secrets (Cloud) or .env (Local).")

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

st.sidebar.header("🔔 Price Alerts")
alert_sym = st.sidebar.selectbox("Symbol", st.session_state.symbols)
alert_val = st.sidebar.number_input("Alert > $", 100.0, step=10.0)
if st.sidebar.button("Set Alert"):
    st.session_state.alerts[alert_sym] = alert_val
if st.sidebar.button("Clear All Alerts"):
    st.session_state.alerts.clear()
    st.session_state.triggered.clear()

# ---------- TABS ----------
col_start, col_stop = st.columns(2)
with col_start:
    start_clicked = st.button("▶️ START STREAMING", type="primary")
with col_stop:
    stop_clicked = st.button("⏹️ STOP STREAMING")

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
    if st.button("Export History as CSV"):
        if st.session_state.history:
            df = pd.DataFrame(st.session_state.history)
            st.download_button("Download CSV", df.to_csv(index=False), "prices.csv")
    st.dataframe(pd.DataFrame(st.session_state.history[-20:]) if st.session_state.history else pd.DataFrame())

def update_alert_tab():
    if st.session_state.triggered:
        alert_tab.warning("\n".join([f"⚠️ {a} crossed threshold!" for a in st.session_state.triggered]))
    else:
        alert_tab.info("No alerts triggered yet")

# ---------- REAL THREAD (no session state access) ----------
def real_stream_thread(symbols_list):
    """Background thread: connects to Alpaca, pushes trades to queue"""
    try:
        from alpaca.data.live import StockDataStream
        from alpaca.data.models import Trade
    except ImportError:
        update_queue.put(("error", "alpaca-py not installed"))
        return

    def trade_callback(trade: Trade):
        update_queue.put(("trade", trade.symbol, trade.price))

    stream = StockDataStream(api_key=API_KEY, secret_key=SECRET_KEY)
    for sym in symbols_list:
        stream.subscribe_trades(trade_callback, sym)
    update_queue.put(("status", "real_started"))
    try:
        stream.run()
    except Exception as e:
        update_queue.put(("error", str(e)))

def demo_stream_thread(symbols_list):
    """Demo mode: random prices"""
    while st.session_state.get("streaming", False):
        for sym in symbols_list:
            old = st.session_state.prices.get(sym, 100) if sym in st.session_state.prices else 100
            if old == 0:
                old = 100
            new_price = round(max(50, min(200, old + random.uniform(-2, 2))), 2)
            update_queue.put(("demo_price", sym, new_price))
        time.sleep(2)

# ---------- START / STOP ----------
if start_clicked and not st.session_state.streaming:
    st.session_state.streaming = True
    st.session_state.triggered.clear()
    st.session_state.data_source = "Demo"
    st.session_state.last_trade = None
    # Clear old queue items
    while not update_queue.empty():
        try: update_queue.get_nowait()
        except: pass

    if use_real and API_KEY:
        t = threading.Thread(target=real_stream_thread, args=(st.session_state.symbols.copy(),), daemon=True)
        t.start()
        st.success("Connecting to Alpaca real data...")
    else:
        t = threading.Thread(target=demo_stream_thread, args=(st.session_state.symbols.copy(),), daemon=True)
        t.start()
    st.rerun()

if stop_clicked and st.session_state.streaming:
    st.session_state.streaming = False
    st.session_state.data_source = "Demo"
    st.rerun()

# ---------- PROCESS QUEUE (main thread) ----------
if st.session_state.streaming:
    try:
        for _ in range(100):
            item = update_queue.get_nowait()
            if item[0] == "trade":
                _, sym, price = item
                price = round(price, 2)
                st.session_state.prices[sym] = price
                st.session_state.last_trade = time.time()
                st.session_state.data_source = "Real"
                if sym in st.session_state.alerts:
                    if price > st.session_state.alerts[sym] and sym not in st.session_state.triggered:
                        st.session_state.triggered.add(sym)
                st.session_state.history.append({
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "symbol": sym,
                    "price": price
                })
                if len(st.session_state.history) > 500:
                    st.session_state.history = st.session_state.history[-500:]
            elif item[0] == "demo_price":
                _, sym, price = item
                st.session_state.prices[sym] = price
                if sym in st.session_state.alerts:
                    if price > st.session_state.alerts[sym] and sym not in st.session_state.triggered:
                        st.session_state.triggered.add(sym)
                st.session_state.history.append({
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "symbol": sym,
                    "price": price
                })
            elif item[0] == "status" and item[1] == "real_started":
                st.session_state.data_source = "Real"
            elif item[0] == "error":
                st.error(f"Connection error: {item[1]}")
                st.session_state.data_source = "Demo"
    except queue.Empty:
        pass

    # Auto fallback to demo if no real data for 20 seconds
    if st.session_state.data_source == "Real" and st.session_state.last_trade:
        if time.time() - st.session_state.last_trade > 20:
            st.session_state.data_source = "Demo"
            st.warning("No real data for 20s. Switching to demo mode.")
            # Start a demo thread if not already? The demo thread will be started only if use_real=False; here we are in real mode but stuck, so we need to start demo thread manually? Simpler: just keep demo data from the existing demo thread? Actually we only have one thread. Better: just set data_source to Demo and let existing thread continue? But the thread is real_stream_thread which is stuck. We need to launch a demo thread. For simplicity, we can just rely on the next start. But user can stop/start. I'll add a fallback thread start.
            if not any(isinstance(t, threading.Thread) and t.name.startswith("Demo") for t in threading.enumerate()):
                demo_th = threading.Thread(target=demo_stream_thread, args=(st.session_state.symbols.copy(),), daemon=True)
                demo_th.start()

# ---------- DISPLAY ----------
if st.session_state.streaming:
    source_display = "Real Alpaca Market Data" if st.session_state.data_source == "Real" else "Demo Mode (Simulated)"
    color = "🟢" if st.session_state.data_source == "Real" else "🟡"
    status_placeholder.success(f"{color} STREAMING ACTIVE - Source: {source_display}")
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

update_alert_tab()

if st.session_state.streaming:
    time.sleep(1)
    st.rerun()