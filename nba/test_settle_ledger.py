import csv
import tempfile
import unittest
from pathlib import Path

from nba.prediction_ledger import FIELDS
from nba.settle_ledger import settle_ledger


class TestSettleLedger(unittest.TestCase):
    def write_ledger(self, folder):
        path = Path(folder) / "predictions.csv"
        row = {field: "" for field in FIELDS}
        row.update({
            "forecast_id": "run-1:event-1:BOS:NYK", "game_date": "2026-11-12",
            "event_id": "event-1", "home_team": "BOS", "away_team": "NYK",
            "projected_home": "112.5", "projected_away": "108.0",
        })
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerow(row)
        return path

    def event(self, home="BOS", away="NYK", completed=True):
        return {
            "id": "event-1", "date": "2026-11-13T01:00:00Z",
            "status": {"type": {"state": "post" if completed else "in", "completed": completed}},
            "competitions": [{
                "date": "2026-11-13T01:00:00Z", "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": home}, "score": "112"},
                    {"homeAway": "away", "team": {"abbreviation": away}, "score": "108"},
                ],
                "status": {"type": {"state": "post" if completed else "in", "completed": completed}},
            }],
        }

    def test_missing_ledger_is_a_safe_noop(self):
        with tempfile.TemporaryDirectory() as folder:
            result = settle_ledger(str(Path(folder) / "not-created.csv"), lambda day: [])
        self.assertEqual(result["status"], "ledger_not_created_yet")
        self.assertEqual(result["settled"], 0)

    def test_settles_only_completed_matching_event(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_ledger(folder)
            result = settle_ledger(str(path), lambda day: [self.event()])
            self.assertEqual(result["settled"], 1, result)
            with path.open(newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["actual_home"], "112")
            self.assertEqual(row["actual_away"], "108")
            self.assertTrue(row["settled_at"])

    def test_does_not_settle_wrong_team_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_ledger(folder)
            result = settle_ledger(str(path), lambda day: [self.event(home="MIA")])
            self.assertEqual(result["settled"], 0)
            self.assertTrue(result["errors"])

    def test_leaves_unfinished_event_pending(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write_ledger(folder)
            result = settle_ledger(str(path), lambda day: [self.event(completed=False)])
            self.assertEqual(result["settled"], 0)
            self.assertEqual(result["pending"], 1)


if __name__ == "__main__":
    unittest.main()
