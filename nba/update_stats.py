"""Refresh NBA team metrics from NBA.com Stats.

All requests are validated before the previous data file is replaced. Current-season
recent and home/road splits are blended with season-level and prior-season baselines.
"""
import json, os, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

URL="https://stats.nba.com/stats/leaguedashteamstats"
HEADERS={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
"Referer":"https://www.nba.com/","Origin":"https://www.nba.com","x-nba-stats-origin":"stats",
"x-nba-stats-token":"true","Accept":"application/json, text/plain, */*"}

def fetch(season,measure,last_n=0,location=""):
    params={"LeagueID":"00","Season":season,"SeasonType":"Regular Season","PerMode":"PerGame",
      "MeasureType":measure,"PlusMinus":"N","PaceAdjust":"N","Rank":"N","LastNGames":str(last_n),
      "Month":"0","OpponentTeamID":"0","Period":"0","TeamID":"0","DateFrom":"","DateTo":"",
      "Location":location,"Outcome":"","SeasonSegment":"","VsConference":"","VsDivision":""}
    req=Request(URL+"?"+urlencode(params),headers=HEADERS)
    last_error=None
    for attempt in range(3):
        try:
            with urlopen(req,timeout=45) as response: data=json.loads(response.read().decode())
            sets=data.get("resultSets") or data.get("resultSet")
            if not sets: raise RuntimeError(f"No result set for {season}/{measure}")
            rows={}
            for row in sets[0]["rowSet"]:
                item=dict(zip(sets[0]["headers"],row))
                code=str(item.get("TEAM_ABBREVIATION","")).upper()
                if code: rows[code]=item
            if len(rows)!=30: raise RuntimeError(f"Incomplete {season}/{measure}/{location}/{last_n}: {len(rows)} teams")
            return rows
        except Exception as exc:
            last_error=exc
            if attempt<2: time.sleep(3*(attempt+1))
    raise RuntimeError(f"NBA Stats request failed after retries: {last_error}")

def val(row,*keys):
    for k in keys:
        if row.get(k) is not None: return float(row[k])
    return None

def metric_row(advanced,factors=None):
    row={"name":advanced.get("TEAM_NAME"),"games_played":int(advanced.get("GP") or 0),
         "pace":val(advanced,"PACE","E_PACE"),
         "off_rating":val(advanced,"OFF_RATING","E_OFF_RATING"),
         "def_rating":val(advanced,"DEF_RATING","E_DEF_RATING")}
    if factors is not None:
        row.update({"efg_pct":val(factors,"EFG_PCT"),
          "tov_pct":val(factors,"TM_TOV_PCT","TOV_PCT"),
          "orb_pct":val(factors,"OREB_PCT","ORB_PCT"),
          "ft_rate":val(factors,"FTA_RATE","FT_RATE"),
          "opp_efg_pct":val(factors,"OPP_EFG_PCT"),
          "opp_tov_pct":val(factors,"OPP_TOV_PCT"),
          "opp_orb_pct":val(factors,"OPP_OREB_PCT","OPP_ORB_PCT"),
          "opp_ft_rate":val(factors,"OPP_FTA_RATE","OPP_FT_RATE")})
    return row


def fetch_score_sd(season):
    params={"PlayerOrTeam":"T","Season":season,"SeasonType":"Regular Season","LeagueID":"00","TeamID":"0"}
    req=Request("https://stats.nba.com/stats/leaguegamefinder?"+urlencode(params),headers=HEADERS)
    last_error=None
    for attempt in range(3):
        try:
            with urlopen(req,timeout=45) as response: data=json.loads(response.read().decode())
            sets=data.get("resultSets") or data.get("resultSet")
            if not sets: raise RuntimeError("LeagueGameFinder returned no result set")
            headers=sets[0]["headers"]; rows=sets[0]["rowSet"]
            points={}
            for values in rows:
                item=dict(zip(headers,values))
                code=str(item.get("TEAM_ABBREVIATION","")).upper()
                score=item.get("PTS")
                if code and score is not None: points.setdefault(code,[]).append(float(score))
            if len(points)<30: raise RuntimeError(f"Game log contains only {len(points)} teams")
            return {code:float(__import__("statistics").pstdev(scores)) for code,scores in points.items() if len(scores)>=2}
        except Exception as exc:
            last_error=exc
            if attempt<2: time.sleep(3*(attempt+1))
    raise RuntimeError(f"LeagueGameFinder failed for {season}: {last_error}")

