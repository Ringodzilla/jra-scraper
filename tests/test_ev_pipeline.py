import unittest

from analysis.ev import build_feature_rows, compute_ev, simulate_race_scenarios
from src.react_workflow import ReviewerAgent, WorkflowSettings
from strategy.betting import generate_tickets


class TestEVPipeline(unittest.TestCase):
    def test_compute_ev_is_race_normalized(self):
        rows = [
            {
                "race_id": "20260329_中山_11",
                "horse_id": "h1",
                "horse_name": "A",
                "horse_number": "1",
                "current_odds": "3.0",
                "current_popularity": "1",
                "current_jockey": "戸崎",
                "assigned_weight": "57",
                "target_track": "中山",
                "target_race_date": "2026-03-29",
                "target_race_number": "11",
                "target_surface": "芝",
                "target_distance": "2000",
                "run_index": "1",
                "date": "2026-03-01",
                "course": "中山",
                "distance": "2000",
                "position": "1",
                "time": "119.9",
                "weight": "57",
                "jockey": "戸崎",
                "last_3f": "34.2",
                "passing_order": "5-5-4-2",
                "odds": "4.8",
                "popularity": "1",
            },
            {
                "race_id": "20260329_中山_11",
                "horse_id": "h1",
                "horse_name": "A",
                "horse_number": "1",
                "current_odds": "3.0",
                "current_popularity": "1",
                "current_jockey": "戸崎",
                "assigned_weight": "57",
                "target_track": "中山",
                "target_race_date": "2026-03-29",
                "target_race_number": "11",
                "target_surface": "芝",
                "target_distance": "2000",
                "run_index": "2",
                "date": "2026-02-01",
                "course": "中山",
                "distance": "2000",
                "position": "2",
                "time": "120.3",
                "weight": "57",
                "jockey": "戸崎",
                "last_3f": "34.6",
                "passing_order": "6-6-5-3",
                "odds": "7.2",
                "popularity": "2",
            },
            {
                "race_id": "20260329_中山_11",
                "horse_id": "h2",
                "horse_name": "B",
                "horse_number": "2",
                "current_odds": "6.0",
                "current_popularity": "4",
                "current_jockey": "ルメール",
                "assigned_weight": "56",
                "target_track": "中山",
                "target_race_date": "2026-03-29",
                "target_race_number": "11",
                "target_surface": "芝",
                "target_distance": "2000",
                "run_index": "1",
                "date": "2026-03-01",
                "course": "東京",
                "distance": "1800",
                "position": "3",
                "time": "109.9",
                "weight": "56",
                "jockey": "ルメール",
                "last_3f": "35.0",
                "passing_order": "9-9-8-6",
                "odds": "5.4",
                "popularity": "4",
            },
            {
                "race_id": "20260329_中山_11",
                "horse_id": "h2",
                "horse_name": "B",
                "horse_number": "2",
                "current_odds": "6.0",
                "current_popularity": "4",
                "current_jockey": "ルメール",
                "assigned_weight": "56",
                "target_track": "中山",
                "target_race_date": "2026-03-29",
                "target_race_number": "11",
                "target_surface": "芝",
                "target_distance": "2000",
                "run_index": "2",
                "date": "2025-12-28",
                "course": "東京",
                "distance": "1800",
                "position": "5",
                "time": "110.8",
                "weight": "56",
                "jockey": "ルメール",
                "last_3f": "35.4",
                "passing_order": "10-10-9-8",
                "odds": "4.1",
                "popularity": "2",
            },
        ]

        feature_rows = build_feature_rows(rows)
        scenario_rows = simulate_race_scenarios(feature_rows)
        scored = compute_ev(scenario_rows)

        self.assertEqual(2, len(scored))
        prob_sum = sum(float(row["win_prob"]) for row in scored)
        self.assertAlmostEqual(1.0, prob_sum, places=4)
        self.assertIn("current_odds", scored[0])
        self.assertIn("predicted_odds", scored[0])
        self.assertIn("fair_odds", scored[0])
        self.assertIn("ev_current", scored[0])
        self.assertIn("ev_predicted", scored[0])
        self.assertTrue(any(row["predicted_odds"] != row["current_odds"] for row in scored))

    def test_generate_tickets_returns_structured_plan(self):
        ev_rows = [
            {
                "race_id": "r1",
                "horse_id": "h1",
                "horse_name": "A",
                "horse_number": "1",
                "win_prob": "0.42",
                "current_odds": "3.2",
                "predicted_odds": "2.9",
                "ev": "1.344",
                "ev_current": "1.344",
                "ev_predicted": "1.218",
                "fair_odds": "2.38",
            },
            {
                "race_id": "r1",
                "horse_id": "h2",
                "horse_name": "B",
                "horse_number": "2",
                "win_prob": "0.20",
                "current_odds": "7.0",
                "predicted_odds": "7.8",
                "ev": "1.4",
                "ev_current": "1.4",
                "ev_predicted": "1.56",
                "fair_odds": "5.0",
            },
        ]
        plan = generate_tickets(ev_rows)
        self.assertIn("tickets", plan)
        self.assertIn("races", plan)
        self.assertTrue(plan["tickets"])
        self.assertEqual("win", plan["tickets"][0]["bet_type"])
        self.assertIn("ev_predicted", plan["tickets"][0])

    def test_reviewer_rejects_meaningful_ev_divergence(self):
        reviewer = ReviewerAgent(WorkflowSettings())
        ev_rows = [
            {
                "race_id": "r1",
                "horse_id": "h1",
                "horse_name": "A",
                "current_odds": "3.0",
                "predicted_odds": "4.2",
                "ev_current": "1.08",
                "ev_predicted": "1.512",
                "win_prob": "0.36",
            }
        ]

        review = reviewer.run(
            {"quality_report": {"issues_by_severity": {}}, "entries": [{"race_id": "r1", "horse_id": "h1"}]},
            scenario_rows=[{"race_id": "r1", "horse_id": "h1"}],
            ev_rows=ev_rows,
            ticket_plan={"tickets": []},
            attempt=0,
        )

        self.assertEqual("NG", review["status"])
        self.assertIn("predicted/current EV divergence", review["reason"])
        self.assertTrue(review["divergent_rows"])

    def test_compute_ev_calibrates_extreme_longshots_toward_market(self):
        feature_rows = []
        odds_ladder = [3.2, 4.1, 6.8, 10.5, 13.2, 18.4, 24.7, 33.0, 55.0, 80.0, 120.0, 260.0]
        score_ladder = [0.86, 0.82, 0.78, 0.74, 0.70, 0.66, 0.62, 0.58, 0.54, 0.60, 0.64, 0.68]
        popularity_ladder = [1, 2, 3, 4, 5, 6, 8, 9, 11, 13, 15, 18]
        for idx, (odds, base_score, popularity) in enumerate(zip(odds_ladder, score_ladder, popularity_ladder), start=1):
            feature_rows.append(
                {
                    "race_id": "r_long",
                    "horse_id": f"h{idx}",
                    "horse_name": f"Horse{idx}",
                    "horse_number": str(idx),
                    "current_odds": str(odds),
                    "current_popularity": str(popularity),
                    "ability_score": base_score,
                    "course_score": 0.58 if idx >= 10 else 0.52,
                    "pace_score": 0.57 if idx >= 10 else 0.50,
                    "weight_score": 0.0,
                    "jockey_score": 0.48 if idx >= 10 else 0.55,
                    "market_support": round(1.0 / odds, 4),
                    "history_count": 4,
                    "odds_snapshot_count": "2",
                    "odds_span_minutes": "10",
                }
            )

        scored = compute_ev(feature_rows)
        by_horse = {row["horse_id"]: row for row in scored}
        favorite = by_horse["h1"]
        longshot = by_horse["h12"]

        self.assertEqual("longshot", longshot["probability_band"])
        self.assertGreater(float(longshot["market_shrink_used"]), float(favorite["market_shrink_used"]))
        self.assertLess(float(longshot["win_prob"]) / float(longshot["market_prob"]), 1.2)
        self.assertLess(float(longshot["predicted_odds"]), float(longshot["current_odds"]) * 1.06)
        self.assertLess(float(longshot["win_prob"]), float(favorite["win_prob"]))


if __name__ == "__main__":
    unittest.main()
