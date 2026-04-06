import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import os
import json

# --- Firebase init (safe for Streamlit reruns) ---
if not firebase_admin._apps:
    firebase_creds = os.environ.get("FIREBASE_CREDENTIALS")
    if firebase_creds:
        cred = credentials.Certificate(json.loads(firebase_creds))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

st.set_page_config(page_title="Profit Tool Dashboard", layout="wide")
st.title("Sports Card Profit Tool")

# --- Load data ---
@st.cache_data(ttl=30)
def load_players():
    docs = db.collection('market_watch').stream()
    rows = []
    for doc in docs:
        d = doc.to_dict()
        d['name'] = doc.id
        buy = d.get('buy_price') or 0
        sell = d.get('sell_price')
        cost_to_rare = d.get('total_rax_invested') or 1
        rare_val = d.get('rare_market_value') or 0
        d['ROI (%)'] = round(((rare_val - cost_to_rare) / cost_to_rare) * 100, 1) if cost_to_rare else 0
        d['profit_loss'] = round(sell - buy, 0) if sell else None
        rows.append(d)
    return pd.DataFrame(rows)

df = load_players()

if df.empty:
    st.info("No players in your market watch yet. Add some using ProfitTool.py.")
    st.stop()

# --- Leaderboard ---
st.subheader("Profit Leaderboard")

display_cols = ['name', 'rarity', 'avg_points_last_5', 'schedule_strength',
                'upcoming_games', 'buy_price', 'profit_loss', 'ROI (%)', 'last_updated']
display_cols = [c for c in display_cols if c in df.columns]

def highlight_buy(row):
    sched = str(row.get('schedule_strength', ''))
    roi = row.get('ROI (%)', 0) or 0
    if 'High Priority' in sched or roi > 20:
        return ['background-color: #1a4a1a; color: #00ff88'] * len(row)
    elif 'Avoid' in sched:
        return ['background-color: #4a1a1a; color: #ff6666'] * len(row)
    return [''] * len(row)

styled = df[display_cols].style.apply(highlight_buy, axis=1)
st.dataframe(styled, use_container_width=True)

# --- Stats summary ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Players", len(df))

flippable = df[df.get('ROI (%)', pd.Series(dtype=float)) > 20] if 'ROI (%)' in df.columns else pd.DataFrame()
col2.metric("Buy Signals", len(flippable))

total_invested = df['buy_price'].sum() if 'buy_price' in df.columns else 0
col3.metric("Total Invested (RAX)", f"{total_invested:,.0f}")

realized = df['profit_loss'].dropna().sum() if 'profit_loss' in df.columns else 0
col4.metric("Realized P/L (RAX)", f"{realized:+,.0f}")

# --- Schedule heat map ---
st.subheader("Schedule Strength")
if 'upcoming_games' in df.columns and 'name' in df.columns:
    sched_df = df[['name', 'upcoming_games', 'schedule_strength']].sort_values('upcoming_games', ascending=False)
    st.bar_chart(sched_df.set_index('name')['upcoming_games'])

# --- Refresh note ---
st.caption("Data auto-refreshes every 30 seconds. Run `refresh-all` in ProfitTool.py to pull latest stats.")
