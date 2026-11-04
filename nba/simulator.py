"""Doug's Elite NBA Simulator.

Team-level Monte Carlo engine. Betting outputs are spreads and totals only.
No player-prop projections or moneyline recommendations.
"""
from __future__ import annotations
import argparse, json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np

LEAGUE={"efg_pct":.540,"tov_pct":.135,"orb_pct":.265,"ft_rate":.250,
        "opp_efg_pct":.540,"opp_tov_pct":.135,"opp_orb_pct":.265,"opp_ft_rate":.250}

@dataclass(frozen=True)
class TeamStats:
    abbreviation:str
    name:str
    games_played:int
    pace:float
    off_rating:float
    def_rating:float
    efg_pct:float
    tov_pct:float
    orb_pct:float
    ft_rate:float
    opp_efg_pct:float
    opp_tov_pct:float
    opp_orb_pct:float
    opp_ft_rate:float
    recent_pace:float|None=None
    recent_off_rating:float|None=None
    recent_def_rating:float|None=None
    home_off_rating:float|None=None
    home_def_rating:float|None=None
    road_off_rating:float|None=None
    road_def_rating:float|None=None
    score_sd:float=11.5
    three_pa_rate:float|None=None
    fg3_pct:float|None=None
    opp_three_pa_rate:float|None=None
    opp_fg3_pct:float|None=None

    @classmethod
    def from_dict(cls,code:str,raw:dict[str,Any]):
        keys=("pace","off_rating","def_rating","efg_pct","tov_pct","orb_pct","ft_rate",
              "opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ft_rate")
        missing=[k for k in keys if raw.get(k) is None]
        if missing: raise ValueError(f"{code} missing metrics: {', '.join(missing)}")
        v={k:float(raw[k]) for k in keys}
        for k in keys:
            if (k.endswith("_pct") or k.endswith("_rate")) and v[k]>1: v[k]/=100
        if not 70<=v["pace"]<=115: raise ValueError(f"{code} pace outside plausible range")
        for k in ("off_rating","def_rating"):
            if not 80<=v[k]<=140: raise ValueError(f"{code} {k} outside plausible range")
        for k in keys:
            if (k.endswith("_pct") or k.endswith("_rate")) and not 0<=v[k]<=1:
                raise ValueError(f"{code} {k} must be 0-1 or 0-100")
        optional={}
        for k in ("recent_pace","recent_off_rating","recent_def_rating","home_off_rating",
                  "home_def_rating","road_off_rating","road_def_rating","score_sd","three_pa_rate","fg3_pct","opp_three_pa_rate","opp_fg3_pct"):
            value=raw.get(k)
            optional[k]=float(value) if value is not None else None
        if optional["score_sd"] is None: optional["score_sd"]=11.5
        for k in ("three_pa_rate","fg3_pct","opp_three_pa_rate","opp_fg3_pct"):
            if optional[k] is not None and optional[k]>1: optional[k]/=100
            if optional[k] is not None and not 0<=optional[k]<=1: raise ValueError(f"{code} {k} must be 0-1 or 0-100")
        if not 7<=optional["score_sd"]<=18: raise ValueError(f"{code} score_sd outside supported range")
        gp=int(raw.get("games_played",raw.get("gp",0)))
        if gp<0: raise ValueError("games_played cannot be negative")
        return cls(code.upper(),str(raw.get("name",code.upper())),gp,**v,**optional)

def load_team_stats(path="nba/team_stats.json"):
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(f"{p} missing. Run Update NBA Statistics first.")
    data=json.loads(p.read_text(encoding="utf-8")); raw=data.get("teams",{})
    if not isinstance(raw,dict) or len(raw)<30: raise ValueError("NBA data must contain all 30 teams")
    return {k.upper():TeamStats.from_dict(k,v) for k,v in raw.items()},data

def _shot_profile_adjustment(t,o):
    # Small correction for opponent three-point accuracy allowed; eFG already
    # captures much of the team's own shot-making, so avoid double-counting it.
    if t.three_pa_rate is None or o.opp_fg3_pct is None: return 0.0
    share=min(.60,max(.20,t.three_pa_rate))
    return max(-1.25,min(1.25,(o.opp_fg3_pct-.36)*300*share*.25))

