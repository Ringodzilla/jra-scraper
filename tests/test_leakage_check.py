from pathlib import Path

from scripts.check_feature_leakage import find_leakage


def test_find_leakage_detects_banned_keywords(tmp_path: Path) -> None:
    target = tmp_path / "feature.py"
    target.write_text("x = row['payout']\n", encoding="utf-8")

    findings = find_leakage([target])
    assert findings
    assert "payout" in findings[0]


def test_find_leakage_ignores_safe_file(tmp_path: Path) -> None:
    target = tmp_path / "feature.py"
    target.write_text("x = row['odds']\n", encoding="utf-8")

    findings = find_leakage([target])
    assert findings == []
