#!/usr/bin/env python3
"""Doug's Elite NHL Simulator.

Uses the public NHL club-stats endpoint when available. If live data cannot be
retrieved, uses clearly labelled league-average fallback inputs. No sportsbook
lines or player availability are fabricated.
"""
from __future__ import annotations
import argparse, json, math, random, statistics, sys
from dataclasses import dataclass, asdict
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

NHL_TEAMS = {
 "ANA":"Anaheim Ducks","BOS":"Boston Bruins","BUF":"Buffalo Sabres","CGY":"Calgary Flames",
 "CAR":"Carolina Hurricanes","CHI":"Chicago Blackhawks","COL":"Colorado Avalanche","CBJ":"Columbus Blue Jackets",
 "DAL":"Dallas Stars","DET":"Detroit Red Wings","EDM":"Edmonton Oilers","FLA":"Florida Panthers",
 "LAK":"Los Angeles Kings","MIN":"Minnesota Wild","MTL":"Montreal Canadiens","NSH":"Nashville Predators",
 "NJD":"New Jersey Devils","NYI":"New York Islanders","NYR":"New York Rangers","OTT":"Ottawa Senators",
 "PHI":"Philadelphia Flyers","PIT":"Pittsburgh Penguins","SJS":"San Jose Sharks","SEA":"Seattle Kraken",
 "STL":"St. Louis Blues","TBL":"Tampa Bay Lightning","TOR":"Toronto Maple Leafs","UTA":"Utah Mammoth",
 "VAN":"Vancouver Canucks","VGK":"Vegas Golden Knights","WPG":"Winnipeg Jets","WSH":"Washington Capitals"
}
LEAGUE_BASE = {"gf":3.05,"ga":3.05,"sf":29.0,"sa":29.0,"pp":0.20,"pk":0.80,"fo":0.50}

@dataclass
class TeamStats:
    code: str
    name: str
    gf: float = 3.05
    ga: float = 3.05
    sf: float = 29.0
    sa: float = 29.0
    pp: float = 0.20
    pk: float = 0.80
    fo: float = 0.50
    source: str = "league-average fallback"

def _num(obj, keys, default):
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (int,float)) and math.isfinite(value):
            return float(value)
    return default

def fetch_team_stats(code: str, timeout: float = 8.0) -> TeamStats:
    if code not in NHL_TEAMS:
        raise ValueError(f"Unknown NHL team code: {code}. Use one of: {', '.join(NHL_TEAMS)}")
    stats = TeamStats(code, NHL_TEAMS[code])
    url = f"https://api-web.nhle.com/v1/club-stats/{code}/now"
    try:
        req = Request(url, headers={"User-Agent":"Doug-NHL-Simulator/1.0"})
        with urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        if not isinstance(payload, dict) or not payload:
            raise ValueError("NHL API returned an empty stats payload")
        stats.gf = _num(payload, ["goalsForPerGame","goalsFor"], stats.gf)
        stats.ga = _num(payload, ["goalsAgainstPerGame","goalsAgainst"], stats.ga)
        stats.sf = _num(payload, ["shotsForPerGame","shotsFor"], stats.sf)
        stats.sa = _num(payload, ["shotsAgainstPerGame","shotsAgainst"], stats.sa)
        stats.pp = _num(payload, ["powerPlayPct"], stats.pp)
        stats.pk = _num(payload, ["penaltyKillPct"], stats.pk)
        stats.fo = _num(payload, ["faceoffWinPct"], stats.fo)
        # NHL endpoints commonly return percentages on a 0-100 scale.
        if stats.pp > 1: stats.pp /= 100
        if stats.pk > 1: stats.pk /= 100
        if stats.fo > 1: stats.fo /= 100
        stats.source = "NHL public club-stats API"
    except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError, KeyError) as exc:
        stats.source = f"league-average fallback (live stats unavailable: {type(exc).__name__})"
    return stats

def poisson(lam: float, rng: random.Random) -> int:
    # Knuth sampler; suitable for the modest NHL goal/shot means used here.
    lam = max(0.01, min(float(lam), 100.0))
    limit = math.exp(-lam)
    product, count = 1.0, 0
    while product > limit:
        count += 1
        product *= rng.random()
    return count - 1

