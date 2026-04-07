import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import requests
from datetime import datetime, timedelta
import os
import json

# --- Firebase Setup ---
try:
    firebase_creds = os.environ.get("FIREBASE_CREDENTIALS")
    if firebase_creds:
        cred = credentials.Certificate(json.loads(firebase_creds))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase initialized successfully!")
except FileNotFoundError:
    print("Error: serviceAccountKey.json not found.")
    exit()

# --- Real App RAX earnings by rarity (official docs) ---
RAX_EARNINGS = {
    "General": 200, "Common": 1000, "Uncommon": 1500,
    "Rare": 2000, "Epic": 5000, "Legendary": 12500,
    "Mystic": 37500, "Iconic": 999999
}
RARITY_ORDER = ["General", "Common", "Uncommon", "Rare", "Epic", "Legendary", "Mystic", "Iconic"]
# --- BallDontLie API Config ---
BDL_API_KEY = "b6d8fdb5-19e6-42ec-8cf2-90ff63cce84b"
BDL_BASE = "https://api.balldontlie.io/v1"
BDL_HEADERS = {"Authorization": BDL_API_KEY}


def fetch_realapp_tools(player_name, season="2026"):
    """Tries to pull market value, R/R and deal score from realapp.tools."""
    import re
    try:
        resp = requests.get("https://realapp.tools", timeout=6)
        text = resp.text
        # Find the player's section in the page
        idx = text.lower().find(player_name.lower().split()[0])
        if idx == -1:
            return None, None, None
        snippet = text[idx:idx+500]
        price_match = re.search(r'PRICE\s*([\d,]+)', snippet)
        rr_match = re.search(r'([\d.]+)\s*R/R', snippet)
        deal_match = re.search(r'Deal\s*(\d+)/95', snippet)
        market_value = int(price_match.group(1).replace(',', '')) if price_match else None
        rr_ratio = float(rr_match.group(1)) if rr_match else None
        deal_score = int(deal_match.group(1)) if deal_match else None
        return market_value, rr_ratio, deal_score
    except Exception:
        return None, None, None


# ─────────────────────────────────────────────
# LIVE STATS FUNCTIONS
# ─────────────────────────────────────────────

def search_player_id(player_name):
    """Search BallDontLie for a player and return their ID."""
    try:
        resp = requests.get(
            f"{BDL_BASE}/players",
            headers=BDL_HEADERS,
            params={"search": player_name, "per_page": 5, "api_key": BDL_API_KEY}
        )
        if resp.status_code == 403:
            print("API key rejected (403). Check your BallDontLie key.")
            return None
        resp.raise_for_status()
        results = resp.json().get("data", [])
        if not results:
            print(f"No player found for '{player_name}'.")
            return None
        player = results[0]
        print(f"Found: {player['first_name']} {player['last_name']} (ID: {player['id']})")
        return player["id"]
    except Exception as e:
        print(f"API error searching player: {e}")
        return None


def fetch_avg_points_last_5(player_name):
    """Fetches last 5 game stats. Returns (avg_points, games_this_week)."""
    player_id = search_player_id(player_name)
    if not player_id:
        return None, None
    try:
        season = datetime.now().year if datetime.now().month > 9 else datetime.now().year - 1
        resp = requests.get(
            f"{BDL_BASE}/stats",
            headers=BDL_HEADERS,
            params={"player_ids[]": player_id, "per_page": 5, "seasons[]": season}
        )
        resp.raise_for_status()
        stats = resp.json().get("data", [])
        if not stats:
            print(f"No recent stats found for '{player_name}'.")
            return None, None
        points = [s["pts"] for s in stats if s.get("pts") is not None]
        avg = round(sum(points) / len(points), 1) if points else 0.0
        week_ago = datetime.now() - timedelta(days=7)
        games_this_week = sum(
            1 for s in stats
            if s.get("game", {}).get("date") and
            datetime.strptime(s["game"]["date"][:10], "%Y-%m-%d") >= week_ago
        )
        print(f"  Avg pts (last {len(points)} games): {avg} | Games this week: {games_this_week}")
        return avg, games_this_week
    except Exception as e:
        print(f"API error fetching stats: {e}")
        return None, None


def fetch_schedule_strength(player_name):
    """Counts upcoming games in next 7 days. Returns (label, count)."""
    player_id = search_player_id(player_name)
    if not player_id:
        return "Unknown", 0
    try:
        resp = requests.get(f"{BDL_BASE}/players/{player_id}", headers=BDL_HEADERS)
        resp.raise_for_status()
        team_id = resp.json().get("data", {}).get("team", {}).get("id")
        if not team_id:
            return "Unknown", 0
        today = datetime.now().strftime("%Y-%m-%d")
        next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        resp = requests.get(
            f"{BDL_BASE}/games",
            headers=BDL_HEADERS,
            params={"team_ids[]": team_id, "start_date": today, "end_date": next_week, "per_page": 10}
        )
        resp.raise_for_status()
        upcoming = len(resp.json().get("data", []))
        label = "High Priority Buy" if upcoming >= 4 else ("Medium" if upcoming >= 3 else "Avoid")
        print(f"  Upcoming games (next 7 days): {upcoming} → {label}")
        return label, upcoming
    except Exception as e:
        print(f"API error fetching schedule: {e}")
        return "Unknown", 0