def _factor_adjustment(t,o):
    own=38*(t.efg_pct-LEAGUE["efg_pct"])-24*(t.tov_pct-LEAGUE["tov_pct"])+15*(t.orb_pct-LEAGUE["orb_pct"])+10*(t.ft_rate-LEAGUE["ft_rate"])
    opp=30*(o.opp_efg_pct-LEAGUE["opp_efg_pct"])-18*(o.opp_tov_pct-LEAGUE["opp_tov_pct"])+10*(o.opp_orb_pct-LEAGUE["opp_orb_pct"])+8*(o.opp_ft_rate-LEAGUE["opp_ft_rate"])
    return own+opp

def matchup_projection(home,away,home_rest=2,away_rest=2,home_travel=0,away_travel=0,
                       home_injury_points=0,away_injury_points=0):
    pace=(home.pace+away.pace)/2
    if home.recent_pace is not None: pace=.8*pace+.2*(home.recent_pace+away.recent_pace if away.recent_pace is not None else home.recent_pace)/2
    h_off=home.home_off_rating or home.off_rating
    h_def=home.home_def_rating or home.def_rating
    a_off=away.road_off_rating or away.off_rating
    a_def=away.road_def_rating or away.def_rating
    h_off=.85*h_off+.15*home.recent_off_rating if home.recent_off_rating is not None else h_off
    a_off=.85*a_off+.15*away.recent_off_rating if away.recent_off_rating is not None else a_off
    h_def=.85*h_def+.15*home.recent_def_rating if home.recent_def_rating is not None else h_def
    a_def=.85*a_def+.15*away.recent_def_rating if away.recent_def_rating is not None else a_def
    he=(h_off+a_def)/2+_factor_adjustment(home,away)+_shot_profile_adjustment(home,away)+1.35
    ae=(a_off+h_def)/2+_factor_adjustment(away,home)+_shot_profile_adjustment(away,home)
    # Small transparent schedule effects; capped to avoid exaggerated travel/rest adjustments.
    h_rest=max(0,min(3,home_rest-1))*0.35
    a_rest=max(0,min(3,away_rest-1))*0.35
    h_b2b=1.0 if home_rest<=0 else 0.0
    a_b2b=1.0 if away_rest<=0 else 0.0
    h_travel=min(max(home_travel,0)/1000,2)*0.35
    a_travel=min(max(away_travel,0)/1000,2)*0.35
    he += (h_rest-h_b2b-h_travel) * 100/pace
    ae += (a_rest-a_b2b-a_travel) * 100/pace
    hp=pace*he/100+home_injury_points
    ap=pace*ae/100+away_injury_points
    return {"pace":pace,"home_efficiency":he,"away_efficiency":ae,
            "home_points":hp,"away_points":ap,"home_margin":hp-ap,
            "total_points":hp+ap,"home_rest_adjustment":h_rest-h_b2b-h_travel,
            "away_rest_adjustment":a_rest-a_b2b-a_travel}

def _wilson_interval(probability,trials,z=1.96):
    p=min(1.0,max(0.0,probability))
    denom=1+z*z/trials
    center=(p+z*z/(2*trials))/denom
    radius=z*((p*(1-p)/trials+z*z/(4*trials*trials))**.5)/denom
    return [max(0.0,(center-radius)*100),min(100.0,(center+radius)*100)]

def _simulate_period(hmean,amean,pace,hsd,asd,trials,seed):
    rng=np.random.default_rng(seed)
    # A shared pace/game-environment shock induces realistic positive scoring correlation.
    pace_shock=rng.normal(0,0.025,trials)
    h=rng.normal(hmean*(1+pace_shock),hsd,trials)
    a=rng.normal(amean*(1+pace_shock),asd,trials)
    return np.maximum(0,np.rint(h)).astype(np.int16),np.maximum(0,np.rint(a)).astype(np.int16)

