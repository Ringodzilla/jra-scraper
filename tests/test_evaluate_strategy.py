from scripts.evaluate_strategy import decide_keep_or_revert, evaluate_strategy


def test_evaluate_strategy_returns_metrics() -> None:
    rows = [
        {
            "race_id": "r1",
            "horse_name": "A",
            "position": "1",
            "last_3f": "34.5",
            "popularity": "1",
            "odds": "2.0",
        },
        {
            "race_id": "r1",
            "horse_name": "B",
            "position": "2",
            "last_3f": "35.0",
            "popularity": "2",
            "odds": "3.0",
        },
        {
            "race_id": "r2",
            "horse_name": "C",
            "position": "3",
            "last_3f": "36.2",
            "popularity": "3",
            "odds": "4.5",
        },
    ]

    metrics = evaluate_strategy(rows, min_ev=1.0, max_bets_per_race=1, stake_per_bet=100)

    assert 0.0 <= metrics["score"] <= 1.0
    assert metrics["race_count"] == 2
    assert metrics["ticket_count"] >= 1
    assert metrics["invested"] >= 100
    assert "validation_roi" in metrics


def test_evaluate_strategy_handles_empty_input() -> None:
    metrics = evaluate_strategy([], min_ev=1.05, max_bets_per_race=2, stake_per_bet=100)
    assert metrics["score"] == 0.0
    assert metrics["race_count"] == 0
    assert metrics["ticket_count"] == 0


def test_decision_prefers_validation_roi() -> None:
    before = {"validation_roi": 1.10, "score": 0.50}
    after = {"validation_roi": 1.05, "score": 0.80}
    decision, reason = decide_keep_or_revert(before, after)

    assert decision == "revert"
    assert "ROI" in reason
