"""Persistent NHL pregame forecast ledger and conservative calibration summary."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
import urllib.request

FIELDS = [
    "run_id", "forecasted_at_utc", "game_date", "season", "home", "away",
    "trials", "seed", "home_win_probability", "away_win_probability",
    "home_puck_line_probability", "away_puck_line_probability",
    "total_line", "over_probability", "under_probability", "push_probability",
    "home_ml_odds", "away_ml_odds", "over_odds", "under_odds",
    "home_puck_odds", "away_puck_odds", "sportsbook_source", "odds_checked_at_utc",
    "home_goalie_id", "away_goalie_id", "team_summary_available",
    "actual_home_goals", "actual_away_goals", "settled_at_utc",
]


def _aware_timestamp(value: str, label: str) -> str:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone.")
    return parsed.astimezone(timezone.utc).isoformat()


def append_forecast(payload: dict[str, Any], path: str | Path, run_id: str,
                    game_date: str, odds_source: str = "", odds_checked_at: str = "") -> bool:
    home, away = str(payload.get("home", "")).upper(), str(payload.get("away", "")).upper()
    if not run_id or not home or not away or home == away:
        raise ValueError("Forecast requires run ID and two different teams.")
    trials = int(payload.get("trials", 0))
    if trials < 1000:
        raise ValueError("Forecast must contain at least 1,000 trials.")
    ml = payload.get("moneyline_pct", {})
    puck = payload.get("puck_line_pct", {})
    total = payload.get("total_pct", {})
    for key, value in (("home win", ml.get("home")), ("away win", ml.get("away")),
                       ("home puck line", puck.get("home_minus_1_5")),
                       ("away puck line", puck.get("away_plus_1_5")),
                       ("over", total.get("over")), ("under", total.get("under")),
                       ("push", total.get("push", 0))):
        if value is None or not 0 <= float(value) <= 100:
            raise ValueError(f"Invalid {key} probability.")
    if abs(float(ml["home"]) + float(ml["away"]) - 100) > 1.0:
        raise ValueError("Moneyline probabilities must sum to approximately 100%.")
    prices = payload.get("sportsbook_prices", {})
    any_prices = any(prices.get(k) not in (None, "", 0, "0") for k in
                     ("home_ml", "away_ml", "over", "under", "home_puck", "away_puck"))
    checked = _aware_timestamp(odds_checked_at, "Odds checked-at timestamp") if odds_checked_at else ""
    if any_prices and (not odds_source.strip() or not checked):
        raise ValueError("Sportsbook prices require a source and timezone-aware quote timestamp.")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if target.exists():
        with target.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    if any(row.get("run_id") == str(run_id) for row in rows):
        return False
    dq = payload.get("data_quality", {})
    summary = dq.get("team_summary_features", {})
    summary_ready = all(summary.get(code, {}).get("available") is True for code in (home, away))
    home_goalie = payload.get("goalies", {}).get(home, {}).get("selected") or {}
    away_goalie = payload.get("goalies", {}).get(away, {}).get("selected") or {}
    row = {
        "run_id": str(run_id), "forecasted_at_utc": datetime.now(timezone.utc).isoformat(),
        "game_date": date.fromisoformat(game_date).isoformat(), "season": payload.get("season", ""),
        "home": home, "away": away, "trials": trials, "seed": payload.get("seed", ""),
        "home_win_probability": ml["home"], "away_win_probability": ml["away"],
        "home_puck_line_probability": puck["home_minus_1_5"],
        "away_puck_line_probability": puck["away_plus_1_5"],
        "total_line": payload.get("total_line", ""), "over_probability": total.get("over"),
        "under_probability": total.get("under"), "push_probability": total.get("push", 0),
        "home_ml_odds": prices.get("home_ml", ""), "away_ml_odds": prices.get("away_ml", ""),
        "over_odds": prices.get("over", ""), "under_odds": prices.get("under", ""),
        "home_puck_odds": prices.get("home_puck", ""), "away_puck_odds": prices.get("away_puck", ""),
        "sportsbook_source": odds_source, "odds_checked_at_utc": checked,
        "home_goalie_id": home_goalie.get("id", ""), "away_goalie_id": away_goalie.get("id", ""),
        "team_summary_available": summary_ready,
        "actual_home_goals": "", "actual_away_goals": "", "settled_at_utc": "",
    }
    write_header = not target.exists() or target.stat().st_size == 0
    with target.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return True


def fetch_score(game_date: str) -> dict[str, Any]:
    url = f"https://api-web.nhle.com/v1/score/{game_date}"
    request = urllib.request.Request(url, headers={"User-Agent": "DougsEliteNHL/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def reconcile(path: str | Path, fetcher: Callable[[str], dict[str, Any]] = fetch_score,
              today: date | None = None) -> int:
    target = Path(path)
    if not target.exists():
        return 0
    today = today or datetime.now(timezone.utc).date()
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    cache: dict[str, list[dict[str, Any]]] = {}
    changed = 0
    for row in rows:
        game_day = row.get("game_date", "")
        if row.get("settled_at_utc") or not game_day or date.fromisoformat(game_day) > today:
            continue
        if game_day not in cache:
            payload = fetcher(game_day)
            cache[game_day] = payload.get("games", []) if isinstance(payload, dict) else []
        game = next((g for g in cache[game_day]
                     if str((g.get("homeTeam") or {}).get("abbrev", "")).upper() == row["home"]
                     and str((g.get("awayTeam") or {}).get("abbrev", "")).upper() == row["away"]), None)
        if not game or str(game.get("gameState", "")).upper() not in {"OFF", "FINAL"}:
            continue
        home_score = (game.get("homeTeam") or {}).get("score")
        away_score = (game.get("awayTeam") or {}).get("score")
        if home_score is None or away_score is None:
            continue
        row["actual_home_goals"], row["actual_away_goals"] = int(home_score), int(away_score)
        row["settled_at_utc"] = datetime.now(timezone.utc).isoformat()
        changed += 1
    if changed:
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return changed


def _probability_metrics(probabilities: list[float], outcomes: list[int]) -> dict[str, Any]:
    if not probabilities:
        return {"sample_size": 0, "brier_score": None, "log_loss": None, "expected_calibration_error": None, "bins": []}
    import math
    clipped = [min(1 - 1e-9, max(1e-9, p)) for p in probabilities]
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / len(outcomes)
    log_loss = -sum(y * math.log(p) + (1 - y) * math.log(1 - p)
                    for p, y in zip(clipped, outcomes)) / len(outcomes)
    bins = []
    ece = 0.0
    for lower in range(0, 100, 10):
        members = [(p, y) for p, y in zip(probabilities, outcomes)
                   if lower / 100 <= p < (lower + 10) / 100
                   or (lower == 90 and p == 1.0)]
        if not members:
            continue
        predicted = sum(p for p, _ in members) / len(members)
        observed = sum(y for _, y in members) / len(members)
        ece += len(members) / len(probabilities) * abs(predicted - observed)
        bins.append({"range": f"{lower}-{lower + 10}%", "count": len(members),
                     "mean_probability": round(predicted, 4),
                     "observed_rate": round(observed, 4)})
    return {"sample_size": len(probabilities), "brier_score": round(brier, 6),
            "log_loss": round(log_loss, 6), "expected_calibration_error": round(ece, 6),
            "bins": bins}


def calibration_summary(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {"settled_games": 0, "calibration_status": "INSUFFICIENT_SAMPLE",
                "markets": {}, "calibrated": False}
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    settled = [r for r in rows if r.get("settled_at_utc")
               and r.get("actual_home_goals") not in ("", None)
               and r.get("actual_away_goals") not in ("", None)]
    if not settled:
        return {"settled_games": 0, "calibration_status": "INSUFFICIENT_SAMPLE",
                "markets": {}, "calibrated": False}
    home_ml_p, home_ml_y = [], []
    puck_p, puck_y = [], []
    total_p, total_y = [], []
    for row in settled:
        hg, ag = int(row["actual_home_goals"]), int(row["actual_away_goals"])
        margin, goals = hg - ag, hg + ag
        if row.get("home_win_probability") not in ("", None) and hg != ag:
            home_ml_p.append(float(row["home_win_probability"]) / 100)
            home_ml_y.append(1 if hg > ag else 0)
        if row.get("home_puck_line_probability") not in ("", None):
            puck_p.append(float(row["home_puck_line_probability"]) / 100)
            puck_y.append(1 if margin > 1.5 else 0)
        if row.get("over_probability") not in ("", None) and row.get("total_line") not in ("", None):
            line = float(row["total_line"])
            if goals != line:
                total_p.append(float(row["over_probability"]) / 100)
                total_y.append(1 if goals > line else 0)
    markets = {
        "moneyline_home": _probability_metrics(home_ml_p, home_ml_y),
        "home_puck_line_minus_1_5": _probability_metrics(puck_p, puck_y),
        "total_over": _probability_metrics(total_p, total_y),
    }
    return {
        "settled_games": len(settled),
        "home_moneyline_brier": markets["moneyline_home"]["brier_score"],
        "markets": markets,
        "calibration_status": "INSUFFICIENT_SAMPLE" if len(settled) < 100 else "REVIEW_REQUIRED",
        "calibrated": False,
        "note": "Descriptive market-specific metrics only. Require chronological holdout, market comparison, sufficient samples and manual review before betting approval.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Append and reconcile NHL pregame forecasts.")
    parser.add_argument("--payload", default="")
    parser.add_argument("--ledger", default="nhl/ledger/predictions.csv")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--game-date", default="")
    parser.add_argument("--odds-source", default="")
    parser.add_argument("--odds-checked-at", default="")
    parser.add_argument("--reconcile", action="store_true")
    args = parser.parse_args()
    if args.reconcile:
        try:
            count = reconcile(args.ledger)
            print(f"NHL forecasts reconciled: {count}")
        except Exception as exc:
            print(f"NHL reconciliation unavailable: {exc}")
    if args.payload:
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
        if not args.game_date:
            raise SystemExit("--game-date is required when appending a forecast.")
        added = append_forecast(payload, args.ledger, args.run_id, args.game_date,
                                args.odds_source, args.odds_checked_at)
        print("NHL forecast appended." if added else "NHL forecast already recorded.")
    print(json.dumps(calibration_summary(args.ledger), indent=2))


if __name__ == "__main__":
    main()
