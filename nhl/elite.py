"""Doug's Elite NHL Simulator: live NHL data + reproducible Monte Carlo.

Baseline team and player projections. Data is sourced from NHL public APIs.
Unknown injuries/confirmed starters are explicitly reported, never invented.
"""
from __future__ import annotations
import argparse, json, math, random, urllib.parse, urllib.request
from datetime import datetime, timezone

WEB = "https://api-web.nhle.com/v1"
STATS = "https://api.nhle.com/stats/rest/en"
TEAMS = ["ANA","BOS","BUF","CAR","CBJ","CGY","CHI","COL","DAL","DET","EDM","FLA","LAK","MIN","MTL","NJD","NSH","NYI","NYR","OTT","PHI","PIT","SEA","SJS","STL","TBL","TOR","UTA","VAN","VGK","WPG","WSH"]

def season_id(now=None):
    now = now or datetime.now(timezone.utc)
    y = now.year if now.month >= 9 else now.year - 1
    return int(f"{y}{y+1}")

def get_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent":"DougsEliteNHL/2.0","Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def stats_report(kind, season, limit=1000):
    q = urllib.parse.urlencode({"isAggregate":"false","isGame":"false","limit":str(limit),
        "cayenneExp":f"gameTypeId=2 and seasonId={season}"})
    payload = get_json(f"{STATS}/{kind}/summary?{q}")
    rows = payload.get("data", [])
    if not isinstance(rows, list):
        raise RuntimeError(f"Unexpected {kind} stats response")
    return rows

def first_num(row, names, default=None):
    for name in names:
        value = row.get(name)
        if isinstance(value, (int,float)) and math.isfinite(value):
            return float(value)
    return default

def team_code(row):
    v = row.get("teamAbbrevs") or row.get("teamAbbrev") or row.get("teamCode") or row.get("teamAbbreviation")
    if isinstance(v, dict): v = v.get("default") or v.get("triCode")
    return str(v).upper() if v else ""

def player_id(row):
    return row.get("playerId") or row.get("player_id") or row.get("id")

def player_name(row):
    full = row.get("skaterFullName") or row.get("playerName")
    if full: return str(full).strip()
    first, last = row.get("skaterFirstName") or row.get("firstName"), row.get("skaterLastName") or row.get("lastName")
    if isinstance(first, dict): first = first.get("default")
    if isinstance(last, dict): last = last.get("default")
    return " ".join(str(x) for x in (first,last) if x) or str(row.get("playerName") or player_id(row) or "Unknown")

def rate(row, fields, gp):
    v = first_num(row, fields, 0.0) or 0.0
    return max(0.0, v / max(1.0, gp))

def poisson(rng, lam):
    lam = max(0.001, min(float(lam), 100.0))
    # Knuth is efficient for NHL goal/point rates; normal approximation for large shot means.
    if lam > 30:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    limit, p, k = math.exp(-lam), 1.0, 0
    while p > limit:
        k += 1
        p *= rng.random()
    return k - 1

def normalize_team(row):
    gp = first_num(row, ["gamesPlayed","games_played"], 0) or 0
    if gp <= 0: return None
    return {
        "team":team_code(row), "games":int(gp),
        "gf":first_num(row,["goalsForPerGame","goalsFor"],None),
        "ga":first_num(row,["goalsAgainstPerGame","goalsAgainst"],None),
        "sf":first_num(row,["shotsForPerGame","shotsFor"],None),
        "sa":first_num(row,["shotsAgainstPerGame","shotsAgainst"],None),
        "pp":first_num(row,["powerPlayPct","powerPlayPercentage"],None),
        "pk":first_num(row,["penaltyKillPct","penaltyKillPercentage"],None),
        "fo":first_num(row,["faceoffWinPct","faceoffWinPercentage"],None),
    }

def load_data(home, away, season):
    team_rows = stats_report("team", season, 100)
    team_stats = {t["team"]:t for t in (normalize_team(r) for r in team_rows) if t and t["team"]}
    if home not in team_stats or away not in team_stats:
        raise RuntimeError(f"Missing current-season team stats for {home} or {away}; no fallback data will be substituted.")
    skaters = stats_report("skater", season, 1500)
    goalies = stats_report("goalie", season, 500)
    roster_data = {}
    for code in (home, away):
        roster_data[code] = get_json(f"{WEB}/roster/{code}/current")
    return team_stats, skaters, goalies, roster_data

