"""CSV profile loading and validation for FBS/FCS team inputs."""
from __future__ import annotations
import csv
from pathlib import Path
from ..engine import TeamProfile

NUMERIC_FIELDS = {
    "points_for": float, "points_against": float,
    "yards_per_play": float, "yards_per_play_allowed": float,
    "plays_per_game": float, "turnovers_per_game": float,
    "pass_yards_per_game": float, "rush_yards_per_game": float,
    "pass_attempts_per_game": float, "completions_per_game": float,
    "completion_pct": float, "yards_per_pass_attempt": float,
    "pass_tds_per_game": float, "interceptions_per_game": float,
    "pass_first_downs_per_game": float, "rush_attempts_per_game": float,
    "yards_per_carry": float, "rush_tds_per_game": float,
    "rush_first_downs_per_game": float, "pass_yards_allowed_per_game": float,
    "opponent_pass_attempts_per_game": float, "opponent_completions_per_game": float,
    "opponent_yards_per_completion": float, "rush_yards_allowed_per_game": float,
    "opponent_rush_attempts_per_game": float, "opponent_yards_per_carry_allowed": float,
    "takeaways_per_game": float, "explosive_play_rate": float,
    "success_rate": float, "strength_rating": float,
    "games_sampled": int,
}


def load_profiles(path: str | Path) -> dict[str, TeamProfile]:
    profiles: dict[str, TeamProfile] = {}
    path = Path(path)
    if not path.exists():
        return profiles
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("team") or row.get("name") or "").strip()
            if not name:
                continue
            values = {"name": name}
            for field, converter in NUMERIC_FIELDS.items():
                raw = row.get(field, "").strip()
                if raw:
                    values[field] = converter(raw)
            if row.get("points_per_drive", "").strip():
                values["points_per_drive"] = float(row["points_per_drive"])
            values["source"] = row.get("source", "user-supplied CSV").strip() or "user-supplied CSV"
            values["as_of"] = row.get("as_of", "").strip()
            profile = TeamProfile(**values)
            profile.validate()
            profiles[name.casefold()] = profile
    return profiles


def get_profile(name: str, profiles: dict[str, TeamProfile]) -> TeamProfile:
    found = profiles.get(name.casefold())
    if found:
        if found.source == "CollegeFootballData API":
            from datetime import date
            if not found.as_of:
                raise ValueError(
                    f"{name}: verified NCAA profile has no data date; refresh team statistics."
                )
            try:
                data_date = date.fromisoformat(found.as_of)
            except ValueError as exc:
                raise ValueError(
                    f"{name}: invalid NCAA profile date; refresh team statistics."
                ) from exc
            age_days = (date.today() - data_date).days
            if age_days < 0 or age_days > 2:
                raise ValueError(
                    f"{name}: NCAA profile is {age_days} days old; refresh team statistics before simulating."
                )
            if not 40.0 <= found.plays_per_game <= 100.0:
                raise ValueError(
                    f"{name}: invalid plays/game ({found.plays_per_game:.1f}); "
                    "refresh NCAA statistics before simulating."
                )
            if not 2.0 <= found.yards_per_play <= 9.5:
                raise ValueError(
                    f"{name}: invalid yards/play ({found.yards_per_play:.2f}); "
                    "refresh NCAA statistics before simulating."
                )
            if not 2.0 <= found.yards_per_play_allowed <= 9.5:
                raise ValueError(
                    f"{name}: invalid yards allowed/play ({found.yards_per_play_allowed:.2f}); "
                    "refresh NCAA statistics before simulating."
                )
        return found
    return TeamProfile(name=name)
