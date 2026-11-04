"""Doug's Elite NBA Simulator: pace/efficiency Monte Carlo engine."""
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
    abbreviation:str; name:str; games_played:int; pace:float; off_rating:float; def_rating:float
    efg_pct:float; tov_pct:float; orb_pct:float; ft_rate:float
    opp_efg_pct:float; opp_tov_pct:float; opp_orb_pct:float; opp_ft_rate:float
    @classmethod
    def from_dict(cls,code:str,raw:dict[str,Any]):
        keys=("pace","off_rating","def_rating","efg_pct","tov_pct","orb_pct","ft_rate","opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ft_rate")
        missing=[k for k in keys if raw.get(k) is None]
        if missing: raise ValueError(f"{code} missing metrics: {', '.join(missing)}")
        v={k:float(raw[k]) for k in keys}
        for k in keys:
            if (k.endswith("_pct") or k.endswith("_rate")) and v[k]>1: v[k]/=100
        if not 70<=v["pace"]<=115: raise ValueError(f"{code} pace outside plausible range")
        for k in ("off_rating","def_rating"):
            if not 80<=v[k]<=140: raise ValueError(f"{code} {k} outside plausible range")
        for k in keys:
            if (k.endswith("_pct") or k.endswith("_rate")) and not 0<=v[k]<=1: raise ValueError(f"{code} {k} must be 0-1 or 0-100")
        gp=int(raw.get("games_played",raw.get("gp",0)))
        if gp<0: raise ValueError("games_played cannot be negative")
        return cls(code.upper(),str(raw.get("name",code.upper())),gp,**v)

def load_team_stats(path="nba/team_stats.json"):
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(f"{p} missing. Run Update NBA Statistics first.")
    data=json.loads(p.read_text(encoding="utf-8")); raw=data.get("teams",{})
    if not isinstance(raw,dict) or not raw: raise ValueError("Data file has no teams")
    return {k.upper():TeamStats.from_dict(k,v) for k,v in raw.items()},data

def factor_adjustment(t,o):
    own=38*(t.efg_pct-LEAGUE["efg_pct"])-24*(t.tov_pct-LEAGUE["tov_pct"])+15*(t.orb_pct-LEAGUE["orb_pct"])+10*(t.ft_rate-LEAGUE["ft_rate"])
    defense=30*(o.opp_efg_pct-LEAGUE["opp_efg_pct"])-18*(o.opp_tov_pct-LEAGUE["opp_tov_pct"])+10*(o.opp_orb_pct-LEAGUE["opp_orb_pct"])+8*(o.opp_ft_rate-LEAGUE["opp_ft_rate"])
    return own+defense

def matchup_projection(home,away):
    pace=(home.pace+away.pace)/2
    he=(home.off_rating+away.def_rating)/2+factor_adjustment(home,away)+1.35
    ae=(away.off_rating+home.def_rating)/2+factor_adjustment(away,home)
    hp,ap=pace*he/100,pace*ae/100
    return {"pace":pace,"home_efficiency":he,"away_efficiency":ae,"home_points":hp,"away_points":ap,"home_margin":hp-ap,"total_points":hp+ap}

def simulate(home,away,trials=1_000_000,seed=42,spread=None,total=None):
    if trials<1: raise ValueError("trials must be positive")
    p=matchup_projection(home,away); rng=np.random.default_rng(seed)
    poss=np.maximum(1,rng.normal(p["pace"],3,trials))
    hs=np.maximum(0,np.rint(rng.normal(poss*p["home_efficiency"]/100,np.sqrt(poss)*1.55))).astype(np.int32)
    aws=np.maximum(0,np.rint(rng.normal(poss*p["away_efficiency"]/100,np.sqrt(poss)*1.55))).astype(np.int32)
    tie=hs==aws
    if np.any(tie):
        hw=rng.random(int(tie.sum()))<p["home_efficiency"]/(p["home_efficiency"]+p["away_efficiency"])
        hs[tie]+=hw.astype(np.int32); aws[tie]+=(~hw).astype(np.int32)
    margin=hs-aws; combined=hs+aws
    r={**p,"trials":trials,"seed":seed,"home_win":float(np.mean(margin>0)*100),"away_win":float(np.mean(margin<0)*100),
       "home_avg":float(np.mean(hs)),"away_avg":float(np.mean(aws)),"total_avg":float(np.mean(combined))}
    if spread is not None:
        m=margin+spread
        r.update({"spread":spread,"home_cover":float(np.mean(m>0)*100),"away_cover":float(np.mean(m<0)*100),"spread_push":float(np.mean(m==0)*100)})
    if total is not None:
        r.update({"total":total,"over":float(np.mean(combined>total)*100),"under":float(np.mean(combined<total)*100),"total_push":float(np.mean(combined==total)*100)})
    rngh=np.random.default_rng(seed+1); poss_h=np.maximum(1,rngh.normal(p["pace"]/2,2,trials))
    hh=np.maximum(0,np.rint(rngh.normal(p["home_points"]/2,np.sqrt(poss_h)*1.05)))
    ah=np.maximum(0,np.rint(rngh.normal(p["away_points"]/2,np.sqrt(poss_h)*1.05)))
    r["first_half"]={"home_win":float(np.mean(hh>ah)*100),"away_win":float(np.mean(ah>hh)*100),"home_avg":float(np.mean(hh)),"away_avg":float(np.mean(ah)),"total_avg":float(np.mean(hh+ah))}
    return r

