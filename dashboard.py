import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import os
import json

# --- Firebase init ---
if not firebase_admin._apps:
    firebase_creds = os.environ.get("FIREBASE_CREDENTIALS")
    if firebase_creds:
        cred = credentials.Certificate(json.loads(firebase_creds))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Page config ---
st.set_page_config(page_title="RaxCartel", page_icon="💰", layout="wide")

# --- Custom CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #0a0a0f;
        color: #e0e0e0;
    }
    .stApp { background-color: #0a0a0f; }

    h1, h2, h3 { color: #ffffff; }

    .metric-card {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 1px solid #2a2a4a;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: 900; color: #00ff88; }
    .metric-label { font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; }

    .rarity-general    { color: #aaaaaa; font-weight: 600; }
    .rarity-common     { color: #ffffff; font-weight: 600; }
    .rarity-uncommon   { color: #00cc44; font-weight: 600; }
    .rarity-rare       { color: #4488ff; font-weight: 600; }
    .rarity-epic       { color: #aa44ff; font-weight: 600; }
    .rarity-legendary  { color: #ffaa00; font-weight: 600; }
    .rarity-mystic     { color: #ff4488; font-weight: 600; }
    .rarity-iconic     { color: #ff2200; font-weight: 600; }

    .deal-good      { color: #00ff88; font-weight: 700; }
    .deal-fair      { color: #ffcc00; font-weight: 700; }
    .deal-expensive { color: #ff4444; font-weight: 700; }

    .player-card {
        background: linear-gradient(135deg, #12122a, #1a1a3e);
        border: 1px solid #2a2a5a;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 10px;
        transition: border-color 0.2s;
    }
    .player-card:hover { border-color: #4444aa; }
    .player-name { font-size: 1.1rem; font-weight: 700; color: #ffffff; }
    .player-meta { font-size: 0.8rem; color: #888; margin-top: 4px; }
    .player-stats { display: flex; gap: 20px; margin-top: 12px; flex-wrap: wrap; }
    .stat-item { text-align: center; }
    .stat-val { font-size: 1rem; font-weight: 700; color: #00ccff; }
    .stat-lbl { font-size: 0.7rem; color: #666; text-transform: uppercase; }

    .buy-signal { border-color: #00ff88 !important; box-shadow: 0 0 12px rgba(0,255,136,0.15); }
    .avoid-signal { border-color: #ff4444 !important; }

    .ticker-bar {
        background: #111122;
        border-bottom: 1px solid #2a2a4a;
        padding: 8px 0;
        font-size: 0.8rem;
        color: #888;
        margin-bottom: 20px;
    }

    div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
    .stButton button {
        background: linear-gradient(135deg, #4444ff, #8844ff);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }
    .stSelectbox > div { background: #1a1a2e; border-color: #2a2a4a; }
    .stTextInput > div > input { background: #1a1a2e; border-color: #2a2a4a; color: white; }
</style>
""", unsafe_allow_html=True)

# --- RAX earnings by rarity (from official docs) ---
RAX_EARNINGS = {
    "General": 200, "Common": 1000, "Uncommon": 1500,
    "Rare": 2000, "Epic": 5000, "Legendary": 12500,
    "Mystic": 37500, "Iconic": 999999
}
RARITY_ORDER = ["General", "Common", "Uncommon", "Rare", "Epic", "Legendary", "Mystic", "Iconic"]

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
        rarity = d.get('rarity', 'Common')
        daily_rax = RAX_EARNINGS.get(rarity, 1000)
        d['daily_rax_earn'] = daily_rax
        d['days_to_breakeven'] = round(buy / daily_rax, 1) if daily_rax and buy else None
        d['profit_loss'] = round(sell - buy, 0) if sell else None
        market_val = d.get('market_value') or 0
        d['roi_pct'] = round(((market_val - buy) / buy) * 100, 1) if buy and market_val else None
        d['deal_score'] = d.get('deal_score') or 0
        rows.append(d)
    return pd.DataFrame(rows) if rows else pd.DataFrame()

df = load_players()

# --- Header ---
st.markdown("""
<div style='text-align:center; padding: 30px 0 10px 0;'>
    <div style='font-size:3rem; font-weight:900; background: linear-gradient(135deg, #00ff88, #4488ff, #aa44ff);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;'>💰 RaxCartel</div>
    <div style='color:#888; font-size:0.9rem; margin-top:4px;'>Real App Profit Intelligence</div>
</div>
""", unsafe_allow_html=True)

if df.empty:
    st.markdown("""
    <div style='text-align:center; padding:60px; color:#555;'>
        <div style='font-size:3rem;'>📭</div>
        <div style='font-size:1.2rem; margin-top:10px;'>No players tracked yet.</div>
        <div style='font-size:0.9rem; margin-top:6px;'>Run <code>python3 ProfitTool.py</code> and use <b>add</b> to get started.</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# --- Top metrics ---
col1, col2, col3, col4, col5 = st.columns(5)
buy_signals = len(df[df['deal_score'] >= 60]) if 'deal_score' in df.columns else 0
total_invested = df['buy_price'].fillna(0).sum()
realized_pl = df['profit_loss'].dropna().sum() if 'profit_loss' in df.columns else 0
avg_deal = df['deal_score'].mean() if 'deal_score' in df.columns else 0

for col, val, label in [
    (col1, len(df), "Players Tracked"),
    (col2, buy_signals, "Buy Signals"),
    (col3, f"{total_invested:,.0f}", "RAX Invested"),
    (col4, f"{realized_pl:+,.0f}", "Realized P/L"),
    (col5, f"{avg_deal:.0f}/95", "Avg Deal Score"),
]:
    with col:
        color = "#00ff88" if "P/L" in label and realized_pl >= 0 else ("#ff4444" if "P/L" in label else "#00ff88")
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value' style='color:{color}'>{val}</div>
            <div class='metric-label'>{label}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- Filters ---
col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
with col_f1:
    rarity_filter = st.selectbox("Rarity", ["All"] + RARITY_ORDER)
with col_f2:
    sort_by = st.selectbox("Sort by", ["Deal Score", "Buy Price", "Daily RAX", "Days to Breakeven", "P/L"])
with col_f3:
    search = st.text_input("Search player", placeholder="e.g. LeBron")

filtered = df.copy()
if rarity_filter != "All":
    filtered = filtered[filtered['rarity'] == rarity_filter]
if search:
    filtered = filtered[filtered['name'].str.contains(search, case=False, na=False)]

sort_map = {
    "Deal Score": "deal_score", "Buy Price": "buy_price",
    "Daily RAX": "daily_rax_earn", "Days to Breakeven": "days_to_breakeven", "P/L": "profit_loss"
}
sort_col = sort_map[sort_by]
if sort_col in filtered.columns:
    filtered = filtered.sort_values(sort_col, ascending=(sort_by == "Days to Breakeven"), na_position='last')

st.markdown(f"<div style='color:#555; font-size:0.8rem; margin-bottom:12px;'>Showing {len(filtered)} players</div>", unsafe_allow_html=True)

# --- Player cards ---
def rarity_color(r):
    colors = {"General":"#aaa","Common":"#fff","Uncommon":"#00cc44","Rare":"#4488ff",
              "Epic":"#aa44ff","Legendary":"#ffaa00","Mystic":"#ff4488","Iconic":"#ff2200"}
    return colors.get(r, "#fff")

def deal_label(score):
    if score >= 60: return ("BUY", "#00ff88")
    if score >= 40: return ("FAIR", "#ffcc00")
    if score >= 20: return ("EXPENSIVE", "#ff8800")
    return ("AVOID", "#ff4444")

for _, row in filtered.iterrows():
    rarity = row.get('rarity', 'Common')
    rc = rarity_color(rarity)
    deal_score = row.get('deal_score', 0) or 0
    dlabel, dcolor = deal_label(deal_score)
    is_buy = deal_score >= 60
    card_class = "player-card buy-signal" if is_buy else ("player-card avoid-signal" if deal_score < 20 else "player-card")

    buy = row.get('buy_price') or 0
    market_val = row.get('market_value') or 0
    daily_rax = row.get('daily_rax_earn') or 0
    breakeven = row.get('days_to_breakeven')
    pl = row.get('profit_loss')
    rr = row.get('rr_ratio') or 0
    sched = row.get('schedule_strength') or 'N/A'
    updated = (row.get('last_updated') or '')[:10]

    breakeven_str = f"{breakeven}d" if breakeven else "N/A"
    pl_str = f"{pl:+,.0f}" if pl is not None else "N/A"
    pl_color = "#00ff88" if pl and pl >= 0 else "#ff4444"
    market_str = f"{market_val:,.0f}" if market_val else "N/A"
    rr_str = f"{rr:.2f}" if rr else "N/A"

    st.markdown(f"""
    <div class='{card_class}'>
        <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
            <div>
                <div class='player-name'>{row['name']}</div>
                <div class='player-meta'>
                    <span style='color:{rc}; font-weight:700;'>{rarity.upper()}</span>
                    &nbsp;·&nbsp; Season {row.get('season', '2026')}
                    &nbsp;·&nbsp; {sched}
                    &nbsp;·&nbsp; <span style='color:#555;'>Updated {updated}</span>
                </div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:1.4rem; font-weight:900; color:{dcolor};'>{dlabel}</div>
                <div style='font-size:0.75rem; color:#555;'>Deal {deal_score}/95</div>
            </div>
        </div>
        <div class='player-stats'>
            <div class='stat-item'><div class='stat-val'>{buy:,.0f}</div><div class='stat-lbl'>Buy Price</div></div>
            <div class='stat-item'><div class='stat-val'>{market_str}</div><div class='stat-lbl'>Market Val</div></div>
            <div class='stat-item'><div class='stat-val'>{daily_rax:,.0f}</div><div class='stat-lbl'>Daily RAX</div></div>
            <div class='stat-item'><div class='stat-val'>{breakeven_str}</div><div class='stat-lbl'>Breakeven</div></div>
            <div class='stat-item'><div class='stat-val'>{rr_str}</div><div class='stat-lbl'>R/R Ratio</div></div>
            <div class='stat-item'><div class='stat-val' style='color:{pl_color};'>{pl_str}</div><div class='stat-lbl'>P/L</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- Schedule chart ---
if 'upcoming_games' in df.columns and df['upcoming_games'].notna().any():
    st.markdown("<br>**Schedule Strength**", unsafe_allow_html=False)
    chart_df = df[['name', 'upcoming_games']].dropna().sort_values('upcoming_games', ascending=False).head(10)
    st.bar_chart(chart_df.set_index('name')['upcoming_games'])

# --- Daily Flip Profit Section ---
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style='font-size:1.3rem; font-weight:800; color:#ffffff; margin-bottom:12px;'>
    💸 Daily Flip Opportunities
</div>
<div style='color:#666; font-size:0.85rem; margin-bottom:16px;'>
    Players where current auction price is below fair value — instant profit if you flip today.
</div>
""", unsafe_allow_html=True)

flip_df = df.copy()
flip_df = flip_df[flip_df.get('fair_value', pd.Series(dtype=float)).notna()] if 'fair_value' in flip_df.columns else pd.DataFrame()

if not flip_df.empty:
    flip_df = flip_df[flip_df['fair_value'] > flip_df['buy_price']]
    flip_df['flip_profit'] = flip_df['fair_value'] - flip_df['buy_price']
    flip_df['flip_roi'] = ((flip_df['flip_profit']) / flip_df['buy_price'] * 100).round(1)
    flip_df = flip_df[flip_df['sport'].isin(['NBA', 'MLB', 'GOLF'])] if 'sport' in flip_df.columns else flip_df
    flip_df = flip_df.sort_values('flip_profit', ascending=False).head(15)

    total_flip = flip_df['flip_profit'].sum()
    st.markdown(f"""
    <div style='background:linear-gradient(135deg,#0a2a0a,#0a1a2a); border:1px solid #00ff88;
    border-radius:12px; padding:16px; margin-bottom:16px; text-align:center;'>
        <div style='font-size:2rem; font-weight:900; color:#00ff88;'>+{total_flip:,.0f} RAX</div>
        <div style='color:#888; font-size:0.8rem;'>Total potential profit if you flip all {len(flip_df)} cards today</div>
    </div>
    """, unsafe_allow_html=True)

    for _, row in flip_df.iterrows():
        rarity = row.get('rarity', 'Common')
        rc = rarity_color(rarity)
        buy = row.get('buy_price') or 0
        fair = row.get('fair_value') or 0
        profit = row.get('flip_profit') or 0
        roi = row.get('flip_roi') or 0
        sport = row.get('sport', '')

        st.markdown(f"""
        <div style='background:#0d1f0d; border:1px solid #00aa44; border-radius:10px;
        padding:14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <div style='font-weight:700; color:#fff; font-size:1rem;'>{row['name']}</div>
                <div style='font-size:0.78rem; color:#888; margin-top:3px;'>
                    <span style='color:{rc};'>{rarity.upper()}</span> · {sport}
                </div>
            </div>
            <div style='display:flex; gap:24px; text-align:center;'>
                <div><div style='color:#aaa; font-size:0.7rem;'>BUY AT</div>
                    <div style='color:#fff; font-weight:700;'>{buy:,.0f}</div></div>
                <div><div style='color:#aaa; font-size:0.7rem;'>FAIR VALUE</div>
                    <div style='color:#00ccff; font-weight:700;'>{fair:,.0f}</div></div>
                <div><div style='color:#aaa; font-size:0.7rem;'>PROFIT</div>
                    <div style='color:#00ff88; font-weight:900; font-size:1.1rem;'>+{profit:,.0f}</div></div>
                <div><div style='color:#aaa; font-size:0.7rem;'>ROI</div>
                    <div style='color:#ffaa00; font-weight:700;'>{roi:.1f}%</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("<div style='color:#555; padding:20px;'>No flip opportunities found right now. Check back soon.</div>", unsafe_allow_html=True)

st.markdown("<br><div style='text-align:center; color:#333; font-size:0.75rem;'>RaxCartel · Data from realapp.tools · Refreshes every 30s</div>", unsafe_allow_html=True)
