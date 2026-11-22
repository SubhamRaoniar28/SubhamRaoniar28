"""Generate self-hosted GitHub stats cards (dark + light) for the profile README.

Fetches public data from the GitHub GraphQL API and writes:
  assets/stats/{dark,light}/stats.svg      totals card
  assets/stats/{dark,light}/languages.svg  most used languages
  assets/stats/{dark,light}/streak.svg     contribution streak

Usage:
  GITHUB_TOKEN=... python3 .github/scripts/stats.py [username]
  python3 .github/scripts/stats.py --sample   # render with sample data, no network
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

USER = "SubhamRaoniar28"
OUT = "assets/stats"
HIDE_LANGS = {"HTML", "CSS", "SCSS"}
LANG_COUNT = 6
FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif'

THEMES = {
    "dark": dict(accent="#61DAFB", streak="#00E7FF", text="#C9D1D9", muted="#8B949E", grid="#30363D", track="#30363D"),
    "light": dict(accent="#087EA4", streak="#087EA4", text="#57606A", muted="#6E7681", grid="#D0D7DE", track="#D0D7DE"),
}

# Primer Octicons (MIT), 16px
ICONS = {'star': ['M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z'], 'git-commit': ['M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5Zm-1.43-.75a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z'], 'git-pull-request': ['M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z'], 'issue-opened': ['M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z', 'M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z'], 'repo': ['M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z'], 'flame': ['M9.533.753V.752c.217 2.385 1.463 3.626 2.653 4.81C13.37 6.74 14.498 7.863 14.498 10c0 3.5-3 6-6.5 6S1.5 13.512 1.5 10c0-1.298.536-2.56 1.425-3.286.376-.308.862 0 1.035.454C4.46 8.487 5.581 8.419 6 8c.282-.282.341-.811-.003-1.5C4.34 3.187 7.035.75 8.77.146c.39-.137.726.194.763.607ZM7.998 14.5c2.832 0 5-1.98 5-4.5 0-1.463-.68-2.19-1.879-3.383l-.036-.037c-1.013-1.008-2.3-2.29-2.834-4.434-.322.256-.63.579-.864.953-.432.696-.621 1.58-.046 2.73.473.947.67 2.284-.278 3.232-.61.61-1.545.84-2.403.633a2.79 2.79 0 0 1-1.436-.874A3.198 3.198 0 0 0 3 10c0 2.53 2.164 4.5 4.998 4.5Z']}


# ---------------------------------------------------------------- data

def gql(query, variables, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-stats-cards"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch(user, token):
    repos, cursor = [], None
    q_main = """
    query($login:String!, $cursor:String) {
      user(login:$login) {
        createdAt
        repositoriesContributedTo(first:1, contributionTypes:[COMMIT,ISSUE,PULL_REQUEST,REPOSITORY]) { totalCount }
        contributionsCollection { totalCommitContributions totalPullRequestContributions totalIssueContributions }
        pullRequests { totalCount }
        issues { totalCount }
        repositories(first:100, after:$cursor, ownerAffiliations:OWNER) {
          pageInfo { hasNextPage endCursor }
          nodes { isFork stargazerCount
            languages(first:10, orderBy:{field:SIZE, direction:DESC}) { edges { size node { name color } } } }
        }
      }
    }"""
    while True:
        u = gql(q_main, {"login": user, "cursor": cursor}, token)["user"]
        repos += u["repositories"]["nodes"]
        if not u["repositories"]["pageInfo"]["hasNextPage"]:
            break
        cursor = u["repositories"]["pageInfo"]["endCursor"]

    # contribution calendar, one year window at a time since the account was created
    q_cal = """
    query($login:String!, $from:DateTime!, $to:DateTime!) {
      user(login:$login) { contributionsCollection(from:$from, to:$to) {
        contributionCalendar { weeks { contributionDays { date contributionCount } } } } }
    }"""
    created = dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    days, start = {}, created
    while start < now:
        end = min(start + dt.timedelta(days=365), now)
        cal = gql(q_cal, {"login": user, "from": start.isoformat(), "to": end.isoformat()}, token)
        for w in cal["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
        start = end

    langs = {}
    for r in repos:
        if r["isFork"]:
            continue
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, [0, e["node"]["color"] or "#8B949E"])[0] += e["size"]

    cc = u["contributionsCollection"]
    return {
        "stars": sum(r["stargazerCount"] for r in repos),  # all owned repos, forks included
        "commits": cc["totalCommitContributions"],
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
        "langs": langs,
        "days": days,
    }


def sample():
    days, d = {}, dt.date(2018, 7, 20)
    while d <= dt.date.today():
        days[d.isoformat()] = 1 if d.day in (3, 9, 21) or (dt.date(2021, 2, 21) <= d <= dt.date(2021, 2, 27)) else 0
        d += dt.timedelta(days=1)
    days[dt.date.today().isoformat()] = 2
    return {"stars": 66, "commits": 25, "prs": 5, "issues": 1, "contributed": 0, "days": days,
            "langs": {"JavaScript": [99180, "#f1e05a"], "Java": [820, "#b07219"], "Python": [600, "#3572A5"],
                      "CSS": [5000, "#663399"], "HTML": [900, "#e34c26"]}}


# ---------------------------------------------------------------- maths

def streaks(days):
    dates = sorted(days)
    total = sum(days.values())
    first = dt.date.fromisoformat(dates[0])
    longest, run, run_start = (0, None, None), 0, None
    for s in dates:
        if days[s] > 0:
            if run == 0:
                run_start = s
            run += 1
            if run > longest[0]:
                longest = (run, run_start, s)
        else:
            run = 0
    today = dt.date.fromisoformat(dates[-1])
    cur, d = 0, today
    if days.get(d.isoformat(), 0) == 0:
        d -= dt.timedelta(days=1)  # today not counted until you contribute
    cur_end = d
    while days.get(d.isoformat(), 0) > 0:
        cur += 1
        d -= dt.timedelta(days=1)
    cur_start = d + dt.timedelta(days=1)
    return {"total": total, "first": first, "current": cur, "cur_start": cur_start, "cur_end": cur_end,
            "longest": longest[0],
            "long_start": dt.date.fromisoformat(longest[1]) if longest[1] else None,
            "long_end": dt.date.fromisoformat(longest[2]) if longest[2] else None}


def fmt(d, year=True):
    return d.strftime("%b %-d, %Y") if year else d.strftime("%b %-d")


# ---------------------------------------------------------------- svg

def svg(w, h, title, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="t">'
            f'<title id="t">{escape(title)}</title>'
            f'<style>text{{font-family:{FONT}}}'
            f'</style>'
            f'{body}</svg>\n')


def icon(name, x, y, colour, size=16):
    s = size / 16
    paths = "".join(f'<path d="{d}"/>' for d in ICONS[name])
    return f'<g transform="translate({x} {y}) scale({s})" fill="{colour}">{paths}</g>'


def stats_card(data, t, name):
    rows = [("star", "Total stars earned", data["stars"]),
            ("git-commit", "Total commits (last year)", data["commits"]),
            ("git-pull-request", "Total PRs", data["prs"]),
            ("issue-opened", "Total issues", data["issues"])]
    body = f'<text x="25" y="36" font-size="18" font-weight="600" fill="{t["accent"]}">{escape(name)}\'s GitHub stats</text>'
    for i, (ic, label, val) in enumerate(rows):
        y = 70 + i * 25
        body += (f'<g class="in" style="animation-delay:{0.1 + i * 0.1:.1f}s">{icon(ic, 25, y - 12, t["accent"])}'
                 f'<text x="50" y="{y}" font-size="14" font-weight="600" fill="{t["text"]}">{label}:</text>'
                 f'<text x="270" y="{y}" font-size="14" font-weight="700" fill="{t["text"]}">{val:,}</text></g>')
    return svg(400, 70 + len(rows) * 25, f"{name}'s GitHub stats", body)


def langs_card(data, t):
    items = sorted(((n, v[0], v[1]) for n, v in data["langs"].items() if n not in HIDE_LANGS),
                   key=lambda x: -x[1])[:LANG_COUNT]
    total = sum(s for _, s, _ in items) or 1
    body = f'<text x="25" y="36" font-size="18" font-weight="600" fill="{t["accent"]}">Most used languages</text>'
    bx, bw = 25, 250
    body += f'<clipPath id="bar"><rect x="{bx}" y="52" width="{bw}" height="8" rx="4"/></clipPath><g clip-path="url(#bar)">'
    body += f'<rect x="{bx}" y="52" width="{bw}" height="8" fill="{t["track"]}"/>'
    x = bx
    for n, s, c in items:
        w = bw * s / total
        body += f'<rect x="{x:.2f}" y="52" width="{max(w, 1.5):.2f}" height="8" fill="{c}"/>'
        x += w
    body += "</g>"
    for i, (n, s, c) in enumerate(items):
        col, row = i % 2, i // 2
        lx, ly = 25 + col * 135, 86 + row * 24
        body += (f'<g class="in" style="animation-delay:{0.1 + i * 0.08:.2f}s"><circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{c}"/>'
                 f'<text x="{lx + 16}" y="{ly}" font-size="12" fill="{t["text"]}">{escape(n)} {100 * s / total:.2f}%</text></g>')
    h = 86 + ((len(items) + 1) // 2) * 24 - 6
    return svg(300, max(h, 120), "Most used languages", body)


def streak_card(data, t):
    """Total contributions and longest streak always; the current streak only while one is running."""
    s = streaks(data["days"])
    a, txt, mut, grid = t["streak"], t["text"], t["muted"], t["grid"]
    h = 165

    def col(cx, num, label, sub=None, accent_label=False):
        out = (f'<text x="{cx}" y="79" text-anchor="middle" font-size="28" font-weight="700" fill="{a}">{num:,}</text>'
               f'<text x="{cx}" y="{140 if accent_label else 116}" text-anchor="middle" font-size="14" '
               f'font-weight="{700 if accent_label else 400}" fill="{a if accent_label else txt}">{label}</text>')
        if sub:
            out += f'<text x="{cx}" y="145" text-anchor="middle" font-size="12" fill="{mut}">{sub}</text>'
        return out

    total = col(82.5, s["total"], "Total contributions", f'{fmt(s["first"])} - Present')
    if s["current"] > 0:
        body = (f'<line x1="165" y1="28" x2="165" y2="{h - 15}" stroke="{grid}"/>'
                f'<line x1="330" y1="28" x2="330" y2="{h - 15}" stroke="{grid}"/>' + total
                + f'<mask id="ring"><rect width="495" height="{h}" fill="#fff"/><rect x="232" y="16" width="31" height="31" fill="#000"/></mask>'
                + f'<circle cx="247.5" cy="71" r="40" fill="none" stroke="{a}" stroke-width="5" mask="url(#ring)"/>'
                + icon("flame", 238.5, 22, a, 18)
                + col(247.5, s["current"], "Current streak", accent_label=True)
                + col(412.5, s["longest"], "Longest streak"))
        return svg(495, h, "Contribution streak", body)
    body = (f'<line x1="165" y1="28" x2="165" y2="{h - 15}" stroke="{grid}"/>' + total
            + col(247.5, s["longest"], "Longest streak"))
    return svg(330, h, "Contributions and longest streak", body)


def main():
    if "--sample" in sys.argv:
        data = sample()
    else:
        token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN is not set")
        user = next((a for a in sys.argv[1:] if not a.startswith("-")), USER)
        data = fetch(user, token)
    name = "Subham Raoniar"
    for theme, t in THEMES.items():
        os.makedirs(os.path.join(OUT, theme), exist_ok=True)
        for fname, content in (("stats.svg", stats_card(data, t, name)),
                               ("languages.svg", langs_card(data, t)),
                               ("streak.svg", streak_card(data, t))):
            with open(os.path.join(OUT, theme, fname), "w") as f:
                f.write(content)
    s = streaks(data["days"])
    print(f'stars={data["stars"]} commits={data["commits"]} prs={data["prs"]} issues={data["issues"]} '
          f'total={s["total"]} current={s["current"]} longest={s["longest"]}')


if __name__ == "__main__":
    main()
