"""
scraper.py — Auto-pulls NBA, MLB, GOLF players from realapp.tools into Firebase.
Run with: python3 scraper.py
"""

import firebase_admin
from firebase_admin import credentials, firestore
import requests
import re
import os
import json
from datetime import datetime

# --- Firebase Setup ---
try:
    firebase_creds = os.environ.get("FIREBASE_CREDENTIALS")
    if firebase_creds:
        cred = credentials.Certificate(json.loads(firebase_creds))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase connected.")
except FileNotFoundError:
    print("Error: serviceAccountKey.json not found.")
    exit()

# --- Config ---
ALLOWED_SPORTS = {"NBA", "MLB", "GOLF"}
RAX_EARNINGS = {
    "General": 200, "Common": 1000, "Uncommon": 1500,
    "Rare": 2000, "Epic": 5000, "Legendary": 12500,
    "Mystic": 37500, "Iconic": 999999
}

def scrape_realapp_tools():
    """Scrapes the realapp.tools discovery page and returns a list of player dicts."""
    print("Fetching realapp.tools...")
    try:
        resp = requests.get("https://realapp.tools", timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch realapp.tools: {e}")
        return []

    text = resp.text
    players = []

    # Each player block looks like:
    # [Player Name](https://realapp.tools/players/ID/SEASON/slug)
    # RARITY SPORT ... PRICE X,XXX Y.YY R/R DEAL SCORE ZZ/95
    pattern = re.compile(
        r'\[([^\]]+)\]\(https://realapp\.tools/players/(\d+)/(\d+)/([^)]+)\)'
        r'(?:[^\[]*?)(GENERAL|COMMON|UNCOMMON|RARE|EPIC|LEGENDARY|MYSTIC|ICONIC)'
        r'(NBA|MLB|GOLF|NFL|NHL|NCAAM|NCAAF|WNBA|MMA|UFC)'
        r'.*?PRICE\s*([\d,]+)'
        r'\s*([\d.]+)\s*R/R'
        r'.*?DEAL\s*SCORE\s*(\d+)/95',
        re.DOTALL | re.IGNORECASE
    )

    seen = set()
    for m in pattern.finditer(text):
        name    = m.group(1).strip()
        pid     = m.group(2)
        season  = m.group(3)
        rarity  = m.group(5).capitalize()
        sport   = m.group(6).upper()
        price   = int(m.group(7).replace(',', ''))
        rr      = float(m.group(8))
        deal    = int(m.group(9))

        if sport not in ALLOWED_SPORTS:
            continue

        # Deduplicate by name+rarity+season (keep highest deal score)
        key = f"{name}_{rarity}_{season}"
        if key in seen:
            continue
        seen.add(key)

        daily_rax = RAX_EARNINGS.get(rarity, 1000)
        breakeven = round(price / daily_rax, 1) if daily_rax and price else None

        players.append({
            "name": name,
            "player_id": pid,
            "season": season,
            "sport": sport,
            "rarity": rarity,
            "market_value": price,
            "rr_ratio": rr,
            "deal_score": deal,
            "buy_price": price,
            "daily_rax_earn": daily_rax,
            "days_to_breakeven": breakeven,
            "sell_price": None,
            "profit_loss": None,
            "rating_progress": 0,
            "total_rax_invested": 0,
            "avg_points_last_5": 0.0,
            "games_this_week": 0,
            "schedule_strength": "Unknown",
            "upcoming_games": 0,
            "is_heating_up": False,
            "last_updated": datetime.now().isoformat()
        })

    return players


def save_to_firebase(players):
    """Saves scraped players to Firebase, updating existing ones."""
    if not players:
        print("No players to save.")
        return

    batch_size = 0
    for p in players:
        doc_id = f"{p['name']} ({p['rarity']} {p['season']})"
        ref = db.collection('market_watch').document(doc_id)
        existing = ref.get()

        if existing.exists:
            # Only update market data, don't overwrite buy_price if user set it
            ref.update({
                "market_value": p["market_value"],
                "rr_ratio": p["rr_ratio"],
                "deal_score": p["deal_score"],
                "daily_rax_earn": p["daily_rax_earn"],
                "last_updated": p["last_updated"]
            })
        else:
            ref.set(p)

        batch_size += 1
        print(f"  {'Updated' if existing.exists else 'Added':8} {doc_id:<40} | {p['sport']:<5} | {p['rarity']:<10} | {p['market_value']:>6,} RAX | Deal {p['deal_score']}/95")

    print(f"\nDone. {batch_size} players saved to Firebase.")


def main():
    print("\n=== RaxCartel Auto-Scraper ===")
    print(f"Sports: {', '.join(ALLOWED_SPORTS)}\n")
    players = scrape_realapp_tools()

    if not players:
        print("No players found. The site may have changed structure.")
        return

    nba   = [p for p in players if p['sport'] == 'NBA']
    mlb   = [p for p in players if p['sport'] == 'MLB']
    golf  = [p for p in players if p['sport'] == 'GOLF']

    print(f"Found: {len(nba)} NBA | {len(mlb)} MLB | {len(golf)} GOLF\n")
    save_to_firebase(players)


if __name__ == "__main__":
    main()
