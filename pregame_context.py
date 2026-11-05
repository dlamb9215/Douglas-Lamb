"""Pregame context gate for fresh NFL player availability and depth data.

Depth-chart order is not official game-day inactive or starter confirmation.
This module reports those limits explicitly and never promotes a depth-chart
listing to an official active designation.
"""
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

VALID_TEAMS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LV", "LAC", "LAR", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SF", "SEA", "TB", "TEN", "WAS",
}


def build_pregame_report(pool, home, away, max_age_hours=36, now=None):
    now = now or datetime.now(timezone.utc)
    home, away = home.upper(), away.upper()
    if home not in VALID_TEAMS or away not in VALID_TEAMS or home == away:
        raise ValueError("Provide two different valid NFL team abbreviations.")
    if not isinstance(pool, dict) or not isinstance(pool.get("players"), list):
        raise ValueError("Player pool must contain a players list.")
    if pool.get("source") != "nflverse":
        raise ValueError("Player pool source is not verified nflverse.")
    retrieved = pool.get("retrieved_at_utc")
    try:
        timestamp = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("Player pool has no valid UTC retrieval timestamp.") from exc
    if timestamp.tzinfo is None:
        raise ValueError("Player pool timestamp must include a timezone.")
    age = now - timestamp.astimezone(timezone.utc)
    if age < timedelta(minutes=-5) or age > timedelta(hours=max_age_hours):
        raise ValueError("Player availability/depth data is stale or future-dated.")

    teams = {}
    for team in (home, away):
        rows = [p for p in pool["players"] if str(p.get("team", "")).upper() == team]
        qbs = sorted(
            [p for p in rows if p.get("position") == "QB"],
            key=lambda p: (p.get("depth_order", 99), p.get("name", "")),
        )
        injury_rows = [
            {
                "name": p.get("name"),
                "position": p.get("position"),
                "status": p.get("injury_status", "unknown"),
                "practice_status": p.get("practice_status"),
                "reported_injury": p.get("reported_injury"),
                "injury_week": p.get("injury_week"),
                "injury_report_modified": p.get("injury_report_modified"),
                "depth_order": p.get("depth_order"),
            }
            for p in rows
            if p.get("injury_status", "unknown") in {"out", "doubtful", "questionable"}
        ]
        qb1 = next((p for p in qbs if p.get("depth_order") == 1), None)
        qb1_ready = bool(
            qb1
            and str(qb1.get("roster_status", "")).lower() in {"act", "active", "1"}
            and qb1.get("injury_status") == "active"
        )
        teams[team] = {
            "player_records": len(rows),
            "quarterback_depth_chart": [
                {
                    "name": p.get("name"),
                    "depth_order": p.get("depth_order"),
                    "roster_status": p.get("roster_status"),
                    "injury_status": p.get("injury_status"),
                    "injury_week": p.get("injury_week"),
                    "games": p.get("games"),
                    "passing_yards_per_game": p.get("passing_yards_per_game"),
                    "passing_tds_per_game": p.get("passing_tds_per_game"),
                    "passing_attempts_per_game": p.get("passing_attempts_per_game"),
                }
                for p in qbs[:3]
            ],
            "projected_qb1": qb1.get("name") if qb1 else None,
            "projected_qb1_available_in_feed": qb1_ready,
            "reported_injuries": injury_rows,
            "official_game_day_inactives_confirmed": False,
            "official_starting_quarterback_confirmed": False,
        }

    team_simulation_ready = all(
        teams[team]["projected_qb1_available_in_feed"]
        for team in (home, away)
    )
    blockers = [
        f"{team}: no active QB1 in the latest depth chart/injury feed"
        for team in (home, away)
        if not teams[team]["projected_qb1_available_in_feed"]
    ]

    return {
        "season": pool.get("season"),
        "source": pool.get("source"),
        "retrieved_at_utc": retrieved,
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "max_age_hours": max_age_hours,
        "home": home,
        "away": away,
        "teams": teams,
        "team_simulation_context": "Current player injury/depth context loaded; this team-score engine does not yet quantify player-specific injury impact.",
        "team_simulation_ready": team_simulation_ready,
        "team_simulation_blockers": blockers,
        "betting_ready": False,\n        "betting_readiness_blockers": [\n            "Player-specific injury impact is not modeled in team scoring.",\n            "Final game-day inactives and official starting lineups are not confirmed.",\n            "Weather is not integrated.",\n            "Sportsbook prices must be entered manually.",\n            "Win-probability thresholds have not been historically calibrated.",\n        ],\n        "player_props_ready": False,
        "blocking_note": "Do not issue player props until official game-day active/inactive and starting-lineup confirmations are supplied.",
        "weather_status": "NOT_INTEGRATED",
        "sportsbook_status": "MANUAL_LINES_REQUIRED",
    }


def main():
    parser = argparse.ArgumentParser(description="Validate fresh NFL pregame context.")
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--input", default="player_pool.json")
    parser.add_argument("--output", default="pregame-context.json")
    parser.add_argument("--max-age-hours", type=int, default=36)
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as handle:
        pool = json.load(handle)
    report = build_pregame_report(pool, args.home, args.away, args.max_age_hours)
    Path(args.output).write_text(json.dumps(report, indent=2) + chr(10), encoding="utf-8")
    print("PREGAME CONTEXT CHECK PASSED")
    print(f"Matchup: {report['away']} at {report['home']}")
    print(f"Season: {report['season']}; retrieved: {report['retrieved_at_utc']}")
    for team, details in report["teams"].items():
        print(f"{team}: {details['player_records']} player records; {len(details['reported_injuries'])} reported injury designations")
        print(f"  QB depth chart: {details['quarterback_depth_chart']}")
    print(f"Team simulation ready: {report['team_simulation_ready']}")
    for blocker in report["team_simulation_blockers"]:
        print(f"BLOCKER: {blocker}")
    print("Final inactives/starters: NOT CONFIRMED")
    print("Player props: BLOCKED")
    print("Weather: NOT INTEGRATED")
    print("Sportsbook lines: MANUAL INPUT REQUIRED")


if __name__ == "__main__":
    main()
