"""Render profile/profile.svg and profile/year.svg from the public GitHub GraphQL API.

Uses only the standard library. Reads GITHUB_TOKEN (Actions' built-in token is enough)
and USERNAME from the environment. Run with --selftest to check the summary logic offline.
"""
import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from xml.sax.saxutils import escape

ROLE = "Data Science undergraduate · Statistics, Brawijaya University"
BG, BORDER, GREEN, TEXT, MUTED = "#0d1117", "#1f3b2c", "#39d353", "#e6edf3", "#8b949e"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
FONT = "font-family=\"'Segoe UI',Ubuntu,'Helvetica Neue',sans-serif\""
MONO = "font-family=\"'JetBrains Mono',Consolas,'SFMono-Regular',monospace\""

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    name login
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      totalCount
      nodes { stargazerCount languages(first: 10) { edges { size node { name color } } } }
    }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions weeks { contributionDays { contributionCount date } } }
    }
  }
}"""


def fetch(login, token):
    now = datetime.now(timezone.utc)
    start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    body = json.dumps({"query": QUERY, "variables": {
        "login": login, "from": start.isoformat(), "to": now.isoformat()}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", body, {
        "Authorization": f"bearer {token}", "User-Agent": "profile-card"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("errors"):
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def summarize(user):
    repos = user["repositories"]
    langs, colors = Counter(), {}
    for repo in repos["nodes"]:
        for edge in repo["languages"]["edges"]:
            langs[edge["node"]["name"]] += edge["size"]
            colors[edge["node"]["name"]] = edge["node"]["color"] or MUTED
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    busiest = max(days, key=lambda d: d["contributionCount"], default={"contributionCount": 0})
    return {
        "name": user["name"] or user["login"], "login": user["login"],
        "repos": repos["totalCount"], "followers": user["followers"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos["nodes"]),
        "total": cal["totalContributions"],
        "active": sum(1 for d in days if d["contributionCount"]),
        "busiest": busiest["contributionCount"],
        "langs": [(n, colors[n]) for n, _ in langs.most_common(4)],
        "days": days,
    }


def frame(width, height, inner, label):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">
<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14" fill="{BG}" stroke="{BORDER}"/>
{inner}
</svg>
"""


def level(count, peak):
    return 0 if not count else min(4, 1 + (count * 4 - 1) // max(peak, 1))


def profile_svg(s):
    rows = [("Repositories", s["repos"]), ("Stars", s["stars"]),
            ("Contributions", s["total"]), ("Followers", s["followers"])]
    out = [
        f'<circle cx="28" cy="28" r="6" fill="#ff5f57"/><circle cx="48" cy="28" r="6" fill="#febc2e"/><circle cx="68" cy="28" r="6" fill="#28c840"/>',
        f'<text x="92" y="33" fill="{MUTED}" font-size="14" {MONO}>README.md</text>',
        f'<line x1="0" y1="54" x2="840" y2="54" stroke="{BORDER}"/>',
        f'<text x="32" y="92" fill="{GREEN}" font-size="15" {MONO}>@{escape(s["login"])}</text>',
        f'<text x="32" y="134" fill="{TEXT}" font-size="34" font-weight="700" {FONT}>{escape(s["name"])}</text>',
        f'<text x="32" y="162" fill="{MUTED}" font-size="15" {FONT}>{escape(ROLE)}</text>',
    ]
    for i, (label, value) in enumerate(rows):
        y = 200 + i * 30
        out.append(f'<rect x="32" y="{y - 11}" width="12" height="12" rx="3" fill="none" stroke="{GREEN}" stroke-width="1.5"/>')
        out.append(f'<text x="56" y="{y}" fill="{TEXT}" font-size="15" {FONT}><tspan font-weight="700">{value}</tspan>'
                   f'<tspan fill="{MUTED}"> {label}</tspan></text>')
    x = 32
    for name, color in s["langs"]:
        w = 30 + 8 * len(name)
        out.append(f'<rect x="{x}" y="318" width="{w}" height="28" rx="14" fill="#161b22" stroke="#30363d"/>'
                   f'<circle cx="{x + 15}" cy="332" r="5" fill="{color}"/>'
                   f'<text x="{x + 26}" y="337" fill="{TEXT}" font-size="13" {MONO}>{escape(name)}</text>')
        x += w + 10
    # Dot-matrix of the last 22 weeks instead of a portrait.
    days, peak = s["days"][-154:], max((d["contributionCount"] for d in s["days"]), default=0)
    for i, d in enumerate(days):
        col, row = divmod(i, 7)
        out.append(f'<rect x="{522 + col * 13}" y="{186 + row * 13}" width="10" height="10" rx="2" '
                   f'fill="{LEVELS[level(d["contributionCount"], peak)]}"/>')
    out.append(f'<text x="522" y="296" fill="{MUTED}" font-size="12" {MONO}>last 22 weeks</text>')
    return frame(840, 370, "\n".join(out), f'{s["name"]} GitHub profile')


def year_svg(s):
    year = datetime.now(timezone.utc).year
    inner = "\n".join([
        f'<text x="32" y="48" fill="{TEXT}" font-size="22" font-weight="700" {FONT}>The city I built in {year}</text>',
        f'<text x="32" y="86" fill="{GREEN}" font-size="13" letter-spacing="1.5" {MONO}>CONTRIBUTIONS</text>',
        f'<text x="32" y="128" fill="{TEXT}" font-size="40" font-weight="700" {MONO}>{s["total"]}</text>',
        f'<text x="32" y="160" fill="{MUTED}" font-size="14" {MONO}>{s["active"]} active days</text>',
        f'<text x="32" y="182" fill="{MUTED}" font-size="14" {MONO}>Busiest day: {s["busiest"]}</text>',
    ])
    return frame(840, 205, inner, f"{year} contribution summary")


def selftest():
    day = lambda n: {"contributionCount": n, "date": "2026-01-01"}
    s = summarize({
        "name": None, "login": "x", "followers": {"totalCount": 2},
        "repositories": {"totalCount": 2, "nodes": [
            {"stargazerCount": 3, "languages": {"edges": [{"size": 10, "node": {"name": "Python", "color": "#3572A5"}}]}},
            {"stargazerCount": 1, "languages": {"edges": [{"size": 5, "node": {"name": "R", "color": None}}]}}]},
        "contributionsCollection": {"contributionCalendar": {"totalContributions": 9,
            "weeks": [{"contributionDays": [day(0), day(7), day(2)]}]}},
    })
    assert (s["name"], s["stars"], s["active"], s["busiest"]) == ("x", 4, 2, 7)
    assert s["langs"] == [("Python", "#3572A5"), ("R", MUTED)]
    assert [level(n, 7) for n in (0, 1, 7)] == [0, 1, 4]
    assert "<svg" in profile_svg(s) and "<svg" in year_svg(s)
    print("selftest ok")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    s = summarize(fetch(os.environ["USERNAME"], os.environ["GITHUB_TOKEN"]))
    os.makedirs("profile", exist_ok=True)
    for name, svg in (("profile.svg", profile_svg(s)), ("year.svg", year_svg(s))):
        with open(os.path.join("profile", name), "w", encoding="utf-8") as f:
            f.write(svg)


if __name__ == "__main__":
    main()