def main():
    season=os.getenv("NBA_SEASON","2026-27")
    prior_season=os.getenv("NBA_PRIOR_SEASON","2025-26")
    path=Path(os.getenv("NBA_DATA_PATH","nba/team_stats.json"))
    # Prior-year baseline.
    prior_adv=fetch(prior_season,"Advanced"); time.sleep(1.2)
    prior_ff=fetch(prior_season,"Four Factors"); time.sleep(1.2)
    prior_base=fetch(prior_season,"Base"); time.sleep(1.2)
    prior_opp=fetch(prior_season,"Opponent"); time.sleep(1.2)
    # Current full-season, recent form and venue splits.
    cur_adv=fetch(season,"Advanced"); time.sleep(1.2)
    cur_ff=fetch(season,"Four Factors"); time.sleep(1.2)
    cur_base=fetch(season,"Base"); time.sleep(1.2)
    cur_opp=fetch(season,"Opponent"); time.sleep(1.2)
    recent_adv=fetch(season,"Advanced",last_n=10); time.sleep(1.2)
    home_adv=fetch(season,"Advanced",location="Home"); time.sleep(1.2)
    road_adv=fetch(season,"Advanced",location="Road"); time.sleep(1.2)
    current_score_sd=fetch_score_sd(season); time.sleep(1.2)
    prior_score_sd=fetch_score_sd(prior_season)
    team_codes=set(cur_adv)
    if any(set(x)!=team_codes for x in (cur_ff,prior_adv,prior_ff,cur_base,cur_opp,prior_base,prior_opp,recent_adv,home_adv,road_adv,current_score_sd,prior_score_sd)):
        raise RuntimeError("Team sets differ between NBA Stats queries; preserving previous data.")
    teams={}
    for code in sorted(team_codes):
        now=metric_row(cur_adv[code],cur_ff[code])
        prior=metric_row(prior_adv[code],prior_ff[code])
        recent=metric_row(recent_adv[code])
        home=metric_row(home_adv[code])
        road=metric_row(road_adv[code])
        gp=max(0,now["games_played"])
        # Eight-game prior-season weight prevents early-season overreaction.
        row=dict(now)
        def ratio(source,numerator,denominator):
            n=val(source,numerator); d=val(source,denominator)
            return n/d if n is not None and d else None
        shot_values={
            "three_pa_rate":ratio(cur_base[code],"FG3A","FGA"),
            "fg3_pct":val(cur_base[code],"FG3_PCT"),
            "opp_three_pa_rate":ratio(cur_opp[code],"OPP_FG3A","OPP_FGA"),
            "opp_fg3_pct":val(cur_opp[code],"OPP_FG3_PCT")}
        prior_shot_values={
            "three_pa_rate":ratio(prior_base[code],"FG3A","FGA"),
            "fg3_pct":val(prior_base[code],"FG3_PCT"),
            "opp_three_pa_rate":ratio(prior_opp[code],"OPP_FG3A","OPP_FGA"),
            "opp_fg3_pct":val(prior_opp[code],"OPP_FG3_PCT")}
        for key,value in shot_values.items():
            prior_value=prior_shot_values[key]
            if value is not None and prior_value is not None:
                row[key]=(value*gp+prior_value*8)/(gp+8)
            elif value is not None: row[key]=value
            elif prior_value is not None: row[key]=prior_value
        for key in ("pace","off_rating","def_rating","efg_pct","tov_pct","orb_pct","ft_rate",
                    "opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ft_rate"):
            row[key]=(now[key]*gp+prior[key]*8)/(gp+8)
        # Recent ten-game trend is shrunk 30% toward the full-season estimate.
        for key in ("pace","off_rating","def_rating"):
            if recent[key] is not None:
                row["recent_"+key]=.70*recent[key]+.30*row[key]
        # Venue splits are used only after at least 3 games at that venue.
        for prefix,venue in (("home",home),("road",road)):
            if venue["games_played"]>=3:
                for key in ("off_rating","def_rating"):
                    row[prefix+"_"+key]=(venue[key]*venue["games_played"]+row[key]*5)/(venue["games_played"]+5)
            else:
                row[prefix+"_off_rating"]=row["off_rating"]
                row[prefix+"_def_rating"]=row["def_rating"]
        row["score_sd"]=((current_score_sd[code]**2*gp+prior_score_sd[code]**2*8)/(gp+8))**.5
        row["prior_season_weight_games"]=8
        row["recent_form_shrinkage"]=.30
        teams[code]=row
    if len(teams)!=30: raise RuntimeError(f"Expected 30 teams, received {len(teams)}")
    payload={"league":"NBA","season":season,"prior_season":prior_season,
      "updated_at":datetime.now(timezone.utc).isoformat(),
      "source":"NBA.com Stats LeagueDashTeamStats Advanced and Four Factors",
      "methods":{"prior_season_weight_games":8,"recent_form_weight":.70,
                 "recent_form_prior_weight":.30,"venue_split_prior_games":5,
                 "venue_split_min_games":3},
      "teams":teams}
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    parsed=json.loads(tmp.read_text(encoding="utf-8"))
    if len(parsed["teams"])!=30: raise RuntimeError("Output validation failed")
    for code,row in parsed["teams"].items():
        required=("pace","off_rating","def_rating","efg_pct","tov_pct","orb_pct","ft_rate",
                  "opp_efg_pct","opp_tov_pct","opp_orb_pct","opp_ft_rate")
        if any(row.get(k) is None for k in required): raise RuntimeError(f"{code} incomplete output")
    tmp.replace(path)
    print(f"Updated {path}: {len(teams)} teams, season {season}, prior {prior_season}")
if __name__=="__main__": main()
