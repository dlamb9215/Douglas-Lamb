import csv
import tempfile
import unittest
from pathlib import Path
from nba.player_props_backtest import evaluate

class TestPlayerPropBacktest(unittest.TestCase):
    def test_metrics_and_push_exclusion(self):
        rows = [
            {"player":"A","stat":"points","projection":24,"actual":27,"line":24.5,"over_probability":60},
            {"player":"B","stat":"points","projection":20,"actual":18,"line":21.5,"over_probability":40},
            {"player":"C","stat":"points","projection":22,"actual":22,"line":22,"over_probability":50},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"props.csv"
            with path.open("w",newline="",encoding="utf-8") as handle:
                writer=csv.DictWriter(handle,fieldnames=rows[0].keys())
                writer.writeheader(); writer.writerows(rows)
            report=evaluate(path)
        self.assertEqual(report["total_rows"],2)
        self.assertEqual(report["by_stat"]["points"]["bets"],2)
        self.assertIn("over_brier",report["by_stat"]["points"])

    def test_excludes_postgame_forecasts_and_reports_sample_gate(self):
        rows=[
            {"forecast_id":"pre","player":"A","stat":"points","projection":24,"actual":27,"line":24.5,
             "over_probability":60,"forecasted_at":"2026-11-12T18:00:00Z","game_start_time":"2026-11-12T23:00:00Z"},
            {"forecast_id":"late","player":"B","stat":"points","projection":20,"actual":18,"line":21.5,
             "over_probability":40,"forecasted_at":"2026-11-12T23:30:00Z","game_start_time":"2026-11-12T23:00:00Z"},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"props.csv"
            with path.open("w",newline="",encoding="utf-8") as handle:
                writer=csv.DictWriter(handle,fieldnames=rows[0].keys())
                writer.writeheader(); writer.writerows(rows)
            report=evaluate(path)
        self.assertEqual(report["total_rows"],1)
        self.assertEqual(report["postgame_rows_excluded"],1)
        self.assertFalse(report["calibration_ready"])
        self.assertFalse(report["by_stat"]["points"]["sample_sufficient_for_review"])

    def test_rejects_duplicate_forecast_ids(self):
        row={"forecast_id":"same","player":"A","stat":"points","projection":24,"actual":27,"line":24.5,"over_probability":60}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"duplicate.csv"
            with path.open("w",newline="",encoding="utf-8") as handle:
                writer=csv.DictWriter(handle,fieldnames=row.keys())
                writer.writeheader(); writer.writerow(row); writer.writerow(row)
            with self.assertRaisesRegex(ValueError,"Duplicate forecast_id"):
                evaluate(path)

    def test_rejects_bad_probability(self):
        rows=[{"player":"A","stat":"points","projection":24,"actual":27,"line":24.5,"over_probability":120}]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"bad.csv"
            with path.open("w",newline="",encoding="utf-8") as handle:
                writer=csv.DictWriter(handle,fieldnames=rows[0].keys())
                writer.writeheader(); writer.writerows(rows)
            with self.assertRaises(ValueError): evaluate(path)

if __name__=="__main__": unittest.main()