def simulate(home,away,trials=1_000_000,seed=42,spread=None,total=None,
             home_rest=2,away_rest=2,home_travel=0,away_travel=0,
             home_injury_points=0,away_injury_points=0):
    if trials<1: raise ValueError("trials must be positive")
    if home_rest<0 or away_rest<0: raise ValueError("rest days cannot be negative")
    if spread is not None and not -40<=spread<=40: raise ValueError("spread outside supported range")
    if total is not None and not 120<=total<=350: raise ValueError("total outside supported range")
    p=matchup_projection(home,away,home_rest,away_rest,home_travel,away_travel,
                         home_injury_points,away_injury_points)
    hsd=max(8.0,home.score_sd); asd=max(8.0,away.score_sd)
    hs,aws=_simulate_period(p["home_points"],p["away_points"],p["pace"],hsd,asd,trials,seed)
    margin=hs-aws; combined=hs+aws
    r={**p,"trials":trials,"seed":seed,"home_avg":float(np.mean(hs)),
       "away_avg":float(np.mean(aws)),"total_avg":float(np.mean(combined)),
       "margin_sd":float(np.std(margin,ddof=1))}
    if spread is not None:
        # sportsbook home line is conventionally negative for a favorite
        adj=margin+spread
        r.update({"spread":spread,"home_cover":float(np.mean(adj>0)*100),
                  "away_cover":float(np.mean(adj<0)*100),"spread_push":float(np.mean(adj==0)*100),
                  "spread_edge_points":float(p["home_margin"]+spread),
                  "home_cover_ci":_wilson_interval(float(np.mean(adj>0)),trials),
                  "away_cover_ci":_wilson_interval(float(np.mean(adj<0)),trials)})
    if total is not None:
        r.update({"total":total,"over":float(np.mean(combined>total)*100),
                  "under":float(np.mean(combined<total)*100),"total_push":float(np.mean(combined==total)*100),
                  "total_edge_points":float(p["total_points"]-total),
                  "over_ci":_wilson_interval(float(np.mean(combined>total)),trials),
                  "under_ci":_wilson_interval(float(np.mean(combined<total)),trials)})
    hh,ha=_simulate_period(p["home_points"]/2,p["away_points"]/2,p["pace"]/2,
                           hsd/np.sqrt(2),asd/np.sqrt(2),trials,seed+1)
    hm=hh-ha; ht=hh+ha
    r["first_half"]={"home_cover":None,"away_cover":None,
                     "home_avg":float(np.mean(hh)),"away_avg":float(np.mean(ha)),
                     "total_avg":float(np.mean(ht))}
    if spread is not None:
        first_line=spread/2; fm=hm+first_line
        r["first_half"].update({"home_cover":float(np.mean(fm>0)*100),
                                "away_cover":float(np.mean(fm<0)*100),"spread_push":float(np.mean(fm==0)*100)})
    if total is not None:
        r["first_half"].update({"over":float(np.mean(ht>total/2)*100),
                                "under":float(np.mean(ht<total/2)*100),"total_push":float(np.mean(ht==total/2)*100)})
    return r

def implied_probability(odds):
    if odds==0: raise ValueError("American odds cannot be zero")
    return 100/(odds+100) if odds>0 else abs(odds)/(abs(odds)+100)

def _decision(prob,edge,threshold=55.0,min_edge=1.5):
    if prob is None: return "NO LINE"
    if prob>=threshold and edge>=min_edge: return "LEAN"
    return "PASS"

