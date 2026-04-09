"""
daily_email.py — Sends daily boost picks to your email every morning.
"""

import requests
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

GMAIL = os.environ.get("GMAIL_ADDRESS")
PASSWORD = os.environ.get("GMAIL_PASSWORD")

PGA_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "x-api-key": "da2-gsrx5bibzbb4njvhl7t37wqyl4",
    "Content-Type": "application/json"
}


def get_golf_picks():
    try:
        r = requests.post("https://orchestrator.pgatour.com/graphql", headers=PGA_HEADERS,
            json={"query": """{ statDetails(tourCode:R,statId:"02415",year:2026){rows{...on StatDetailsPlayer{playerName rank stats{statValue}}}}}"""},
            timeout=10)
        birdies = {}
        for row in r.json().get("data",{}).get("statDetails",{}).get("rows",[]):
            try: birdies[row["playerName"]] = float(row["stats"][0]["statValue"])
            except: pass

        r2 = requests.post("https://orchestrator.pgatour.com/graphql", headers=PGA_HEADERS,
            json={"query": """{ statDetails(tourCode:R,statId:"02416",year:2026){rows{...on StatDetailsPlayer{playerName rank stats{statValue}}}}}"""},
            timeout=10)
        eagles = {}
        for row in r2.json().get("data",{}).get("statDetails",{}).get("rows",[]):
            try: eagles[row["playerName"]] = float(row["stats"][0]["statValue"].replace("%",""))
            except: pass

        picks = []
        for name in set(birdies) | set(eagles):
            b = birdies.get(name, 0)
            e = eagles.get(name, 0) / 100
            # Legendary booster: 18 RAX/birdie, 45 RAX/eagle, 2x major
            rax = round((b * 18 + e * 18 * 45) * 2, 0)
            picks.append({"name": name, "birdies": b, "eagle_pct": eagles.get(name, 0), "rax": int(rax)})

        picks.sort(key=lambda x: x["rax"], reverse=True)
        return picks[:5]
    except Exception as e:
        print(f"Golf error: {e}")
        return []


def get_nba_picks():
    try:
        # Get today's games from ESPN
        r = requests.get("http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard", timeout=8)
        events = r.json().get("events", [])
        playing_teams = set()
        for e in events:
            for comp in e["competitions"][0]["competitors"]:
                playing_teams.add(comp["team"]["abbreviation"])

        # Get season leaders
        r2 = requests.get("https://stats.nba.com/stats/leagueleaders",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nba.com/"},
            params={"LeagueID":"00","PerMode":"PerGame","Scope":"S","Season":"2025-26","SeasonType":"Regular Season","StatCategory":"PTS"},
            timeout=10)
        hdrs = r2.json()["resultSet"]["headers"]
        players = []
        for row in r2.json()["resultSet"]["rowSet"][:50]:
            p = dict(zip(hdrs, row))
            if p.get("TEAM") in playing_teams:
                rax = round(p.get("PTS", 0) * 4.5, 0)
                players.append({"name": p["PLAYER"], "team": p["TEAM"], "pts": p.get("PTS",0), "rax": int(rax)})

        players.sort(key=lambda x: x["rax"], reverse=True)
        return players[:3]
    except Exception as e:
        print(f"NBA error: {e}")
        return []


def get_mlb_picks():
    try:
        r = requests.get("http://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard", timeout=8)
        events = r.json().get("events", [])
        pitchers = []
        for event in events[:5]:
            comp = event["competitions"][0]
            for team in comp["competitors"]:
                for l in team.get("leaders", []):
                    if "strikeout" in l.get("name","").lower():
                        leaders = l.get("leaders", [])
                        if leaders:
                            name = leaders[0].get("athlete",{}).get("fullName","")
                            val = leaders[0].get("displayValue","")
                            if name:
                                pitchers.append({"name": name, "stat": val})
        return pitchers[:3]
    except Exception as e:
        print(f"MLB error: {e}")
        return []