def auto_update_player_stats(player_name):
    """Fetches live stats and updates Firebase for a player."""
    print(f"\nFetching live stats for '{player_name}'...")
    avg_pts, games_this_week = fetch_avg_points_last_5(player_name)
    schedule_label, upcoming_games = fetch_schedule_strength(player_name)
    if avg_pts is None:
        print("Could not fetch stats — player saved without live data.")
        return
    player_ref = db.collection('market_watch').document(player_name)
    if not player_ref.get().exists:
        print(f"Player '{player_name}' not in database. Add them first.")
        return
    player_ref.update({
        "avg_points_last_5": avg_pts,
        "games_this_week": games_this_week,
        "schedule_strength": schedule_label,
        "upcoming_games": upcoming_games,
        "last_updated": datetime.now().isoformat()
    })
    print(f"'{player_name}' stats updated in Firebase.")


def auto_update_all_players():
    """Refreshes live stats for every player in the database."""
    players = db.collection('market_watch').stream()
    count = 0
    for player in players:
        auto_update_player_stats(player.id)
        count += 1
    print(f"\nRefreshed {count} player(s).")


# ─────────────────────────────────────────────
# CRUD FUNCTIONS
# ─────────────────────────────────────────────

def add_player_to_market_watch(player_name, rarity, rating_progress, total_rax_invested, buy_price=0, season="2026"):
    """Adds a player and tries to fetch live stats and market data."""
    print(f"\nFetching live stats for '{player_name}'...")
    avg_pts, games_this_week = fetch_avg_points_last_5(player_name)
    schedule_label, upcoming_games = fetch_schedule_strength(player_name)
    market_value, rr_ratio, deal_score = fetch_realapp_tools(player_name, season)

    daily_rax = RAX_EARNINGS.get(rarity, 1000)
    days_to_breakeven = round(buy_price / daily_rax, 1) if daily_rax and buy_price else None

    player_ref = db.collection('market_watch').document(player_name)
    player_data = {
        'rarity': rarity,
        'season': season,
        'rating_progress': rating_progress,
        'total_rax_invested': total_rax_invested,
        'avg_points_last_5': avg_pts or 0.0,
        'games_this_week': games_this_week or 0,
        'schedule_strength': schedule_label or "Unknown",
        'upcoming_games': upcoming_games or 0,
        'is_heating_up': (avg_pts or 0) > 20,
        'buy_price': buy_price,
        'market_value': market_value,
        'rr_ratio': rr_ratio,
        'deal_score': deal_score,
        'daily_rax_earn': daily_rax,
        'days_to_breakeven': days_to_breakeven,
        'sell_price': None,
        'profit_loss': None,
        'last_updated': datetime.now().isoformat()
    }
    player_ref.set(player_data)
    print(f"Player '{player_name}' saved. Daily RAX: {daily_rax} | Breakeven: {days_to_breakeven} days")


def update_player(player_name):
    """Updates specific fields for an existing player."""
    player_ref = db.collection('market_watch').document(player_name)
    player_doc = player_ref.get()
    if not player_doc.exists:
        print(f"Player '{player_name}' not found.")
        return
    print(f"\nUpdating '{player_name}'. Press Enter to keep current value.")
    data = player_doc.to_dict()
    fields = {'rarity': str, 'rating_progress': int, 'total_rax_invested': int, 'buy_price': float, 'sell_price': float}
    updates = {}
    for field, cast in fields.items():
        val = input(f"{field} (current: {data.get(field)}): ").strip()
        if val:
            try:
                updates[field] = cast(val)
            except ValueError:
                print(f"Invalid value for {field}, skipping.")
    buy = updates.get('buy_price', data.get('buy_price') or 0)
    sell = updates.get('sell_price', data.get('sell_price'))
    if sell is not None:
        updates['profit_loss'] = sell - buy
    if updates:
        player_ref.update(updates)
        print(f"'{player_name}' updated.")
        if 'profit_loss' in updates:
            print(f"Profit/Loss: {updates['profit_loss']:+.0f} RAX")


def delete_player(player_name):
    player_ref = db.collection('market_watch').document(player_name)
    if not player_ref.get().exists:
        print(f"Player '{player_name}' not found.")
        return
    player_ref.delete()
    print(f"Player '{player_name}' deleted.")


def list_players():
    players = db.collection('market_watch').stream()
    found = False
    print("\n--- Market Watch ---")
    print(f"{'Name':<22} {'Rarity':<8} {'Avg Pts':<9} {'Sched':<18} {'Buy':<8} {'P/L':<10} {'Updated'}")
    print("-" * 90)
    for player in players:
        found = True
        d = player.to_dict()
        pl = d.get('profit_loss')
        pl_str = f"{pl:+.0f}" if pl is not None else "N/A"
        updated = (d.get('last_updated') or "")[:10]
        print(f"{player.id:<22} {d.get('rarity',''):<8} {str(d.get('avg_points_last_5','')):<9} {d.get('schedule_strength',''):<18} {d.get('buy_price',0):<8} {pl_str:<10} {updated}")
    if not found:
        print("  No players found.")


