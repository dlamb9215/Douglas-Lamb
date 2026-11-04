"""Refresh NBA team metrics from DunkAPI (ESPN-derived team aggregates).

Requires DUNKAPI_API_KEY in the environment. The key is never stored in this file.
Fetches current and prior season team data, validates all 30 teams, then atomically
replaces nba/team_stats.json. DunkAPI currently exposes pace, ratings and selected
four factors; unavailable opponent factors use documented league-average priors.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_URL = "https://mcp.dunkapi.com/v1/get_team_stats"
LEAGUE = {
    "efg_pct": 0.540, "tov_pct": 0.135, "orb_pct": 0.265, "ft_rate": 0.250,
    "opp_efg_pct": 0.540, "opp_tov_pct": 0.135,
    "opp_orb_pct": 0.265, "opp_ft_rate": 0.250,
}

def fetch(season: int, api_key: str) -> dict:
    body = json.dumps({"season": season, "season_type": "regular", "league": "nba"}).encode()
    request = urllib.request.Request(
        API_URL, data=body,
        headers={"Content-Type": "application/json", "x-api-key": api_key,
                 "User-Agent": "DougsEliteNBASimulator/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"DunkAPI request failed for season {season}: {exc}") from exc
    data = payload.get("data", payload)
    rows = data.get("teams") if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) != 30:
        raise RuntimeError(f"Expected 30 NBA teams for {season}; received {len(rows) if isinstance(rows, list) else 0}")
    result = {}
    for item in rows:
        code = str(item.get("abbrev", "")).upper()
        if not code or code in result:
            raise RuntimeError(f"Missing or duplicate team abbreviation in season {season}")
        result[code] = item
    return result

def number(row, key, fallback=None):
    value = row.get(key)
    return float(value) if value is not None else fallback

def make_team(code, current, prior):
    gp = int(current.get("games") or 0)
    p_gp = int(prior.get("games") or 0)
    if gp < 0 or p_gp < 0:
        raise RuntimeError(f"Invalid games played for {code}")
    out = {"name": current.get("display_name", code), "games_played": gp}
    mappings = {
        "pace": "pace", "off_rating": "off_rating", "def_rating": "def_rating",
        "efg_pct": "efg_pct", "tov_pct": "tov_pct", "orb_pct": "oreb_pct",
        "ft_rate": "ft_rate",
    }
    for target, source in mappings.items():
        now = number(current, source)
        old = number(prior, source)
        if now is None:
            raise RuntimeError(f"{code} missing required current metric: {source}")
        if old is not None and gp + 8 > 0:
            out[target] = (now * gp + old * 8) / (gp + 8)
        else:
            out[target] = now
    # DunkAPI's published team-stat schema does not currently expose all opponent
    # four factors or recent/venue splits. Use neutral league priors, not invented values.
    out["opp_efg_pct"] = number(current, "opp_efg_pct", LEAGUE["opp_efg_pct"])
    out["opp_tov_pct"] = LEAGUE["opp_tov_pct"]
    out["opp_orb_pct"] = LEAGUE["opp_orb_pct"]
    out["opp_ft_rate"] = LEAGUE["opp_ft_rate"]
    out["three_pa_rate"] = number(current, "three_rate")
    out["fg3_pct"] = None
    out["opp_three_pa_rate"] = None
    out["opp_fg3_pct"] = None
    out["recent_pace"] = None
    out["recent_off_rating"] = None
    out["recent_def_rating"] = None
    out["home_off_rating"] = out["off_rating"]
    out["home_def_rating"] = out["def_rating"]
    out["road_off_rating"] = out["off_rating"]
    out["road_def_rating"] = out["def_rating"]
    out["score_sd"] = 11.5
    out["prior_season_weight_games"] = 8
    out["data_limitations"] = "Provider does not expose opponent TOV/ORB/FT factors, recent form, venue splits, 3P accuracy, or team score SD in get_team_stats; neutral priors used where unavailable."
    return out

def main():
    api_key = os.getenv("DUNKAPI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DUNKAPI_API_KEY secret is missing. Add it in GitHub repository Settings > Secrets and variables > Actions.")
    season = int(os.getenv("NBA_SEASON", "2027"))
    prior_season = int(os.getenv("NBA_PRIOR_SEASON", "2026"))
    path = Path(os.getenv("NBA_DATA_PATH", "nba/team_stats.json"))
    current = fetch(season, api_key)
    prior = fetch(prior_season, api_key)
    if set(current) != set(prior):
        raise RuntimeError("Current and prior season team sets differ; previous data preserved.")
    teams = {code: make_team(code, current[code], prior[code]) for code in sorted(current)}
    for code, row in teams.items():
        required = ("pace", "off_rating", "def_rating", "efg_pct", "tov_pct", "orb_pct",
                    "ft_rate", "opp_efg_pct", "opp_tov_pct", "opp_orb_pct", "opp_ft_rate")
        if any(row.get(k) is None for k in required):
            raise RuntimeError(f"{code} has incomplete required metrics")
    payload = {
        "league": "NBA", "season": season, "prior_season": prior_season,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "DunkAPI get_team_stats (ESPN-derived)",
        "methods": {
            "prior_season_weight_games": 8,
            "provider": "DunkAPI",
            "missing_opponent_factor_policy": "league-average neutral priors",
            "recent_and_venue_splits": "not supplied by provider; disabled",
        },
        "teams": teams,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    parsed = json.loads(tmp.read_text(encoding="utf-8"))
    if len(parsed.get("teams", {})) != 30:
        raise RuntimeError("Output validation failed; previous data preserved.")
    tmp.replace(path)
    print(f"Updated {path}: {len(teams)} teams, season {season}, prior {prior_season}")
    print("Provider limitations: missing opponent four factors/recent/venue splits use neutral baselines.")

if __name__ == "__main__":
    main()
