"""
bot.py — Logs into Real app and posts daily boost picks to the Rax Guide group.
Runs via GitHub Actions on a schedule.
"""

import os
import asyncio
import requests
from datetime import datetime, timezone

# --- Config from environment variables ---
REAL_USERNAME = os.environ.get("REAL_USERNAME", "lee")
REAL_PASSWORD = os.environ.get("REAL_PASSWORD", "")
GROUP_URL = "https://www.realsports.io/groups/z2OcNFpFBkq"
LOGIN_URL = "https://www.realsports.io/login"

# --- Player slug lookup (realapp.com/[slug]/2026) ---
# Add more players here as you find their links
PLAYER_SLUGS = {
    # Golf
    "Scottie Scheffler": "nYBtrHOFY3V",
    "Rory McIlroy": "0xT8FgFKoxyb",
    "Taylor Moore": "zxwtOHEFy7V",
    # NBA
    "Luka Dončić": "d6tJHgFWvo3y",
    "Luka Doncic": "d6tJHgFWvo3y",
    # MLB
    "Mason Miller": "extPTdF3QO0",
}

def player_link(name):
    slug = PLAYER_SLUGS.get(name)
    if slug:
        return f"realapp.com/{slug}/2026"
    return ""
PGA_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "x-api-key": "da2-gsrx5bibzbb4njvhl7t37wqyl4",
    "Content-Type": "application/json"
}

BOOSTER_RAX = {
    "Rare":      {"birdie": 8,  "eagle": 20, "3pt": 12, "pts": 2.0},
    "Epic":      {"birdie": 12, "eagle": 30, "3pt": 15, "pts": 3.0},
    "Legendary": {"birdie": 18, "eagle": 45, "3pt": 20, "pts": 4.5},
    "Mystic":    {"birdie": 28, "eagle": 70, "3pt": 30, "pts": 7.0},
}


def get_golf_picks():
    """Get top 5 golf boost picks from PGA Tour stats."""
    try:
        r = requests.post("https://orchestrator.pgatour.com/graphql", headers=PGA_HEADERS,
            json={"query": """{ statDetails(tourCode:R,statId:"02415",year:2026){rows{...on StatDetailsPlayer{playerName rank stats{statValue}}}}}"""},
            timeout=10)
        birdies = {}
        for row in r.json().get("data", {}).get("statDetails", {}).get("rows", []):
            try: birdies[row["playerName"]] = float(row["stats"][0]["statValue"])
            except: pass

        r2 = requests.post("https://orchestrator.pgatour.com/graphql", headers=PGA_HEADERS,
            json={"query": """{ statDetails(tourCode:R,statId:"02416",year:2026){rows{...on StatDetailsPlayer{playerName rank stats{statValue}}}}}"""},
            timeout=10)
        eagles = {}
        for row in r2.json().get("data", {}).get("statDetails", {}).get("rows", []):
            try: eagles[row["playerName"]] = float(row["stats"][0]["statValue"].replace("%", ""))
            except: pass

        # Get entity IDs from Supabase API
        SUPABASE_URL = "https://mfsyhtuqybbxprgwwykd.supabase.co"
        TOKEN = "sb_publishable_Al7QsFGnNTlknoI8KVxjag_JUwrytZy"
        HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

        picks = []
        for name in set(birdies) | set(eagles):
            b = birdies.get(name, 0)
            e = eagles.get(name, 0) / 100
            rax = round((b * 18 + e * 18 * 45) * 2, 0)
            picks.append({"name": name, "birdies": b, "rax": int(rax), "entity_id": None})

        picks.sort(key=lambda x: x["rax"], reverse=True)
        top = picks[:5]

        # Fetch entity IDs for top picks
        for p in top:
            try:
                r3 = requests.post(f"{SUPABASE_URL}/functions/v1/market-data",
                    headers=HEADERS,
                    json={"action": "get_player_suggestions", "payload": {"query": p["name"].split()[0], "season": 2026}},
                    timeout=8)
                suggestions = [s for s in r3.json().get("suggestions", []) if s.get("sport","").lower() == "golf"]
                if suggestions:
                    p["entity_id"] = suggestions[0]["entityId"]
            except: pass

        return top
    except Exception as e:
        print(f"Golf stats error: {e}")
        return []


def get_nba_picks():
    """Get top 3 NBA boost picks with entity IDs."""
    try:
        r = requests.get("https://stats.nba.com/stats/leagueleaders",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nba.com/"},
            params={"LeagueID": "00", "PerMode": "PerGame", "Scope": "S",
                    "Season": "2025-26", "SeasonType": "Regular Season", "StatCategory": "PTS"},
            timeout=10)
        players = []
        hdrs = r.json()["resultSet"]["headers"]
        for row in r.json()["resultSet"]["rowSet"][:3]:
            p = dict(zip(hdrs, row))
            rax = round(p.get("PTS", 0) * 4.5, 0)
            players.append({
                "name": p["PLAYER"],
                "team": p["TEAM"],
                "pts": p.get("PTS", 0),
                "rax": int(rax),
                "entity_id": p.get("PLAYER_ID")
            })
        return players
    except Exception as e:
        print(f"NBA stats error: {e}")
        return []


