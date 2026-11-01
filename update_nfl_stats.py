import csv
import json
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SEASON = 2026
API_URL = (
    "https://api.github.com/repos/"
    "nflverse/nflverse-data/releases/tags/stats_team"
)
OUTPUT = Path("nfl_team_stats.json")
TEAM_ALIASES = {"LA": "LAR"}


def normalize_team(value):
    team = (value or "").upper()
    return TEAM_ALIASES.get(team, team)


def download_csv(filename):
    request = urllib.request.Request(
        API_URL,
        headers={"User-Agent": "Doug-Elite-Game-Simulator"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.loads(response.read().decode("utf-8"))

    asset = next(
        (a for a in release["assets"] if a["name"] == filename),
        None
    )
    if asset is None:
        raise RuntimeError(f"Missing data file: {filename}")

    request = urllib.request.Request(
        asset["browser_download_url"],
        headers={"User-Agent": "Doug-Elite-Game-Simulator"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return list(csv.DictReader(
            response.read().decode("utf-8-sig").splitlines()
        ))

def download_schedule():
    url = (
        "https://github.com/nflverse/nflverse-data/"
        "releases/download/schedules/games.csv"
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Doug-Elite-Game-Simulator"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return list(csv.DictReader(
            response.read().decode("utf-8-sig").splitlines()
        ))
        
def num(row, field):
    try:
        value = row.get(field, "")
        return float(value) if value not in ("", None) else 0.0
    except (TypeError, ValueError):
        return 0.0


def rate(a, b):
    return round(a / b, 3) if b else None


def average(a, games):
    return round(a / games, 2) if games else None


def main():
    regular = download_csv(f"stats_team_reg_{SEASON}.csv")
    schedule = download_schedule()
    weekly = download_csv(f"stats_team_week_{SEASON}.csv")

    teams = {}
    scoring = defaultdict(lambda: {
        "games": 0,
        "points_for": 0,
        "points_against": 0,
    })

    for game in schedule:
        if game.get("season") != str(SEASON):
            continue
        if game.get("game_type") != "REG":
            continue

        home = normalize_team(game.get("home_team"))
        away = normalize_team(game.get("away_team"))
        home_score = game.get("home_score")
        away_score = game.get("away_score")

        if not home_score or not away_score:
            continue

        home_score = int(float(home_score))
        away_score = int(float(away_score))

        scoring[home]["games"] += 1
        scoring[home]["points_for"] += home_score
        scoring[home]["points_against"] += away_score

        scoring[away]["games"] += 1
        scoring[away]["points_for"] += away_score
        scoring[away]["points_against"] += home_score
    for row in regular:
        if row.get("season_type") != "REG":
            continue

        team = normalize_team(row.get("team"))
        games = num(row, "games")
        if not team or games <= 0:
            continue

        py = num(row, "passing_yards")
        pa = num(row, "attempts")
        comp = num(row, "completions")
        ptd = num(row, "passing_tds")
        interceptions = num(row, "passing_interceptions")
        pfirst = num(row, "passing_first_downs")

        ry = num(row, "rushing_yards")
        carries = num(row, "carries")
        rtd = num(row, "rushing_tds")
        rfirst = num(row, "rushing_first_downs")

        sacks = num(row, "sacks_suffered")
        plays = pa + carries + sacks
        total_yards = py + ry

        takeaways = (
            num(row, "def_interceptions")
            + num(row, "fumble_recovery_opp")
        )
        giveaways = (
            interceptions
            + num(row, "sack_fumbles_lost")
            + num(row, "rushing_fumbles_lost")
            + num(row, "receiving_fumbles_lost")
        )

        teams[team] = {
            "team": team,
            "games_played": int(games),
            "points_for_per_game": average(
    scoring[team]["points_for"],
    scoring[team]["games"]
),
"points_allowed_per_game": average(
    scoring[team]["points_against"],
    scoring[team]["games"]
),
            "offense": {
                "passing": {
                    "yards_per_game": average(py, games),
                    "attempts_per_game": average(pa, games),
                    "completions_per_game": average(comp, games),
                    "completion_pct": round(comp / pa * 100, 2) if pa else None,
                    "yards_per_attempt": rate(py, pa),
                    "touchdowns": average(ptd, games),
                    "interceptions": average(interceptions, games),
                    "first_downs_per_game": average(pfirst, games),
                },
                "rushing": {
                    "yards_per_game": average(ry, games),
                    "attempts_per_game": average(carries, games),
                    "yards_per_carry": rate(ry, carries),
                    "touchdowns": average(rtd, games),
                    "first_downs_per_game": average(rfirst, games),
                },
                "total": {
                    "yards_per_game": average(total_yards, games),
                    "plays_per_game": average(plays, games),
                    "yards_per_play": rate(total_yards, plays),
                },
            },
            "defense": {
                "passing": {},
                "rushing": {},
                "total": {},
            },
            "turnovers": {
                "takeaways": takeaways,
                "giveaways": giveaways,
                "differential": takeaways - giveaways,
            },
        }

    # Build defensive totals from the offenses each team faced.
    allowed = defaultdict(lambda: {
        "games": 0,
        "points_allowed": 0,
        "pass_yards": 0,
        "pass_attempts": 0,
        "completions": 0,
        "pass_tds": 0,
        "pass_first": 0,
        "rush_yards": 0,
        "carries": 0,
        "rush_tds": 0,
        "rush_first": 0,
        "sacks": 0,
        "def_interceptions": 0,
    })

    for row in weekly:
        if row.get("season_type") != "REG":
            continue

        opponent = normalize_team(row.get("opponent_team"))
        team = normalize_team(row.get("team"))

        if opponent not in teams or team not in teams:
            continue

        d = allowed[opponent]
        d["games"] += 1
        d["pass_yards"] += num(row, "passing_yards")
        d["pass_attempts"] += num(row, "attempts")
        d["completions"] += num(row, "completions")
        d["pass_tds"] += num(row, "passing_tds")
        d["pass_first"] += num(row, "passing_first_downs")
        d["rush_yards"] += num(row, "rushing_yards")
        d["carries"] += num(row, "carries")
        d["rush_tds"] += num(row, "rushing_tds")
        d["rush_first"] += num(row, "rushing_first_downs")
        d["sacks"] += num(row, "sacks_suffered")

    # Defensive interceptions are credited to the defending team.
    for row in weekly:
        if row.get("season_type") != "REG":
            continue
        team = normalize_team(row.get("team"))
        if team in allowed:
            allowed[team]["def_interceptions"] += num(
                row, "def_interceptions"
            )

    for team, record in teams.items():
        d = allowed[team]
        games = d["games"]

        if games == 0:
            continue

        py = d["pass_yards"]
        pa = d["pass_attempts"]
        comp = d["completions"]
        ry = d["rush_yards"]
        carries = d["carries"]
        total_yards = py + ry
        plays = pa + carries + d["sacks"]

        record["defense"] = {
            "passing": {
                "yards_per_game": average(py, games),
                "attempts_per_game": average(pa, games),
                "completions_per_game": average(comp, games),
                "completion_pct": round(comp / pa * 100, 2) if pa else None,
                "yards_per_attempt": rate(py, pa),
                "touchdowns": average(d["pass_tds"], games),
                "interceptions": average(d["def_interceptions"], games),
                "first_downs_per_game": average(d["pass_first"], games),
            },
            "rushing": {
                "yards_per_game": average(ry, games),
                "attempts_per_game": average(carries, games),
                "yards_per_carry": rate(ry, carries),
                "touchdowns": average(d["rush_tds"], games),
                "first_downs_per_game": average(d["rush_first"], games),
            },
            "total": {
                "yards_per_game": average(total_yards, games),
                "plays_per_game": average(plays, games),
                "yards_per_play": rate(total_yards, plays),
            },
        }

    if len(teams) != 32:
        raise RuntimeError(
            f"Expected 32 teams, imported {len(teams)}. "
            "Existing file was not changed."
        )

    for team, record in teams.items():
        for category in ("passing", "rushing", "total"):
            if not record["defense"][category]:
                raise RuntimeError(
                    f"Missing defensive data for {team}."
                )

    OUTPUT.write_text(
        json.dumps(
            [teams[key] for key in sorted(teams)],
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print("NFL statistics successfully imported.")
    print(f"Season: {SEASON}")
    print("Teams: 32")
    print("Offense: populated")
    print("Defense: populated from opponent game statistics")
    print("Source: nflverse")
    print(datetime.now(timezone.utc).isoformat())


if __name__ == "__main__":
    main()