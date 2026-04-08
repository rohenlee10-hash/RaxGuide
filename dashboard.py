import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import os
import json
import requests

# --- Firebase init ---
if not firebase_admin._apps:
    firebase_creds = os.environ.get("FIREBASE_CREDENTIALS")
    if firebase_creds:
        cred = credentials.Certificate(json.loads(firebase_creds))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- API ---
SUPABASE_URL = "https://mfsyhtuqybbxprgwwykd.supabase.co"
TOKEN = "sb_publishable_Al7QsFGnNTlknoI8KVxjag_JUwrytZy"
API_HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

RARITY_NUM = {3: "Rare", 4: "Epic", 5: "Legendary", 6: "Mystic", 7: "Iconic"}
RARITY_RATING = {"Rare": 80, "Epic": 180, "Legendary": 380, "Mystic": 1380, "Iconic": 3380}
RAX_EARNINGS = {
    "General": 200, "Common": 1000, "Uncommon": 1500,
    "Rare": 2000, "Epic": 5000, "Legendary": 12500,
    "Mystic": 37500, "Iconic": 999999
}
RARITY_ORDER = ["General", "Common", "Uncommon", "Rare", "Epic", "Legendary", "Mystic", "Iconic"]

def call_api(action, payload={}):
    try:
        r = requests.post(
            f"{SUPABASE_URL}/functions/v1/market-data",
            headers=API_HEADERS,
            json={"action": action, "payload": payload},
            timeout=10
        )
        return r.json()
    except Exception:
        return {}

@st.cache_data(ttl=300)
def get_player_listings(entity_id, season=2026):
    data = call_api("get_player_sales_by_entity", {"entityId": entity_id, "season": season})
    listings = data.get("summary", {}).get("listings", [])
    return [l for l in listings if not l.get("is_ended")]

@st.cache_data(ttl=60)
def get_player_suggestions(query):
    data = call_api("get_player_suggestions", {"query": query, "season": 2026})
    return data.get("suggestions", [])

def calc_upgrade_cost(live_listings, target_rating, target_rarity_num):
    by_rarity = {}
    for l in live_listings:
        r = RARITY_NUM.get(l["rarity"])
        if r and l.get("rarity", 99) < target_rarity_num:
            rating = l.get("value") or RARITY_RATING.get(r, 0)
            price = l.get("bid", 0)
            if r not in by_rarity:
                by_rarity[r] = []
            by_rarity[r].append({"price": price, "rating": rating})
    all_passes = []
    for r, passes in by_rarity.items():
        for p in passes:
            all_passes.append({**p, "rarity": r})
    all_passes.sort(key=lambda x: x["price"] / max(x["rating"], 1))
    total_cost, total_rating, passes_used = 0, 0, []
    for p in all_passes:
        if total_rating >= target_rating:
            break
        total_cost += p["price"]
        total_rating += p["rating"]
        passes_used.append(p)
    return total_cost, total_rating, passes_used

