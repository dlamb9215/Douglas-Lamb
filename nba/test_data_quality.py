import unittest
from datetime import datetime, timezone, timedelta

from nba.data_quality import EXPECTED_TEAMS, validate_payload

def payload():
    teams = {}
    for code in EXPECTED_TEAMS:
        teams[code] = {
            "games_played": 12, "pace": 99.0, "off_rating": 115.0,
            "def_rating": 112.0, "efg_pct": .54, "tov_pct": .135,
            "orb_pct": .265, "ft_rate": .25, "opp_efg_pct": .54,
            "opp_tov_pct": .135, "opp_orb_pct": .265, "opp_ft_rate": .25,
            "recent_pace": None, "recent_off_rating": None,
            "recent_def_rating": None, "home_off_rating": 115.0,
            "home_def_rating": 112.0, "road_off_rating": 115.0,
            "road_def_rating": 112.0, "fg3_pct": None,
            "opp_three_pa_rate": None, "opp_fg3_pct": None,
        }
    return {
        "league": "NBA", "season": 2027, "prior_season": 2026,
        "updated_at": "2026-11-08T05:00:00+00:00",
        "source": "DunkAPI get_team_stats (ESPN-derived)",
        "methods": {"prior_season_weight_games": 8}, "teams": teams,
    }

class TestNBADataQuality(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 8, 5, 30, tzinfo=timezone.utc)

    def test_valid_30_team_file(self):
        report = validate_payload(payload(), 72, self.now)
        self.assertTrue(report["ready"])
        self.assertEqual(report["team_count"], 30)
        self.assertEqual(report["age_hours"], .5)

    def test_rejects_stale_file(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_payload(payload(), 0.25, self.now)

    def test_rejects_future_timestamp(self):
        data = payload()
        data["updated_at"] = (self.now + timedelta(hours=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "future"):
            validate_payload(data, 72, self.now)

    def test_rejects_missing_team(self):
        data = payload()
        data["teams"].pop("BOS")
        with self.assertRaisesRegex(ValueError, "missing team records"):
            validate_payload(data, 72, self.now)

    def test_rejects_invalid_metric_range(self):
        data = payload()
        data["teams"]["BOS"]["efg_pct"] = 54
        with self.assertRaisesRegex(ValueError, "decimal from 0 to 1"):
            validate_payload(data, 72, self.now)

    def test_flags_small_sample_and_missing_features(self):
        data = payload()
        data["teams"]["BOS"]["games_played"] = 6
        report = validate_payload(data, 72, self.now)
        self.assertTrue(any("Early-season sample" in warning for warning in report["warnings"]))
        self.assertTrue(any("Unavailable optional team features" in warning for warning in report["warnings"]))

    def test_rejects_invalid_optional_three_point_feature(self):
        data = payload()
        data["teams"]["BOS"]["three_pa_rate"] = 1.4
        with self.assertRaisesRegex(ValueError, "three_pa_rate"):
            validate_payload(data, 72, self.now)

    def test_requires_timezone_aware_timestamp(self):
        data = payload()
        data["updated_at"] = "2026-11-08T05:00:00"
        with self.assertRaisesRegex(ValueError, "include a timezone"):
            validate_payload(data, 72, self.now)

if __name__ == "__main__":
    unittest.main()
