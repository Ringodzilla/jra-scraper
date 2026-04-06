from __future__ import annotations

import csv
from collections import defaultdict


def _to_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


def build_features(race_last5_path: str, entries_path: str, odds_path: str) -> list[dict]:
    stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "finish_sum": 0.0,
            "last3f_sum": 0.0,
            "pop_sum": 0.0,
            "weight_sum": 0.0,
            "count": 0.0,
        }
    )

    with open(race_last5_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            horse_id = row["horse_id"]
            s = stats[horse_id]
            s["finish_sum"] += _to_float(row.get("position"), 10.0)
            s["last3f_sum"] += _to_float(row.get("last_3f"), 36.0)
            s["pop_sum"] += _to_float(row.get("popularity"), 10.0)
            s["weight_sum"] += _to_float(row.get("weight"), 55.0)
            s["count"] += 1.0

    odds_map: dict[tuple[str, str], float] = {}
    with open(odds_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            odds_map[(row["race_id"], row["horse_id"])] = _to_float(row.get("win_odds"), 0.0)

    rows: list[dict] = []
    with open(entries_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            horse_id = row["horse_id"]
            s = stats.get(horse_id, {"finish_sum": 10.0, "last3f_sum": 36.0, "pop_sum": 10.0, "weight_sum": 55.0, "count": 1.0})
            count = max(s["count"], 1.0)

            avg_finish = s["finish_sum"] / count
            avg_last3f = s["last3f_sum"] / count
            avg_pop = s["pop_sum"] / count
            run_count = s["count"]
            assigned_weight = _to_float(row.get("assigned_weight"), 55.0)
            win_odds = odds_map.get((row["race_id"], horse_id), 0.0)

            ability_score = (
                -1.8 * avg_finish
                - 0.8 * avg_pop
                - 0.3 * assigned_weight
                - 0.5 * avg_last3f
                + 0.2 * run_count
            )

            rows.append(
                {
                    "race_id": row["race_id"],
                    "horse_id": horse_id,
                    "horse_name": row.get("horse_name", ""),
                    "horse_number": int(_to_float(row.get("horse_number"), 0)),
                    "win_odds": win_odds,
                    "ability_score": ability_score,
                }
            )

    return rows
