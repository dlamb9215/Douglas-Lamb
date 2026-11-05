"""Live NFL player data ingestion from nflverse CSV releases.

Player game logs, current roster, depth chart and injury report data are
downloaded at runtime. A depth-chart QB/RB/WR/TE order of 1 is treated as
listed first on the chart, NOT proof of a final game-day starting lineup.
Final inactives and official game-day starters must be checked separately.
"""
import csv
import io
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen


BASE = "https://github.com/nflverse/nflverse-data/releases/download"
POSITIONS = {"QB", "RB", "WR", "TE"}
INACTIVE_TERMS = {"out", "doubtful", "inactive", "ir", "injured reserve", "suspended"}


def _get(url, timeout=25):
    request = Request(url, headers={"User-Agent": "DougsEliteGameSimulator/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8-sig")


def _rows_from_text(text):
    return list(csv.DictReader(io.StringIO(text)))


def _first(row, *names):
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return None


def _float(row, *names):
    value = _first(row, *names)
    try:
        return float(value) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _norm(value):
    return str(value or "").strip().lower()


def _status_from_injury(row):
    status = _norm(_first(row, "report_status", "game_status", "status"))
    # Keep official designations distinct; doubtful is not the same as out.
    if any(term in status for term in ("out", "inactive", "injured reserve", "suspended", "ir")):
        return "out"
    if "doubtful" in status:
        return "doubtful"
    if "questionable" in status:
        return "questionable"
    return "active"


def _aggregate_stats(stat_rows, season, last_n_weeks):
    grouped = {}
    for row in stat_rows:
        try:
            row_season = int(_first(row, "season") or 0)
            week = int(_first(row, "week") or 0)
        except (TypeError, ValueError):
            continue
        if row_season != season:
            continue
        pid = _first(row, "player_id", "gsis_id", "gsis")
        name = _first(row, "player_display_name", "player_name", "full_name")
        team = _first(row, "recent_team", "team", "posteam")
        position = _first(row, "position")
        if not (pid or name) or position not in POSITIONS:
            continue
        key = str(pid or name)
        entry = grouped.setdefault(key, {
            "player_id": pid, "name": name, "team": team,
            "position": position, "weeks": set(), "games": 0,
            "passing_attempts": 0.0, "completions": 0.0,
            "passing_yards": 0.0, "passing_tds": 0.0,
            "interceptions": 0.0, "carries": 0.0,
            "rushing_yards": 0.0, "rushing_tds": 0.0,
            "targets": 0.0, "receptions": 0.0,
            "receiving_yards": 0.0, "receiving_tds": 0.0,
        })
        entry["weeks"].add(week)
        entry["games"] += 1
        aliases = {
            "passing_attempts": ("attempts", "passing_attempts"),
            "completions": ("completions", "passing_completions"),
            "passing_yards": ("passing_yards",),
            "passing_tds": ("passing_tds", "passing_touchdowns"),
            "interceptions": ("interceptions", "passing_interceptions"),
            "carries": ("carries", "rushing_attempts"),
            "rushing_yards": ("rushing_yards",),
            "rushing_tds": ("rushing_tds", "rushing_touchdowns"),
            "targets": ("targets",),
            "receptions": ("receptions",),
            "receiving_yards": ("receiving_yards",),
            "receiving_tds": ("receiving_tds", "receiving_touchdowns"),
        }
        for stat, fields in aliases.items():
            entry[stat] += _float(row, *fields)

    result = []
    for entry in grouped.values():
        weeks = sorted(entry.pop("weeks"))
        if not weeks:
            continue
        keep = set(weeks[-last_n_weeks:])
        # Re-aggregate only the selected recent weeks from source rows.
        selected = [r for r in stat_rows
                    if str(_first(r, "player_id", "gsis_id", "gsis") or
                           _first(r, "player_display_name", "player_name", "full_name")) ==
                    str(entry["player_id"] or entry["name"])
                    and int(_first(r, "season") or 0) == season
                    and int(_first(r, "week") or 0) in keep]
        entry["games"] = len(selected)
        for stat in ("passing_attempts", "completions", "passing_yards",
                     "passing_tds", "interceptions", "carries",
                     "rushing_yards", "rushing_tds", "targets",
                     "receptions", "receiving_yards", "receiving_tds"):
            entry[stat] = round(sum(_float(r, *({
                "passing_attempts": ("attempts", "passing_attempts"),
                "completions": ("completions", "passing_completions"),
                "passing_yards": ("passing_yards",),
                "passing_tds": ("passing_tds", "passing_touchdowns"),
                "interceptions": ("interceptions", "passing_interceptions"),
                "carries": ("carries", "rushing_attempts"),
                "rushing_yards": ("rushing_yards",),
                "rushing_tds": ("rushing_tds", "rushing_touchdowns"),
                "targets": ("targets",), "receptions": ("receptions",),
                "receiving_yards": ("receiving_yards",),
                "receiving_tds": ("receiving_tds", "receiving_touchdowns"),
            }[stat])) for r in selected), 2)
        for stat in ("passing_attempts", "completions", "passing_yards",
                     "passing_tds", "interceptions", "carries",
                     "rushing_yards", "rushing_tds", "targets",
                     "receptions", "receiving_yards", "receiving_tds"):
            entry[stat + "_per_game"] = round(entry[stat] / max(1, entry["games"]), 2)
        entry["weeks_in_sample"] = weeks[-last_n_weeks:]
        result.append(entry)
    return result


def build_player_pool(stat_rows, roster_rows, depth_rows, injury_rows,
                      season, last_n_weeks=5, snap_rows=None):
    """Join recent player production to roster/depth/injury status.

    Players are marked eligible only when roster status is active, they are
    listed first at their position on a depth chart, and no adverse injury
    designation is present. This is not a substitute for final inactives.
    """
    stats = _aggregate_stats(stat_rows, season, last_n_weeks)
    snap_rows = snap_rows or []
    snap_totals = {}
    for snap in snap_rows:
        try:
            snap_season = int(_first(snap, "season") or 0)
            snap_week = int(_first(snap, "week") or 0)
        except (TypeError, ValueError):
            continue
        if snap_season != season:
            continue
        snap_name = _norm(_first(snap, "player", "player_name", "full_name"))
        snap_team = str(_first(snap, "team", "recent_team") or "").upper()
        if not snap_name:
            continue
        snap_totals.setdefault((snap_name, snap_team), []).append(snap)
    roster_by_id = {
        str(_first(r, "gsis_id", "player_id")): r for r in roster_rows
        if _first(r, "gsis_id", "player_id")
    }
    # 2025+ nflverse depth charts use dt/team/pos_abb/pos_rank.
    # Keep only the latest chart snapshot for each team, then match the
    # player's actual position instead of overwriting multi-position rows.
    latest_depth_dt_by_team = {}
    for row in depth_rows:
        team_code = str(_first(row, "team", "club_code") or "").upper()
        dt = str(_first(row, "dt") or "")
        if team_code and dt > latest_depth_dt_by_team.get(team_code, ""):
            latest_depth_dt_by_team[team_code] = dt

    depth_by_id = {}
    for row in depth_rows:
        pid = _first(row, "gsis_id", "player_id")
        team_code = str(_first(row, "team", "club_code") or "").upper()
        dt = str(_first(row, "dt") or "")
        if not pid:
            continue
        latest_dt = latest_depth_dt_by_team.get(team_code)
        if latest_dt and dt and dt != latest_dt:
            continue
        depth_by_id.setdefault(str(pid), []).append(row)

    # Injury reports are weekly. Use the latest published week for each
    # team so a prior week's OUT designation cannot leak into this week's pool.
    latest_injury_week_by_team = {}
    for row in injury_rows:
        team_code = str(_first(row, "team") or "").upper()
        try:
            row_season = int(_first(row, "season") or season)
            week = int(_first(row, "week") or 0)
        except (TypeError, ValueError):
            continue
        if row_season == season and team_code and week:
            latest_injury_week_by_team[team_code] = max(
                week, latest_injury_week_by_team.get(team_code, 0)
            )

    injury_by_id = {}
    for row in injury_rows:
        pid = _first(row, "gsis_id", "player_id")
        team_code = str(_first(row, "team") or "").upper()
        try:
            row_season = int(_first(row, "season") or season)
            week = int(_first(row, "week") or 0)
        except (TypeError, ValueError):
            continue
        if (
            pid
            and row_season == season
            and week == latest_injury_week_by_team.get(team_code)
        ):
            injury_by_id[str(pid)] = row

    def depth_rank(row):
        try:
            return int(float(_first(
                row, "pos_rank", "depth_order", "depth_team", "order"
            ) or 99))
        except (TypeError, ValueError):
            return 99

    pool = []
    for player in stats:
        pid = str(player["player_id"] or "")
        roster = roster_by_id.get(pid, {})
        depth_candidates = depth_by_id.get(pid, [])
        matching_depth = [
            row for row in depth_candidates
            if str(_first(row, "pos_abb", "depth_position", "position") or "").upper()
            == str(player["position"]).upper()
        ]
        depth_candidates = matching_depth or depth_candidates
        depth = min(depth_candidates, key=depth_rank, default={})
        injury = injury_by_id.get(pid, {})
        roster_status = _norm(_first(roster, "status", "roster_status"))
        depth_position = _first(depth, "pos_abb", "depth_position", "position") or player["position"]
        try:
            depth_order = int(float(_first(
                depth, "pos_rank", "depth_order", "depth_team", "order"
            ) or 99))
        except (TypeError, ValueError):
            depth_order = 99
        injury_status = _status_from_injury(injury) if injury else "active"
        roster_active = roster_status in {"act", "active", "1"}
        listed_first = depth_order == 1 and depth_position in POSITIONS
        eligible = roster_active and listed_first and injury_status == "active"
        player_snaps = snap_totals.get((_norm(player["name"]), str(player["team"] or "").upper()), [])
        recent_weeks = set(player.get("weeks_in_sample", []))
        player_snaps = [r for r in player_snaps if int(_first(r, "week") or 0) in recent_weeks]
        offense_snaps = sum(_float(r, "offense_snaps", "off_snap") for r in player_snaps)
        offense_pct_values = [_float(r, "offense_pct", "off_pct") for r in player_snaps if _first(r, "offense_pct", "off_pct") not in (None, "")]
        player.update({
            "offense_snaps_total": round(offense_snaps, 2),
            "offense_snaps_per_game": round(offense_snaps / max(1, len(player_snaps)), 2),
            "offense_snap_pct_avg": round(sum(offense_pct_values) / max(1, len(offense_pct_values)), 2) if offense_pct_values else None,
            "snap_games": len(player_snaps),
            "roster_status": roster_status or "not_found",
            "depth_order": depth_order,
            "depth_position": depth_position,
            "injury_status": injury_status,
            "status": "active" if eligible else (
                injury_status if injury_status != "active" else "unknown"
            ),
            "starter": bool(eligible),
            "eligibility_note": (
                "Listed first on depth chart; final game-day active status still requires confirmation."
                if eligible else
                "Blocked: roster/depth chart/injury data does not establish an eligible starter."
            ),
        })
        pool.append(player)
    return pool


def fetch_player_pool(season=None, last_n_weeks=5):
    """Download latest nflverse weekly stats, roster, depth charts and injuries."""
    season = int(season or datetime.now(timezone.utc).year)
    if not isinstance(last_n_weeks, int) or not 1 <= last_n_weeks <= 18:
        raise ValueError("last_n_weeks must be between 1 and 18.")
    urls = {
        "player_stats": f"{BASE}/stats_player/stats_player_week_{season}.csv",
        "rosters": f"{BASE}/rosters/roster_{season}.csv",
        "depth_charts": f"{BASE}/depth_charts/depth_charts_{season}.csv",
        "injuries": f"{BASE}/injuries/injuries_{season}.csv",
        "snap_counts": f"{BASE}/snap_counts/snap_counts_{season}.csv",
    }
    downloaded = {}
    for label, url in urls.items():
        try:
            downloaded[label] = _rows_from_text(_get(url))
        except Exception as exc:
            raise RuntimeError(
                f"Could not load required {label} feed from nflverse: {exc}"
            ) from exc
        if not downloaded[label]:
            raise RuntimeError(f"The nflverse {label} feed returned no records.")
    pool = build_player_pool(
        downloaded["player_stats"], downloaded["rosters"],
        downloaded["depth_charts"], downloaded["injuries"],
        season, last_n_weeks, downloaded["snap_counts"],
    )
    return {
        "season": season,
        "last_n_weeks": last_n_weeks,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "nflverse",
        "source_urls": urls,
        "player_count": len(pool),
        "eligible_depth_chart_first_players": sum(p["starter"] for p in pool),
        "players": pool,
        "warning": "Depth-chart first-listed is not official game-day starter/inactive confirmation.",
    }


def save_player_pool(data, path="player_pool.json"):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
