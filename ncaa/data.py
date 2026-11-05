"""CSV profile loading and validation for FBS/FCS team inputs."""
from __future__ import annotations
import csv
from pathlib import Path
from .engine import TeamProfile

NUMERIC_FIELDS = {
    "points_for": float, "points_against": float,
    "yards_per_play": float, "yards_per_play_allowed": float,
    "plays_per_game": float, "turnovers_per_game": float,
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
        return found
    return TeamProfile(name=name)