def build_player_pool(code, roster, skater_rows, goalie_rows):
    active = {}
    for group in ("forwards","defensemen"):
        for p in roster.get(group, []) or []:
            pid = player_id(p)
            if pid: active[str(pid)] = {"id":pid,"name":player_name(p),"position":group[:-1].upper() if group.endswith("s") else group.upper()}
    # API may expose roster group as goalies; goalie props are handled separately.
    skaters = []
    for row in skater_rows:
        if team_code(row) != code: continue
        pid = player_id(row)
        if not pid or str(pid) not in active: continue
        gp = first_num(row,["gamesPlayed"],0) or 0
        if gp < 1: continue
        meta = active[str(pid)]
        skaters.append({
            **meta, "games":int(gp),
            "goals_pg":rate(row,["goals"],gp),
            "assists_pg":rate(row,["assists"],gp),
            "points_pg":rate(row,["points"],gp),
            "shots_pg":rate(row,["shots"],gp),
            "blocks_pg":rate(row,["blockedShots"],gp),
            "toi_min":(first_num(row,["timeOnIcePerGame","avgTimeOnIce"],0) or 0)/60,
        })
    goalies = []
    roster_goalies = {str(player_id(p)):p for p in (roster.get("goalies",[]) or []) if player_id(p)}
    for row in goalie_rows:
        pid = player_id(row)
        if team_code(row) != code or not pid or str(pid) not in roster_goalies: continue
        gp = first_num(row,["gamesPlayed"],0) or 0
        if gp < 1: continue
        goalies.append({
            "id":pid, "name":player_name(row), "games":int(gp),
            "starts":first_num(row,["gamesStarted"],gp) or gp,
            "save_pct":first_num(row,["savePct","savePercentage"],0.90) or 0.90,
            "gaa":first_num(row,["goalsAgainstAverage"],3.0) or 3.0,
        })
    goalies.sort(key=lambda x:(x["starts"],x["games"]),reverse=True)
    skaters.sort(key=lambda x:x["points_pg"],reverse=True)
    return skaters, goalies

def matchup_means(h, a):
    league_gf = (h["gf"] + a["gf"] + h["ga"] + a["ga"]) / 4
    home = 0.55*h["gf"] + 0.45*a["ga"]
    away = 0.55*a["gf"] + 0.45*h["ga"]
    # small explicit home-ice adjustment
    home *= 1.035
    # Special teams nudge only when source rates are available and in percentage units.
    if h["pp"] is not None and a["pk"] is not None:
        home *= max(.94,min(1.06,1 + ((h["pp"]-20) + (80-a["pk"]))*0.001))
    if a["pp"] is not None and h["pk"] is not None:
        away *= max(.94,min(1.06,1 + ((a["pp"]-20) + (80-h["pk"]))*0.001))
    return max(.5,home), max(.5,away), league_gf

