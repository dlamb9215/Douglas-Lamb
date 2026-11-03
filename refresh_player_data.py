"""Refresh the cached player pool from nflverse."""
import argparse
from nfl_player_data import fetch_player_pool, save_player_pool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int)
    parser.add_argument("--weeks", type=int, default=5)
    parser.add_argument("--output", default="player_pool.json")
    args = parser.parse_args()
    data = fetch_player_pool(args.season, args.weeks)
    save_player_pool(data, args.output)
    print("NFL PLAYER DATA REFRESH")
    print(f"Season: {data['season']}")
    print(f"Recent weeks: {data['last_n_weeks']}")
    print(f"Players: {data['player_count']}")
    print(f"Depth-chart first listed: {data['eligible_depth_chart_first_players']}")
    print(f"Retrieved: {data['retrieved_at_utc']}")
    print(data["warning"])


if __name__ == "__main__":
    main()