# --- Page config ---
st.set_page_config(page_title="RaxCartel", page_icon="⛳", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #060d06; color: #e0e0e0; }
.stApp { background-color: #060d06; }
h1,h2,h3 { color: #ffffff; }
.stTabs [data-baseweb="tab-list"] { background: #0d1a0d; border-radius: 12px; padding: 4px; gap: 4px; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #888; border-radius: 8px; font-weight: 600; padding: 8px 20px; }
.stTabs [aria-selected="true"] { background: linear-gradient(135deg, #1a6b1a, #2d8b2d) !important; color: white !important; }
.metric-card { background: linear-gradient(135deg, #0d1a0d, #0a1f0a); border: 1px solid #1a3a1a; border-radius: 12px; padding: 20px; text-align: center; }
.metric-value { font-size: 2rem; font-weight: 900; color: #00ff88; }
.metric-label { font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; }
.player-card { background: linear-gradient(135deg, #0a1a0a, #0d200d); border: 1px solid #1a3a1a; border-radius: 12px; padding: 16px; margin-bottom: 10px; }
.player-card:hover { border-color: #2d8b2d; }
.buy-signal { border-color: #00ff88 !important; box-shadow: 0 0 12px rgba(0,255,136,0.15); }
.avoid-signal { border-color: #ff4444 !important; }
.player-name { font-size: 1.1rem; font-weight: 700; color: #ffffff; }
.player-meta { font-size: 0.8rem; color: #888; margin-top: 4px; }
.player-stats { display: flex; gap: 20px; margin-top: 12px; flex-wrap: wrap; }
.stat-item { text-align: center; }
.stat-val { font-size: 1rem; font-weight: 700; color: #00ff88; }
.stat-lbl { font-size: 0.7rem; color: #666; text-transform: uppercase; }
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
.stButton button { background: linear-gradient(135deg, #1a6b1a, #2d8b2d); color: white; border: none; border-radius: 8px; font-weight: 600; }
.stSelectbox > div { background: #0d1a0d; border-color: #1a3a1a; }
.stTextInput > div > input { background: #0d1a0d; border-color: #1a3a1a; color: white; }
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown("""
<div style='text-align:center; padding: 30px 0 10px 0;'>
    <div style='font-size:3.5rem; font-weight:900; background: linear-gradient(135deg, #00ff88, #2d8b2d, #00cc44);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;'>⛳ RaxCartel</div>
    <div style='color:#4a8b4a; font-size:0.95rem; margin-top:4px; font-weight:600;'>Golf · NBA · MLB Profit Intelligence</div>
    <div style='color:#2a4a2a; font-size:0.75rem; margin-top:6px;'>Created by <span style='color:#00ff88;'>@lee</span></div>
</div>
""", unsafe_allow_html=True)

# --- Quick links ---
st.markdown("""
<div style='display:flex; gap:12px; justify-content:center; margin-bottom:24px; flex-wrap:wrap;'>
    <a href='https://www.realapp.com/ajUQFRFBAqD' target='_blank'
    style='background:#0d1a0d; border:1px solid #2d8b2d; border-radius:8px; padding:8px 18px;
    color:#00ff88; text-decoration:none; font-weight:600; font-size:0.85rem;'>
    ⛳ My Golf Collection</a>
    <a href='https://www.realapp.com/QYI5FJFYD49' target='_blank'
    style='background:#0d1a0d; border:1px solid #2d8b2d; border-radius:8px; padding:8px 18px;
    color:#00ff88; text-decoration:none; font-weight:600; font-size:0.85rem;'>
    💰 My RAX Method</a>
</div>
""", unsafe_allow_html=True)

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
        fair_val = d.get('fair_value') or 0
        d['flip_profit'] = fair_val - buy if fair_val and buy else None
        d['deal_score'] = d.get('deal_score') or 0
        rows.append(d)
    return pd.DataFrame(rows) if rows else pd.DataFrame()

df = load_players()

if df.empty:
    st.markdown("<div style='text-align:center; padding:60px; color:#2a4a2a;'><div style='font-size:3rem;'>⛳</div><div style='font-size:1.2rem; margin-top:10px; color:#4a8b4a;'>No players yet. Run python3 scraper.py to populate.</div></div>", unsafe_allow_html=True)
    st.stop()

# --- Top metrics ---
col1, col2, col3, col4, col5 = st.columns(5)
buy_signals = len(df[df['deal_score'] >= 60]) if 'deal_score' in df.columns else 0
total_invested = df['buy_price'].fillna(0).sum()
realized_pl = df['profit_loss'].dropna().sum() if 'profit_loss' in df.columns else 0
flip_opps = df['flip_profit'].dropna()
total_flip = flip_opps[flip_opps > 0].sum() if len(flip_opps) else 0

for col, val, label in [
    (col1, len(df), "Players Tracked"),
    (col2, buy_signals, "Buy Signals"),
    (col3, f"+{total_flip:,.0f}", "Potential Profit"),
    (col4, f"{realized_pl:+,.0f}", "Realized P/L"),
    (col5, len(df[df['deal_score'] >= 40]) if 'deal_score' in df.columns else 0, "Fair+ Deals"),
]:
    with col:
        color = "#ff4444" if "P/L" in label and realized_pl < 0 else "#00ff88"
        st.markdown(f"""<div class='metric-card'>
            <div class='metric-value' style='color:{color}'>{val}</div>
            <div class='metric-label'>{label}</div></div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- Sport tabs ---
tab_golf, tab_nba, tab_mlb, tab_all, tab_flip, tab_picks, tab_boost, tab_calc = st.tabs([
    "⛳ Golf", "🏀 NBA", "⚾ MLB", "🌐 All", "💸 Flip Opportunities", "🎯 Daily Picks", "🚀 Boosters & Packs", "⚡ Upgrade Calculator"
])

def rarity_color(r):
    return {"General":"#aaa","Common":"#fff","Uncommon":"#00cc44","Rare":"#ff8800",
            "Epic":"#ff3333","Legendary":"#aa44ff","Mystic":"#ffaa00","Iconic":"#ff44aa"}.get(r, "#fff")

def deal_label(score):
    if score >= 60: return ("BUY", "#00ff88")
    if score >= 40: return ("FAIR", "#ffcc00")
    if score >= 20: return ("EXPENSIVE", "#ff8800")
    return ("AVOID", "#ff4444")

def render_players(data, tab_key="default"):
    if data.empty:
        st.markdown("<div style='color:#2a4a2a; padding:20px;'>No players found.</div>", unsafe_allow_html=True)
        return

    col_f1, col_f2 = st.columns([2, 2])
    with col_f1:
        sort_by = st.selectbox("Sort by", ["Value Rating", "Buy Price", "Flip Profit"], key=f"sort_{tab_key}")
    with col_f2:
        search = st.text_input("Search", placeholder="Player name...", key=f"search_{tab_key}")

    if search:
        data = data[data['name'].str.contains(search, case=False, na=False)]

    sort_map = {"Value Rating": "deal_score", "Buy Price": "buy_price", "Flip Profit": "flip_profit"}
    sc = sort_map.get(sort_by, "deal_score")
    if sc in data.columns:
        data = data.sort_values(sc, ascending=False, na_position='last')

    st.markdown(f"<div style='color:#2a4a2a; font-size:0.8rem; margin-bottom:12px;'>{len(data)} players</div>", unsafe_allow_html=True)

    for _, row in data.iterrows():
        rarity = row.get('rarity', 'Common')
        rc = rarity_color(rarity)
        deal_score = row.get('deal_score', 0) or 0
        dlabel, dcolor = deal_label(deal_score)
        card_class = "player-card buy-signal" if deal_score >= 60 else ("player-card avoid-signal" if deal_score < 20 else "player-card")
        buy = row.get('buy_price') or 0
        market_val = row.get('market_value') or 0
        daily_rax = row.get('daily_rax_earn') or 0
        breakeven = row.get('days_to_breakeven')
        pl = row.get('profit_loss')
        flip = row.get('flip_profit')
        rr = row.get('rr_ratio') or 0
        sport = row.get('sport', '')
        updated = (row.get('last_updated') or '')[:10]
        breakeven_str = f"{breakeven}d" if breakeven else "N/A"
        pl_str = f"{pl:+,.0f}" if pl is not None else "N/A"
        flip_str = f"+{flip:,.0f}" if flip and flip > 0 else "N/A"
        pl_color = "#00ff88" if pl and pl >= 0 else "#ff4444"
        market_str = f"{market_val:,.0f}" if market_val else "N/A"
        rr_str = f"{rr:.2f}" if rr else "N/A"
        sport_icon = "⛳" if sport == "GOLF" else ("🏀" if sport == "NBA" else "⚾")

        st.markdown(f"""
        <div class='{card_class}'>
            <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
                <div>
                    <div class='player-name'>{sport_icon} {row['name']}</div>
                    <div class='player-meta'>
                        <span style='color:{rc}; font-weight:700;'>{rarity.upper()}</span>
                        &nbsp;·&nbsp; {sport} &nbsp;·&nbsp; Season {row.get('season','2026')}
                        &nbsp;·&nbsp; <span style='color:#2a4a2a;'>Updated {updated}</span>
                    </div>
                </div>
                <div style='text-align:right;'>
                    <div style='font-size:1.4rem; font-weight:900; color:{dcolor};'>{dlabel}</div>
                    <div style='font-size:0.75rem; color:#2a4a2a;'>Value Rating {deal_score}/95</div>
                </div>
            </div>
            <div class='player-stats'>
                <div class='stat-item'><div class='stat-val'>{buy:,.0f}</div><div class='stat-lbl'>Buy Price</div></div>
                <div class='stat-item'><div class='stat-val'>{market_str}</div><div class='stat-lbl'>Market Val</div></div>
                <div class='stat-item'><div class='stat-val'>{breakeven_str}</div><div class='stat-lbl'>Breakeven</div></div>
                <div class='stat-item'><div class='stat-val'>{rr_str}</div><div class='stat-lbl'>R/R</div></div>
                <div class='stat-item'><div class='stat-val' style='color:#00ff88;'>{flip_str}</div><div class='stat-lbl'>Potential Profit</div></div>
                <div class='stat-item'><div class='stat-val' style='color:{pl_color};'>{pl_str}</div><div class='stat-lbl'>My P/L</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- Render tabs ---
with tab_golf:
    golf_df = df[df.get('sport', pd.Series(dtype=str)).str.upper() == 'GOLF'] if 'sport' in df.columns else df
    if golf_df.empty:
        st.info("No golf players yet. Run the scraper.")
    else:
        render_players(golf_df, "golf")

with tab_nba:
    nba_df = df[df.get('sport', pd.Series(dtype=str)).str.upper() == 'NBA'] if 'sport' in df.columns else df
    render_players(nba_df, "nba")

with tab_mlb:
    mlb_df = df[df.get('sport', pd.Series(dtype=str)).str.upper() == 'MLB'] if 'sport' in df.columns else df
    render_players(mlb_df, "mlb")

with tab_all:
    render_players(df, "all")

with tab_flip:
    st.markdown("""
    <div style='font-size:1.1rem; font-weight:800; color:#fff; margin-bottom:8px;'>💸 Daily Flip Opportunities</div>
    <div style='color:#4a8b4a; font-size:0.85rem; margin-bottom:16px;'>Cards where current price is below fair value — instant profit if you flip today.</div>
    """, unsafe_allow_html=True)

    if 'fair_value' in df.columns and 'buy_price' in df.columns:
        flip_df = df[(df['fair_value'].notna()) & (df['fair_value'] > df['buy_price'])].copy()
        flip_df['flip_profit'] = flip_df['fair_value'] - flip_df['buy_price']
        flip_df['flip_roi'] = ((flip_df['flip_profit']) / flip_df['buy_price'] * 100).round(1)
        flip_df = flip_df.sort_values('flip_profit', ascending=False).head(20)

        total = flip_df['flip_profit'].sum()
        st.markdown(f"""
        <div style='background:linear-gradient(135deg,#0a2a0a,#0a1f0a); border:1px solid #00ff88;
        border-radius:12px; padding:16px; margin-bottom:16px; text-align:center;'>
            <div style='font-size:2rem; font-weight:900; color:#00ff88;'>+{total:,.0f} RAX</div>
            <div style='color:#4a8b4a; font-size:0.8rem;'>Total potential profit across {len(flip_df)} cards today</div>
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
            sport_icon = "⛳" if sport == "GOLF" else ("🏀" if sport == "NBA" else "⚾")
            st.markdown(f"""
            <div style='background:#0a1a0a; border:1px solid #1a4a1a; border-radius:10px;
            padding:14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <div style='font-weight:700; color:#fff;'>{sport_icon} {row['name']}</div>
                    <div style='font-size:0.78rem; color:#4a8b4a; margin-top:3px;'>
                        <span style='color:{rc};'>{rarity.upper()}</span> · {sport}
                    </div>
                </div>
                <div style='display:flex; gap:24px; text-align:center;'>
                    <div><div style='color:#666; font-size:0.7rem;'>BUY AT</div><div style='color:#fff; font-weight:700;'>{buy:,.0f}</div></div>
                    <div><div style='color:#666; font-size:0.7rem;'>FAIR VALUE</div><div style='color:#00ccff; font-weight:700;'>{fair:,.0f}</div></div>
                    <div><div style='color:#666; font-size:0.7rem;'>PROFIT</div><div style='color:#00ff88; font-weight:900; font-size:1.1rem;'>+{profit:,.0f}</div></div>
                    <div><div style='color:#666; font-size:0.7rem;'>ROI</div><div style='color:#ffaa00; font-weight:700;'>{roi:.1f}%</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

with tab_picks:
    st.markdown("""
    <div style='font-size:1.1rem; font-weight:800; color:#fff; margin-bottom:4px;'>🎯 Daily Karma Picks</div>
    <div style='color:#4a8b4a; font-size:0.85rem; margin-bottom:16px;'>
        Who to pick in today's polls to maximize karma. Remember: picking the <b style='color:#ffaa00;'>least popular player who wins</b> earns the most karma (up to 100).
    </div>
    """, unsafe_allow_html=True)

    # Daily karma checklist
    st.markdown("""
    <div style='background:#0d1a0d; border:1px solid #1a3a1a; border-radius:12px; padding:16px; margin-bottom:20px;'>
        <div style='font-weight:700; color:#fff; margin-bottom:10px;'>✅ Daily Karma Checklist</div>
        <div style='display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:0.85rem;'>
            <div style='color:#aaa;'>📺 View live game feed <span style='color:#00ff88;'>+10 karma</span></div>
            <div style='color:#aaa;'>💬 Leave one comment <span style='color:#00ff88;'>+10 karma</span></div>
            <div style='color:#aaa;'>👍 React to a play/performance <span style='color:#00ff88;'>+10 karma</span></div>
            <div style='color:#aaa;'>🏆 Vote for Game of the Day <span style='color:#00ff88;'>+20 karma/sport</span></div>
            <div style='color:#aaa;'>📊 Pre-game spread poll <span style='color:#00ff88;'>+10-100 karma</span></div>
            <div style='color:#aaa;'>🌟 Pre-game player poll <span style='color:#00ff88;'>+10-100 karma</span></div>
        </div>
        <div style='margin-top:10px; padding:8px; background:#0a2a0a; border-radius:8px; font-size:0.8rem; color:#ffaa00;'>
            💡 Pro tip: In player polls, pick the player you think will score most BUT who has fewer votes — the less popular the winner, the more karma you earn.
        </div>
    </div>
    """, unsafe_allow_html=True)

    picks_sport = st.selectbox("Sport", ["NBA", "MLB"], key="picks_sport")

    @st.cache_data(ttl=1800)
    def get_nba_games_today():
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            resp = requests.get(
                "https://api.balldontlie.io/v1/games",
                headers={"Authorization": "b6d8fdb5-19e6-42ec-8cf2-90ff63cce84b"},
                params={"dates[]": today, "per_page": 20},
                timeout=8
            )
            return resp.json().get("data", [])
        except Exception:
            return []

    @st.cache_data(ttl=3600)
    def get_nba_scoring_leaders():
        """Fetch current season scoring leaders from NBA Stats API."""
        try:
            resp = requests.get(
                "https://stats.nba.com/stats/leagueleaders",
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nba.com/"},
                params={"LeagueID": "00", "PerMode": "PerGame", "Scope": "S",
                        "Season": "2025-26", "SeasonType": "Regular Season", "StatCategory": "PTS"},
                timeout=10
            )
            data = resp.json()
            hdrs = data["resultSet"]["headers"]
            rows = data["resultSet"]["rowSet"]
            players = []
            for r in rows[:50]:
                p = dict(zip(hdrs, r))
                players.append({
                    "name": p.get("PLAYER"),
                    "team": p.get("TEAM"),
                    "team_id": p.get("TEAM_ID"),
                    "pts": p.get("PTS", 0),
                    "ast": p.get("AST", 0),
                    "reb": p.get("REB", 0),
                    "fg3m": p.get("FG3M", 0),
                    "rank": p.get("RANK"),
                })
            return players
        except Exception:
            return []

    @st.cache_data(ttl=1800)
    def get_mlb_games_today():
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            resp = requests.get(
                "https://statsapi.mlb.com/api/v1/schedule",
                params={"sportId": 1, "date": today, "hydrate": "probablePitcher,team"},
                timeout=8
            )
            dates = resp.json().get("dates", [])
            return dates[0].get("games", []) if dates else []
        except Exception:
            return []

    @st.cache_data(ttl=3600)
    def get_mlb_top_hitters():
        try:
            resp = requests.get(
                "https://statsapi.mlb.com/api/v1/stats/leaders",
                params={"leaderCategories": "homeRuns,battingAverage,rbi", "season": 2025, "limit": 20},
                timeout=8
            )
            return resp.json().get("leagueLeaders", [])
        except Exception:
            return []

    if picks_sport == "NBA":
        games = get_nba_games_today()
        leaders = get_nba_scoring_leaders()
        # Build team -> top players map
        team_players = {}
        for p in leaders:
            t = p["team"]
            if t not in team_players:
                team_players[t] = []
            team_players[t].append(p)

        if not games:
            st.info("No NBA games today or API unavailable.")
        else:
            st.markdown(f"<div style='color:#4a8b4a; font-size:0.85rem; margin-bottom:12px;'>{len(games)} NBA games today</div>", unsafe_allow_html=True)
            for g in games:
                home = g["home_team"]["full_name"]
                away = g["visitor_team"]["full_name"]
                home_abbr = g["home_team"]["abbreviation"]
                away_abbr = g["visitor_team"]["abbreviation"]
                time_str = g.get("status","")[:16].replace("T"," ").replace("Z"," UTC") if "T" in str(g.get("status","")) else g.get("status","")

                # Get top scorers for each team
                home_stars = team_players.get(home_abbr, [])[:3]
                away_stars = team_players.get(away_abbr, [])[:3]

                def player_row(p, is_underdog=False):
                    tag = "⭐ POLL PICK" if is_underdog else ""
                    return f"<div style='display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #1a3a1a;'><span style='color:#fff;'>{p['name']} <span style='color:#ffaa00; font-size:0.75rem;'>{tag}</span></span><span style='color:#4a8b4a; font-size:0.82rem;'>{p['pts']} PPG · {p['reb']} REB · {p['ast']} AST</span></div>"

                home_html = "".join([player_row(p, i==1) for i, p in enumerate(home_stars)]) if home_stars else "<div style='color:#555;'>No data</div>"
                away_html = "".join([player_row(p, i==1) for i, p in enumerate(away_stars)]) if away_stars else "<div style='color:#555;'>No data</div>"

                # Poll pick = #2 scorer on the better team (not the most obvious pick)
                all_stars = home_stars + away_stars
                poll_pick = all_stars[1] if len(all_stars) > 1 else (all_stars[0] if all_stars else None)
                poll_html = f"<div style='margin-top:10px; padding:8px; background:#0a2a0a; border-radius:6px; font-size:0.85rem;'><span style='color:#ffaa00; font-weight:700;'>🎯 Poll Pick: </span><span style='color:#fff; font-weight:700;'>{poll_pick['name']}</span> <span style='color:#4a8b4a;'>({poll_pick['pts']} PPG) — not the #1 pick, earns more karma if correct</span></div>" if poll_pick else ""

                st.markdown(f"""
                <div style='background:#0d1a0d; border:1px solid #1a3a1a; border-radius:10px; padding:14px; margin-bottom:10px;'>
                    <div style='font-weight:700; color:#fff; font-size:1rem;'>🏀 {away} @ {home}</div>
                    <div style='color:#4a8b4a; font-size:0.8rem; margin-top:2px;'>🕐 {time_str}</div>
                    <div style='display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:10px;'>
                        <div>
                            <div style='color:#888; font-size:0.75rem; margin-bottom:4px;'>{away} TOP SCORERS</div>
                            {away_html}
                        </div>
                        <div>
                            <div style='color:#888; font-size:0.75rem; margin-bottom:4px;'>{home} TOP SCORERS</div>
                            {home_html}
                        </div>
                    </div>
                    {poll_html}
                </div>
                """, unsafe_allow_html=True)

    else:  # MLB
        games = get_mlb_games_today()
        if not games:
            st.info("No MLB games today.")
        else:
            st.markdown(f"<div style='color:#4a8b4a; font-size:0.85rem; margin-bottom:12px;'>{len(games)} MLB games today</div>", unsafe_allow_html=True)
            for g in games:
                away = g["teams"]["away"]["team"]["name"]
                home = g["teams"]["home"]["team"]["name"]
                away_pitcher = g["teams"]["away"].get("probablePitcher", {}).get("fullName", "TBD")
                home_pitcher = g["teams"]["home"].get("probablePitcher", {}).get("fullName", "TBD")
                game_time = g.get("gameDate", "")[:16].replace("T", " ") + " UTC"
                st.markdown(f"""
                <div style='background:#0d1a0d; border:1px solid #1a3a1a; border-radius:10px; padding:14px; margin-bottom:8px;'>
                    <div style='font-weight:700; color:#fff; font-size:1rem;'>⚾ {away} @ {home}</div>
                    <div style='color:#4a8b4a; font-size:0.8rem; margin-top:4px;'>🕐 {game_time}</div>
                    <div style='display:flex; gap:20px; margin-top:8px; font-size:0.82rem;'>
                        <div><span style='color:#888;'>Away SP:</span> <span style='color:#fff;'>{away_pitcher}</span></div>
                        <div><span style='color:#888;'>Home SP:</span> <span style='color:#fff;'>{home_pitcher}</span></div>
                    </div>
                    <div style='margin-top:10px; padding:8px; background:#0a1a0a; border-radius:6px; font-size:0.8rem; color:#ffaa00;'>
                        💡 For player poll: pick a power hitter facing a weak pitcher. Avoid the most obvious pick (Judge/Ohtani) — go for their teammate for more karma.
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("""
    <div style='background:#1a1a0a; border:1px solid #3a3a1a; border-radius:10px; padding:14px; margin-top:8px;'>
        <div style='font-weight:700; color:#ffaa00; margin-bottom:8px;'>📈 Karma Poll Strategy</div>
        <div style='font-size:0.82rem; color:#aaa; line-height:1.6;'>
            • <b style='color:#fff;'>Spread polls:</b> Pick the favored team — they cover more often<br>
            • <b style='color:#fff;'>Player polls:</b> The LEAST voted winner gives the MOST karma (up to 100)<br>
            • <b style='color:#fff;'>Best play:</b> Pick a star player's teammate who is likely to have a big game<br>
            • <b style='color:#fff;'>Wager karma:</b> Only wager on games you're confident about — you can lose it<br>
            • <b style='color:#fff;'>In-game polls:</b> Answer every single one — they add up fast (+5 to +50 each)
        </div>
    </div>
    """, unsafe_allow_html=True)

with tab_boost:
    st.markdown("""
    <div style='font-size:1.1rem; font-weight:800; color:#fff; margin-bottom:4px;'>🚀 Boosters & Pack Timing</div>
    <div style='color:#4a8b4a; font-size:0.85rem; margin-bottom:16px;'>
        When to open packs, which booster to use, and who to boost today.
    </div>
    """, unsafe_allow_html=True)

    # Pack reset countdown
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    reset_hour = 15  # 10am EST = 15:00 UTC
    reset_today = now_utc.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
    if now_utc > reset_today:
        reset_today += timedelta(days=1)
    time_left = reset_today - now_utc
    hours_left = int(time_left.total_seconds() // 3600)
    mins_left = int((time_left.total_seconds() % 3600) // 60)

    st.markdown(f"""
    <div style='background:#0d1a0d; border:1px solid #2d8b2d; border-radius:12px; padding:16px; margin-bottom:20px;'>
        <div style='font-weight:700; color:#fff; font-size:1rem; margin-bottom:12px;'>⏰ Pack Reset Timer</div>
        <div style='display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; text-align:center;'>
            <div style='background:#0a1a0a; border-radius:8px; padding:12px;'>
                <div style='font-size:1.5rem; font-weight:900; color:#00ff88;'>{hours_left}h {mins_left}m</div>
                <div style='color:#888; font-size:0.75rem;'>Until next reset</div>
            </div>
            <div style='background:#0a1a0a; border-radius:8px; padding:12px;'>
                <div style='font-size:1.5rem; font-weight:900; color:#ffaa00;'>10am EST</div>
                <div style='color:#888; font-size:0.75rem;'>Daily reset time</div>
            </div>
            <div style='background:#0a1a0a; border-radius:8px; padding:12px;'>
                <div style='font-size:1.5rem; font-weight:900; color:#ff4488;'>2,000</div>
                <div style='color:#888; font-size:0.75rem;'>Yesterday packs (grab fast)</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Daily pack limits
    st.markdown("""
    <div style='background:#0d1a0d; border:1px solid #1a3a1a; border-radius:12px; padding:16px; margin-bottom:20px;'>
        <div style='font-weight:700; color:#fff; margin-bottom:10px;'>📦 Daily Pack Limits</div>
        <div style='display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:0.85rem;'>
            <div style='background:#0a1a0a; border-radius:8px; padding:10px;'>
                <div style='color:#fff; font-weight:600;'>Starter Pack — 100 RAX</div>
                <div style='color:#888; font-size:0.78rem; margin-top:4px;'>3 plays + 1 Common/Uncommon booster · 3/day</div>
            </div>
            <div style='background:#0a1a0a; border-radius:8px; padding:10px;'>
                <div style='color:#fff; font-weight:600;'>General Pack — 200 RAX</div>
                <div style='color:#888; font-size:0.78rem; margin-top:4px;'>5 plays + 1 Rare/Epic/Legendary booster · 5/day</div>
            </div>
            <div style='background:#0a1a0a; border-radius:8px; padding:10px;'>
                <div style='color:#ffaa00; font-weight:600;'>Yesterday Pack — 250 RAX ⚡</div>
                <div style='color:#888; font-size:0.78rem; margin-top:4px;'>5 yesterday plays + booster · 3/day · Only 2,000 available</div>
            </div>
            <div style='background:#0a1a0a; border-radius:8px; padding:10px;'>
                <div style='color:#fff; font-weight:600;'>Player/Team Pack</div>
                <div style='color:#888; font-size:0.78rem; margin-top:4px;'>Targeted plays for specific player/team</div>
            </div>
        </div>
        <div style='margin-top:10px; padding:8px; background:#1a1a0a; border-radius:8px; font-size:0.8rem; color:#ffaa00;'>
            💡 Open Yesterday packs RIGHT at 10am EST — they sell out fast. Set an alarm.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Booster tiers and RAX values
    st.markdown("""
    <div style='background:#0d1a0d; border:1px solid #1a3a1a; border-radius:12px; padding:16px; margin-bottom:20px;'>
        <div style='font-weight:700; color:#fff; margin-bottom:10px;'>⚡ Booster Card Tiers</div>
        <div style='font-size:0.8rem; color:#888; margin-bottom:10px;'>Example: NBA 3-pointer booster RAX per made 3</div>
        <div style='display:flex; flex-direction:column; gap:6px;'>
            <div style='display:flex; justify-content:space-between; background:#0a1a0a; border-radius:6px; padding:8px 12px;'>
                <span style='color:#aaa; font-weight:600;'>Common</span>
                <span style='color:#aaa;'>~5 RAX per stat</span>
                <span style='color:#888; font-size:0.75rem;'>From Starter packs</span>
            </div>
            <div style='display:flex; justify-content:space-between; background:#0a1a0a; border-radius:6px; padding:8px 12px;'>
                <span style='color:#00cc44; font-weight:600;'>Uncommon</span>
                <span style='color:#00cc44;'>~8 RAX per stat</span>
                <span style='color:#888; font-size:0.75rem;'>From Starter packs</span>
            </div>
            <div style='display:flex; justify-content:space-between; background:#0a1a0a; border-radius:6px; padding:8px 12px;'>
                <span style='color:#ff8800; font-weight:600;'>Rare</span>
                <span style='color:#ff8800;'>~12 RAX per stat</span>
                <span style='color:#888; font-size:0.75rem;'>From General/Yesterday packs</span>
            </div>
            <div style='display:flex; justify-content:space-between; background:#0a1a0a; border-radius:6px; padding:8px 12px;'>
                <span style='color:#ff3333; font-weight:600;'>Epic</span>
                <span style='color:#ff3333;'>~15 RAX per stat</span>
                <span style='color:#888; font-size:0.75rem;'>From General/Yesterday packs</span>
            </div>
            <div style='display:flex; justify-content:space-between; background:#0a1a0a; border-radius:6px; padding:8px 12px;'>
                <span style='color:#aa44ff; font-weight:600;'>Legendary</span>
                <span style='color:#aa44ff;'>~20 RAX per stat</span>
                <span style='color:#888; font-size:0.75rem;'>From General/Yesterday packs</span>
            </div>
            <div style='display:flex; justify-content:space-between; background:#0a1a0a; border-radius:6px; padding:8px 12px;'>
                <span style='color:#ffaa00; font-weight:600;'>Mystic</span>
                <span style='color:#ffaa00;'>~30 RAX per stat</span>
                <span style='color:#888; font-size:0.75rem;'>Rare drop</span>
            </div>
            <div style='display:flex; justify-content:space-between; background:#0a1a0a; border-radius:6px; padding:8px 12px;'>
                <span style='color:#ff44aa; font-weight:600;'>Iconic</span>
                <span style='color:#ff44aa;'>~50+ RAX per stat</span>
                <span style='color:#888; font-size:0.75rem;'>Very rare drop</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Who to boost today
    st.markdown("""
    <div style='font-weight:700; color:#fff; margin-bottom:10px;'>🎯 Who to Boost Today</div>
    <div style='color:#4a8b4a; font-size:0.85rem; margin-bottom:12px;'>
        Use your best booster on the player most likely to rack up the boosted stat today.
        Apply before their game starts — boosters expire after the game.
    </div>
    """, unsafe_allow_html=True)

    boost_sport = st.selectbox("Sport", ["NBA", "MLB", "Golf"], key="boost_sport")

    @st.cache_data(ttl=3600)
    def get_golf_birdie_stats():
        """Fetch birdies per round and eagles % from PGA Tour GraphQL."""
        PGA_HEADERS = {
            "User-Agent": "Mozilla/5.0",
            "x-api-key": "da2-gsrx5bibzbb4njvhl7t37wqyl4",
            "Content-Type": "application/json"
        }
        birdies, eagles = {}, {}
        try:
            resp = requests.post(
                "https://orchestrator.pgatour.com/graphql",
                headers=PGA_HEADERS,
                json={"query": """{ statDetails(tourCode: R, statId: "02415", year: 2026) { rows { ... on StatDetailsPlayer { playerName rank stats { statValue } } } } }"""},
                timeout=10
            )
            for r in resp.json().get("data", {}).get("statDetails", {}).get("rows", []):
                val = r.get("stats", [{}])[0].get("statValue", "0")
                try:
                    birdies[r["playerName"]] = float(val)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            resp2 = requests.post(
                "https://orchestrator.pgatour.com/graphql",
                headers=PGA_HEADERS,
                json={"query": """{ statDetails(tourCode: R, statId: "02416", year: 2026) { rows { ... on StatDetailsPlayer { playerName rank stats { statValue } } } } }"""},
                timeout=10
            )
            for r in resp2.json().get("data", {}).get("statDetails", {}).get("rows", []):
                val = r.get("stats", [{}])[0].get("statValue", "0")
                try:
                    eagles[r["playerName"]] = float(val.replace("%",""))
                except Exception:
                    pass
        except Exception:
            pass
        return birdies, eagles

    if boost_sport == "NBA":
        nba_games = get_nba_games_today() if 'get_nba_games_today' in dir() else []
        if not nba_games:
            st.info("No NBA games today or API unavailable.")
        else:
            st.markdown(f"""
            <div style='background:#0a1a0a; border:1px solid #1a3a1a; border-radius:10px; padding:14px;'>
                <div style='color:#fff; font-weight:700; margin-bottom:8px;'>Today's NBA Games ({len(nba_games)} games)</div>
                <div style='font-size:0.82rem; color:#aaa; line-height:1.8;'>
                    {'<br>'.join([f"🏀 {g['visitor_team']['full_name']} @ {g['home_team']['full_name']}" for g in nba_games])}
                </div>
                <div style='margin-top:12px; padding:8px; background:#1a1a0a; border-radius:6px; font-size:0.8rem;'>
                    <div style='color:#ffaa00; font-weight:700; margin-bottom:6px;'>Best booster targets by stat:</div>
                    <div style='color:#aaa;'>🎯 3PT booster → Pick a high-volume 3pt shooter (Curry, Trae, Lillard)</div>
                    <div style='color:#aaa;'>🏀 Points booster → Pick the highest scorer in a high-total game</div>
                    <div style='color:#aaa;'>🔄 Assists booster → Pick a pass-first PG (Haliburton, Brunson, SGA)</div>
                    <div style='color:#aaa;'>💪 Rebounds booster → Pick a big in a fast-paced game (Jokic, Embiid, Gobert)</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        mlb_games = get_mlb_games_today() if 'get_mlb_games_today' in dir() else []
        if not mlb_games:
            st.info("No MLB games today.")
        else:
            st.markdown("<div style='display:flex; flex-direction:column; gap:8px;'>", unsafe_allow_html=True)
            for g in mlb_games[:8]:
                away = g["teams"]["away"]["team"]["name"]
                home = g["teams"]["home"]["team"]["name"]
                away_p = g["teams"]["away"].get("probablePitcher", {}).get("fullName", "TBD")
                home_p = g["teams"]["home"].get("probablePitcher", {}).get("fullName", "TBD")
                st.markdown(f"""
                <div style='background:#0a1a0a; border:1px solid #1a3a1a; border-radius:10px; padding:12px; margin-bottom:6px;'>
                    <div style='font-weight:700; color:#fff;'>⚾ {away} @ {home}</div>
                    <div style='display:flex; gap:20px; margin-top:6px; font-size:0.82rem;'>
                        <div><span style='color:#888;'>Away SP:</span> <span style='color:#ff8800;'>{away_p}</span></div>
                        <div><span style='color:#888;'>Home SP:</span> <span style='color:#ff8800;'>{home_p}</span></div>
                    </div>
                    <div style='margin-top:8px; font-size:0.78rem; color:#ffaa00;'>
                        💡 Boost a SP if they're facing a weak lineup. Boost a power hitter if facing a weak pitcher.
                    </div>
                </div>
                """, unsafe_allow_html=True)

    if boost_sport == "Golf":
        birdies, eagles = get_golf_birdie_stats()

        # Booster RAX estimates based on Real app docs (Legendary NBA 3pt = 20 RAX)
        BOOSTER_RAX = {
            "Common":    {"birdie": 3,  "eagle": 8},
            "Uncommon":  {"birdie": 5,  "eagle": 12},
            "Rare":      {"birdie": 8,  "eagle": 20},
            "Epic":      {"birdie": 12, "eagle": 30},
            "Legendary": {"birdie": 18, "eagle": 45},
            "Mystic":    {"birdie": 28, "eagle": 70},
            "Iconic":    {"birdie": 45, "eagle": 110},
        }

        st.markdown("""
        <div style='background:#0d1a0d; border:1px solid #1a3a1a; border-radius:12px; padding:16px; margin-bottom:16px;'>
            <div style='font-weight:700; color:#fff; margin-bottom:10px;'>⛳ Golf Booster RAX Values (estimated)</div>
            <div style='display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; font-size:0.82rem;'>
        """, unsafe_allow_html=True)

        rarity_colors = {"Common":"#aaa","Uncommon":"#00cc44","Rare":"#ff8800","Epic":"#ff3333","Legendary":"#aa44ff","Mystic":"#ffaa00","Iconic":"#ff44aa"}
        for rarity, vals in BOOSTER_RAX.items():
            rc = rarity_colors.get(rarity, "#fff")
            st.markdown(f"""
            <div style='background:#0a1a0a; border-radius:6px; padding:8px; text-align:center;'>
                <div style='color:{rc}; font-weight:700;'>{rarity}</div>
                <div style='color:#aaa; font-size:0.78rem;'>🐦 {vals['birdie']} RAX/birdie</div>
                <div style='color:#aaa; font-size:0.78rem;'>🦅 {vals['eagle']} RAX/eagle</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("</div></div>", unsafe_allow_html=True)

        # Who to boost
        st.markdown("<div style='font-weight:700; color:#fff; margin-bottom:8px;'>🎯 Best Players to Boost Today</div>", unsafe_allow_html=True)
        st.markdown("<div style='color:#4a8b4a; font-size:0.82rem; margin-bottom:12px;'>Ranked by projected RAX from birdies using a Legendary booster. Masters is active — 2x RAX multiplier applies.</div>", unsafe_allow_html=True)

        boost_rarity = st.selectbox("Your booster rarity", list(BOOSTER_RAX.keys()), index=4, key="golf_boost_rarity")
        rax_per_birdie = BOOSTER_RAX[boost_rarity]["birdie"]
        rax_per_eagle = BOOSTER_RAX[boost_rarity]["eagle"]

        # Combine birdie + eagle projections (4 rounds assumed, Masters = 2x)
        IS_MAJOR = True  # Masters is on
        multiplier = 2.0 if IS_MAJOR else 1.0

        rows = []
        all_players = set(birdies.keys()) | set(eagles.keys())
        for name in all_players:
            b = birdies.get(name, 0)
            e_pct = eagles.get(name, 0) / 100
            # Per round projected RAX
            birdie_rax = b * rax_per_birdie * multiplier
            eagle_rax = e_pct * 18 * rax_per_eagle * multiplier  # ~18 holes, eagle% per hole
            total = round(birdie_rax + eagle_rax, 1)
            rows.append({"Player": name, "Birdies/Rd": b, "Eagle%": f"{eagles.get(name,0):.2f}%",
                         "Est. RAX/Round": total, "Boost?": "✅ YES" if total > 30 else ("⚠️ MAYBE" if total > 15 else "❌ SKIP")})

        rows.sort(key=lambda x: x["Est. RAX/Round"], reverse=True)

        for r in rows[:20]:
            color = "#00ff88" if "YES" in r["Boost?"] else ("#ffaa00" if "MAYBE" in r["Boost?"] else "#555")
            st.markdown(f"""
            <div style='background:#0a1a0a; border:1px solid #1a3a1a; border-radius:8px; padding:10px; margin-bottom:6px;
            display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <div style='color:#fff; font-weight:700;'>⛳ {r["Player"]}</div>
                    <div style='color:#888; font-size:0.78rem;'>{r["Birdies/Rd"]} birdies/rd · {r["Eagle%"]} eagle rate</div>
                </div>
                <div style='text-align:right;'>
                    <div style='color:#00ccff; font-weight:700;'>{r["Est. RAX/Round"]} RAX/rd</div>
                    <div style='color:{color}; font-weight:700; font-size:0.85rem;'>{r["Boost?"]}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style='background:#1a1a0a; border:1px solid #3a3a1a; border-radius:8px; padding:10px; margin-top:8px; font-size:0.8rem; color:#888;'>
            ⚠️ RAX values are estimates based on Real app docs. Actual values may differ. Masters 2x multiplier applied.
            Apply booster before the player's round starts.
        </div>
        """, unsafe_allow_html=True)

with tab_calc:
    st.markdown("""
    <div style='font-size:1.1rem; font-weight:800; color:#fff; margin-bottom:4px;'>⚡ Upgrade Calculator</div>
    <div style='color:#4a8b4a; font-size:0.85rem; margin-bottom:16px;'>
        Is it cheaper to grind Rares or buy the target rarity directly?
    </div>
    """, unsafe_allow_html=True)

    search_col, target_col = st.columns([3, 1])
    with search_col:
        player_search = st.text_input("Search player", placeholder="e.g. Scottie Scheffler", key="upgrade_search")
    with target_col:
        target_rarity = st.selectbox("Target", ["Legendary", "Mystic", "Iconic"], key="upgrade_target")
    if player_search:
        suggestions = get_player_suggestions(player_search)
        if not suggestions:
            st.warning("No players found.")
        else:
            player_options = {f"{s['name']} ({s.get('sport','').upper()})": s for s in suggestions[:10]}
            selected = st.selectbox("Select player", list(player_options.keys()))
            player = player_options[selected]
            entity_id = player["entityId"]
            season = player.get("season", 2026)

            with st.spinner("Fetching live listings..."):
                live = get_player_listings(entity_id, season)

            target_rating = RARITY_RATING[target_rarity]
            target_rarity_num = {v: k for k, v in RARITY_NUM.items()}.get(target_rarity)
            direct_listings = sorted([l for l in live if l.get("rarity") == target_rarity_num], key=lambda x: x.get("bid", 999999))
            direct_price = direct_listings[0]["bid"] if direct_listings else None
            grind_cost, grind_rating, passes_used = calc_upgrade_cost(live, target_rating, target_rarity_num)

            c1, c2 = st.columns(2)
            with c1:
                if direct_price:
                    st.markdown(f"""
                    <div style='background:#0d1a0d; border:1px solid #4488ff; border-radius:12px; padding:20px; text-align:center;'>
                        <div style='color:#888; font-size:0.8rem; text-transform:uppercase;'>Buy {target_rarity} Directly</div>
                        <div style='font-size:2rem; font-weight:900; color:#4488ff; margin:8px 0;'>{direct_price:,} RAX</div>
                        <div style='color:#555; font-size:0.75rem;'>Floor price on market</div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='background:#0d1a0d; border:1px solid #333; border-radius:12px; padding:20px; text-align:center; color:#555;'>No {target_rarity} listed</div>", unsafe_allow_html=True)

            with c2:
                if passes_used:
                    cheaper = direct_price and grind_cost < direct_price
                    border = "#00ff88" if cheaper else "#ff4444"
                    label = "CHEAPER TO GRIND ✅" if cheaper else "CHEAPER TO BUY DIRECT ❌"
                    savings = (direct_price - grind_cost) if direct_price else 0
                    savings_html = f"<div style='color:#00ff88; font-size:0.85rem; margin-top:4px;'>Save {savings:,} RAX</div>" if cheaper and savings > 0 else ""
                    st.markdown(f"""
                    <div style='background:#0a1a0a; border:1px solid {border}; border-radius:12px; padding:20px; text-align:center;'>
                        <div style='color:#888; font-size:0.8rem; text-transform:uppercase;'>Grind with Cheaper Passes</div>
                        <div style='font-size:2rem; font-weight:900; color:{border}; margin:8px 0;'>{grind_cost:,} RAX</div>
                        <div style='color:#aaa; font-size:0.8rem; font-weight:700;'>{label}</div>
                        {savings_html}
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='background:#0d1a0d; border:1px solid #333; border-radius:12px; padding:20px; text-align:center; color:#555;'>Not enough passes listed to grind</div>", unsafe_allow_html=True)

            if live:
                st.markdown(f"<br><div style='color:#4a8b4a; font-size:0.85rem;'>{len(live)} live listings for {player['name']}</div>", unsafe_allow_html=True)
                rows = [{"Rarity": RARITY_NUM.get(l.get("rarity"), "?"), "Price (RAX)": l.get("bid", 0),
                         "Rating": round(l.get("value", 0), 1), "RAX/Rating": round(l.get("rax_per_rating", 0), 2)}
                        for l in sorted(live, key=lambda x: x.get("bid", 0))]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.markdown("<br><div style='text-align:center; color:#1a3a1a; font-size:0.75rem;'>RaxCartel · Data from realapp.tools · Created by @lee</div>", unsafe_allow_html=True)
