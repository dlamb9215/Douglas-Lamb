import unittest
from injury_exposure import build_injury_exposure


class InjuryExposureTests(unittest.TestCase):
    def test_weights_reported_designations_by_snap_share_and_role(self):
        pool={"players":[
            {"team":"BUF","name":"QB","position":"QB","injury_status":"questionable","offense_snap_pct_avg":90},
            {"team":"BUF","name":"WR","position":"WR","injury_status":"out","offense_snap_pct_avg":80},
            {"team":"BUF","name":"RB","position":"RB","injury_status":"active","offense_snap_pct_avg":60},
        ]}
        report=build_injury_exposure(pool,["BUF"])
        self.assertEqual(report["BUF"]["players_with_reported_designations"],2)
        self.assertEqual(report["BUF"]["players"][0]["player"],"QB")
        self.assertEqual(report["BUF"]["weighted_injury_exposure_index"],174.5)

    def test_unknown_status_is_not_treated_as_injured(self):
        report=build_injury_exposure({"players":[
            {"team":"BUF","name":"X","position":"WR","injury_status":"unknown","offense_snap_pct_avg":90}
        ]},["BUF"])
        self.assertEqual(report["BUF"]["players_with_reported_designations"],0)


if __name__ == "__main__":
    unittest.main()
