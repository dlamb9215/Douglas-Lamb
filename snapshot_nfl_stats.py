"""Archive the current validated NFL team-stat file as an immutable snapshot."""
import json
from datetime import datetime, timezone
from pathlib import Path

from nfl_data import validate_source_data

SOURCE = Path("nfl_team_stats.json")
SNAPSHOT_DIR = Path("data_snapshots")


def main():
    records = json.loads(SOURCE.read_text(encoding="utf-8"))
    validate_source_data(records)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = SNAPSHOT_DIR / f"nfl_team_stats_{timestamp}.json"
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite snapshot: {destination}")
    destination.write_text(
        json.dumps(records, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Archived {len(records)} teams to {destination}")


if __name__ == "__main__":
    main()
