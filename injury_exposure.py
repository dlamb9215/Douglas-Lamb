"""NFL injury exposure summaries based on recent snap share.

This produces scenario inputs only. It does not apply arbitrary point penalties
to team scoring. Official final inactive and starter confirmation remains
required for player props and final injury scenarios.
"""


POSITION_WEIGHTS = {"QB": 3.0, "RB": 1.25, "WR": 1.0, "TE": 0.8, "OL": 1.4, "DL": 1.2, "LB": 0.9, "DB": 0.8}
STATUS_WEIGHTS = {"out": 1.0, "doubtful": 0.75, "questionable": 0.35}


def build_injury_exposure(pool, teams):
    players = pool.get("players", [])
    result = {}
    for team in teams:
        exposures = []
        for player in players:
            if str(player.get("team", "")).upper() != team:
                continue
            status = str(player.get("injury_status", "unknown")).lower()
            if status not in STATUS_WEIGHTS:
                continue
            snap_pct = player.get("offense_snap_pct_avg")
            if not isinstance(snap_pct, (int, float)) or isinstance(snap_pct, bool):
                snap_pct = 0.0
            position = str(player.get("position", "")).upper()
            role_weight = POSITION_WEIGHTS.get(position, 0.5)
            exposure = max(0.0, min(100.0, float(snap_pct))) * STATUS_WEIGHTS[status] * role_weight
            exposures.append({
                "player": player.get("name"),
                "position": position,
                "injury_status": status,
                "practice_status": player.get("practice_status"),
                "snap_share_pct": round(float(snap_pct), 1),
                "role_weight": role_weight,
                "status_weight": STATUS_WEIGHTS[status],
                "weighted_exposure": round(exposure, 2),
                "reported_injury": player.get("reported_injury"),
            })
        result[team] = {
            "players_with_reported_designations": len(exposures),
            "weighted_injury_exposure_index": round(sum(x["weighted_exposure"] for x in exposures), 2),
            "players": sorted(exposures, key=lambda x: x["weighted_exposure"], reverse=True),
            "interpretation": "Relative snap-share exposure index only; not points, win probability, or a calibrated injury adjustment."
        }
    return result