def build_message():
    """Build a short daily boost message with player links."""
    today = datetime.now(timezone.utc).strftime("%b %d")
    golf = get_golf_picks()
    nba = get_nba_picks()

    lines = [f"⛳ Boost Picks — {today}", ""]

    lines.append("GOLF (Legendary · 2x Major)")
    for p in golf:
        link = player_link(p["name"])
        link_str = f" {link}" if link else ""
        lines.append(f"🐦 {p['name']} ~{p['rax']} RAX{link_str}")

    lines.append("")
    lines.append("🏀 NBA (Legendary pts)")
    for p in nba:
        link = player_link(p["name"])
        link_str = f" {link}" if link else ""
        lines.append(f"{p['name']} ({p['team']}) ~{p['rax']} RAX{link_str}")

    return "\n".join(lines)


async def post_to_group(message):
    """Use Playwright to log in and post message to the group."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        print("Navigating to web app login...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)
        await page.screenshot(path="debug_1_login.png")
        print(f"Login page URL: {page.url}")

        # Log in
        await page.wait_for_timeout(3000)
        await page.screenshot(path="debug_1b_login_loaded.png")

        # Print all buttons and inputs on login page
        buttons = await page.query_selector_all('button')
        print(f"Buttons found: {len(buttons)}")
        for b in buttons:
            txt = await b.inner_text()
            print(f"  Button: '{txt}'")

        inputs = await page.query_selector_all('input')
        print(f"Inputs found: {len(inputs)}")
        for inp in inputs:
            t = await inp.get_attribute('type')
            p2 = await inp.get_attribute('placeholder')
            print(f"  Input type='{t}' placeholder='{p2}'")

        # Fill login
        username_input = await page.query_selector('input[type="text"], input[type="email"]')
        password_input = await page.query_selector('input[type="password"]')
        if username_input:
            await username_input.fill(REAL_USERNAME)
        if password_input:
            await password_input.fill(REAL_PASSWORD)
        await page.screenshot(path="debug_2_filled.png")

        # Click first button
        btn = await page.query_selector('button')
        if btn:
            await btn.click()
        else:
            await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(5000)
        await page.screenshot(path="debug_3_after_login.png")
        print(f"After login URL: {page.url}")

        # Navigate to group
        print("Navigating to group...")
        await page.goto(GROUP_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(8000)
        await page.screenshot(path="debug_4_group.png")

        print(f"Current URL: {page.url}")

        # Print all interactive elements to debug
        inputs = await page.query_selector_all('input, textarea, div[contenteditable], [role="textbox"]')
        print(f"Found {len(inputs)} input elements")
        for i, el in enumerate(inputs[:10]):
            tag = await el.evaluate("el => el.tagName")
            placeholder = await el.evaluate("el => el.placeholder || el.getAttribute('aria-label') || el.getAttribute('data-placeholder') || ''")
            print(f"  [{i}] {tag} placeholder='{placeholder}'")

        # Find the message input
        selectors = [
            '[role="textbox"]',
            'div[contenteditable="true"]',
            'textarea',
            'input[type="text"]',
        ]

        input_el = None
        for sel in selectors:
            el = await page.query_selector(sel)
            if el:
                input_el = el
                print(f"Found input: {sel}")
                break

        if not input_el:
            await page.screenshot(path="debug_5_no_input.png")
            print("Could not find message input. Check debug screenshots.")
            await browser.close()
            return False

        # Type and send message
        await input_el.click()
        await input_el.fill(message)
        await page.screenshot(path="debug_6_typed.png")

        # Find send button
        send_btn = await page.query_selector('button[type="submit"], button:has-text("Send"), button:has-text("Post")')
        if send_btn:
            await send_btn.click()
            await page.wait_for_timeout(2000)
            await page.screenshot(path="debug_7_sent.png")
            print("Message sent!")
        else:
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(2000)
            print("Pressed Enter to send.")

        await browser.close()
        return True


async def main():
    print("=== RaxGuide Daily Bot ===")
    message = build_message()
    print("Message to post:")
    print(message)
    print()

    if not REAL_PASSWORD:
        print("No REAL_PASSWORD set. Set it as a GitHub/environment secret.")
        return

    success = await post_to_group(message)
    if success:
        print("Done!")
    else:
        print("Failed to post. Check debug screenshots.")


if __name__ == "__main__":
    asyncio.run(main())
