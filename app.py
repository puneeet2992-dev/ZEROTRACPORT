import datetime
import os
import shutil
import xml.etree.ElementTree as ET
from kiteconnect import KiteConnect
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Zerodha Pro Portfolio Tracker", layout="wide")
st.title("📈 Pro Portfolio Tracker: Dividends, Target Alerts & Mobile Ready")

TOKEN_FILE = "access_token.txt"
auto_token = ""
if os.path.exists(TOKEN_FILE):
  with open(TOKEN_FILE, "r") as f:
    auto_token = f.read().strip()

# Sidebar Authentication
st.sidebar.header("Zerodha Authentication")
api_key = st.sidebar.text_input("API Key", value="8pez266pu6j4nkiq")
access_token = st.sidebar.text_input(
    "Daily Access Token", type="password", value=auto_token
)

HISTORY_FILE = "portfolio_history.csv"
BACKUP_DIR = "backups"


def make_automatic_backup():
  if os.path.exists(HISTORY_FILE):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(
        BACKUP_DIR, f"portfolio_history_backup_{timestamp}.csv"
    )
    shutil.copy(HISTORY_FILE, backup_path)
    return backup_path
  return None


def log_daily_prices(df):
  today_str = datetime.date.today().strftime("%Y-%m-%d")
  df["Date"] = today_str
  record_df = df[["Date", "tradingsymbol", "quantity", "last_price"]]

  if os.path.exists(HISTORY_FILE):
    history_df = pd.read_csv(HISTORY_FILE)
    history_df = history_df[history_df["Date"] != today_str]
    updated_df = pd.concat([history_df, record_df], ignore_index=True)
  else:
    updated_df = record_df

  updated_df.to_csv(HISTORY_FILE, index=False)
  make_automatic_backup()
  return updated_df


# Fetch Portfolio Holdings
if st.sidebar.button("⚡ Fetch Portfolio Holdings"):
  if api_key and access_token:
    try:
      kite = KiteConnect(api_key=api_key)
      kite.set_access_token(access_token)
      holdings = kite.holdings()
      df = pd.DataFrame(holdings)
      log_daily_prices(df)
      st.sidebar.success("Logged portfolio holdings & backed up CSV!")
      st.rerun()
    except Exception as e:
      st.sidebar.error(f"Error fetching data: {e}")
  else:
    st.sidebar.warning("Missing API Key or Access Token.")

# Sidebar Watchlist Section
st.sidebar.markdown("---")
st.sidebar.header("➕ Add Watchlist Stock")
custom_symbol = st.sidebar.text_input(
    "Stock Symbol (e.g., RELIANCE, TCS)", value=""
).upper()
custom_price = st.sidebar.number_input(
    "Current Price (₹)", min_value=0.0, value=0.0, step=0.01
)

if st.sidebar.button("Add Stock to Tracker"):
  if custom_symbol and custom_price > 0:
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    new_entry = pd.DataFrame([{
        "Date": today_str,
        "tradingsymbol": custom_symbol,
        "quantity": 0,
        "last_price": custom_price,
    }])

    if os.path.exists(HISTORY_FILE):
      history_df = pd.read_csv(HISTORY_FILE)
      updated_df = pd.concat([history_df, new_entry], ignore_index=True)
    else:
      updated_df = new_entry

    updated_df.to_csv(HISTORY_FILE, index=False)
    make_automatic_backup()
    st.sidebar.success(f"Added {custom_symbol} successfully!")
    st.rerun()

# Sidebar Delete Section
if os.path.exists(HISTORY_FILE):
  st.sidebar.markdown("---")
  st.sidebar.header("🗑️ Delete Stock from Tracker")
  hist_df_temp = pd.read_csv(HISTORY_FILE)
  stock_list_temp = sorted(hist_df_temp["tradingsymbol"].unique())
  stock_to_delete = st.sidebar.selectbox(
      "Select Stock to Remove:", stock_list_temp
  )

  if st.sidebar.button("Remove Stock"):
    updated_df = hist_df_temp[
        hist_df_temp["tradingsymbol"] != stock_to_delete
    ]
    updated_df.to_csv(HISTORY_FILE, index=False)
    make_automatic_backup()
    st.sidebar.success(f"Removed {stock_to_delete} from history!")
    st.rerun()