def main():
    ap=argparse.ArgumentParser(description="Doug's Elite NBA Simulator")
    ap.add_argument("--home",required=True); ap.add_argument("--away",required=True)
    ap.add_argument("--data",default="nba/team_stats.json")
    ap.add_argument("--spread",type=float,help="Home spread, e.g. -4.5")
    ap.add_argument("--total",type=float)
    ap.add_argument("--home-rest",type=float,default=2); ap.add_argument("--away-rest",type=float,default=2)
    ap.add_argument("--home-travel",type=float,default=0); ap.add_argument("--away-travel",type=float,default=0)
    ap.add_argument("--home-injury-points",type=float,default=0,help="Manual estimated team points lost to unavailable players")
    ap.add_argument("--away-injury-points",type=float,default=0)
    ap.add_argument("--trials",type=int,default=1_000_000); ap.add_argument("--max-trials",type=int,default=5_000_000)
    ap.add_argument("--seed",type=int,default=42); ap.add_argument("--no-auto-refine",action="store_true"); ap.add_argument("--json-output",default="")
    a=ap.parse_args()
    if a.trials<1 or a.max_trials<a.trials: ap.error("Invalid trial counts")
    if a.home.upper()==a.away.upper(): ap.error("Home and away teams must differ")
    teams,meta=load_team_stats(a.data)
    if a.home.upper() not in teams or a.away.upper() not in teams: ap.error("Team abbreviation missing from NBA data")
    h,w=teams[a.home.upper()],teams[a.away.upper()]
    kwargs=dict(home_rest=a.home_rest,away_rest=a.away_rest,home_travel=a.home_travel,away_travel=a.away_travel,
                home_injury_points=a.home_injury_points,away_injury_points=a.away_injury_points)
    r=simulate(h,w,a.trials,a.seed,a.spread,a.total,**kwargs)
    close=abs(r["home_margin"]+ (a.spread or 0))<=3
    if a.spread is not None: close=close or 47<=r["home_cover"]<=53
    if a.total is not None: close=close or 47<=r["over"]<=53
    if close and not a.no_auto_refine and a.max_trials>a.trials:
        r=simulate(h,w,a.max_trials,a.seed,a.spread,a.total,**kwargs)
    print("\nDOUG'S ELITE NBA SIMULATOR\n========================="); print(f"{w.name} at {h.name}")
    for t in (h,w):
        print(f"{t.name}: GP {t.games_played} | Pace {t.pace:.1f} | ORtg {t.off_rating:.1f} | DRtg {t.def_rating:.1f} | eFG {t.efg_pct:.3f} | TOV {t.tov_pct:.3f} | ORB {t.orb_pct:.3f} | FT rate {t.ft_rate:.3f} | 3PA rate {t.three_pa_rate if t.three_pa_rate is not None else float('nan'):.3f}")
    print(f"Projected pace {r['pace']:.1f} | Score {h.name} {r['home_points']:.1f} - {w.name} {r['away_points']:.1f}")
    print(f"Projected total {r['total_points']:.1f} | Home margin {r['home_margin']:+.1f}")
    print(f"Trials {r['trials']:,} | Seed {r['seed']} | Margin SD {r['margin_sd']:.1f}")
    print(f"Schedule adjustments: home {r['home_rest_adjustment']:+.2f} pts | away {r['away_rest_adjustment']:+.2f} pts")
    if a.spread is not None:
        hp=_decision(r["home_cover"],r["spread_edge_points"])
        apick=_decision(r["away_cover"],-r["spread_edge_points"])
        print(f"\nSPREAD {a.spread:+.1f}: {h.name} cover {r['home_cover']:.2f}% | {w.name} cover {r['away_cover']:.2f}% | push {r['spread_push']:.2f}%")
        print(f"Home spread edge {r['spread_edge_points']:+.1f} pts | {h.name}: {hp} | {w.name}: {apick}")
        print(f"95% Monte Carlo interval: home {r['home_cover_ci'][0]:.2f}-{r['home_cover_ci'][1]:.2f}% | away {r['away_cover_ci'][0]:.2f}-{r['away_cover_ci'][1]:.2f}%")
    if a.total is not None:
        over_dec=_decision(r["over"],r["total_edge_points"])
        under_dec=_decision(r["under"],-r["total_edge_points"])
        print(f"\nTOTAL {a.total:.1f}: Over {r['over']:.2f}% | Under {r['under']:.2f}% | push {r['total_push']:.2f}%")
        print(f"Model total edge {r['total_edge_points']:+.1f} pts | Over: {over_dec} | Under: {under_dec}")
        print(f"95% Monte Carlo interval: over {r['over_ci'][0]:.2f}-{r['over_ci'][1]:.2f}% | under {r['under_ci'][0]:.2f}-{r['under_ci'][1]:.2f}%")
    f=r["first_half"]
    print(f"\nFIRST HALF projected score: {h.name} {f['home_avg']:.1f} - {w.name} {f['away_avg']:.1f} | Total {f['total_avg']:.1f}")
    if a.spread is not None: print(f"First-half spread cover: home {f['home_cover']:.2f}% | away {f['away_cover']:.2f}% | push {f['spread_push']:.2f}%")
    if a.total is not None: print(f"First-half total: over {f['over']:.2f}% | under {f['under']:.2f}% | push {f['total_push']:.2f}%")
    print(f"\nDATA: {meta.get('season','unknown')} | updated {meta.get('updated_at','unknown')}")
    print("Injury adjustment is manual unless an independently verified report is supplied.")
    print("Model status: estimates require out-of-sample backtesting before being treated as betting edges.")
    if a.json_output:
        payload={"home_team":h.abbreviation,"away_team":w.abbreviation,"season":meta.get("season"),"data_updated_at":meta.get("updated_at"),"spread_line":a.spread,"total_line":a.total,"home_rest":a.home_rest,"away_rest":a.away_rest,"home_travel_miles":a.home_travel,"away_travel_miles":a.away_travel,"home_injury_points":a.home_injury_points,"away_injury_points":a.away_injury_points,"result":r}
        Path(a.json_output).write_text(json.dumps(payload,indent=2)+"\\n",encoding="utf-8")
if __name__=="__main__": main()
