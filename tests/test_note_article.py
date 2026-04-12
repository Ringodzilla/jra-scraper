import unittest

from report.note import build_note_article, generate_note_markdown
from src.react_workflow import ArticleWriterAgent


class TestNoteArticle(unittest.TestCase):
    def test_generate_note_markdown_is_paste_ready(self):
        ev_rows = [
            {
                "race_id": "r1",
                "horse_id": "h10",
                "horse_name": "ナムラコスモス",
                "horse_number": "10",
                "win_prob": "0.053034",
                "current_odds": "21.1",
                "predicted_odds": "21.086224",
                "predicted_odds_source": "live",
                "ev_current": "1.119015",
            },
            {
                "race_id": "r1",
                "horse_id": "h1",
                "horse_name": "フェスティバルヒル",
                "horse_number": "1",
                "win_prob": "0.054268",
                "current_odds": "20.5",
                "predicted_odds": "20.638951",
                "predicted_odds_source": "live",
                "ev_current": "1.112499",
            },
        ]
        tickets = {
            "tickets": [
                {
                    "race_id": "r1",
                    "horse_id": "h10",
                    "horse_name": "ナムラコスモス",
                    "horse_number": "10",
                    "stake": 100,
                    "win_prob": "0.053034",
                    "win_odds": "21.1",
                    "ev_current": "1.119015",
                }
            ]
        }
        review = {"status": "OK", "reason": "quality gates passed"}
        quality_report = {"issue_count": 0, "live_snapshot_count": 8}
        race_config = {
            "race_name": "第86回桜花賞GⅠ",
            "race_date": "2026-04-12",
            "track": "阪神",
            "race_number": 11,
            "source_url": "https://example.test/race",
            "note_title": "第86回桜花賞GⅠ EV分析",
        }

        markdown = generate_note_markdown(
            "第86回桜花賞GⅠ",
            ev_rows,
            tickets,
            review=review,
            quality_report=quality_report,
            race_config=race_config,
        )

        self.assertIn("# 第86回桜花賞GⅠ EV分析", markdown)
        self.assertIn("## 結論", markdown)
        self.assertIn("## 買い目", markdown)
        self.assertIn("## AI評価上位", markdown)
        self.assertIn("単勝 10 ナムラコスモス 100円", markdown)
        self.assertIn("開催日: 2026-04-12", markdown)

    def test_article_writer_outputs_hold_article_when_review_ng(self):
        agent = ArticleWriterAgent()
        article = agent.run(
            [
                {
                    "race_name": "第86回桜花賞GⅠ",
                    "race_date": "2026-04-12",
                    "track": "阪神",
                    "race_number": 11,
                    "note_title": "第86回桜花賞GⅠ EV分析",
                }
            ],
            ev_rows=[
                {
                    "race_id": "r1",
                    "horse_id": "h7",
                    "horse_name": "アランカール",
                    "horse_number": "7",
                    "win_prob": "0.11",
                    "current_odds": "6.7",
                    "predicted_odds": "7.3",
                    "predicted_odds_source": "structural",
                    "ev_current": "0.737",
                }
            ],
            ticket_plan={"tickets": []},
            review={"status": "NG", "reason": "predicted/current EV divergence detected"},
            quality_report={"issue_count": 0, "live_snapshot_count": 4},
        )

        self.assertEqual("hold", article["status"])
        self.assertFalse(article["publish_ready"])
        self.assertIn("今回は購入見送りです。", article["markdown"])
        self.assertIn("reviewerがNG", article["markdown"])

    def test_build_note_article_returns_structured_metadata(self):
        article = build_note_article(
            "サンプルレース",
            ev_rows=[],
            tickets={"tickets": []},
            review={"status": "OK", "reason": "quality gates passed"},
            quality_report={"issue_count": 0, "live_snapshot_count": 0},
        )

        self.assertEqual("ready", article["status"])
        self.assertIn("markdown", article)
        self.assertIn("headline", article)


if __name__ == "__main__":
    unittest.main()
