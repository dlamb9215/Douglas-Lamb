"""Validate NBA team-stat provenance, completeness, ranges and freshness.

This is a data-readiness gate, not a model-accuracy test. It intentionally warns
when the upstream provider lacks features rather than filling them with guesses.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_TEAMS = {
    "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GS",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NO", "NY",
    "OKC", "ORL", "PHI", "PHX", "POR", "SA", "SAC", "TOR", "UTAH", "WSH",
}
REQUIRED = (
    "pace", "off_rating", "def_rating", "efg_pct", "tov_pct", "orb_pct",
    "ft_rate", "opp_efg_pct", "opp_tov_pct", "opp_orb_pct", "opp_ft_rate",
)
PERCENT_FIELDS = {
    "efg_pct", "tov_pct", "orb_pct", "ft_rate", "opp_efg_pct",
    "opp_tov_pct", "opp_orb_pct", "opp_ft_rate",
}
OPTIONAL_FIELDS = (
    "recent_pace", "recent_off_rating", "recent_def_rating",
    "home_off_rating", "home_def_rating", "road_off_rating", "road_def_rating",
    "three_pa_rate", "fg3_pct", "opp_three_pa_rate", "opp_fg3_pct", "score_sd",
)

def _timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("updated_at must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("updated_at must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("updated_at must include a timezone")
    return parsed.astimezone(timezone.utc)

def validate_payload(payload: dict, max_age_hours: float = 72, now: datetime | None = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        raise ValueError("NBA data root must be a JSON object")
    if payload.get("league") != "NBA":
        errors.append("league metadata must be NBA")
    if not isinstance(payload.get("season"), int) or not isinstance(payload.get("prior_season"), int):
        errors.append("season and prior_season metadata must be integers")
    elif payload["prior_season"] >= payload["season"]:
        errors.append("prior_season must be earlier than season")

    try:
        updated = _timestamp(payload.get("updated_at"))
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("validation clock must include a timezone")
        age_hours = (current.astimezone(timezone.utc) - updated).total_seconds() / 3600
        if age_hours < -0.083333:
            errors.append(f"data timestamp is in the future by {-age_hours:.2f} hours")
        elif age_hours > max_age_hours:
            errors.append(f"data is stale: {age_hours:.1f} hours old (limit {max_age_hours:.1f})")
    except ValueError as exc:
        errors.append(str(exc))
        age_hours = None

    teams = payload.get("teams")
    if not isinstance(teams, dict):
        errors.append("teams must be an object")
        teams = {}
    actual = set(teams)
    missing_teams = sorted(EXPECTED_TEAMS - actual)
    extra_teams = sorted(actual - EXPECTED_TEAMS)
    if missing_teams:
        errors.append("missing team records: " + ", ".join(missing_teams))
    if extra_teams:
        errors.append("unexpected team codes: " + ", ".join(extra_teams))
    if len(teams) != 30:
        errors.append(f"expected exactly 30 team records; found {len(teams)}")

    low_sample = []
    feature_counts = {field: 0 for field in OPTIONAL_FIELDS}
    for code, row in teams.items():
        if not isinstance(row, dict):
            errors.append(f"{code} record must be an object")
            continue
        for field in REQUIRED:
            value = row.get(field)
            try:
                number = float(value)
            except (TypeError, ValueError):
                errors.append(f"{code}.{field} is missing or non-numeric")
                continue
            if field == "pace" and not 70 <= number <= 115:
                errors.append(f"{code}.pace outside 70-115")
            elif field in ("off_rating", "def_rating") and not 80 <= number <= 140:
                errors.append(f"{code}.{field} outside 80-140")
            elif field in PERCENT_FIELDS and not 0 <= number <= 1:
                errors.append(f"{code}.{field} must be stored as a decimal from 0 to 1")
        try:
            gp = int(row.get("games_played", -1))
            if gp < 0:
                errors.append(f"{code}.games_played must be non-negative")
            elif gp < 10:
                low_sample.append(code)
        except (TypeError, ValueError):
            errors.append(f"{code}.games_played must be an integer")
        for field in OPTIONAL_FIELDS:
            value = row.get(field)
            if value is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                errors.append(f"{code}.{field} must be numeric when supplied")
                continue
            if field in {"recent_pace"} and not 70 <= number <= 115:
                errors.append(f"{code}.{field} outside 70-115")
            elif field in {"recent_off_rating", "recent_def_rating", "home_off_rating",
                           "home_def_rating", "road_off_rating", "road_def_rating"} and not 80 <= number <= 140:
                errors.append(f"{code}.{field} outside 80-140")
            elif field in {"three_pa_rate", "fg3_pct", "opp_three_pa_rate", "opp_fg3_pct"} and not 0 <= number <= 1:
                errors.append(f"{code}.{field} must be stored as a decimal from 0 to 1")
            elif field == "score_sd" and not 7 <= number <= 18:
                errors.append(f"{code}.score_sd outside 7-18")
            # Venue fields equal to overall ratings are provider fallbacks, not splits.
            base = "off_rating" if field.endswith("off_rating") else "def_rating"
            if not (field.startswith(("home_", "road_")) and number == row.get(base)):
                feature_counts[field] += 1

    if low_sample:
        warnings.append(
            "Early-season sample: fewer than 10 current-season games for "
            + ", ".join(sorted(low_sample))
            + "; prior-season shrinkage remains important."
        )
    unavailable = [field for field, count in feature_counts.items() if count == 0]
    if unavailable:
        warnings.append("Unavailable optional team features: " + ", ".join(unavailable))
    if payload.get("source") != "DunkAPI get_team_stats (ESPN-derived)":
        warnings.append("Unrecognized or missing provider provenance; verify source before using.")
    methods = payload.get("methods", {})
    if methods.get("prior_season_weight_games") != 8:
        warnings.append("Prior-season shrinkage metadata is missing or differs from the documented 8-game weight.")

    report = {
        "ready": not errors,
        "team_count": len(teams),
        "season": payload.get("season"),
        "prior_season": payload.get("prior_season"),
        "updated_at": payload.get("updated_at"),
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "optional_feature_coverage": feature_counts,
        "errors": errors,
        "warnings": warnings,
    }
    if errors:
        raise ValueError(json.dumps(report, indent=2))
    return report

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate NBA simulator team data readiness")
    parser.add_argument("--data", default="nba/team_stats.json")
    parser.add_argument("--max-age-hours", type=float, default=72)
    args = parser.parse_args()
    if args.max_age_hours <= 0:
        parser.error("--max-age-hours must be positive")
    payload = json.loads(Path(args.data).read_text(encoding="utf-8"))
    report = validate_payload(payload, args.max_age_hours)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
