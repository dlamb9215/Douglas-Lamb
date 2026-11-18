"""Multi-source NBA matchup data preflight.

Combines the repository's existing adapters into one provenance/readiness report.
This module never invents starters, minutes, injuries, or sportsbook prices.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from nba.data_quality import validate_payload
from nba.injuries import fetch_official_injuries
from nba.schedule import build_context
from nba.player_props import validate_game_availability, validate_lineup_roster_membership, fetch_roster
from nba.odds import matchup_odds
from nba.espn_odds import fetch_espn_bet_odds


TEAM_CODE_ALIASES = {"GSW": "GS", "NOP": "NO", "NYK": "NY", "SAS": "SA", "UTA": "UTAH", "WAS": "WSH"}

TEAM_NAMES = {
    "ATL": "Atlanta Hawks", "BKN": "Brooklyn Nets", "BOS": "Boston Celtics",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GS": "Golden State Warriors", "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets", "IND": "Indiana Pacers", "LAC": "LA Clippers",
    "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies", "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves", "NO": "New Orleans Pelicans",
    "NOP": "New Orleans Pelicans", "NY": "New York Knicks", "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder", "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns", "POR": "Portland Trail Blazers", "SA": "San Antonio Spurs",
    "SAS": "San Antonio Spurs", "SAC": "Sacramento Kings", "TOR": "Toronto Raptors",
    "UTAH": "Utah Jazz", "UTA": "Utah Jazz", "WSH": "Washington Wizards",
    "WAS": "Washington Wizards",
}



def _person_key(value: str) -> str:
    import re
    tokens = re.findall(r"[a-z0-9]+", str(value).casefold())
    while tokens and tokens[-1] in {"jr", "sr", "ii", "iii", "iv"}:
        tokens.pop()
    return " ".join(tokens)


def validate_injury_roster_consistency(player_statuses: list[dict[str, Any]],
                                       team_codes: tuple[str, str]) -> dict[str, Any]:
    """Cross-check every parsed injury row against that team's live ESPN roster.

    A mismatch is a hard data-quality failure: the player status is not trusted
    for player-level modeling until the source/team association is corrected.
    """
    rosters: dict[str, set[str]] = {}
    for code in team_codes:
        roster = fetch_roster(code)
        rosters[code] = {_person_key(player.get("name", "")) for player in roster if player.get("name")}
    mismatches = []
    unknown_teams = []
    for row in player_statuses:
        code = str(row.get("team", "")).upper()
        name = str(row.get("player", "")).strip()
        if code not in rosters:
            unknown_teams.append({"team": code, "player": name})
            continue
        if _person_key(name) not in rosters[code]:
            mismatches.append({"team": code, "player": name})
    return {
        "status": "passed" if not mismatches and not unknown_teams else "failed",
        "checked_injury_rows": len(player_statuses),
        "mismatches": mismatches,
        "unknown_team_rows": unknown_teams,
        "roster_provider": "ESPN current team roster",
        "note": "Roster membership cross-check; does not establish game availability or starting status.",
    }


def fetch_sportradar_injuries(api_key: str) -> dict[str, Any]:
    """Fetch the licensed Sportradar injury feed as an independent cross-check.

    The NBA official report remains authoritative for official team submissions.
    Sportradar status is retained as corroborating provider data only.
    """
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("SPORTRADAR_API_KEY is not configured")
    url = "https://api.sportradar.com/nba/trial/v8/en/league/injuries.json?" + urllib.parse.urlencode({"api_key": key})
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Sportradar NBA injury feed request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Sportradar NBA injury response was not a JSON object")
    teams = payload.get("teams", [])
    if not isinstance(teams, list):
        raise RuntimeError("Sportradar NBA injury response has no teams array")
    player_count = injury_count = 0
    for team in teams:
        if not isinstance(team, dict):
            continue
        players = team.get("players", [])
        if not isinstance(players, list):
            continue
        player_count += len(players)
        for player in players:
            if isinstance(player, dict):
                injuries = player.get("injuries", [])
                if isinstance(injuries, list):
                    injury_count += len(injuries)
    return {
        "status": "available", "provider": "Sportradar NBA API v8",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "team_count": len(teams), "player_count": player_count,
        "injury_record_count": injury_count,
        "note": "Independent cross-check only; does not replace the NBA official injury report or confirm starters/minutes.",
    }

def build_report(home: str, away: str, game_date: date, team_stats_path: str = "nba/team_stats.json",
                 lineup_path: str = "", season: int = 2027) -> dict[str, Any]:
    home, away = home.upper(), away.upper()
    home_code, away_code = TEAM_CODE_ALIASES.get(home, home), TEAM_CODE_ALIASES.get(away, away)
    if home_code == away_code or home not in TEAM_NAMES or away not in TEAM_NAMES:
        raise ValueError("Provide two different recognized NBA team abbreviations")
    report: dict[str, Any] = {
        "game": {"date": game_date.isoformat(), "home": home, "away": away},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {}, "readiness": {}, "warnings": [],
    }

    try:
        payload = json.loads(Path(team_stats_path).read_text(encoding="utf-8"))
        quality = validate_payload(payload, max_age_hours=72)
        report["sources"]["team_stats"] = {
            "status": "available", "provider": payload.get("source"),
            "updated_at": payload.get("updated_at"), "quality": quality,
        }
        report["readiness"]["team_stats"] = True
        report["warnings"].extend(quality.get("warnings", []))
    except Exception as exc:
        report["sources"]["team_stats"] = {"status": "unavailable", "error": str(exc)}
        report["readiness"]["team_stats"] = False

    try:
        context = build_context(home, away, game_date, lookback_days=10)
        report["sources"]["schedule_rest"] = {
            "status": "available", "provider": context.get("source"),
            "retrieved_at": context.get("retrieved_at"),
            "event": context.get("event"),
            "home_rest_days": context.get("home_rest_days"),
            "away_rest_days": context.get("away_rest_days"),
            "warnings": context.get("warnings", []),
        }
        report["readiness"]["schedule"] = True
        report["warnings"].extend(context.get("warnings", []))
    except Exception as exc:
        report["sources"]["schedule_rest"] = {"status": "unavailable", "error": str(exc)}
        report["readiness"]["schedule"] = False
        context = {}

    try:
        injuries = fetch_official_injuries(game_date, home, away, season)
        official = injuries.get("source") == "NBA official injury report"
        report["sources"]["injuries"] = {
            "status": "available" if injuries.get("player_statuses") or injuries.get("team_submission") else "incomplete",
            "provider": injuries.get("source"), "retrieved_at": injuries.get("retrieved_at"),
            "report_url": injuries.get("report_url"),
            "team_submission": injuries.get("team_submission", {}),
            "player_statuses": injuries.get("player_statuses", []),
            "official": official, "warnings": injuries.get("warnings", []),
        }
        submissions_complete = all(
            injuries.get("team_submission", {}).get(code) == "SUBMITTED"
            for code in (home_code, away_code)
        )
        roster_check = {"status": "not_run", "checked_injury_rows": 0, "mismatches": [],
                        "note": "No parsed injury rows required roster cross-check."}
        if official and injuries.get("player_statuses"):
            try:
                roster_check = validate_injury_roster_consistency(
                    injuries.get("player_statuses", []), (home_code, away_code)
                )
            except Exception as roster_error:
                roster_check = {"status": "unavailable", "error": str(roster_error),
                                "checked_injury_rows": 0, "mismatches": []}
        report["sources"]["injury_roster_validation"] = roster_check
        report["readiness"]["injury_roster_consistent"] = roster_check.get("status") in {"passed", "not_run"}
        report["readiness"]["official_injuries"] = official and submissions_complete and report["readiness"]["injury_roster_consistent"]
        report["warnings"].extend(injuries.get("warnings", []))
        if roster_check.get("status") == "failed":
            report["warnings"].append(
                "Injury-report player/team assignments failed current-roster validation; do not use those injury rows for player props or bet approval."
            )
        elif roster_check.get("status") == "unavailable":
            report["warnings"].append(
                "Could not validate injury-report player/team assignments against current rosters; player-level availability remains blocked."
            )
        if not official:
            report["warnings"].append("Third-party injury fallback is context only; official injury confirmation is not satisfied.")
    except Exception as exc:
        report["sources"]["injuries"] = {"status": "unavailable", "error": str(exc)}
        report["readiness"]["official_injuries"] = False
        report["warnings"].append("Player availability is unknown; do not treat any player as confirmed active.")

    lineup = None
    if lineup_path:
        try:
            lineup = json.loads(Path(lineup_path).read_text(encoding="utf-8"))
            valid, reason = validate_game_availability(lineup, [home_code, away_code])
            roster_checks = {}
            if valid:
                for code in (home_code, away_code):
                    roster = fetch_roster(code)
                    roster_checks[code] = validate_lineup_roster_membership(
                        lineup.get("teams", {}).get(code, {}), roster
                    )
                invalid_rosters = {code: detail[1] for code, detail in roster_checks.items() if not detail[0]}
                if invalid_rosters:
                    valid = False
                    reason = "lineup starters do not match current team rosters: " + "; ".join(
                        f"{code}: {detail}" for code, detail in invalid_rosters.items()
                    )
            report["sources"]["lineups"] = {
                "status": "confirmed" if valid else "incomplete",
                "provider": lineup.get("source"), "confirmed_at": lineup.get("confirmed_at"),
                "validation": reason,
                "roster_validation": {code: {"passed": detail[0], "detail": detail[1]}
                                      for code, detail in roster_checks.items()},
            }
            report["readiness"]["confirmed_lineups"] = valid
        except Exception as exc:
            report["sources"]["lineups"] = {"status": "invalid", "error": str(exc)}
            report["readiness"]["confirmed_lineups"] = False
    else:
        report["sources"]["lineups"] = {
            "status": "not_supplied",
            "note": "No game-specific confirmed starter/minutes payload supplied. Depth charts and projected lineups are not confirmations.",
        }
        report["readiness"]["confirmed_lineups"] = False
    if not report["readiness"]["confirmed_lineups"]:
        report["warnings"].append("Player props and team-market availability remain blocked until both teams have five confirmed available starters with game-specific minutes.")

    odds_key = os.getenv("ODDS_API_KEY", "").strip()
    if odds_key:
        try:
            odds = matchup_odds(TEAM_NAMES[home], TEAM_NAMES[away], odds_key)
            report["sources"]["sportsbook_odds"] = odds
            report["readiness"]["two_sided_odds"] = bool(
                odds.get("home_ml_odds") is not None and odds.get("away_ml_odds") is not None
                and odds.get("moneyline_last_updated")
            )
        except Exception as exc:
            report["sources"]["sportsbook_odds"] = {"status": "unavailable", "provider": "The Odds API v4", "error": str(exc)}
            report["readiness"]["two_sided_odds"] = False
    else:
        report["sources"]["sportsbook_odds"] = {
            "status": "not_configured", "provider": "The Odds API v4",
            "note": "Add ODDS_API_KEY in GitHub Actions secrets to retrieve multi-book prices.",
        }
        report["readiness"]["two_sided_odds"] = False

    sportradar_key = os.getenv("SPORTRADAR_API_KEY", "").strip()
    if sportradar_key:
        try:
            report["sources"]["sportradar_injuries"] = fetch_sportradar_injuries(sportradar_key)
        except Exception as exc:
            report["sources"]["sportradar_injuries"] = {
                "status": "unavailable", "provider": "Sportradar NBA API v8", "error": str(exc)
            }
            report["warnings"].append("Sportradar cross-check failed; NBA official injury report remains the primary source.")
    else:
        report["sources"]["sportradar_injuries"] = {
            "status": "not_configured", "provider": "Sportradar NBA API v8",
            "note": "Optional licensed provider cross-check; add SPORTRADAR_API_KEY to GitHub Actions secrets."
        }

    event = (context.get("event") or {})
    event_id = event.get("event_id")
    if event_id:
        try:
            espn_odds = fetch_espn_bet_odds(event_id)
            report["sources"]["espn_bet"] = espn_odds
            # ESPN BET is a supported primary quote source in this workflow.
            # Only accept both sides with a bookmaker quote timestamp; retrieval
            # time alone is not evidence that the underlying price is current.
            espn_ml_ready = (
                espn_odds.get("home_ml_odds") is not None
                and espn_odds.get("away_ml_odds") is not None
                and bool(espn_odds.get("last_updated"))
            )
            if not report["readiness"].get("two_sided_odds", False) and espn_ml_ready:
                report["readiness"]["two_sided_odds"] = True
                report["sources"]["sportsbook_odds"] = {
                    "status": "available", "provider": espn_odds.get("source", "ESPN BET"),
                    "home_ml_odds": espn_odds["home_ml_odds"],
                    "away_ml_odds": espn_odds["away_ml_odds"],
                    "moneyline_last_updated": espn_odds.get("last_updated"),
                    "event_id": event_id,
                    "retrieved_at": espn_odds.get("retrieved_at"),
                }
            report["readiness"]["espn_bet_moneyline"] = espn_ml_ready
            report["readiness"]["espn_bet_spread"] = (
                espn_odds.get("home_spread") is not None
                and espn_odds.get("home_spread_odds") is not None
                and espn_odds.get("away_spread_odds") is not None
                and bool(espn_odds.get("last_updated"))
            )
            report["readiness"]["espn_bet_total"] = (
                espn_odds.get("total") is not None
                and espn_odds.get("over_odds") is not None
                and espn_odds.get("under_odds") is not None
                and bool(espn_odds.get("last_updated"))
            )
        except Exception as exc:
            report["sources"]["espn_bet"] = {"status": "unavailable", "provider": "ESPN BET", "error": str(exc)}
            report["readiness"]["espn_bet_moneyline"] = False
            report["readiness"]["espn_bet_spread"] = False
            report["readiness"]["espn_bet_total"] = False
    else:
        report["sources"]["espn_bet"] = {"status": "not_checked", "note": "No verified ESPN event ID from schedule adapter."}
        report["readiness"]["espn_bet_moneyline"] = False
        report["readiness"]["espn_bet_spread"] = False
        report["readiness"]["espn_bet_total"] = False

    report["readiness"]["bet_eligible_data"] = all(
        report["readiness"].get(key, False)
        for key in ("team_stats", "schedule", "official_injuries", "injury_roster_consistent", "confirmed_lineups", "two_sided_odds")
    )
    report["warnings"].append("This is a data-readiness report, not proof of model accuracy or profitability. Calibration remains a separate required gate.")
    report["overall_status"] = "ready_for_review" if report["readiness"]["bet_eligible_data"] else "simulation_only_missing_inputs"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a multi-source NBA matchup data-readiness report")
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--season", type=int, default=2027)
    parser.add_argument("--team-stats", default="nba/team_stats.json")
    parser.add_argument("--lineups", default="")
    parser.add_argument("--output", default="nba-data-readiness.json")
    args = parser.parse_args()
    report = build_report(args.home, args.away, date.fromisoformat(args.date),
                          args.team_stats, args.lineups, args.season)
    rendered = json.dumps(report, indent=2)
    Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