def build_plain_text(golf, nba, mlb, today):
    lines = [f"⛳ RaxGuide Boost Picks — {today}", ""]
    lines.append("GOLF (Legendary booster · 2x Major)")
    for p in golf:
        lines.append(f"  🐦 {p['name']} — {p['birdies']:.2f} birdies/rd · ~{p['rax']} RAX/rd")
    lines.append("")
    lines.append("🏀 NBA (Legendary pts booster — playing today)")
    for p in nba:
        lines.append(f"  {p['name']} ({p['team']}) — {p['pts']} PPG · ~{p['rax']} RAX/game")
    if mlb:
        lines.append("")
        lines.append("⚾ MLB (Legendary K booster)")
        for p in mlb:
            lines.append(f"  {p['name']} — {p['stat']}")
    lines += ["", "📊 Full stats: raxguide.onrender.com"]
    return "\n".join(lines)


def build_html(golf, nba, mlb, today):
    def row(emoji, name, detail, rax):
        return f"""
        <tr>
            <td style='padding:10px; border-bottom:1px solid #1a3a1a;'>{emoji} <b style='color:#fff;'>{name}</b></td>
            <td style='padding:10px; border-bottom:1px solid #1a3a1a; color:#888;'>{detail}</td>
            <td style='padding:10px; border-bottom:1px solid #1a3a1a; color:#00ff88; font-weight:bold; text-align:right;'>~{rax} RAX</td>
        </tr>"""

    golf_rows = "".join([row("🐦", p["name"], f"{p['birdies']:.2f} birdies/rd", p["rax"]) for p in golf])
    nba_rows = "".join([row("🏀", p["name"], f"{p['pts']} PPG ({p['team']})", p["rax"]) for p in nba])
    mlb_rows = "".join([row("⚾", p["name"], p["stat"], "varies") for p in mlb]) if mlb else ""

    return f"""
    <html><body style='background:#060d06; color:#e0e0e0; font-family:Inter,sans-serif; padding:20px;'>
        <div style='max-width:600px; margin:0 auto;'>
            <h1 style='color:#00ff88; font-size:1.8rem;'>⛳ RaxGuide Boost Picks</h1>
            <p style='color:#888;'>{today}</p>

            <h2 style='color:#fff; font-size:1rem; margin-top:24px;'>GOLF — Legendary Booster · 2x Major</h2>
            <table width='100%' style='border-collapse:collapse; background:#0d1a0d; border-radius:8px;'>
                {golf_rows}
            </table>

            <h2 style='color:#fff; font-size:1rem; margin-top:24px;'>🏀 NBA — Legendary Pts Booster (Playing Today)</h2>
            <table width='100%' style='border-collapse:collapse; background:#0d1a0d; border-radius:8px;'>
                {nba_rows}
            </table>

            {"<h2 style='color:#fff; font-size:1rem; margin-top:24px;'>⚾ MLB — Legendary K Booster</h2><table width='100%' style='border-collapse:collapse; background:#0d1a0d; border-radius:8px;'>" + mlb_rows + "</table>" if mlb else ""}

            <p style='margin-top:24px; color:#555; font-size:0.8rem;'>
                Full stats & rankings: <a href='https://raxguide.onrender.com' style='color:#00ff88;'>raxguide.onrender.com</a><br>
                by @lee
            </p>
        </div>
    </html></body>"""


def send_email(subject, plain, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL
    msg["To"] = GMAIL
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL, PASSWORD)
        server.send_message(msg)
    print(f"Email sent to {GMAIL}")


def main():
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    print(f"Building picks for {today}...")

    golf = get_golf_picks()
    nba = get_nba_picks()
    mlb = get_mlb_picks()

    plain = build_plain_text(golf, nba, mlb, today)
    html = build_html(golf, nba, mlb, today)

    print(plain)

    if not GMAIL or not PASSWORD:
        print("No email credentials. Set GMAIL_ADDRESS and GMAIL_PASSWORD secrets.")
        return

    send_email(f"⛳ RaxGuide Boost Picks — {today}", plain, html)


if __name__ == "__main__":
    main()
