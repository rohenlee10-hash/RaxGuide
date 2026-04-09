import streamlit as st
import requests
import firebase_admin
from firebase_admin import credentials, firestore
import os, json
from datetime import datetime, timezone, timedelta

# --- Firebase ---
if not firebase_admin._apps:
    fc = os.environ.get("FIREBASE_CREDENTIALS")
    cred = credentials.Certificate(json.loads(fc)) if fc else credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Page config ---
st.set_page_config(page_title="RaxGuide", page_icon="⛳", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
html, body, [class*="css"] { font-family:'Inter',sans-serif; background:#060d06; color:#e0e0e0; }
.stApp { background:#060d06; }
.stTabs [data-baseweb="tab-list"] { background:#0d1a0d; border-radius:12px; padding:4px; gap:4px; }
.stTabs [data-baseweb="tab"] { background:transparent; color:#888; border-radius:8px; font-weight:600; padding:8px 20px; }
.stTabs [aria-selected="true"] { background:linear-gradient(135deg,#1a6b1a,#2d8b2d) !important; color:white !important; }
.card { background:#0d1a0d; border:1px solid #1a3a1a; border-radius:12px; padding:16px; margin-bottom:10px; }
.card-green { border-color:#00ff88 !important; box-shadow:0 0 12px rgba(0,255,136,0.1); }
.card-yellow { border-color:#ffaa00 !important; }
.card-red { border-color:#333 !important; }
.stSelectbox > div { background:#0d1a0d; }
.stTextInput > div > input { background:#0d1a0d; color:white; }
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown("""
<div style='text-align:center; padding:24px 0 8px;'>
    <div style='font-size:2.8rem; font-weight:900; background:linear-gradient(135deg,#00ff88,#2d8b2d);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;'>⛳ RaxGuide</div>
    <div style='color:#2d8b2d; font-size:0.85rem; margin-top:4px;'>Boost Intelligence · Daily Picks · Pack Timing</div>
    <div style='color:#1a3a1a; font-size:0.72rem; margin-top:4px;'>by <span style='color:#00ff88;'>@lee</span></div>
</div>
""", unsafe_allow_html=True)

# --- Booster RAX per stat (based on Real app docs) ---
BOOSTER_RAX = {
    "Common":    {"birdie":3,  "eagle":8,  "3pt":5,  "pts":0.8, "ast":1.0, "reb":0.8, "hr":8,  "k":3},
    "Uncommon":  {"birdie":5,  "eagle":12, "3pt":8,  "pts":1.2, "ast":1.5, "reb":1.2, "hr":12, "k":5},
    "Rare":      {"birdie":8,  "eagle":20, "3pt":12, "pts":2.0, "ast":2.5, "reb":2.0, "hr":18, "k":8},
    "Epic":      {"birdie":12, "eagle":30, "3pt":15, "pts":3.0, "ast":3.5, "reb":3.0, "hr":25, "k":12},
    "Legendary": {"birdie":18, "eagle":45, "3pt":20, "pts":4.5, "ast":5.0, "reb":4.0, "hr":35, "k":18},
    "Mystic":    {"birdie":28, "eagle":70, "3pt":30, "pts":7.0, "ast":8.0, "reb":6.0, "hr":55, "k":28},
    "Iconic":    {"birdie":45, "eagle":110,"3pt":50, "pts":12,  "ast":14,  "reb":10,  "hr":90, "k":45},
}
RARITY_COLORS = {
    "Common":"#aaa","Uncommon":"#00cc44","Rare":"#ff8800",
    "Epic":"#ff3333","Legendary":"#aa44ff","Mystic":"#ffaa00","Iconic":"#ff44aa"
}

# --- Cached data fetchers ---
@st.cache_data(ttl=3600)
def get_golf_stats():
    PGA = {"User-Agent":"Mozilla/5.0","x-api-key":"da2-gsrx5bibzbb4njvhl7t37wqyl4","Content-Type":"application/json"}
    birdies, eagles = {}, {}
    try:
        r = requests.post("https://orchestrator.pgatour.com/graphql", headers=PGA,
            json={"query":"""{ statDetails(tourCode:R,statId:"02415",year:2026){rows{...on StatDetailsPlayer{playerName rank stats{statValue}}}}}"""},timeout=10)
        for row in r.json().get("data",{}).get("statDetails",{}).get("rows",[]):
            try: birdies[row["playerName"]] = float(row["stats"][0]["statValue"])
            except: pass
    except: pass
    try:
        r2 = requests.post("https://orchestrator.pgatour.com/graphql", headers=PGA,
            json={"query":"""{ statDetails(tourCode:R,statId:"02416",year:2026){rows{...on StatDetailsPlayer{playerName rank stats{statValue}}}}}"""},timeout=10)
        for row in r2.json().get("data",{}).get("statDetails",{}).get("rows",[]):
            try: eagles[row["playerName"]] = float(row["stats"][0]["statValue"].replace("%",""))
            except: pass
    except: pass
    return birdies, eagles

@st.cache_data(ttl=3600)
def get_nba_stats():
    try:
        r = requests.get("https://stats.nba.com/stats/leagueleaders",
            headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.nba.com/"},
            params={"LeagueID":"00","PerMode":"PerGame","Scope":"S","Season":"2025-26","SeasonType":"Regular Season","StatCategory":"PTS"},
            timeout=10)
        hdrs = r.json()["resultSet"]["headers"]
        return [dict(zip(hdrs,row)) for row in r.json()["resultSet"]["rowSet"][:100]]
    except: return []

@st.cache_data(ttl=1800)
def get_nba_games():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        r = requests.get("https://api.balldontlie.io/v1/games",
            headers={"Authorization":"b6d8fdb5-19e6-42ec-8cf2-90ff63cce84b"},
            params={"dates[]":today,"per_page":20},timeout=8)
        return r.json().get("data",[])
    except: return []

@st.cache_data(ttl=1800)
def get_mlb_games():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        r = requests.get("https://statsapi.mlb.com/api/v1/schedule",
            params={"sportId":1,"date":today,"hydrate":"probablePitcher,team"},timeout=8)
        dates = r.json().get("dates",[])
        return dates[0].get("games",[]) if dates else []
    except: return []

# --- Tabs ---
tab_golf, tab_nba, tab_mlb, tab_packs = st.tabs(["⛳ Golf Boosts","🏀 NBA Boosts","⚾ MLB Boosts","📦 Pack Timing"])

# ── GOLF ──────────────────────────────────────────────────────────────
with tab_golf:
    st.markdown("<div style='color:#4a8b4a; font-size:0.85rem; margin-bottom:16px;'>Ranked by projected RAX per round. Masters active — 2x multiplier applied.</div>", unsafe_allow_html=True)

    col1, col2 = st.columns([1,3])
    with col1:
        boost_rarity = st.selectbox("Your booster", list(BOOSTER_RAX.keys()), index=4, key="golf_rarity")
        is_major = st.checkbox("Major tournament (2x)", value=True, key="golf_major")
    
    multiplier = 2.0 if is_major else 1.0
    rax_b = BOOSTER_RAX[boost_rarity]["birdie"]
    rax_e = BOOSTER_RAX[boost_rarity]["eagle"]

    birdies, eagles = get_golf_stats()

    rows = []
    for name in set(birdies) | set(eagles):
        b = birdies.get(name, 0)
        e = eagles.get(name, 0) / 100
        birdie_rax = b * rax_b * multiplier
        eagle_rax = e * 18 * rax_e * multiplier
        total = round(birdie_rax + eagle_rax, 1)
        rows.append({"name": name, "birdies": b, "eagle_pct": eagles.get(name, 0), "total": total})

    rows.sort(key=lambda x: x["total"], reverse=True)

    with col2:
        st.markdown(f"""
        <div style='display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:16px;'>
            <div class='card' style='text-align:center;'>
                <div style='font-size:1.4rem; font-weight:900; color:#00ff88;'>{rax_b} RAX</div>
                <div style='color:#888; font-size:0.75rem;'>per birdie ({boost_rarity})</div>
            </div>
            <div class='card' style='text-align:center;'>
                <div style='font-size:1.4rem; font-weight:900; color:#ffaa00;'>{rax_e} RAX</div>
                <div style='color:#888; font-size:0.75rem;'>per eagle ({boost_rarity})</div>
            </div>
            <div class='card' style='text-align:center;'>
                <div style='font-size:1.4rem; font-weight:900; color:#4488ff;'>{multiplier}x</div>
                <div style='color:#888; font-size:0.75rem;'>tournament multiplier</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    for r in rows[:25]:
        verdict = "✅ BOOST" if r["total"] > 35 else ("⚠️ MAYBE" if r["total"] > 18 else "❌ SKIP")
        vc = "#00ff88" if "BOOST" in verdict else ("#ffaa00" if "MAYBE" in verdict else "#444")
        card_cls = "card card-green" if "BOOST" in verdict else ("card card-yellow" if "MAYBE" in verdict else "card card-red")
        st.markdown(f"""
        <div class='{card_cls}' style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <div style='font-weight:700; color:#fff; font-size:0.95rem;'>⛳ {r["name"]}</div>
                <div style='color:#888; font-size:0.78rem; margin-top:3px;'>
                    🐦 {r["birdies"]:.2f} birdies/rd &nbsp;·&nbsp; 🦅 {r["eagle_pct"]:.2f}% eagle rate
                </div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:1.3rem; font-weight:900; color:#00ccff;'>{r["total"]} RAX/rd</div>
                <div style='font-weight:700; color:{vc};'>{verdict}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ── NBA ──────────────────────────────────────────────────────────────
with tab_nba:
    st.markdown("<div style='color:#4a8b4a; font-size:0.85rem; margin-bottom:16px;'>Projected RAX per game based on season averages and your booster.</div>", unsafe_allow_html=True)

    col1, col2 = st.columns([1,3])
    with col1:
        nba_rarity = st.selectbox("Your booster", list(BOOSTER_RAX.keys()), index=4, key="nba_rarity")
        nba_stat = st.selectbox("Booster stat", ["pts","3pt","ast","reb"], key="nba_stat")
        nba_playoffs = st.checkbox("Playoffs (2x)", value=False, key="nba_playoffs")

    nba_mult = 2.0 if nba_playoffs else 1.0
    rax_per = BOOSTER_RAX[nba_rarity][nba_stat]
    stat_map = {"pts":"PTS","3pt":"FG3M","ast":"AST","reb":"REB"}
    stat_key = stat_map[nba_stat]

    players = get_nba_stats()
    games = get_nba_games()
    playing_teams = set()
    for g in games:
        playing_teams.add(g["home_team"]["abbreviation"])
        playing_teams.add(g["visitor_team"]["abbreviation"])

    with col2:
        st.markdown(f"""
        <div style='display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:16px;'>
            <div class='card' style='text-align:center;'>
                <div style='font-size:1.4rem; font-weight:900; color:#00ff88;'>{rax_per} RAX</div>
                <div style='color:#888; font-size:0.75rem;'>per {nba_stat} ({nba_rarity})</div>
            </div>
            <div class='card' style='text-align:center;'>
                <div style='font-size:1.4rem; font-weight:900; color:#4488ff;'>{len(games)}</div>
                <div style='color:#888; font-size:0.75rem;'>games today</div>
            </div>
            <div class='card' style='text-align:center;'>
                <div style='font-size:1.4rem; font-weight:900; color:#ffaa00;'>{nba_mult}x</div>
                <div style='color:#888; font-size:0.75rem;'>multiplier</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    rows = []
    for p in players:
        stat_val = p.get(stat_key, 0) or 0
        proj_rax = round(stat_val * rax_per * nba_mult, 1)
        playing = p.get("TEAM") in playing_teams
        rows.append({"name": p.get("PLAYER"), "team": p.get("TEAM"), "stat": stat_val, "rax": proj_rax, "playing": playing})

    rows.sort(key=lambda x: x["rax"], reverse=True)

    shown = 0
    for r in rows:
        if not r["playing"] and shown < 5:
            pass
        if shown >= 20:
            break
        verdict = "✅ BOOST" if r["rax"] > 40 else ("⚠️ MAYBE" if r["rax"] > 20 else "❌ SKIP")
        vc = "#00ff88" if "BOOST" in verdict else ("#ffaa00" if "MAYBE" in verdict else "#444")
        card_cls = "card card-green" if "BOOST" in verdict else ("card card-yellow" if "MAYBE" in verdict else "card card-red")
        playing_tag = f"<span style='color:#00ff88; font-size:0.72rem;'>● PLAYING TODAY</span>" if r["playing"] else "<span style='color:#555; font-size:0.72rem;'>○ not playing</span>"
        st.markdown(f"""
        <div class='{card_cls}' style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <div style='font-weight:700; color:#fff; font-size:0.95rem;'>🏀 {r["name"]} <span style='color:#888; font-size:0.8rem;'>({r["team"]})</span></div>
                <div style='color:#888; font-size:0.78rem; margin-top:3px;'>
                    {r["stat"]:.1f} {nba_stat}/game &nbsp;·&nbsp; {playing_tag}
                </div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:1.3rem; font-weight:900; color:#00ccff;'>{r["rax"]} RAX/game</div>
                <div style='font-weight:700; color:{vc};'>{verdict}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        shown += 1

# ── MLB ──────────────────────────────────────────────────────────────
with tab_mlb:
    st.markdown("<div style='color:#4a8b4a; font-size:0.85rem; margin-bottom:16px;'>Today's starting pitchers and boost recommendations.</div>", unsafe_allow_html=True)

    col1, col2 = st.columns([1,3])
    with col1:
        mlb_rarity = st.selectbox("Your booster", list(BOOSTER_RAX.keys()), index=4, key="mlb_rarity")
        mlb_stat = st.selectbox("Booster stat", ["k","hr"], key="mlb_stat")
        mlb_playoffs = st.checkbox("Playoffs (2x)", value=False, key="mlb_playoffs")

    mlb_mult = 2.0 if mlb_playoffs else 1.0
    mlb_rax = BOOSTER_RAX[mlb_rarity][mlb_stat]
    games = get_mlb_games()

    with col2:
        st.markdown(f"""
        <div style='display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:16px;'>
            <div class='card' style='text-align:center;'>
                <div style='font-size:1.4rem; font-weight:900; color:#00ff88;'>{mlb_rax} RAX</div>
                <div style='color:#888; font-size:0.75rem;'>per {mlb_stat} ({mlb_rarity})</div>
            </div>
            <div class='card' style='text-align:center;'>
                <div style='font-size:1.4rem; font-weight:900; color:#4488ff;'>{len(games)}</div>
                <div style='color:#888; font-size:0.75rem;'>games today</div>
            </div>
            <div class='card' style='text-align:center;'>
                <div style='font-size:1.4rem; font-weight:900; color:#ffaa00;'>{mlb_mult}x</div>
                <div style='color:#888; font-size:0.75rem;'>multiplier</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    if not games:
        st.info("No MLB games today.")
    else:
        # SP avg ~6 K/game, HR hitters avg ~0.15 HR/game
        sp_avg_k = 6.0
        hr_avg = 0.15
        for g in games:
            away = g["teams"]["away"]["team"]["name"]
            home = g["teams"]["home"]["team"]["name"]
            away_p = g["teams"]["away"].get("probablePitcher", {}).get("fullName", "TBD")
            home_p = g["teams"]["home"].get("probablePitcher", {}).get("fullName", "TBD")
            game_time = g.get("gameDate","")[:16].replace("T"," ") + " UTC"

            if mlb_stat == "k":
                away_rax = round(sp_avg_k * mlb_rax * mlb_mult, 1)
                home_rax = round(sp_avg_k * mlb_rax * mlb_mult, 1)
                away_verdict = "✅ BOOST SP" if away_rax > 40 else "⚠️ MAYBE"
                home_verdict = "✅ BOOST SP" if home_rax > 40 else "⚠️ MAYBE"
                away_detail = f"{sp_avg_k} K avg · {away_rax} RAX proj"
                home_detail = f"{sp_avg_k} K avg · {home_rax} RAX proj"
            else:
                hr_rax = round(hr_avg * mlb_rax * mlb_mult, 1)
                away_verdict = "⚠️ MAYBE"
                home_verdict = "⚠️ MAYBE"
                away_detail = f"~{hr_avg} HR/game · {hr_rax} RAX proj"
                home_detail = f"~{hr_avg} HR/game · {hr_rax} RAX proj"

            st.markdown(f"""
            <div class='card'>
                <div style='font-weight:700; color:#fff; margin-bottom:8px;'>⚾ {away} @ {home} <span style='color:#555; font-size:0.78rem;'>{game_time}</span></div>
                <div style='display:grid; grid-template-columns:1fr 1fr; gap:10px;'>
                    <div style='background:#0a1a0a; border-radius:8px; padding:10px;'>
                        <div style='color:#888; font-size:0.72rem; margin-bottom:4px;'>AWAY SP</div>
                        <div style='color:#fff; font-weight:700;'>{away_p}</div>
                        <div style='color:#4a8b4a; font-size:0.78rem; margin-top:4px;'>{away_detail}</div>
                        <div style='color:#00ff88; font-weight:700; margin-top:4px;'>{away_verdict}</div>
                    </div>
                    <div style='background:#0a1a0a; border-radius:8px; padding:10px;'>
                        <div style='color:#888; font-size:0.72rem; margin-bottom:4px;'>HOME SP</div>
                        <div style='color:#fff; font-weight:700;'>{home_p}</div>
                        <div style='color:#4a8b4a; font-size:0.78rem; margin-top:4px;'>{home_detail}</div>
                        <div style='color:#00ff88; font-weight:700; margin-top:4px;'>{home_verdict}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ── PACK TIMING ──────────────────────────────────────────────────────
with tab_packs:
    now_utc = datetime.now(timezone.utc)
    reset = now_utc.replace(hour=15, minute=0, second=0, microsecond=0)
    if now_utc > reset:
        reset += timedelta(days=1)
    tl = reset - now_utc
    h, m = int(tl.total_seconds()//3600), int((tl.total_seconds()%3600)//60)

    st.markdown(f"""
    <div class='card' style='text-align:center; margin-bottom:20px;'>
        <div style='font-size:2.5rem; font-weight:900; color:#00ff88;'>{h}h {m}m</div>
        <div style='color:#888;'>until 10am EST pack reset</div>
        <div style='color:#ffaa00; font-size:0.82rem; margin-top:6px;'>⚡ Yesterday packs — only 2,000 available. Open right at reset.</div>
    </div>

    <div style='display:grid; grid-template-columns:1fr 1fr; gap:12px;'>
        <div class='card'>
            <div style='font-weight:700; color:#fff; margin-bottom:6px;'>Starter Pack — 100 RAX</div>
            <div style='color:#888; font-size:0.82rem;'>3 plays + Common/Uncommon booster</div>
            <div style='color:#4a8b4a; font-size:0.78rem; margin-top:4px;'>3 per day</div>
        </div>
        <div class='card'>
            <div style='font-weight:700; color:#fff; margin-bottom:6px;'>General Pack — 200 RAX</div>
            <div style='color:#888; font-size:0.82rem;'>5 plays + Rare/Epic/Legendary booster</div>
            <div style='color:#4a8b4a; font-size:0.78rem; margin-top:4px;'>5 per day</div>
        </div>
        <div class='card card-yellow'>
            <div style='font-weight:700; color:#ffaa00; margin-bottom:6px;'>Yesterday Pack — 250 RAX ⚡</div>
            <div style='color:#888; font-size:0.82rem;'>5 yesterday plays + booster</div>
            <div style='color:#ffaa00; font-size:0.78rem; margin-top:4px;'>3 per day · Only 2,000 total — sell out fast</div>
        </div>
        <div class='card'>
            <div style='font-weight:700; color:#fff; margin-bottom:6px;'>Player/Team Pack</div>
            <div style='color:#888; font-size:0.82rem;'>Targeted plays for specific player/team</div>
            <div style='color:#4a8b4a; font-size:0.78rem; margin-top:4px;'>Best for leveling up a specific card</div>
        </div>
    </div>

    <div class='card' style='margin-top:16px;'>
        <div style='font-weight:700; color:#fff; margin-bottom:10px;'>⚡ Booster Tiers</div>
        <div style='display:flex; flex-direction:column; gap:6px;'>
    """, unsafe_allow_html=True)

    for rarity, vals in BOOSTER_RAX.items():
        rc = RARITY_COLORS[rarity]
        st.markdown(f"""
        <div style='display:flex; justify-content:space-between; background:#0a1a0a; border-radius:6px; padding:8px 12px;'>
            <span style='color:{rc}; font-weight:700; width:90px;'>{rarity}</span>
            <span style='color:#aaa; font-size:0.82rem;'>⛳ {vals['birdie']} RAX/birdie</span>
            <span style='color:#aaa; font-size:0.82rem;'>🦅 {vals['eagle']} RAX/eagle</span>
            <span style='color:#aaa; font-size:0.82rem;'>🏀 {vals['3pt']} RAX/3pt</span>
            <span style='color:#aaa; font-size:0.82rem;'>⚾ {vals['k']} RAX/K</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center; color:#1a3a1a; font-size:0.72rem; margin-top:20px;'>RaxGuide · by @lee</div>", unsafe_allow_html=True)
