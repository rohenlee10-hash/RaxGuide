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

# --- BallDontLie API Config ---
# Get your free key at https://www.balldontlie.io
BDL_API_KEY = "b6d8fdb5-19e6-42ec-8cf2-90ff63cce84b"
BDL_BASE = "https://api.balldontlie.io/v1"
BDL_HEADERS = {"Authorization": BDL_API_KEY}


# ─────────────────────────────────────────────
# LIVE STATS FUNCTIONS
# ─────────────────────────────────────────────

def search_player_id(player_name):
    """Search BallDontLie for a player and return their ID."""
    resp = requests.get(f"{BDL_BASE}/players", headers=BDL_HEADERS, params={"search": player_name, "per_page": 5})
    resp.raise_for_status()
    results = resp.json().get("data", [])
    if not results:
        print(f"No player found for '{player_name}'.")
        return None
    # Pick the first match
    player = results[0]
    print(f"Found: {player['first_name']} {player['last_name']} (ID: {player['id']})")
    return player["id"]


def fetch_avg_points_last_5(player_name):
    """
    Fetches the last 5 game stats for a player from BallDontLie.
    Returns (avg_points, games_this_week).
    """
    player_id = search_player_id(player_name)
    if not player_id:
        return None, None

    # Fetch last 5 game stats
    resp = requests.get(
        f"{BDL_BASE}/stats",
        headers=BDL_HEADERS,
        params={
            "player_ids[]": player_id,
            "per_page": 5,
            "seasons[]": datetime.now().year if datetime.now().month > 9 else datetime.now().year - 1
        }
    )
    resp.raise_for_status()
    stats = resp.json().get("data", [])

    if not stats:
        print(f"No recent stats found for '{player_name}'.")
        return None, None

    points = [s["pts"] for s in stats if s.get("pts") is not None]
    avg = round(sum(points) / len(points), 1) if points else 0.0

    # Count games in the last 7 days
    week_ago = datetime.now() - timedelta(days=7)
    games_this_week = sum(
        1 for s in stats
        if s.get("game", {}).get("date") and
        datetime.strptime(s["game"]["date"][:10], "%Y-%m-%d") >= week_ago
    )

    print(f"  Avg pts (last {len(points)} games): {avg} | Games this week: {games_this_week}")
    return avg, games_this_week


def fetch_schedule_strength(player_name):
    """
    Counts upcoming games in the next 7 days for a player's team.
    Returns a label: 'High Priority', 'Medium', or 'Avoid'.
    """
    player_id = search_player_id(player_name)
    if not player_id:
        return "Unknown", 0

    # Get player's team
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
        params={
            "team_ids[]": team_id,
            "start_date": today,
            "end_date": next_week,
            "per_page": 10
        }
    )
    resp.raise_for_status()
    upcoming = len(resp.json().get("data", []))

    if upcoming >= 4:
        label = "High Priority Buy"
    elif upcoming >= 3:
        label = "Medium"
    else:
        label = "Avoid"

    print(f"  Upcoming games (next 7 days): {upcoming} → {label}")
    return label, upcoming


def auto_update_player_stats(player_name):
    """Fetches live stats and updates Firebase for a player."""
    print(f"\nFetching live stats for '{player_name}'...")
    avg_pts, games_this_week = fetch_avg_points_last_5(player_name)
    schedule_label, upcoming_games = fetch_schedule_strength(player_name)

    if avg_pts is None:
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

def add_player_to_market_watch(player_name, rarity, rating_progress, total_rax_invested, buy_price=0):
    """Adds a player and immediately fetches their live stats."""
    avg_pts, games_this_week = fetch_avg_points_last_5(player_name)
    schedule_label, upcoming_games = fetch_schedule_strength(player_name)

    player_ref = db.collection('market_watch').document(player_name)
    player_data = {
        'rarity': rarity,
        'rating_progress': rating_progress,
        'total_rax_invested': total_rax_invested,
        'avg_points_last_5': avg_pts or 0.0,
        'games_this_week': games_this_week or 0,
        'schedule_strength': schedule_label,
        'upcoming_games': upcoming_games,
        'is_heating_up': (avg_pts or 0) > 20,  # auto-set based on points
        'buy_price': buy_price,
        'sell_price': None,
        'profit_loss': None,
        'last_updated': datetime.now().isoformat()
    }
    player_ref.set(player_data)
    print(f"Player '{player_name}' added with live stats.")


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
    """Applies profit logic using live data from Firebase."""
    player_ref = db.collection('market_watch').document(player_name)
    player_doc = player_ref.get()
    if not player_doc.exists:
        return f"Player '{player_name}' not found."

    d = player_doc.to_dict()
    rarity = d.get('rarity')
    buy_price = d.get('buy_price', 0)
    avg_pts = d.get('avg_points_last_5', 0)
    schedule = d.get('schedule_strength', 'Unknown')
    upcoming = d.get('upcoming_games', 0)
    games_this_week = d.get('games_this_week', 0)

    try:
        current_rare_market_value = float(input("Current Rare market value (RAX): "))
        cost_to_hit_rare = float(input("Cost to hit Rare (RAX): "))
    except ValueError:
        return "Invalid market value input."

    results = []

    # Rare Flip check
    if rarity == 'Common' and current_rare_market_value > (cost_to_hit_rare + 300):
        profit_estimate = current_rare_market_value - buy_price
        roi = ((current_rare_market_value - cost_to_hit_rare) / cost_to_hit_rare) * 100 if cost_to_hit_rare else 0
        results.append(f"FLIP TO RARE | Est. profit: {profit_estimate:+.0f} RAX | ROI: {roi:.1f}%")

    # Schedule strength multiplier
    if upcoming >= 4:
        results.append(f"HIGH PRIORITY BUY — {upcoming} games this week (schedule is stacked)")
    elif upcoming == 2:
        results.append("AVOID — only 2 games this week, slow RAX gain")

    # Heat check
    if games_this_week >= 4 and avg_pts > 20:
        results.append(f"HOLD FOR RAX — heating up ({avg_pts} avg pts, {games_this_week} games played)")

    # Price gap alert
    if rarity == 'Common':
        gap = current_rare_market_value - buy_price
        if gap > 1000:
            results.append(f"PRICE GAP ALERT — {gap:.0f} RAX gap between Common and Rare. Strong grind candidate.")

    return ("STRATEGY: " + " | ".join(results)) if results else "STRATEGY: NO IMMEDIATE ACTION"


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
            rarity = input("Rarity (Common, Rare, Epic): ")
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
            add_player_to_market_watch(player_name, rarity, rating_progress, total_rax_invested, buy_price)

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
