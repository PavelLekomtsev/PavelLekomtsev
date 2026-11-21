#!/usr/bin/env python3
"""Daily stats cards: GitHub activity and languages (needs GITHUB_TOKEN, standard library only).

usage: build_stats.py --out DIR
Writes DIR/activity.svg and DIR/languages.svg only after every request succeeded.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from hudkit.fonts import load_fonts
from hudkit.palette import PAL
from hudkit.svg import corners, esc, svg_doc

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "profile-assets"}
MONTH_LETTERS = "JFMAMJJASOND"
DROP = {"HTML", "CSS", "SCSS"}
RENAME = {"C": "C / C++", "C++": "C / C++", "Jupyter Notebook": "Jupyter"}
# https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml
COLORS = {"Python": "#3572A5", "TypeScript": "#3178c6", "Jupyter": "#DA5B0B", "JavaScript": "#f1e05a",
          "Shell": "#89e051", "C / C++": "#f34b7d", "Vue": "#41b883", "Dockerfile": "#384d54",
          "Makefile": "#427819", "Rust": "#dea584", "Go": "#00ADD8", "Kotlin": "#A97BFF"}

QUERY = """query($login: String!, $from12: DateTime!, $fromYtd: DateTime!, $to: DateTime!) {
  user(login: $login) {
    last12: contributionsCollection(from: $from12, to: $to) {
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
    ytd: contributionsCollection(from: $fromYtd, to: $to) { contributionCalendar { totalContributions } }
    pullRequests { totalCount }
    organizations { totalCount }
  }
}"""


# ------------------------------------------------------------------ data
def month_buckets(days, today: date) -> list:
    """Contributions per calendar month for the 12 months ending with today's month, oldest first."""
    keys = []
    y, m = today.year, today.month
    for _ in range(12):
        keys.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    keys.reverse()
    sums = dict.fromkeys(keys, 0)
    for day, count in days:
        k = (int(day[:4]), int(day[5:7]))
        if k in sums:
            sums[k] += count
    return [(MONTH_LETTERS[m - 1], sums[(y, m)]) for y, m in keys]


def active_days(days) -> int:
    return sum(1 for _, c in days if c > 0)


def longest_streak(days) -> int:
    best = run = 0
    prev = None
    for day, count in sorted(days):
        d = date.fromisoformat(day)
        if count > 0:
            run = run + 1 if prev is not None and d - prev == timedelta(days=1) and run > 0 else 1
            best = max(best, run)
        else:
            run = 0
        prev = d
    return best


def kpis(total_12mo, total_ytd, prs, orgs, days) -> list:
    """Four (value, label) pairs; thin PR / org counts give way to calendar-based numbers."""
    out = [(str(total_12mo), "contributions · 12 mo"), (str(total_ytd), "contributions this year")]
    out.append((str(prs), "pull requests") if prs >= 3 else (str(active_days(days)), "active days · 12 mo"))
    out.append((str(orgs), "organizations") if orgs >= 2 else (str(longest_streak(days)), "longest streak · days"))
    return out


def merge_languages(per_repo) -> list:
    """Top 6 languages by bytes across repos: (name, bytes, colour); markup languages dropped."""
    total = {}
    for langs in per_repo:
        for name, size in langs.items():
            if name in DROP:
                continue
            key = RENAME.get(name, name)
            total[key] = total.get(key, 0) + size
    ranked = sorted(total.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    return [(name, size, COLORS.get(name, "#8b949e")) for name, size in ranked]


# ------------------------------------------------------------------ network
def _request(url: str, token: str, body: dict = None) -> bytes:
    headers = dict(HEADERS, Authorization=f"Bearer {token}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def fetch_profile(login: str, token: str, today: date) -> dict:
    # contributionsCollection spans at most one year
    variables = {
        "login": login,
        "from12": f"{today - timedelta(days=364)}T00:00:00Z",
        "fromYtd": f"{today.year}-01-01T00:00:00Z",
        "to": f"{today}T23:59:59Z",
    }
    reply = json.loads(_request(f"{API}/graphql", token, {"query": QUERY, "variables": variables}))
    if reply.get("errors"):
        raise RuntimeError("GraphQL: " + "; ".join(e.get("message", "?") for e in reply["errors"]))
    user = reply["data"]["user"]
    cal = user["last12"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    return {"days": days, "total_12mo": cal["totalContributions"],
            "total_ytd": user["ytd"]["contributionCalendar"]["totalContributions"],
            "prs": user["pullRequests"]["totalCount"], "orgs": user["organizations"]["totalCount"]}


def fetch_languages(repos, token: str) -> list:
    out = []
    for repo in repos:
        try:
            out.append(json.loads(_request(f"{API}/repos/{repo}/languages", token)))
        except urllib.error.HTTPError as err:
            if err.code != 404:
                raise
            print(f"warning: {repo} not found, skipped", file=sys.stderr)
    return out


# ------------------------------------------------------------------ rendering
def _card(fonts, w, h, title, note):
    return [f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="{PAL["panel"]}" stroke="{PAL["line"]}"/>',
            corners(10, 10, w - 20, h - 20, n=12),
            f'<text class="hd" x="28" y="40">{esc(fonts["JB7"].use(title))}</text>',
            f'<text class="hd2" x="{w - 28}" y="40" text-anchor="end">{esc(fonts["JB5"].use(note))}</text>']


def render_activity(kpi_pairs, months, root: Path) -> str:
    fonts = load_fonts(str(root / "scripts" / "fonts"))
    w, h = 434, 242
    out = _card(fonts, w, h, "GITHUB ACTIVITY", "last 12 months")
    for i, (value, label) in enumerate(kpi_pairs):
        x, y = 28 + (i % 2) * 200, 84 + (i // 2) * 58
        out.append(f'<text class="kv" x="{x}" y="{y}">{esc(fonts["JB7"].use(value))}</text>')
        out.append(f'<text class="kl" x="{x}" y="{y + 18}">{esc(fonts["JB5"].use(label))}</text>')
    mx = max((c for _, c in months), default=0) or 1
    bw, gap, base = 24, 8.6, 214
    for i, (label, count) in enumerate(months):
        x = 28 + i * (bw + gap)
        share = (count / mx) ** 0.5  # sqrt keeps quiet months visible next to busy ones
        bh = max(2.0, 36 * share)
        out.append(f'<rect class="bar" x="{x:.1f}" y="{base - bh:.1f}" width="{bw}" height="{bh:.1f}" rx="2" '
                   f'fill="{PAL["cyan"] if count else PAL["line"]}" opacity="{0.4 + 0.6 * share:.2f}"/>')
        out.append(f'<text class="mo" x="{x + bw / 2:.1f}" y="{base + 14}" text-anchor="middle">'
                   f'{fonts["JB5"].use(label)}</text>')
    css = (f".hd{{font:13px JB7;fill:{PAL['cyan']};letter-spacing:2px}}.hd2{{font:11.5px JB5;fill:{PAL['hud']}}}"
           f".kv{{font:28px JB7;fill:{PAL['text']}}}.kl{{font:11.5px JB5;fill:{PAL['muted']}}}"
           f".mo{{font:9.5px JB5;fill:{PAL['hud']}}}")
    return svg_doc(w, h, "\n".join(out), fonts, "GitHub activity", css)


def render_languages(langs, root: Path) -> str:
    fonts = load_fonts(str(root / "scripts" / "fonts"))
    w, h = 434, 242
    total = sum(size for _, size, _ in langs) or 1
    out = _card(fonts, w, h, "LANGUAGES", "public repos · by code size")
    out.append('<clipPath id="bar"><rect x="28" y="62" width="378" height="12" rx="6"/></clipPath><g clip-path="url(#bar)">')
    x = 28.0
    for _, size, color in langs:
        seg = 378 * size / total
        out.append(f'<rect x="{x:.1f}" y="62" width="{seg + 0.5:.1f}" height="12" fill="{color}"/>')
        x += seg
    out.append("</g>")
    for i, (name, size, color) in enumerate(langs):
        cx, cy = 28 + (i % 2) * 200, 112 + (i // 2) * 36
        pct = f"{100 * size / total:.1f}%"
        out.append(f'<circle cx="{cx + 6}" cy="{cy - 5}" r="6" fill="{color}"/>')
        out.append(f'<text class="ln" x="{cx + 20}" y="{cy}">{esc(fonts["SG5"].use(name))}</text>')
        out.append(f'<text class="lp" x="{cx + 178}" y="{cy}" text-anchor="end">{fonts["JB5"].use(pct)}</text>')
    css = (f".hd{{font:13px JB7;fill:{PAL['cyan']};letter-spacing:2px}}.hd2{{font:11.5px JB5;fill:{PAL['hud']}}}"
           f".ln{{font:15px SG5;fill:{PAL['text']}}}.lp{{font:13px JB5;fill:{PAL['muted']}}}")
    return svg_doc(w, h, "\n".join(out), fonts, "Languages", css)


# ------------------------------------------------------------------ entry point
def main(argv) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("error: GITHUB_TOKEN is not set", file=sys.stderr)
        return 1
    content = json.loads((ROOT / "scripts" / "content.json").read_text(encoding="utf-8"))
    today = datetime.now(timezone.utc).date()
    try:
        profile = fetch_profile(content["login"], token, today)
        per_repo = fetch_languages(content["languages_repos"], token)
    except (urllib.error.URLError, RuntimeError, KeyError, ValueError) as err:
        print(f"error: GitHub API request failed: {err}", file=sys.stderr)
        return 1
    langs = merge_languages(per_repo)
    if not langs:
        print("error: no language data returned", file=sys.stderr)
        return 1
    pairs = kpis(profile["total_12mo"], profile["total_ytd"], profile["prs"], profile["orgs"], profile["days"])
    activity = render_activity(pairs, month_buckets(profile["days"], today), ROOT)
    languages = render_languages(langs, ROOT)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "activity.svg").write_text(activity, encoding="utf-8")
    (args.out / "languages.svg").write_text(languages, encoding="utf-8")
    print(f"wrote {args.out}/activity.svg and languages.svg")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
