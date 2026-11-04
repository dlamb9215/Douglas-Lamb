"""Refresh NBA team metrics from NBA.com Stats; preserve last good data on failure."""
import json, os, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

URL="https://stats.nba.com/stats/leaguedashteamstats"
HEADERS={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
"Referer":"https://www.nba.com/","Origin":"https://www.nba.com","x-nba-stats-origin":"stats",
"x-nba-stats-token":"true","Accept":"application/json, text/plain, */*"}

def fetch(season,measure):
    p={"LeagueID":"00","Season":season,"SeasonType":"Regular Season","PerMode":"PerGame",
       "MeasureType":measure,"PlusMinus":"N","PaceAdjust":"N","Rank":"N","LastNGames":"0",
       "Month":"0","OpponentTeamID":"0","Period":"0","TeamID":"0","DateFrom":"","DateTo":"",
       "Location":"","Outcome":"","SeasonSegment":"","VsConference":"","VsDivision":""}
    req=Request(URL+"?"+urlencode(p),headers=HEADERS)
    with urlopen(req,timeout=45) as response: data=json.loads(response.read().decode())
    sets=data.get("resultSets") or data.get("resultSet")
    if not sets: raise RuntimeError(f"No result set for {season}/{measure}")
    rows={}
    for row in sets[0]["rowSet"]:
        item=dict(zip(sets[0]["headers"],row))
        code=str(item.get("TEAM_ABBREVIATION","")).upper()
        if code: rows[code]=item
    if len(rows)!=30: raise RuntimeError(f"Incomplete {season}/{measure}: got {len(rows)} teams")
    return rows

def val(row,*keys):
    for k in keys:
        if row.get(k) is not None: return float(row[k])
    return None

def normalize(season):
    adv=fetch(season,"Advanced"); time.sleep(1.5); ff=fetch(season,"Four Factors")
    out={}
    for code,a in adv.items():
        f=ff[code]
        out[code]={"name":a.get("TEAM_NAME",code),"games_played":int(a.get("GP") or 0),
        "pace":val(a,"PACE"),"off_rating":val(a,"OFF_RATING","E_OFF_RATING"),
        "def_rating":val(a,"DEF_RATING","E_DEF_RATING"),"efg_pct":val(f,"EFG_PCT"),
        "tov_pct":val(f,"TM_TOV_PCT","TOV_PCT"),"orb_pct":val(f,"OREB_PCT","ORB_PCT"),
        "ft_rate":val(f,"FTA_RATE","FT_RATE"),"opp_efg_pct":val(f,"OPP_EFG_PCT"),
        "opp_tov_pct":val(f,"OPP_TOV_PCT"),"opp_orb_pct":val(f,"OPP_OREB_PCT","OPP_ORB_PCT"),
        "opp_ft_rate":val(f,"OPP_FTA_RATE","OPP_FT_RATE")}
        missing=[k for k,v in out[code].items() if v is None and k!="name"]
        if missing: raise RuntimeError(f"{code} missing metrics: {missing}")
    return out

def main():
    season=os.getenv("NBA_SEASON","2026-27"); prior_season=os.getenv("NBA_PRIOR_SEASON","2025-26")
    path=Path(os.getenv("NBA_DATA_PATH","nba/team_stats.json"))
    current=normalize(season); prior=normalize(prior_season)
    if set(current)!=set(prior): raise RuntimeError("Current and prior season team sets differ")
    keys=("pace","off_rating","def_rating","efg_pct","tov_pct","orb_pct","ft_rate","opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ft_rate")
    teams={}
    for code,row in current.items():
        gp=max(0,row["games_played"]); blended=dict(row)
        for k in keys: blended[k]=(row[k]*gp+prior[code][k]*8)/(gp+8)
        blended["prior_season_weight_games"]=8
        teams[code]=blended
    payload={"league":"NBA","season":season,"prior_season":prior_season,
      "updated_at":datetime.now(timezone.utc).isoformat(),
      "source":"NBA.com Stats Advanced + Four Factors dashboards",
      "early_sample_method":"Current season blended with prior season using an eight-game prior weight.",
      "teams":teams}
    if len(teams)!=30: raise RuntimeError("Refusing to write incomplete team data")
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    json.loads(tmp.read_text(encoding="utf-8")); tmp.replace(path)
    print(f"Updated {path}: {len(teams)} teams, season {season}")
if __name__=="__main__": main()