# ─────────────────────────────────────────────
# STRATEGY / FLIP LOGIC
# ─────────────────────────────────────────────

def should_i_flip(player_name):
    """Applies profit logic using real RAX earnings and market data."""
    player_ref = db.collection('market_watch').document(player_name)
    player_doc = player_ref.get()
    if not player_doc.exists:
        return f"Player '{player_name}' not found."
    d = player_doc.to_dict()
    rarity = d.get('rarity', 'Common')
    buy_price = d.get('buy_price', 0)
    market_value = d.get('market_value', 0) or 0
    deal_score = d.get('deal_score', 0) or 0
    rr_ratio = d.get('rr_ratio', 0) or 0
    upcoming = d.get('upcoming_games', 0)
    daily_rax = RAX_EARNINGS.get(rarity, 1000)
    days_to_breakeven = round(buy_price / daily_rax, 1) if daily_rax and buy_price else None

    results = []

    # Deal score from realapp.tools
    if deal_score >= 60:
        results.append(f"STRONG BUY — Deal score {deal_score}/95 (realapp.tools)")
    elif deal_score >= 40:
        results.append(f"FAIR DEAL — Score {deal_score}/95")
    elif deal_score > 0:
        results.append(f"OVERPRICED — Score {deal_score}/95, consider waiting")

    # R/R ratio check
    if rr_ratio >= 15:
        results.append(f"HIGH R/R RATIO — {rr_ratio:.2f} RAX earned per RAX spent")

    # Breakeven analysis
    if days_to_breakeven:
        results.append(f"Breakeven in {days_to_breakeven} days at {daily_rax:,} RAX/day ({rarity})")

    # Market value flip
    if market_value and buy_price:
        profit = market_value - buy_price
        roi = (profit / buy_price) * 100
        if profit > 0:
            results.append(f"FLIP PROFIT — Sell at {market_value:,} RAX = {profit:+,.0f} RAX ({roi:.1f}% ROI)")

    # Schedule
    if upcoming >= 4:
        results.append(f"STACKED SCHEDULE — {upcoming} games this week, max RAX grind")
    elif upcoming <= 2:
        results.append(f"SLOW WEEK — only {upcoming} games, low RAX gain")

    # Rarity upgrade suggestion
    rarity_idx = RARITY_ORDER.index(rarity) if rarity in RARITY_ORDER else 0
    if rarity_idx < len(RARITY_ORDER) - 1:
        next_rarity = RARITY_ORDER[rarity_idx + 1]
        next_earn = RAX_EARNINGS.get(next_rarity, 0)
        results.append(f"UPGRADE TIP — Upgrading to {next_rarity} earns {next_earn:,} RAX/day vs {daily_rax:,} now")

    return ("STRATEGY:\n  " + "\n  ".join(results)) if results else "STRATEGY: NO IMMEDIATE ACTION"


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────

def main_loop():
    print("\n--- Sports Card Profit Tool ---")
    while True:
        action = input("\nOptions: add | check | update | delete | list | refresh | refresh-all | quit\n> ").strip().lower()

        if action == 'quit':
            print("Goodbye!")
            break
        elif action == 'add':
            player_name = input("Player Name: ")
            print("Rarities: General | Common | Uncommon | Rare | Epic | Legendary | Mystic | Iconic")
            rarity = input("Rarity: ").strip().capitalize()
            if rarity not in RARITY_ORDER:
                print(f"Invalid rarity. Choose from: {', '.join(RARITY_ORDER)}")
                continue
            season = input("Season (e.g. 2026, default 2026): ").strip() or "2026"
            while True:
                try:
                    rating_progress = int(input("Rating Progress (0-100): "))
                    if not 0 <= rating_progress <= 100:
                        raise ValueError
                    break
                except ValueError:
                    print("Enter an integer between 0 and 100.")
            while True:
                try:
                    total_rax_invested = int(input("Total RAX Invested: "))
                    break
                except ValueError:
                    print("Enter an integer.")
            while True:
                try:
                    buy_price = float(input("Buy Price (RAX): "))
                    break
                except ValueError:
                    print("Enter a number.")
            add_player_to_market_watch(player_name, rarity, rating_progress, total_rax_invested, buy_price, season)
        elif action == 'check':
            player_name = input("Player name: ")
            print(should_i_flip(player_name))
        elif action == 'update':
            player_name = input("Player name: ")
            update_player(player_name)
        elif action == 'delete':
            player_name = input("Player name: ")
            if input(f"Delete '{player_name}'? (yes/no): ").strip().lower() == 'yes':
                delete_player(player_name)
        elif action == 'list':
            list_players()
        elif action == 'refresh':
            player_name = input("Player name to refresh stats: ")
            auto_update_player_stats(player_name)
        elif action == 'refresh-all':
            auto_update_all_players()
        else:
            print("Invalid option.")


if __name__ == "__main__":
    main_loop()
