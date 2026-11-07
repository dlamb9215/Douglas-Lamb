"""Fetch and normalize FBS team-season data from CollegeFootballData.

Requires CFBD_API_KEY in the environment. Never commits credentials or silently
replaces a valid cache after a failed/incomplete API response.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://api.collegefootballdata.com"
PROFILE_FIELDS = [
    "team", "classification", "points_for", "points_against", "yards_per_play",
    "yards_per_play_allowed", "plays_per_game", "points_per_drive",
    "pass_yards_per_game", "rush_yards_per_game", "pass_attempts_per_game", "completions_per_game", "completion_pct", "yards_per_pass_attempt",
    "pass_tds_per_game", "interceptions_per_game", "pass_first_downs_per_game", "rush_attempts_per_game", "yards_per_carry", "rush_tds_per_game", "rush_first_downs_per_game",
    "pass_yards_allowed_per_game", "opponent_pass_attempts_per_game", "opponent_completions_per_game", "opponent_yards_per_completion", "opponent_yards_per_pass_attempt_allowed", "rush_yards_allowed_per_game", "opponent_rush_attempts_per_game", "opponent_yards_per_carry_allowed",
    "turnovers_per_game", "takeaways_per_game", "turnover_margin_per_game", "explosive_play_rate",
    "success_rate", "strength_rating", "games_sampled", "source", "as_of",
]


def api_get(path: str, params: dict, api_key: str) -> list | dict:
    query = urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{BASE_URL}{path}?{query}"
    request = Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "DougsEliteNCAASimulator/1.0",
    })
    try:
        with urlopen(request, timeout=40) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("CFBD returned 401: check the CFBD_API_KEY GitHub secret.") from exc
        if exc.code == 403:
            raise RuntimeError("CFBD returned 403: the API key may not include this endpoint/tier.") from exc
        if exc.code == 429:
            raise RuntimeError("CFBD rate limit reached. Retry after the provider's reset window.") from exc
        raise RuntimeError(f"CFBD API error {exc.code} for {path}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not reach CFBD endpoint {path}: {exc}") from exc
    if not isinstance(payload, (list, dict)):
        raise RuntimeError(f"Unexpected response type from {path}")
    return payload


def number(value):
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def norm(text: str) -> str:
    return "".join(ch.lower() for ch in str(text) if ch.isalnum())


def extract_stats(team_row: dict) -> dict:
    """Normalize CFBD game-team stat arrays without assuming stat order."""
    result = {}
    for item in team_row.get("stats", []) or []:
        key = norm(item.get("category", ""))
        value = number(item.get("stat"))
        if key and value is not None:
            result[key] = value
    return result


def pick(stats: dict, *keys):
    for key in keys:
        value = stats.get(norm(key))
        if value is not None:
            return value
    return None


def parse_advanced(rows: list) -> dict:
    result = {}
    for row in rows:
        team = row.get("team") or row.get("school")
        if not team:
            continue
        offense = row.get("offense") or {}
        defense = row.get("defense") or {}
        result[team.casefold()] = {
            "offense": offense if isinstance(offense, dict) else {},
            "defense": defense if isinstance(defense, dict) else {},
        }
    return result


def resolve_play_counts(raw: dict, offense_advanced: dict,
                        defense_advanced: dict, games_n: int,
                        team: str) -> tuple[float, float]:
    """Use CFBD advanced play totals; reject implausible fallback denominators."""
    if games_n <= 0:
        raise RuntimeError(f"{team}: cannot validate play counts without completed games.")
    offense_plays = number(offense_advanced.get("plays"))
    defense_plays = number(defense_advanced.get("plays"))
    if offense_plays is None:
        offense_plays = raw.get("plays")
    if defense_plays is None:
        defense_plays = raw.get("plays_allowed")
    for label, total in (("offense", offense_plays), ("defense", defense_plays)):
        per_game = total / games_n if total is not None else 0.0
        if not 40.0 <= per_game <= 100.0:
            raise RuntimeError(
                f"{team}: invalid {label} plays/game ({per_game:.1f}); "
                "advanced CFBD play totals are required when box-score play counts are incomplete."
            )
    return offense_plays, defense_plays


def build_team_aliases(team_rows: list[dict]) -> dict[str, str]:
    candidates: dict[str, set[str]] = {}
    for row in team_rows:
        canonical = str(row.get("school") or row.get("name") or "").strip()
        if not canonical:
            continue
        values = [canonical, row.get("abbreviation")]
        mascot = str(row.get("mascot") or "").strip()
        if mascot:
            values.append(f"{canonical} {mascot}")
        alternate = row.get("alternateNames") or []
        if isinstance(alternate, list):
            values.extend(alternate)
        for value in values:
            alias = str(value or "").strip().casefold()
            if alias:
                candidates.setdefault(alias, set()).add(canonical)
    return {alias: next(iter(names)) for alias, names in candidates.items() if len(names) == 1}


def build_dataset(year: int, season_type: str, api_key: str,
                  classification: str = "fbs") -> tuple[list, dict, dict]:
    classification = classification.casefold()
    if classification not in {"fbs", "fcs"}:
        raise ValueError("classification must be fbs or fcs")
    directory_rows = api_get(
        "/teams/fbs" if classification == "fbs" else "/teams",
        {"year": year} if classification == "fbs" else {},
        api_key,
    )
    if not isinstance(directory_rows, list) or not directory_rows:
        raise RuntimeError(f"CFBD did not return the {classification.upper()} team directory.")
    selected_rows = [
        row for row in directory_rows
        if classification == "fbs" or str(row.get("classification", "")).casefold() == "fcs"
    ]
    team_names = {
        str(row.get("school") or row.get("name") or "").casefold()
        for row in selected_rows
        if row.get("school") or row.get("name")
    }
    if len(team_names) < 50:
        raise RuntimeError(
            f"CFBD returned only {len(team_names)} {classification.upper()} teams; "
            "refusing to publish an incomplete directory."
        )
    games = api_get("/games", {
        "year": year, "seasonType": season_type, "classification": classification
    }, api_key)
    # CFBD requires one of week, team, or conference when querying
    # game-level team box scores by season. Fetch each week separately.
    team_games = []
    max_week = 22 if classification == "fcs" else 18
    for week in range(1, max_week):
        week_rows = api_get("/games/teams", {
            "year": year, "week": week, "seasonType": season_type,
            "classification": classification
        }, api_key)
        if isinstance(week_rows, list):
            team_games.extend(week_rows)
    provider_warnings = []
    try:
        advanced_rows = api_get("/stats/season/advanced", {
            "year": year, "excludeGarbageTime": "true", "classification": classification
        }, api_key)
    except RuntimeError as exc:
        if "403" not in str(exc) and "404" not in str(exc):
            raise
        advanced_rows = []
        provider_warnings.append(f"Advanced team metrics unavailable: {exc}")
    try:
        elo_rows = api_get("/ratings/elo", {"year": year}, api_key)
    except RuntimeError as exc:
        if "403" not in str(exc) and "404" not in str(exc):
            raise
        elo_rows = []
        provider_warnings.append(f"Elo ratings unavailable: {exc}")

    if not isinstance(games, list) or not isinstance(team_games, list):
        raise RuntimeError("CFBD games endpoints did not return arrays.")
    completed = [
        g for g in games
        if g.get("homePoints") is not None and g.get("awayPoints") is not None
        and g.get("homeTeam") and g.get("awayTeam")
        and str(g.get("homeTeam")).casefold() in team_names
        and str(g.get("awayTeam")).casefold() in team_names
    ]
    if not completed:
        raise RuntimeError(
            f"CFBD returned no completed {year} {season_type} FBS games; "
            "refusing to overwrite team data with an empty dataset."
        )

    # Keep only completed games between teams in the selected classification.
    completed_ids = {g.get("id") for g in completed}
    team_games = [
        game for game in team_games
        if game.get("id") in completed_ids
    ]
    team_totals = {}
    for game in team_games:
        game_id = game.get("id")
        if game_id is None:
            continue
        for team in game.get("teams", []) or []:
            name = team.get("team")
            if not name or str(name).casefold() not in team_names:
                continue
            row = team_totals.setdefault(name, {
                "games": 0, "points_for": 0.0, "points_against": 0.0,
                "yards_for": 0.0, "yards_allowed": 0.0, "plays": 0.0, "plays_allowed": 0.0,
                "turnovers": 0.0, "takeaways": 0.0, "pass_yards": 0.0,
                "rush_yards": 0.0, "pass_attempts": 0.0, "completions": 0.0,
                "rush_attempts": 0.0, "first_downs": 0.0, "sacks": 0.0,
                "pass_tds": 0.0, "interceptions_thrown": 0.0, "pass_first_downs": 0.0, "rush_tds": 0.0, "rush_first_downs": 0.0,
                "pass_yards_allowed": 0.0, "opp_pass_attempts": 0.0, "opp_completions": 0.0, "rush_yards_allowed": 0.0, "opp_rush_attempts": 0.0,
            })
            stats = extract_stats(team)
            row["games"] += 1
            row["points_for"] += number(team.get("points")) or 0.0
            row["pass_yards"] += pick(stats, "netPassingYards", "passingYards", "passYards") or 0.0
            row["rush_yards"] += pick(stats, "rushingYards", "rushYards") or 0.0
            row["pass_attempts"] += pick(stats, "passAttempts", "passingAttempts") or 0.0
            row["completions"] += pick(stats, "passCompletions", "completions") or 0.0
            row["pass_tds"] += pick(stats, "passingTDs", "passTDs") or 0.0
            row["interceptions_thrown"] += pick(stats, "interceptions", "interceptionsThrown") or 0.0
            row["pass_first_downs"] += pick(stats, "passingFirstDowns", "passFirstDowns") or 0.0
            row["rush_attempts"] += pick(stats, "rushAttempts", "rushingAttempts") or 0.0
            row["rush_tds"] += pick(stats, "rushingTDs", "rushTDs") or 0.0
            row["rush_first_downs"] += pick(stats, "rushingFirstDowns", "rushFirstDowns") or 0.0
            row["first_downs"] += pick(stats, " firstDowns", "firstDowns") or 0.0
            row["turnovers"] += pick(stats, "turnovers", "totalTurnovers") or 0.0
            row["sacks"] += pick(stats, "sacks", "sacksAllowed") or 0.0
            total_yards = pick(stats, "totalYards", "yards")
            if total_yards is None:
                total_yards = (pick(stats, "netPassingYards", "passingYards", "passYards") or 0.0) + (pick(stats, "rushingYards", "rushYards") or 0.0)
            row["yards_for"] += total_yards
            total_plays = pick(stats, "totalPlays", "plays")
            if total_plays is None:
                total_plays = (pick(stats, "passAttempts", "passingAttempts") or 0.0) + (pick(stats, "rushAttempts", "rushingAttempts") or 0.0) + (pick(stats, "sacks") or 0.0)
            row["plays"] += total_plays

    # Match completed game opponents to calculate points/yards allowed and takeaways.
    by_game = {}
    for item in team_games:
        by_game[item.get("id")] = item.get("teams", []) or []
    game_lookup = {g.get("id"): g for g in completed}
    for game_id, teams in by_game.items():
        if game_id not in game_lookup or len(teams) < 2:
            continue
        for own in teams:
            other = next((x for x in teams if x.get("team") != own.get("team")), None)
            if not other or own.get("team") not in team_totals:
                continue
            row = team_totals[own["team"]]
            row["points_against"] += number(other.get("points")) or 0.0
            other_stats = extract_stats(other)
            other_yards = pick(other_stats, "totalYards", "yards")
            if other_yards is None:
                other_yards = (pick(other_stats, "netPassingYards", "passingYards", "passYards") or 0.0) + (pick(other_stats, "rushingYards", "rushYards") or 0.0)
            row["yards_allowed"] += other_yards
            row["pass_yards_allowed"] += pick(other_stats, "netPassingYards", "passingYards", "passYards") or 0.0
            row["opp_pass_attempts"] += pick(other_stats, "passAttempts", "passingAttempts") or 0.0
            row["opp_completions"] += pick(other_stats, "passCompletions", "completions") or 0.0
            row["rush_yards_allowed"] += pick(other_stats, "rushingYards", "rushYards") or 0.0
            row["opp_rush_attempts"] += pick(other_stats, "rushAttempts", "rushingAttempts") or 0.0
            other_plays = pick(other_stats, "totalPlays", "plays")
            if other_plays is None:
                other_plays = (pick(other_stats, "passAttempts", "passingAttempts") or 0.0) + (pick(other_stats, "rushAttempts", "rushingAttempts") or 0.0) + (pick(other_stats, "sacks") or 0.0)
            row["plays_allowed"] += other_plays
            own_stats = extract_stats(own)
            own_takeaways = pick(own_stats, "interceptions", "defensiveInterceptions") or 0.0
            own_takeaways += pick(own_stats, "fumblesRecovered", "fumblesRecoveredByDefense") or 0.0
            row["takeaways"] += own_takeaways

    advanced = parse_advanced(advanced_rows if isinstance(advanced_rows, list) else [])
    elo = {}
    if isinstance(elo_rows, list):
        for row in elo_rows:
            name = row.get("team")
            rating = number(row.get("elo"))
            if name and rating is not None:
                elo[name.casefold()] = rating

    profiles, rankings = [], {}
    for team, raw in sorted(team_totals.items()):
        games_n = raw["games"]
        if games_n <= 0:
            continue
        adv = advanced.get(team.casefold(), {})
        off_adv, def_adv = adv.get("offense", {}), adv.get("defense", {})
        offense_plays, defense_plays = resolve_play_counts(
            raw, off_adv, def_adv, games_n, team
        )
        plays_pg = offense_plays / games_n
        yards_pg = raw["yards_for"] / games_n
        allowed_pg = raw["yards_allowed"] / games_n
        ypp = raw["yards_for"] / offense_plays
        ypp_allowed = raw["yards_allowed"] / defense_plays
        if not 2.0 <= ypp <= 9.5 or not 2.0 <= ypp_allowed <= 9.5:
            raise RuntimeError(
                f"{team}: implausible yards-per-play values "
                f"(offense {ypp:.2f}, defense {ypp_allowed:.2f}); refusing to publish."
            )
        success = number(off_adv.get("successRate"))
        # CFBD's advanced "explosiveness" is an efficiency index, not a
        # probability/rate. The simulator expects a 0..1 explosive-play rate,
        # so retain the documented conservative prior until a true play-count
        # numerator/denominator is calculated from play-by-play data.
        explosive = number(off_adv.get("explosivePlayRate"))
        elo_rating = elo.get(team.casefold(), 0.0)
        # Keep ratings on a comparable centered scale; Elo is informational, not a raw model rating.
        strength = (elo_rating - 1500.0) / 25.0 if elo_rating else 0.0
        profile = {
            "team": team,
            "classification": classification,
            "points_for": round(raw["points_for"] / games_n, 3),
            "points_against": round(raw["points_against"] / games_n, 3),
            "yards_per_play": round(ypp, 4),
            "yards_per_play_allowed": round(ypp_allowed, 4),
            "plays_per_game": round(plays_pg, 3),
            "points_per_drive": "",
            "pass_yards_per_game": round(raw["pass_yards"] / games_n, 2),
            "rush_yards_per_game": round(raw["rush_yards"] / games_n, 2),
            "pass_attempts_per_game": round(raw["pass_attempts"] / games_n, 2),
            "completions_per_game": round(raw["completions"] / games_n, 2),
            "completion_pct": round(raw["completions"] / raw["pass_attempts"], 4) if raw["pass_attempts"] else 0.0,
            "yards_per_pass_attempt": round(raw["pass_yards"] / raw["pass_attempts"], 3) if raw["pass_attempts"] else 0.0,
            "pass_tds_per_game": round(raw["pass_tds"] / games_n, 3),
            "interceptions_per_game": round(raw["interceptions_thrown"] / games_n, 3),
            "pass_first_downs_per_game": round(raw["pass_first_downs"] / games_n, 3),
            "rush_attempts_per_game": round(raw["rush_attempts"] / games_n, 2),
            "yards_per_carry": round(raw["rush_yards"] / raw["rush_attempts"], 3) if raw["rush_attempts"] else 0.0,
            "rush_tds_per_game": round(raw["rush_tds"] / games_n, 3),
            "rush_first_downs_per_game": round(raw["rush_first_downs"] / games_n, 3),
            "pass_yards_allowed_per_game": round(raw["pass_yards_allowed"] / games_n, 2),
            "opponent_pass_attempts_per_game": round(raw["opp_pass_attempts"] / games_n, 2),
            "opponent_completions_per_game": round(raw["opp_completions"] / games_n, 2),
            "opponent_yards_per_completion": round(raw["pass_yards_allowed"] / raw["opp_completions"], 3) if raw["opp_completions"] else 0.0,
            "opponent_yards_per_pass_attempt_allowed": round(raw["pass_yards_allowed"] / raw["opp_pass_attempts"], 3) if raw["opp_pass_attempts"] else 0.0,
            "rush_yards_allowed_per_game": round(raw["rush_yards_allowed"] / games_n, 2),
            "opponent_rush_attempts_per_game": round(raw["opp_rush_attempts"] / games_n, 2),
            "opponent_yards_per_carry_allowed": round(raw["rush_yards_allowed"] / raw["opp_rush_attempts"], 3) if raw["opp_rush_attempts"] else 0.0,
            "turnovers_per_game": round(raw["turnovers"] / games_n, 3),
            "takeaways_per_game": round(raw["takeaways"] / games_n, 3),
            "turnover_margin_per_game": round((raw["takeaways"] - raw["turnovers"]) / games_n, 3),
            "explosive_play_rate": round(explosive, 5) if explosive is not None else 0.12,
            "success_rate": round(success, 5) if success is not None else 0.42,
            "strength_rating": round(strength, 4),
            "games_sampled": games_n,
            "source": "CollegeFootballData API",
            "as_of": datetime.now(timezone.utc).date().isoformat(),
        }
        profiles.append(profile)
        rankings[team] = {
            "games": games_n,
            "points_for_per_game": profile["points_for"],
            "points_against_per_game": profile["points_against"],
            "passing_yards_per_game": round(raw["pass_yards"] / games_n, 2),
            "pass_yards_allowed_per_game": round(raw["pass_yards_allowed"] / games_n, 2),
            "rush_yards_allowed_per_game": round(raw["rush_yards_allowed"] / games_n, 2),
            "completion_pct": round(raw["completions"] / raw["pass_attempts"], 4) if raw["pass_attempts"] else None,
            "yards_per_pass_attempt": round(raw["pass_yards"] / raw["pass_attempts"], 3) if raw["pass_attempts"] else None,
            "yards_per_carry": round(raw["rush_yards"] / raw["rush_attempts"], 3) if raw["rush_attempts"] else None,
            "opponent_yards_per_completion": round(raw["pass_yards_allowed"] / raw["opp_completions"], 3) if raw["opp_completions"] else None,
            "opponent_yards_per_pass_attempt_allowed": round(raw["pass_yards_allowed"] / raw["opp_pass_attempts"], 3) if raw["opp_pass_attempts"] else None,
            "opponent_yards_per_carry_allowed": round(raw["rush_yards_allowed"] / raw["opp_rush_attempts"], 3) if raw["opp_rush_attempts"] else None,
            "rushing_yards_per_game": round(raw["rush_yards"] / games_n, 2),
            "passing_attempts_per_game": round(raw["pass_attempts"] / games_n, 2) if raw["pass_attempts"] > 0 else None,
            "completions_per_game": round(raw["completions"] / games_n, 2) if raw["completions"] > 0 else None,
            "rushing_attempts_per_game": round(raw["rush_attempts"] / games_n, 2),
            "first_downs_per_game": round(raw["first_downs"] / games_n, 2),
            "yards_per_play": round(ypp, 3),
            "yards_allowed_per_play": round(ypp_allowed, 3),
            "total_yards_per_game": round(yards_pg, 2),
            "total_yards_allowed_per_game": round(allowed_pg, 2),
            "turnovers_per_game": profile["turnovers_per_game"],
            "takeaways_per_game": profile["takeaways_per_game"],
            "success_rate": profile["success_rate"],
            "explosiveness": profile["explosive_play_rate"],
            "elo": elo_rating if elo_rating else None,
            "offense_advanced": off_adv,
            "defense_advanced": def_adv,
            "source": "CollegeFootballData API",
            "as_of": profile["as_of"],
        }

    # National ranks: lower numeric rank is better; rank defense yards allowed ascending.
    rank_specs = {
        "scoring_offense_rank": ("points_for_per_game", True),
        "scoring_defense_rank": ("points_against_per_game", False),
        "passing_offense_rank": ("passing_yards_per_game", True),
        "passing_attempts_rank": ("passing_attempts_per_game", True),
        "completion_pct_rank": ("completion_pct", True),
        "yards_per_pass_attempt_rank": ("yards_per_pass_attempt", True),
        "rushing_yards_per_carry_rank": ("yards_per_carry", True),
        "passing_defense_yards_rank": ("pass_yards_allowed_per_game", False),
        "rushing_defense_yards_rank": ("rush_yards_allowed_per_game", False),
        "passing_defense_rank": ("pass_yards_allowed_per_game", False),
        "rushing_defense_rank": ("rush_yards_allowed_per_game", False),
        "rushing_offense_rank": ("rushing_yards_per_game", True),
        "total_offense_rank": ("total_yards_per_game", True),
        "total_defense_rank": ("total_yards_allowed_per_game", False),
        "yards_per_play_rank": ("yards_per_play", True),
        "yards_allowed_per_play_rank": ("yards_allowed_per_play", False),
        "turnover_margin_rank": ("turnover_margin_per_game", True),
    }
    for metric, value in rankings.items():
        for rank_name, (field, descending) in rank_specs.items():
            ordered = sorted(
                rankings.items(),
                key=lambda pair: pair[1].get(field, 0.0),
                reverse=descending,
            )
            value[rank_name] = next(i for i, pair in enumerate(ordered, 1) if pair[0] == metric)

    metadata = {
        "provider": "CollegeFootballData",
        "year": year,
        "season_type": season_type,
        "classification": classification,
        "team_aliases": build_team_aliases(selected_rows),
        "classification_completed_games": len(completed),
        "fbs_completed_games": len(completed) if classification == "fbs" else 0,
        "teams_with_box_scores": len(profiles),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "note": "Ranks are among teams returned with usable game box scores; incomplete-season ranks change weekly.",
        "provider_warnings": provider_warnings,
    }
    return profiles, rankings, metadata


def write_outputs(profiles: list, rankings: dict, metadata: dict, output_dir: Path,
                  classification: str = "fbs") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if classification == "fbs" else "_fcs"
    profile_path = output_dir / f"team_profiles{suffix}.csv"
    temp_path = profile_path.with_suffix(".csv.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROFILE_FIELDS)
        writer.writeheader()
        writer.writerows(profiles)
    temp_path.replace(profile_path)
    (output_dir / f"team_rankings{suffix}.json").write_text(
        json.dumps({"metadata": metadata, "teams": rankings}, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh NCAA FBS/FCS team profiles from CFBD")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--season-type", choices=("regular", "postseason", "both"), default="regular")
    parser.add_argument("--classification", choices=("fbs", "fcs"), default="fbs")
    parser.add_argument("--output-dir", default="ncaa/data")
    args = parser.parse_args()
    key = os.environ.get("CFBD_API_KEY", "").strip()
    if not key:
        raise SystemExit("CFBD_API_KEY is missing. Add it as a GitHub Actions secret.")
    profiles, rankings, metadata = build_dataset(args.year, args.season_type, key, args.classification)
    if len(profiles) < 50:
        raise SystemExit(
            f"Only {len(profiles)} FBS profiles were produced; refusing to publish a partial national dataset."
        )
    write_outputs(profiles, rankings, metadata, Path(args.output_dir), args.classification)
    suffix = "" if args.classification == "fbs" else "_fcs"
    print(f"Refreshed {len(profiles)} {args.classification.upper()} team profiles from {metadata['classification_completed_games']} completed games.")
    print(f"Updated {args.output_dir}/team_profiles{suffix}.csv and team_rankings{suffix}.json")


if __name__ == "__main__":
    main()
