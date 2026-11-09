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

    def test_rejects_bad_probability(self):
        rows=[{"player":"A","stat":"points","projection":24,"actual":27,"line":24.5,"over_probability":120}]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"bad.csv"
            with path.open("w",newline="",encoding="utf-8") as handle:
                writer=csv.DictWriter(handle,fieldnames=rows[0].keys())
                writer.writeheader(); writer.writerows(rows)
            with self.assertRaises(ValueError): evaluate(path)

if __name__=="__main__": unittest.main()
