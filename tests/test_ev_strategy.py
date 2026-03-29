import unittest

from analysis.ev import compute_ev
from strategy.betting import generate_tickets


class TestEVStrategy(unittest.TestCase):
    def test_compute_ev_and_tickets(self):
        rows = [
            {"horse_name": "A", "position": "1", "last_3f": "34.0", "popularity": "3", "odds": "5.0"},
            {"horse_name": "B", "position": "2", "last_3f": "35.0", "popularity": "1", "odds": "2.0"},
        ]
        scored = compute_ev(rows)
        self.assertTrue(scored[0].get("ev") is not None)
        tickets = generate_tickets(scored, mode="safe")
        self.assertIn("tansho", tickets)


if __name__ == "__main__":
    unittest.main()