# Backup Management in Sidebar
st.sidebar.markdown("---")
st.sidebar.header("💾 Backup Center")
if st.sidebar.button("📦 Trigger Manual Backup"):
  path = make_automatic_backup()
  if path:
    st.sidebar.success(f"Backup saved to `{path}`!")
  else:
    st.sidebar.warning("No history file found to backup.")

# --- Main Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Daily Matrix & Signals",
    "🎯 Price Target Alerts",
    "💰 Dividend Yield Tracker",
    "⚠️ Promoter / Institutional Alerts",
    "📈 Candlestick Charts",
])

if os.path.exists(HISTORY_FILE):
  hist_df = pd.read_csv(HISTORY_FILE)
  hist_df["last_price"] = pd.to_numeric(hist_df["last_price"], errors="coerce")
  hist_df["quantity"] = pd.to_numeric(
      hist_df.get("quantity", 0), errors="coerce"
  ).fillna(0)
  hist_df["Date"] = pd.to_datetime(hist_df["Date"])
  hist_df = hist_df.sort_values("Date")
  all_stocks = sorted(hist_df["tradingsymbol"].unique())

  # TAB 1: DAILY MATRIX & SIGNALS
  with tab1:
    st.subheader("🚨 EMA Crossover Signals (Past 30 Days)")
    crossover_alerts = []
    thirty_days_ago = pd.to_datetime(
        datetime.date.today() - datetime.timedelta(days=30)
    )

    for symbol in all_stocks:
      stock_df = hist_df[hist_df["tradingsymbol"] == symbol].copy()
      if len(stock_df) >= 2:
        stock_df["EMA5"] = (
            stock_df["last_price"].ewm(span=5, adjust=False).mean()
        )
        stock_df["EMA13"] = (
            stock_df["last_price"].ewm(span=13, adjust=False).mean()
        )
        stock_df["Prev_EMA5"] = stock_df["EMA5"].shift(1)
        stock_df["Prev_EMA13"] = stock_df["EMA13"].shift(1)

        recent_df = stock_df[stock_df["Date"] >= thirty_days_ago]
        for _, row in recent_df.iterrows():
          if (row["Prev_EMA5"] <= row["Prev_EMA13"]) and (
              row["EMA5"] > row["EMA13"]
          ):
            crossover_alerts.append({
                "Date": row["Date"].strftime("%Y-%m-%d"),
                "Stock": symbol,
                "Signal": "🟢 BULLISH CROSSOVER",
                "Price": f"₹{row['last_price']:.2f}",
            })
          if (row["Prev_EMA5"] >= row["Prev_EMA13"]) and (
              row["EMA5"] < row["EMA13"]
          ):
            crossover_alerts.append({
                "Date": row["Date"].strftime("%Y-%m-%d"),
                "Stock": symbol,
                "Signal": "🔴 BEARISH CROSSOVER",
                "Price": f"₹{row['last_price']:.2f}",
            })

    if crossover_alerts:
      st.dataframe(pd.DataFrame(crossover_alerts), use_container_width=True)
    else:
      st.info("No recent EMA crossovers detected.")

    st.markdown("---")
    st.subheader("📊 Price Matrix")
    hist_df["Date_Str"] = hist_df["Date"].dt.strftime("%Y-%m-%d")
    matrix_df = hist_df.pivot_table(
        index="tradingsymbol",
        columns="Date_Str",
        values="last_price",
        aggfunc="last",
    )

    if matrix_df.shape[1] >= 2:
      latest_date = matrix_df.columns[-1]
      prev_date = matrix_df.columns[-2]
      matrix_df["Change (₹)"] = matrix_df[latest_date] - matrix_df[prev_date]
      matrix_df["Change (%)"] = (
          matrix_df["Change (₹)"] / matrix_df[prev_date]
      ) * 100
      matrix_df["Status"] = matrix_df["Change (%)"].apply(
          lambda x: "🟢 BULLISH"
          if x > 0
          else ("🔴 BEARISH" if x < 0 else "⚪ NEUTRAL")
      )

      cols = ["Status", "Change (%)", "Change (₹)"] + [
          c
          for c in matrix_df.columns
          if c not in ["Status", "Change (%)", "Change (₹)"]
      ]
      matrix_df = matrix_df[cols].sort_values(
          by="Change (%)", ascending=False
      )

    st.dataframe(
        matrix_df.style.format({
            col: "₹{:.2f}"
            for col in matrix_df.columns
            if col not in ["Status", "Change (%)"]
        }).format({"Change (%)": "{:+.2f}%"}),
        use_container_width=True,
        height=400,
    )

  # TAB 2: PRICE TARGET ALERTS
  with tab2:
    st.subheader("🎯 Custom Buy/Sell Target Alert Monitor")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
      target_stock = st.selectbox("Select Stock:", all_stocks)
    with col2:
      buy_target = st.number_input(
          "Buy Target Below (₹):", min_value=0.0, value=0.0, step=1.0
      )
    with col3:
      sell_target = st.number_input(
          "Sell Target Above (₹):", min_value=0.0, value=0.0, step=1.0
      )
    with col4:
      st.markdown("<br>", unsafe_allow_html=True)
      save_target = st.button("Set Price Targets")

    TARGET_FILE = "price_targets.csv"
    if save_target and target_stock:
      target_data = pd.DataFrame([{
          "Stock": target_stock,
          "Buy_Below": buy_target,
          "Sell_Above": sell_target,
      }])
      if os.path.exists(TARGET_FILE):
        existing_targets = pd.read_csv(TARGET_FILE)
        existing_targets = existing_targets[
            existing_targets["Stock"] != target_stock
        ]
        updated_targets = pd.concat(
            [existing_targets, target_data], ignore_index=True
        )
      else:
        updated_targets = target_data
      updated_targets.to_csv(TARGET_FILE, index=False)
      st.success(f"Saved price targets for {target_stock}!")

    st.markdown("---")
    st.subheader("🔔 Active Target Alerts")

    if os.path.exists(TARGET_FILE):
      targets_df = pd.read_csv(TARGET_FILE)
      latest_prices = (
          hist_df.groupby("tradingsymbol")["last_price"].last().to_dict()
      )

      alerts_triggered = False
      summary_rows = []

      for _, row in targets_df.iterrows():
        sym = row["Stock"]
        cur_p = latest_prices.get(sym, 0.0)
        b_target = row["Buy_Below"]
        s_target = row["Sell_Above"]

        status = "HOLD / IN RANGE"
        if b_target > 0 and cur_p <= b_target:
          status = "🟢 BUY ZONE REACHED"
          st.success(
              f"🎯 **BUY ALERT:** {sym} current price **₹{cur_p:.2f}** is below"
              f" your Buy Target of **₹{b_target:.2f}**!"
          )
          alerts_triggered = True

        if s_target > 0 and cur_p >= s_target:
          status = "🔴 PROFIT / SELL ZONE REACHED"
          st.warning(
              f"🎯 **SELL ALERT:** {sym} current price **₹{cur_p:.2f}** is above"
              f" your Profit Target of **₹{s_target:.2f}**!"
          )
          alerts_triggered = True

        summary_rows.append({
            "Stock": sym,
            "Current Price": f"₹{cur_p:.2f}",
            "Buy Target (<)": f"₹{b_target:.2f}" if b_target > 0 else "Disabled",
            "Sell Target (>)": f"₹{s_target:.2f}"
            if s_target > 0
            else "Disabled",
            "Alert Condition": status,
        })

      if not alerts_triggered:
        st.info("No active price target breaches today.")

      st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)

  # TAB 3: DIVIDEND TRACKER
  with tab3:
    st.subheader("💰 Portfolio Dividend Income & Yield Dashboard")

    if st.button("📊 Scan & Calculate Portfolio Dividends"):
      dividend_records = []
      total_annual_passive_income = 0.0

      with st.spinner("Fetching dividend distributions..."):
        latest_holdings = (
            hist_df.groupby("tradingsymbol")
            .agg({"last_price": "last", "quantity": "last"})
            .reset_index()
        )

        for _, row in latest_holdings.iterrows():
          sym = row["tradingsymbol"]
          price = row["last_price"]
          qty = row["quantity"]

          try:
            ticker_str = f"{sym}.NS" if not sym.endswith(".NS") else sym
            ticker = yf.Ticker(ticker_str)
            info = ticker.info

            div_yield = (
                info.get("dividendYield", 0) * 100
                if info.get("dividendYield")
                else 0.0
            )
            div_rate = info.get("dividendRate", 0.0) or 0.0

            annual_payout = qty * div_rate
            total_annual_passive_income += annual_payout

            dividend_records.append({
                "Stock": sym,
                "Current Price": f"₹{price:.2f}",
                "Shares Owned": int(qty),
                "Dividend Yield (%)": f"{div_yield:.2f}%",
                "DPS (₹/Share)": f"₹{div_rate:.2f}",
                "Est. Annual Dividend Income": f"₹{annual_payout:.2f}",
            })
          except Exception:
            dividend_records.append({
                "Stock": sym,
                "Current Price": f"₹{price:.2f}",
                "Shares Owned": int(qty),
                "Dividend Yield (%)": "N/A",
                "DPS (₹/Share)": "N/A",
                "Est. Annual Dividend Income": "₹0.00",
            })

      st.metric(
          label="💵 Total Projected Annual Dividend Income",
          value=f"₹{total_annual_passive_income:,.2f}",
      )
      st.dataframe(pd.DataFrame(dividend_records), use_container_width=True)

  # TAB 4: PROMOTER & INSTITUTIONAL ALERTS
  with tab4:
    st.subheader("⚠️ Institutional & Promoter Shareholding Monitor")
    if st.button("🔍 Scan Portfolio Shareholding Patterns"):
      holding_data = []

      with st.spinner("Analyzing ownership patterns..."):
        for symbol in all_stocks:
          try:
            ticker_str = (
                f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
            )
            ticker = yf.Ticker(ticker_str)
            info = ticker.info

            insiders = (
                info.get("heldPercentInsiders", 0) * 100
                if info.get("heldPercentInsiders")
                else 0
            )
            institutions = (
                info.get("heldPercentInstitutions", 0) * 100
                if info.get("heldPercentInstitutions")
                else 0
            )

            warnings = []
            if insiders < 40 and insiders > 0:
              warnings.append(
                  f"⚠️ Low Promoter Ownership ({insiders:.1f}% < 40%)"
              )
            if institutions < 10 and institutions > 0:
              warnings.append(
                  f"⚠️ Weak Institutional Backing ({institutions:.1f}% < 10%)"
              )

            status = (
                "🟢 Strong Promoter Ownership"
                if insiders >= 50
                else (
                    "🟢 High Institutional Backing"
                    if institutions >= 30
                    else "🟡 Neutral / Mixed"
                )
            )

            holding_data.append({
                "Stock": symbol,
                "Promoter Holding (%)": f"{insiders:.2f}%"
                if insiders
                else "N/A",
                "FII/DII Institutional (%)": f"{institutions:.2f}%"
                if institutions
                else "N/A",
                "Holding Verdict": status,
                "Active Alerts": " | ".join(warnings)
                if warnings
                else "✅ Healthy Distribution",
            })

            if warnings:
              st.warning(
                  f"**{symbol} Shareholding Notice:** " + " | ".join(warnings)
              )

          except Exception:
            holding_data.append({
                "Stock": symbol,
                "Promoter Holding (%)": "N/A",
                "FII/DII Institutional (%)": "N/A",
                "Holding Verdict": "Data Unavailable",
                "Active Alerts": "N/A",
            })

      st.dataframe(pd.DataFrame(holding_data), use_container_width=True)

  # TAB 5: CANDLESTICK CHARTS
  with tab5:
    st.subheader("📈 Dark Candlestick Chart & Technical Indicators")
    selected_chart_stock = st.selectbox(
        "Select Stock for Charting:", all_stocks, key="chart_select"
    )

    def get_yf_candles_robust(symbol):
      clean_symbol = symbol.strip().upper().replace("&", "%26")
      tickers_to_try = [f"{symbol}.NS", f"{clean_symbol}.NS", clean_symbol]

      for t in tickers_to_try:
        try:
          df = yf.Ticker(t).history(
              period="6m", interval="1d", auto_adjust=True
          )
          if not df.empty and len(df) > 3:
            if isinstance(df.columns, pd.MultiIndex):
              df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            date_col = (
                "Date"
                if "Date" in df.columns
                else ("Datetime" if "Datetime" in df.columns else df.columns[0])
            )
            df.rename(columns={date_col: "Date"}, inplace=True)
            df["Date"] = pd.to_datetime(df["Date"])
            return df, t
        except Exception:
          continue
      return pd.DataFrame(), None

    with st.spinner(f"Loading chart for {selected_chart_stock}..."):
      df_candles, resolved_ticker = get_yf_candles_robust(
          selected_chart_stock
      )

      if df_candles.empty:
        stock_local = (
            hist_df[hist_df["tradingsymbol"] == selected_chart_stock]
            .sort_values("Date")
            .copy()
        )
        if len(stock_local) >= 2:
          stock_local["Close"] = stock_local["last_price"]
          stock_local["Open"] = stock_local["Close"].shift(1).fillna(
              stock_local["Close"]
          )
          stock_local["High"] = stock_local[["Open", "Close"]].max(axis=1)
          stock_local["Low"] = stock_local[["Open", "Close"]].min(axis=1)
          df_candles = stock_local
          resolved_ticker = f"{selected_chart_stock} (Local Data)"

      if not df_candles.empty:
        df_candles["Formatted_Date"] = pd.to_datetime(
            df_candles["Date"]
        ).dt.strftime("%d-%b-%Y")
        df_candles["EMA5"] = (
            df_candles["Close"].ewm(span=5, adjust=False).mean()
        )
        df_candles["EMA13"] = (
            df_candles["Close"].ewm(span=13, adjust=False).mean()
        )
        df_candles["EMA26"] = (
            df_candles["Close"].ewm(span=26, adjust=False).mean()
        )

        fig = go.Figure()
        fig.add_trace(
            go.Candlestick(
                x=df_candles["Formatted_Date"],
                open=df_candles["Open"],
                high=df_candles["High"],
                low=df_candles["Low"],
                close=df_candles["Close"],
                name="Candles",
                increasing_fillcolor="#00E676",
                increasing_line_color="#00E676",
                decreasing_fillcolor="#FF1744",
                decreasing_line_color="#FF1744",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df_candles["Formatted_Date"],
                y=df_candles["EMA5"],
                mode="lines",
                name="EMA (5)",
                line=dict(color="#FFD700", width=1.5),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_candles["Formatted_Date"],
                y=df_candles["EMA13"],
                mode="lines",
                name="EMA (13)",
                line=dict(color="#FF5252", width=1.5),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_candles["Formatted_Date"],
                y=df_candles["EMA26"],
                mode="lines",
                name="EMA (26)",
                line=dict(color="#00E5FF", width=1.5),
            )
        )

        fig.update_layout(
            title=f"{selected_chart_stock} Price Action ({resolved_ticker})",
            xaxis_title="Date (DD-MMM-YYYY)",
            yaxis_title="Price (₹)",
            hovermode="x unified",
            template="plotly_dark",
            paper_bgcolor="#121212",
            plot_bgcolor="#121212",
            height=600,
            xaxis=dict(
                type="category",
                rangeslider=dict(visible=False),
                gridcolor="#2A2A2A",
            ),
            yaxis=dict(gridcolor="#2A2A2A"),
        )

        st.plotly_chart(fig, use_container_width=True)
      else:
        st.error(f"No price data recorded for {selected_chart_stock}.")

else:
  st.info("No price data recorded yet.")