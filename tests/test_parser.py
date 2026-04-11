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
        self.assertEqual("1", horses[0].horse_number)

    def test_parse_race_detail_repairs_shifted_rows(self):
        html = """
        <html><body>
        <table class="race_table_01">
          <tr><th>枠</th><th>馬番</th><th>馬名</th><th>騎手</th><th>斤量</th><th>単勝</th></tr>
          <tr><td>1</td><td>1</td><td class="horse"><a href="/JRADB/accessU.html?CNAME=a1">サンプルホースA</a></td><td>戸崎</td><td>57.0</td><td>3.2</td></tr>
          <tr><td>1</td><td>2</td><td class="horse"><a href="/JRADB/accessU.html?CNAME=a2">サンプル</a></td><td>ホースB</td><td>ルメール</td><td>56</td><td>4.8</td></tr>
        </table>
        </body></html>
        """
        horses = self.parser.parse_race_detail(html, race_id="20260329_中山_11", race_name="11R")
        self.assertEqual(2, len(horses))
        self.assertEqual("サンプル ホースB", horses[1].horse_name)
        self.assertEqual("2", horses[1].horse_number)
        self.assertEqual("ルメール", horses[1].current_jockey)
        self.assertEqual("4.8", horses[1].current_odds)

    def test_parse_race_detail_raises_when_no_horses_found(self):
        html = "<html><body><table class='race_table_01'><tr><th>馬名</th></tr></table></body></html>"
        with self.assertRaisesRegex(ValueError, "No horses parsed"):
            self.parser.parse_race_detail(html, race_id="r1", race_name="11R")

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
