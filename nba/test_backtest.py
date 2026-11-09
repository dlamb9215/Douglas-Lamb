import csv
import tempfile
import unittest
from pathlib import Path
from nba.backtest import evaluate

class TestBacktest(unittest.TestCase):
    def test_metrics_on_small_fixture(self):
        rows=[
            {"projected_home":110,"projected_away":105,"actual_home":112,"actual_away":104,
             "spread":-3.5,"total":215.5,"home_cover_probability":60,"over_probability":55,"home_win_probability":65},
            {"projected_home":100,"projected_away":108,"actual_home":98,"actual_away":110,
             "spread":2.5,"total":210.5,"home_cover_probability":45,"over_probability":48,"home_win_probability":40},
        ]
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"games.csv"
            with path.open("w",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=rows[0].keys())
                writer.writeheader(); writer.writerows(rows)
            result=evaluate(path)
        self.assertEqual(result["games"],2)
        self.assertGreaterEqual(result["total_points_mae"],0)
        self.assertIn("moneyline_brier",result)\n        self.assertEqual(result["moneyline_games"],2)\n        self.assertIn("spread_brier",result)
        self.assertIn("total_calibration",result)

if __name__=="__main__": unittest.main()
