from pathlib import Path
import unittest

try:
    from jra_scraper.parser import JRAParser
    HAS_BS4 = True
except ModuleNotFoundError:
    HAS_BS4 = False


FIX = Path(__file__).parent / "fixtures"


@unittest.skipUnless(HAS_BS4, "beautifulsoup4 is required for parser tests")
class TestJRAParser(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = JRAParser("https://www.jra.go.jp")

    def test_parse_race_list_dedupes_and_extracts_structured_race_id(self):
        html = (FIX / "race_list.html").read_text(encoding="utf-8")
        races = self.parser.parse_race_list(html)
        self.assertEqual(2, len(races))
        self.assertTrue(races[0].race_id.startswith("20260301_中山_11"))

    def test_parse_race_detail_extracts_horses_and_ids(self):
        html = (FIX / "race_detail.html").read_text(encoding="utf-8")
        horses = self.parser.parse_race_detail(html, race_id="r1", race_name="11R")
        self.assertEqual(2, len(horses))
        self.assertEqual("サンプルホースA", horses[0].horse_name)
        self.assertTrue(horses[0].horse_id)

    def test_parse_horse_last5_maps_structured_columns(self):
        html = (FIX / "horse_history.html").read_text(encoding="utf-8")
        rows = self.parser.parse_horse_last5(
            html,
            race_id="r1",
            horse_id="h1",
            horse_name="サンプルホースA",
            horse_url="https://www.jra.go.jp/JRADB/accessU.html?CNAME=x",
        )
        self.assertEqual(5, len(rows))
        self.assertEqual("1", rows[0]["run_index"])
        self.assertIn("pace", rows[0])
        self.assertIn("last_3f", rows[0])
        self.assertIn("track_condition", rows[0])
        self.assertIn("weather", rows[0])
        self.assertIn("passing_order", rows[0])
        self.assertIn("odds", rows[0])
        self.assertIn("popularity", rows[0])

    def test_parse_horse_last5_fills_last3f_fallback_when_missing(self):
        html = """
        <table>
          <tr><th>日付</th><th>レース名</th><th>距離</th><th>着順</th><th>人気</th></tr>
          <tr><td>2026/03/01</td><td>テスト特別</td><td>芝1800</td><td>2</td><td>3</td></tr>
        </table>
        """
        rows = self.parser.parse_horse_last5(
            html,
            race_id="r1",
            horse_id="h1",
            horse_name="サンプルホースA",
            horse_url="https://www.jra.go.jp/JRADB/accessU.html?CNAME=x",
        )
        self.assertEqual("36.0", rows[0]["last_3f"])


if __name__ == "__main__":
    unittest.main()