def simulate(home_code, away_code, team_stats, skaters, goalies, rosters, trials=100000,
             total=6.0, puck_line=1.5, seed=20261115, home_goalie_id=None, away_goalie_id=None):
    if trials < 1000:
        raise ValueError("Use at least 1,000 trials.")
    h, a = team_stats[home_code], team_stats[away_code]
    hm, am, _ = matchup_means(h, a)
    hp, hg = build_player_pool(home_code, rosters[home_code], skaters, goalies)
    ap, ag = build_player_pool(away_code, rosters[away_code], skaters, goalies)
    selected = {}
    for code, pool, chosen in ((home_code, hg, home_goalie_id), (away_code, ag, away_goalie_id)):
        found = next((g for g in pool if str(g["id"]) == str(chosen)), None) if chosen else None
        selected[code] = found or (pool[0] if pool else None)
    if selected[away_code]:
        hm *= max(.88, min(1.12, selected[away_code]["gaa"] / 3.0))
    if selected[home_code]:
        am *= max(.88, min(1.12, selected[home_code]["gaa"] / 3.0))

    rng = random.Random(seed)
    wins_h = wins_a = tie = over = under = push = cover_h = cover_a = 0
    goals_h = goals_a = shots_h = shots_a = 0
    period_h, period_a = [0, 0, 0], [0, 0, 0]
    goalie_saves = {
        str(g["id"]): 0 for g in
        ([selected[home_code]] if selected[home_code] else []) +
        ([selected[away_code]] if selected[away_code] else [])
    }

    for _ in range(trials):
        # Period-level goals add up exactly to the regulation score.
        h_period = [poisson(rng, hm / 3) for _ in range(3)]
        a_period = [poisson(rng, am / 3) for _ in range(3)]
        gh, ga = sum(h_period), sum(a_period)
        for i in range(3):
            period_h[i] += h_period[i]
            period_a[i] += a_period[i]

        sh = max(gh, poisson(rng, max(18, (h["sf"] or 29) * .55 + (a["sa"] or 29) * .45)))
        sa = max(ga, poisson(rng, max(18, (a["sf"] or 29) * .55 + (h["sa"] or 29) * .45)))
        # Sudden-death OT/shootout proxy; winner receives one additional goal.
        if gh == ga:
            tie += 1
            if rng.random() < .52:
                gh += 1
            else:
                ga += 1
        if gh > ga:
            wins_h += 1
        else:
            wins_a += 1
        margin = gh - ga
        if margin > puck_line:
            cover_h += 1
        else:
            cover_a += 1
        game_total = gh + ga
        if game_total > total:
            over += 1
        elif game_total < total:
            under += 1
        else:
            push += 1
        goals_h += gh
        goals_a += ga
        shots_h += sh
        shots_a += sa
        if selected[home_code]:
            gid = str(selected[home_code]["id"])
            goalie_saves[gid] += max(0, sa - ga)
        if selected[away_code]:
            gid = str(selected[away_code]["id"])
            goalie_saves[gid] += max(0, sh - gh)

    pct = lambda n: round(100 * n / trials, 2)
    def poisson_tail(lam, k):
        return max(0.0, 1 - sum(math.exp(-lam) * lam**i / math.factorial(i) for i in range(k)))

    props = []
    for team, pool in ((home_code, hp), (away_code, ap)):
        for p in pool:
            props.append({
                "player_id": p["id"], "player": p["name"], "team": team, "position": p["position"],
                "games_sample": p["games"], "toi_min": round(p["toi_min"], 1),
                "shots_pg": round(p["shots_pg"], 2), "goals_pg": round(p["goals_pg"], 3),
                "assists_pg": round(p["assists_pg"], 3), "points_pg": round(p["points_pg"], 3),
                "p_1plus_shot_pct": round(100 * poisson_tail(p["shots_pg"], 1), 2),
                "p_2plus_shots_pct": round(100 * poisson_tail(p["shots_pg"], 2), 2),
                "p_3plus_shots_pct": round(100 * poisson_tail(p["shots_pg"], 3), 2),
                "p_1plus_goal_pct": round(100 * poisson_tail(p["goals_pg"], 1), 2),
                "p_1plus_point_pct": round(100 * poisson_tail(p["points_pg"], 1), 2),
                "p_1plus_assist_pct": round(100 * poisson_tail(p["assists_pg"], 1), 2)
            })
    props.sort(key=lambda x: x["points_pg"], reverse=True)

    goalie_props = []
    for gid, saves in goalie_saves.items():
        mean = saves / trials
        goalie_props.append({
            "goalie_id": gid, "projected_saves": round(mean, 1),
            "p_20plus_saves_pct": round(100 * poisson_tail(mean, 20), 2),
            "p_25plus_saves_pct": round(100 * poisson_tail(mean, 25), 2),
            "p_30plus_saves_pct": round(100 * poisson_tail(mean, 30), 2)
        })

    return {
        "season": h.get("season", season_id()), "home": home_code, "away": away_code,
        "trials": trials, "seed": seed,
        "goal_means": {"home": round(hm, 2), "away": round(am, 2)},
        "moneyline_pct": {"home": pct(wins_h), "away": pct(wins_a)},
        "regulation_tie_pct": pct(tie),
        "puck_line_pct": {"home_minus_1_5": pct(cover_h), "away_plus_1_5": pct(cover_a)},
        "total_line": total, "total_pct": {"over": pct(over), "under": pct(under), "push": pct(push)},
        "projected_score": {"home": round(goals_h / trials, 2), "away": round(goals_a / trials, 2)},
        "projected_shots": {"home": round(shots_h / trials, 1), "away": round(shots_a / trials, 1)},
        "period_goals_avg": {
            "home": [round(x / trials, 2) for x in period_h],
            "away": [round(x / trials, 2) for x in period_a]
        },
        "goalies": {
            code: {"selected": selected[code], "status": "projected from season starts; confirm official starter"}
            for code in (home_code, away_code)
        },
        "goalie_save_props": goalie_props, "player_props": props,
        "data_quality": {
            "home_games": h["games"], "away_games": a["games"],
            "injuries": "Not verified by this data endpoint; check official injury report/inactives before betting.",
            "lineups": "Current roster filtered; game-day scratches and line combinations are not guaranteed.",
            "goalies": "Top season-start goalie is a projection, not a confirmed starter."
        },
        "limitations": [
            "Player prop probabilities use independent Poisson approximations from season per-game rates; they are not correlated to game outcomes.",
            "Goalie save probabilities use the simulated mean saves and a Poisson tail approximation.",
            "No shift-level deployment, travel/rest, or confirmed lineup adjustment is claimed.",
            "Overtime winner uses a 52/48 home-ice proxy; shootout skills are not separately modeled.",
            "No betting edge is reported without actual sportsbook odds and vig removal."
        ]
    }

def main():
    p=argparse.ArgumentParser(description="Doug's Elite NHL Simulator")
    p.add_argument("--home",required=True,choices=TEAMS); p.add_argument("--away",required=True,choices=TEAMS)
    p.add_argument("--trials",type=int,default=100000); p.add_argument("--total",type=float,default=6.0)
    p.add_argument("--puck-line",type=float,default=1.5); p.add_argument("--seed",type=int,default=20261115)
    p.add_argument("--home-goalie-id"); p.add_argument("--away-goalie-id")
    p.add_argument("--season",type=int,default=season_id()); p.add_argument("--output",default="nhl-elite-results.json")
    args=p.parse_args()
    if args.home==args.away: p.error("Home and away must differ.")
    team,skaters,goalies,rosters=load_data(args.home,args.away,args.season)
    result=simulate(args.home,args.away,team,skaters,goalies,rosters,args.trials,args.total,args.puck_line,args.seed,args.home_goalie_id,args.away_goalie_id)
    result["team_stats"]={c:team[c] for c in (args.home,args.away)}
    with open(args.output,"w",encoding="utf-8") as f: json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))

if __name__=="__main__": main()
