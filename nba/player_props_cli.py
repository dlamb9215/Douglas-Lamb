"""Run experimental NBA player props from a verified JSON input file.

Input JSON: {"player": "...", "team": "...", "status": "available",
"lineup_confirmed": true, "minutes": 34, "minutes_sd": 2.5,
"points_per_minute": 0.72, "rebounds_per_minute": 0.18,
"assists_per_minute": 0.20, "lines": {"points": 24.5}}
"""
import argparse
import json
from pathlib import Path
from nba.elite_analytics import simulate_player_props


def main():
    parser = argparse.ArgumentParser(description="Doug's Elite NBA player-prop experiment")
    parser.add_argument("--input", required=True, help="Verified player projection JSON")
    parser.add_argument("--trials", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="nba-player-props.json")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    lines = payload.pop("lines", {})
    result = simulate_player_props(payload, trials=args.trials, seed=args.seed, lines=lines)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
