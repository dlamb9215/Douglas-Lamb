import unittest
from datetime import datetime, timezone, timedelta

from betting_engine.integrations import evaluate_two_way_market, evaluate_market_set


class SharedIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 11, 20, 0, tzinfo=timezone.utc)
        self.quote = (self.now - timedelta(minutes=10)).isoformat()

    def test_two_way_prices_compute_no_vig_and_pass_until_gates_are_earned(self):
        result = evaluate_two_way_market(
            sport="NBA", event="Away at Home", market="moneyline", line=None,
            selection_a="Home", probability_a=.65, odds_a=-110,
            selection_b="Away", probability_b=.35, odds_b=+100,
            sportsbook="ExampleBook", quoted_at=self.quote,
            data_ready=True, availability_confirmed=True,
            calibration_ready=False, now=self.now,
        )
        self.assertEqual(result["decision"], "PASS")
        home = result["selections"][0]
        self.assertIsNotNone(home["no_vig_market_probability"])
        self.assertIn("out-of-sample calibration gate not passed", home["blockers"])

    def test_missing_two_way_price_fails_closed(self):
        result = evaluate_two_way_market(
            sport="NFL", event="A at B", market="spread", line=-3.5,
            selection_a="A -3.5", probability_a=.6, odds_a=-110,
            selection_b="B +3.5", probability_b=.4, odds_b=None,
        )
        self.assertEqual(result["decision"], "PASS")
        self.assertIn("both current sportsbook prices", result["blockers"][0])

    def test_stale_quote_blocks_both_sides(self):
        result = evaluate_two_way_market(
            sport="NFL", event="A at B", market="total", line=45.5,
            selection_a="Over", probability_a=.6, odds_a=-110,
            selection_b="Under", probability_b=.4, odds_b=-110,
            sportsbook="Book", quoted_at=(self.now-timedelta(hours=8)).isoformat(),
            data_ready=True, availability_confirmed=True, calibration_ready=True,
            now=self.now,
        )
        self.assertEqual(result["decision"], "PASS")
        self.assertTrue(all("stale" in row["blockers"][0] for row in result["selections"]))

    def test_market_set_never_promotes_pass(self):
        market = {"market": "moneyline", "decision": "PASS", "selections": [
            {"selection": "A", "decision": "PASS", "blockers": ["calibration"]},
            {"selection": "B", "decision": "PASS", "blockers": ["calibration"]},
        ]}
        self.assertEqual(evaluate_market_set([market])["status"], "PASS_ALL_MARKETS")


if __name__ == "__main__":
    unittest.main()