def expected_goals(offense: TeamStats, defense: TeamStats, home: bool) -> float:
    # Blend scoring production with opponent goals allowed; modest home-ice bump.
    base = 0.55 * offense.gf + 0.45 * defense.ga
    special_teams = 1.0 + 0.12 * ((offense.pp - LEAGUE_BASE["pp"]) - (defense.pk - LEAGUE_BASE["pk"]))
    return max(1.5, min(5.5, base * special_teams * (1.045 if home else 0.955)))

def run_simulation(home: TeamStats, away: TeamStats, trials: int = 100_000, seed: int = 20261105) -> dict:
    if trials < 1000:
        raise ValueError("Use at least 1,000 trials; default is 100,000.")
    rng = random.Random(seed)
    home_goals, away_goals, home_shots, away_shots = [], [], [], []
    home_wins = away_wins = ties_after_reg = 0
    for _ in range(trials):
        hg = poisson(expected_goals(home, away, True), rng)
        ag = poisson(expected_goals(away, home, False), rng)
        hs = max(hg, poisson(max(18, 0.55*home.sf + 0.45*away.sa), rng))
        aws = max(ag, poisson(max(18, 0.55*away.sf + 0.45*home.sa), rng))
        home_goals.append(hg); away_goals.append(ag)
        home_shots.append(hs); away_shots.append(aws)
        if hg > ag: home_wins += 1
        elif ag > hg: away_wins += 1
        else: ties_after_reg += 1
    hmean, amean = statistics.fmean(home_goals), statistics.fmean(away_goals)
    total_goals = [a+b for a,b in zip(home_goals,away_goals)]
    total_shots = [a+b for a,b in zip(home_shots,away_shots)]
    def pct(n): return round(100*n/trials, 2)
    return {
      "trials":trials, "seed":seed,
      "home":{"team":home.code,"name":home.name,"win_pct_including_ot_proxy":pct(home_wins + ties_after_reg*0.5),
              "regulation_win_pct":pct(home_wins),"expected_goals":round(hmean,2),
              "expected_shots":round(statistics.fmean(home_shots),1),"stats_source":home.source},
      "away":{"team":away.code,"name":away.name,"win_pct_including_ot_proxy":pct(away_wins + ties_after_reg*0.5),
              "regulation_win_pct":pct(away_wins),"expected_goals":round(amean,2),
              "expected_shots":round(statistics.fmean(away_shots),1),"stats_source":away.source},
      "draw_after_regulation_pct":pct(ties_after_reg),
      "total_goals_mean":round(statistics.fmean(total_goals),2),
      "total_shots_mean":round(statistics.fmean(total_shots),1),
      "total_goals_over":{"4.5":pct(sum(x>4.5 for x in total_goals)),
                          "5.5":pct(sum(x>5.5 for x in total_goals)),
                          "6.5":pct(sum(x>6.5 for x in total_goals))},
      "team_goal_markets":{"home_2plus":pct(sum(x>=2 for x in home_goals)),
                           "home_3plus":pct(sum(x>=3 for x in home_goals)),
                           "away_2plus":pct(sum(x>=2 for x in away_goals)),
                           "away_3plus":pct(sum(x>=3 for x in away_goals))},
      "model_notes":[
        "Goals are simulated with Poisson scoring rates blended from team goals-for and opponent goals-against.",
        "Shots are simulated from team shots-for and opponent shots-against rates.",
        "Tied regulation games are split 50/50 for the moneyline proxy; overtime/shootout is not separately modelled.",
        "No player props, confirmed goalie adjustment, injuries, line combinations, or sportsbook vig are included in this baseline."
      ]
    }

def main():
    parser=argparse.ArgumentParser(description="Doug's Elite NHL Simulator")
    parser.add_argument("--home",required=True,choices=sorted(NHL_TEAMS))
    parser.add_argument("--away",required=True,choices=sorted(NHL_TEAMS))
    parser.add_argument("--trials",type=int,default=100000)
    parser.add_argument("--seed",type=int,default=20261105)
    args=parser.parse_args()
    if args.home == args.away: parser.error("Home and away teams must be different.")
    home, away = fetch_team_stats(args.home), fetch_team_stats(args.away)
    result=run_simulation(home,away,args.trials,args.seed)
    print("DOUG'S ELITE NHL SIMULATOR")
    print(json.dumps(result,indent=2))
    with open("nhl-simulation-results.json","w",encoding="utf-8") as f:
        json.dump(result,f,indent=2)

if __name__=="__main__":
    main()
