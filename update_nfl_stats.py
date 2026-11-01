import csv
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SEASON = 2026
REPO_API = (
    "https://api.github.com/repos/"
    "nflverse/nflverse-data/releases/tags/stats_team"
)

OUTPUT_FILE = Path("nfl_team_stats.json")

def download_csv():
    request = urllib.request.Request(
        REPO_API,
        headers={"User-Agent": "Doug-Elite-Game-Simulator"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.loads(response.read().decode("utf-8"))

    filename = f"stats_team_reg_{SEASON}.csv"

    asset = next(
        (item for item in release["assets"]
         if item["name"] == filename),
        None
    )

    if asset is None:
        raise RuntimeError(f"Could not find {filename} in the data release.")

    request = urllib.request.Request(
        asset["browser_download_url"],
        headers={"User-Agent": "Doug-Elite-Game-Simulator"}
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8-sig")


def number(row, field):
    value = row.get(field, "")
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def per_game(value, games):
    if value is None or not games:
        return None
    return round(value / games, 2)


def safe_rate(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator, 3)


def main():
    csv_text = download_csv()
    rows = list(csv.DictReader(csv_text.splitlines()))

    teams = {}

    for row in rows:
        if row.get("season_type", "REG") != "REG":
            continue

        team = row.get("team", "").upper()
        games = number(row, "games")

        if not team or not games or games <= 0:
            continue

        pass_yards = number(row, "passing_yards")
        pass_attempts = number(row, "attempts")
        completions = number(row, "completions")
        pass_tds = number(row, "passing_tds")
        interceptions = number(row, "passing_interceptions")
        pass_first = number(row, "passing_first_downs")

        rush_yards = number(row, "rushing_yards")
        carries = number(row, "carries")
        rush_tds = number(row, "rushing_tds")
        rush_first = number(row, "rushing_first_downs")

        sacks = number(row, "sacks_suffered") or 0
        plays = (
            (pass_attempts or 0)
            + (carries or 0)
            + sacks
        )

        total_yards = (
            (pass_yards or 0)
            + (rush_yards or 0)
        )

        takeaways = (
            (number(row, "def_interceptions") or 0)
            + (number(row, "fumble_recovery_opp") or 0)
        )

        fumbles_lost = sum(
            number(row, field) or 0
            for field in (
                "sack_fumbles_lost",
                "rushing_fumbles_lost",
                "receiving_fumbles_lost",
            )
        )

        giveaways = (interceptions or 0) + fumbles_lost

        teams[team] = {
            "team": team,
            "offense": {
                "passing": {
                    "yards_per_game": per_game(pass_yards, games),
                    "attempts_per_game": per_game(pass_attempts, games),
                    "completions_per_game": per_game(completions, games),
                    "completion_pct": (
                        round(completions / pass_attempts * 100, 2)
                        if completions is not None
                        and pass_attempts else None
                    ),
                    "yards_per_attempt": safe_rate(
                        pass_yards, pass_attempts
                    ),
                    "touchdowns": per_game(pass_tds, games),
                    "interceptions": per_game(interceptions, games),
                    "first_downs_per_game": per_game(pass_first, games),
                },
                "rushing": {
                    "yards_per_game": per_game(rush_yards, games),
                    "attempts_per_game": per_game(carries, games),
                    "yards_per_carry": safe_rate(rush_yards, carries),
                    "touchdowns": per_game(rush_tds, games),
                    "first_downs_per_game": per_game(rush_first, games),
                },
                "total": {
                    "yards_per_game": per_game(total_yards, games),
                    "plays_per_game": per_game(plays, games),
                    "yards_per_play": safe_rate(total_yards, plays),
                },
            },
            "defense": {
                "passing": {},
                "rushing": {},
                "total": {},
            },
            "turnovers": {
                "takeaways": round(takeaways, 2),
                "giveaways": round(giveaways, 2),
                "differential": round(takeaways - giveaways, 2),
            },
        }

    if len(teams) != 32:
        raise RuntimeError(
            f"Expected 32 NFL teams, but imported {len(teams)}. "
            "The existing data file was not changed."
        )

    OUTPUT_FILE.write_text(
        json.dumps(
            [teams[key] for key in sorted(teams)],
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print(f"Imported offensive stats for {len(teams)} teams.")
    print(f"Season: {SEASON}")
    print("Defensive fields remain blank until verified data is added.")
    print(
        "Source update checked at: "
        + datetime.now(timezone.utc).isoformat()
    )


if __name__ == "__main__":
    main()