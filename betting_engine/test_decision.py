import unittest
from datetime import datetime, timezone, timedelta

from betting_engine.decision import (
    BetCandidate, evaluate, implied_probability, no_vig_probabilities,
    rank_candidates,
)


class BettingDecisionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 11, 18, 0, tzinfo=timezone.utc)
        self.base = BetCandidate(
            sport="NBA", event="A at B", market="spread", selection="B -2.5",
            model_probability=0.60, odds_american=-110,
            sportsbook="TestBook", quoted_at=(self.now-timedelta(hours=1)).isoformat(),
            data_ready=True, availability_confirmed=True, calibration_ready=True,
        )

    def test_implied_and_no_vig(self):
        self.assertAlmostEqual(implied_probability(-110), 110/210)
        a, b = no_vig_probabilities(-110, -110)
        self.assertAlmostEqual(a, 0.5)
        self.assertAlmostEqual(b, 0.5)

    def test_positive_edge_can_qualify(self):
        result = evaluate(self.base, now=self.now)
        self.assertEqual(result["decision"], "BET")
        self.assertGreater(result["expected_value_per_unit"], 0)
        self.assertLessEqual(result["capped_kelly_fraction"], 0.05)

    def test_evaluation_attaches_no_vig_market_comparison(self):
        from dataclasses import replace
        candidate = replace(self.base, opposite_odds_american=+100)
        result = evaluate(candidate, now=self.now)
        self.assertIsNotNone(result["no_vig_market_probability"])
        self.assertIn("edge_vs_no_vig_market", result)

    def test_missing_calibration_blocks_bet(self):
        from dataclasses import replace
        result = evaluate(replace(self.base, calibration_ready=False), now=self.now)
        self.assertEqual(result["decision"], "PASS")
        self.assertTrue(any("calibration" in x for x in result["blockers"]))

    def test_stale_quote_rejected(self):
        from dataclasses import replace
        with self.assertRaises(ValueError):
            evaluate(replace(self.base, quoted_at=(self.now-timedelta(hours=7)).isoformat()), now=self.now)

    def test_invalid_probability_rejected(self):
        from dataclasses import replace
        with self.assertRaises(ValueError):
            evaluate(replace(self.base, model_probability=1.2), now=self.now)

    def test_ranker_passes_invalid_quote(self):
        from dataclasses import replace
        rows = rank_candidates([replace(self.base, quoted_at="")], now=self.now)
        self.assertEqual(rows[0]["decision"], "PASS")


if __name__ == "__main__":
    unittest.main()
