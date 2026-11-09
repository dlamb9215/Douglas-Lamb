"""Evaluate archived NBA predictions against final scores and closing markets.

CSV columns required: projected_home, projected_away, actual_home, actual_away.
Optional: home_win_probability, spread, total, home_cover_probability, over_probability,
closing_spread, closing_total. Probabilities are percentages (0-100).
"""
import argparse, csv, json, math
from pathlib import Path

def mean(values):
    return sum(values)/len(values) if values else None

def calibration(rows,key,outcome):
    bins=[]
    for low in range(0,100,10):
        group=[r for r in rows if r.get(key) is not None and low<=r[key]<low+10]
        if group:
            bins.append({"range":f"{low}-{low+10}%","count":len(group),
                         "mean_probability":mean([r[key] for r in group]),
                         "observed_rate":mean([r[outcome] for r in group])*100})
    return bins

def evaluate(path):
    with open(path,newline="",encoding="utf-8") as f: raw=list(csv.DictReader(f))
    if not raw: raise ValueError("No archived game rows found")
    rows=[]
    for i,r in enumerate(raw,2):
        try:
            ph=float(r["projected_home"]); pa=float(r["projected_away"])
            ah=float(r["actual_home"]); aa=float(r["actual_away"])
        except (KeyError,TypeError,ValueError) as e:
            raise ValueError(f"Invalid required prediction/score values on CSV row {i}: {e}")
        item={"projected_home":ph,"projected_away":pa,"actual_home":ah,"actual_away":aa,
              "predicted_total":ph+pa,"actual_total":ah+aa,
              "predicted_margin":ph-pa,"actual_margin":ah-aa}
        for key in ("home_win_probability","spread","total","home_cover_probability","over_probability","closing_spread","closing_total"):
            try: item[key]=float(r[key]) if r.get(key,"").strip() else None
            except ValueError: item[key]=None
        for probability_key in ("home_win_probability", "home_cover_probability", "over_probability"):
            probability = item.get(probability_key)
            if probability is not None and not 0 <= probability <= 100:
                raise ValueError(f"{probability_key} outside 0-100 on CSV row {i}")
        item["home_win"] = (1 if item["actual_home"] > item["actual_away"] else 0) if item["actual_home"] != item["actual_away"] else None
        if item["spread"] is not None:
            item["home_cover"] = 1 if item["actual_margin"]+item["spread"]>0 else 0 if item["actual_margin"]+item["spread"]<0 else None
        if item["total"] is not None:
            item["over"] = 1 if item["actual_total"]>item["total"] else 0 if item["actual_total"]<item["total"] else None
        rows.append(item)
    result={"games":len(rows),
      "home_points_mae":mean([abs(x["projected_home"]-x["actual_home"]) for x in rows]),
      "away_points_mae":mean([abs(x["projected_away"]-x["actual_away"]) for x in rows]),
      "total_points_mae":mean([abs(x["predicted_total"]-x["actual_total"]) for x in rows]),
      "margin_mae":mean([abs(x["predicted_margin"]-x["actual_margin"]) for x in rows]),
      "total_bias":mean([x["predicted_total"]-x["actual_total"] for x in rows]),
      "moneyline_games":sum(x.get("home_win") is not None for x in rows),
      "spread_games":sum(x.get("home_cover") is not None for x in rows),
      "total_games":sum(x.get("over") is not None for x in rows)}
    for key,outcome,name in (("home_win_probability","home_win","moneyline"),("home_cover_probability","home_cover","spread"),("over_probability","over","total")):
        eligible=[x for x in rows if x.get(key) is not None and x.get(outcome) is not None]
        if eligible:
            probs=[x[key]/100 for x in eligible]; actual=[x[outcome] for x in eligible]
            clipped=[min(.999999,max(.000001,p)) for p in probs]
            result[name+"_brier"]=mean([(p-y)**2 for p,y in zip(probs,actual)])
            result[name+"_log_loss"]=mean([-(y*math.log(p)+(1-y)*math.log(1-p)) for p,y in zip(clipped,actual)])
            result[name+"_calibration"]=calibration(eligible,key,outcome)
            result[name+"_hit_rate"]=mean(actual)*100
    spread_clv=[x["closing_spread"]-x["spread"] for x in rows if x.get("closing_spread") is not None and x.get("spread") is not None]
    total_clv=[x["closing_total"]-x["total"] for x in rows if x.get("closing_total") is not None and x.get("total") is not None]
    if spread_clv: result["mean_closing_spread_minus_opening_spread"]=mean(spread_clv)
    if total_clv: result["mean_closing_total_minus_opening_total"]=mean(total_clv)
    return result

def main():
    p=argparse.ArgumentParser(description="Backtest archived Doug's Elite NBA Simulator predictions")
    p.add_argument("--csv",required=True); p.add_argument("--output",default="nba-backtest-report.json")
    a=p.parse_args(); report=evaluate(a.csv)
    Path(a.output).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__": main()
