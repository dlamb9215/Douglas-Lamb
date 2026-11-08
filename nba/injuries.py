"""Fetch and parse the NBA's official daily injury-report PDF.

The report is authoritative for the league's submitted participation designations.
It does not establish starters, expected minutes, or the point impact of an absence.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from pypdf import PdfReader

BASE = "https://official.nba.com/nba-injury-report-{season_slug}-season"
PDF_HOST = "https://ak-static.cms.nba.com"
TEAM_NAMES = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GS", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NO",
    "New York Knicks": "NY", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC", "San Antonio Spurs": "SA", "Toronto Raptors": "TOR",
    "Utah Jazz": "UTAH", "Washington Wizards": "WSH",
}
TEAM_NAMES_SORTED = sorted(TEAM_NAMES, key=len, reverse=True)
PLAYER_ROW = re.compile(
    r"^(?P<last>[^,]+),\s*(?P<first>.+?)\s+"
    r"(?P<status>Available|Out|Questionable|Doubtful|Probable)\b"
    r"(?:\s+(?P<reason>.*))?$", re.IGNORECASE
)
REPORT_LINK = re.compile(r"Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{1,2})_(\d{2})(AM|PM)\.pdf", re.I)

class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)

def _get(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "text/html,application/pdf,*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"NBA injury report source returned HTTP {response.status}")
            return response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"NBA official injury report request failed: {exc}") from exc

def latest_report_url(game_date: date, season: int = 2027) -> str:
    season_slug = f"{season-1}-{str(season)[-2:]}"
    page_url = BASE.format(season_slug=season_slug)
    html = _get(page_url).decode("utf-8", errors="replace")
    links = _Links()
    links.feed(html)
    choices = []
    for href in links.hrefs:
        match = REPORT_LINK.search(href)
        if not match:
            continue
        report_day = date.fromisoformat(match.group(1))
        if report_day > game_date or (game_date - report_day).days > 1:
            continue
        hour = int(match.group(2))
        minute = int(match.group(3))
        suffix = match.group(4).upper()
        hour = hour % 12 + (12 if suffix == "PM" else 0)
        report_time = datetime.combine(report_day, datetime.min.time()).replace(
            hour=hour, minute=minute, tzinfo=timezone.utc
        )
        url = href if href.startswith("http") else PDF_HOST + href
        choices.append((report_time, url))
    if not choices:
        raise RuntimeError(
            f"No NBA official injury-report PDF found for {game_date.isoformat()} "
            "or the preceding day. Do not substitute stale designations."
        )
    return max(choices, key=lambda item: item[0])[1]

def parse_report_text(text: str, teams: set[str] | None = None) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    team_submission: dict[str, str] = {}
    current_team = None
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or line.startswith(("Injury Report:", "Page ")):
            continue
        # Team names may share a PDF text line with the first player row.
        found_team = None
        remainder = line
        for team_name in TEAM_NAMES_SORTED:
            pos = line.find(team_name)
            if pos >= 0:
                found_team = TEAM_NAMES[team_name]
                remainder = line[pos + len(team_name):].strip()
                break
        if found_team:
            current_team = found_team
            if teams is not None and current_team not in teams:
                current_team = None
                continue
            if remainder.upper() == "NOT YET SUBMITTED":
                team_submission[found_team] = "NOT YET SUBMITTED"
                continue
            if not remainder:
                continue
            line = remainder
        if current_team is None:
            continue
        if line.upper() == "NOT YET SUBMITTED":
            team_submission[current_team] = "NOT YET SUBMITTED"
            continue
        match = PLAYER_ROW.match(line)
        if match:
            player = f"{match.group('first').strip()} {match.group('last').strip()}"
            rows.append({
                "team": current_team, "player": player,
                "status": match.group("status").title(),
                "reason": (match.group("reason") or "").strip(),
            })
    if teams is not None:
        rows = [row for row in rows if row["team"] in teams]
        team_submission = {key: value for key, value in team_submission.items() if key in teams}
    return {"players": rows, "team_submission": team_submission}

def fetch_official_injuries(game_date: date, home: str, away: str, season: int = 2027) -> dict[str, Any]:
    aliases = {"GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH", "WAS": "WSH"}
    target_teams = {aliases.get(home.upper(), home.upper()), aliases.get(away.upper(), away.upper())}
    report_url = latest_report_url(game_date, season)
    pdf = _get(report_url)
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    parsed = parse_report_text(text, target_teams)
    if not parsed["players"] and not parsed["team_submission"]:
        raise RuntimeError("Official injury report was downloaded but no rows for the requested teams could be parsed.")
    return {
        "game_date": game_date.isoformat(), "teams": sorted(target_teams),
        "report_url": report_url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "player_statuses": parsed["players"], "team_submission": parsed["team_submission"],
        "source": "NBA official injury report",
        "warnings": [
            "Questionable and Doubtful players are not treated as confirmed active.",
            "This report does not confirm starters or minutes projections.",
            "Team point adjustments are not inferred from status labels; player impact must be modeled separately.",
        ],
    }

def main():
    parser = argparse.ArgumentParser(description="Fetch the NBA official injury report for a matchup")
    parser.add_argument("--date", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--season", type=int, default=2027)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    result = fetch_official_injuries(date.fromisoformat(args.date), args.home, args.away, args.season)
    rendered = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

if __name__ == "__main__":
    main()
