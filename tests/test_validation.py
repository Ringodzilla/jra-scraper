import unittest

from jra_scraper.validation import OUTPUT_COLUMNS, build_race_info_rows, build_row_id, validate_rows


class TestValidation(unittest.TestCase):
    def test_validate_rows_normalizes_and_caps_five(self):
        rows = []
        for i in range(1, 8):
            rows.append(
                {
                    "race_id": "20260329_中山_11",
                    "horse_id": "h1",
                    "horse_name": "A",
                    "run_index": str(i),
                    "date": f"2026/03/0{i}",
                    "race_name": "弥生賞",
                    "course": "芝",
                    "distance": "芝2000",
                    "position": f"{i}着",
                    "time": "1:59.9",
                    "margin": "0.2",
                    "weight": "57.0kg",
                    "jockey": "戸崎",
                    "pace": "36.0",
                    "last_3f": "34.2",
                    "field_size": "18頭",
                    "track_condition": "良",
                    "weather": "晴",
                    "passing_order": "5-5-4-2",
                    "odds": "3.2倍",
                    "popularity": "1人気",
                }
            )
        rows.append(rows[0].copy())

        validated = validate_rows(rows)
        self.assertEqual(5, len(validated))
        self.assertEqual([str(i) for i in range(1, 6)], [r["run_index"] for r in validated])
        self.assertEqual("2026-03-01", validated[0]["date"])
        self.assertEqual("2000", validated[0]["distance"])
        self.assertEqual("1", validated[0]["position"])
        self.assertEqual("57", validated[0]["weight"])
        self.assertEqual("119.9", validated[0]["time"])
        self.assertEqual("0.2", validated[0]["margin"])
        self.assertEqual("36", validated[0]["pace"])
        self.assertEqual("34.2", validated[0]["last_3f"])
        self.assertEqual("2", validated[0]["passing_order"])
        self.assertEqual("2", validated[0]["corner_4"])
        self.assertEqual("3.2", validated[0]["odds"])
        self.assertEqual("1", validated[0]["popularity"])
        self.assertEqual("1", validated[0]["last3f_rank"])
        self.assertEqual("0", validated[0]["last3f_diff"])
        self.assertEqual("1.5", validated[0]["last3f_score"])
        self.assertEqual("1", validated[0]["last3f_top_flag"])
        self.assertEqual("2", validated[0]["expected_position"])
        self.assertEqual("逃げ", validated[0]["style"])
        self.assertEqual("0", validated[0]["pace_maker_flag"])
        self.assertEqual("mid", validated[0]["race_pace"])
        self.assertEqual("18", validated[0]["field_size"])
        self.assertEqual("1", validated[0]["odds_rank"])
        self.assertEqual("1", validated[0]["performance_rank"])
        self.assertEqual("0", validated[0]["gap_index"])
        self.assertEqual("0", validated[0]["trouble_flag"])
        self.assertEqual(set(OUTPUT_COLUMNS), set(validated[0].keys()))

    def test_build_row_id_stable(self):
        row = {
            "race_id": "r1",
            "horse_id": "h1",
            "run_index": "1",
            "date": "2026-01-01",
            "race_name": "X",
            "position": "1",
            "odds": "3.2",
        }
        self.assertEqual(build_row_id(row), build_row_id(row.copy()))

    def test_build_race_info_rows_by_race_id(self):
        rows = [
            {
                "race_id": "r1",
                "date": "2026-03-01",
                "race_name": "弥生賞",
                "course": "芝",
                "distance": "2000",
                "field_size": "18",
                "race_pace": "mid",
                "pace_maker_flag": "0",
                "track_condition": "良",
                "weather": "晴",
            },
            {
                "race_id": "r1",
                "date": "2026-03-01",
                "race_name": "弥生賞",
                "course": "芝",
                "distance": "2000",
                "field_size": "",
                "race_pace": "",
                "pace_maker_flag": "",
                "track_condition": "",
                "weather": "",
            },
        ]
        info = build_race_info_rows(rows)
        self.assertEqual(1, len(info))
        self.assertEqual("r1", info[0]["race_id"])
        self.assertEqual("18", info[0]["field_size"])
        self.assertEqual("mid", info[0]["race_pace"])


if __name__ == "__main__":
    unittest.main()