def implied_probability(odds):
    if odds==0: raise ValueError("American odds cannot be zero")
    return 100/(odds+100) if odds>0 else abs(odds)/(abs(odds)+100)

def main():
    ap=argparse.ArgumentParser(description="Doug's Elite NBA Simulator")
    ap.add_argument("--home",required=True); ap.add_argument("--away",required=True); ap.add_argument("--data",default="nba/team_stats.json")
    ap.add_argument("--spread",type=float,help="Home team spread, e.g. -4.5"); ap.add_argument("--total",type=float)
    ap.add_argument("--home-odds",type=int); ap.add_argument("--away-odds",type=int); ap.add_argument("--over-odds",type=int); ap.add_argument("--under-odds",type=int)
    ap.add_argument("--trials",type=int,default=1_000_000); ap.add_argument("--max-trials",type=int,default=5_000_000)
    ap.add_argument("--seed",type=int,default=42); ap.add_argument("--no-auto-refine",action="store_true")
    a=ap.parse_args()
    if a.trials<1 or a.max_trials<a.trials: ap.error("Invalid trial counts")
    if a.home.upper()==a.away.upper(): ap.error("Home and away teams must differ")
    teams,meta=load_team_stats(a.data)
    if a.home.upper() not in teams or a.away.upper() not in teams: ap.error("Team abbreviation missing from NBA data")
    h,w=teams[a.home.upper()],teams[a.away.upper()]
    r=simulate(h,w,a.trials,a.seed,a.spread,a.total)
    close=abs(r["home_margin"])<=3
    if a.spread is not None: close=close or 47<=r["home_cover"]<=53
    if a.total is not None: close=close or 47<=r["over"]<=53
    if close and not a.no_auto_refine and a.max_trials>a.trials: r=simulate(h,w,a.max_trials,a.seed,a.spread,a.total)
    print("\nDOUG'S ELITE NBA SIMULATOR\n========================="); print(f"{w.name} at {h.name}")
    for t in (h,w): print(f"{t.name}: GP {t.games_played} | Pace {t.pace:.1f} | ORtg {t.off_rating:.1f} | DRtg {t.def_rating:.1f} | eFG {t.efg_pct:.3f} | TOV {t.tov_pct:.3f} | ORB {t.orb_pct:.3f} | FT rate {t.ft_rate:.3f}")
    print(f"Projected pace {r['pace']:.1f} | Score {h.name} {r['home_points']:.1f} - {w.name} {r['away_points']:.1f} | Total {r['total_points']:.1f}")
    print(f"Trials {r['trials']:,} | Seed {r['seed']} | ML {h.name} {r['home_win']:.2f}% / {w.name} {r['away_win']:.2f}%")
    if "home_cover" in r: print(f"Spread {r['spread']:+.1f}: Home {r['home_cover']:.2f}% | Away {r['away_cover']:.2f}% | Push {r['spread_push']:.2f}%")
    if "over" in r: print(f"Total {r['total']:.1f}: Over {r['over']:.2f}% | Under {r['under']:.2f}% | Push {r['total_push']:.2f}%")
    f=r["first_half"]; print(f"First half: {h.name} win {f['home_win']:.2f}% / {w.name} win {f['away_win']:.2f}% | Score {f['home_avg']:.1f}-{f['away_avg']:.1f}")
    print(f"Data season {meta.get('season','unknown')} | updated {meta.get('updated_at','unknown')}")
    print("Limitations: team-level only; no player minutes, injuries, confirmed starters or player props yet.")
    if a.home_odds is not None and a.away_odds is not None:
        x,y=implied_probability(a.home_odds),implied_probability(a.away_odds); z=x+y
        print(f"Vig-free ML: Home {x/z*100:.2f}% (edge {r['home_win']-x/z*100:+.2f}pp), Away {y/z*100:.2f}% (edge {r['away_win']-y/z*100:+.2f}pp)")
    if a.over_odds is not None and a.under_odds is not None and "over" in r:
        x,y=implied_probability(a.over_odds),implied_probability(a.under_odds); z=x+y
        print(f"Vig-free total: Over {x/z*100:.2f}% (edge {r['over']-x/z*100:+.2f}pp), Under {y/z*100:.2f}% (edge {r['under']-y/z*100:+.2f}pp)")
if __name__=="__main__": main()
