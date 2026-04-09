from __future__ import annotations

import math
from collections import defaultdict


def _softmax(scores: list[float]) -> list[float]:
    if not scores:
        return []
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    total = sum(exps)
    return [e / total for e in exps] if total > 0 else [0.0 for _ in scores]


def estimate_win_probs(rows: list[dict]) -> list[dict]:
    by_race: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_race[str(row["race_id"])].append(row)

    out: list[dict] = []
    for race_id, group in by_race.items():
        probs = _softmax([float(x["ability_score"]) for x in group])
        for row, prob in zip(group, probs):
            ev = prob * float(row["win_odds"])
            out.append(
                {
                    "race_id": race_id,
                    "horse_id": row["horse_id"],
                    "horse_name": row["horse_name"],
                    "horse_number": int(row["horse_number"]),
                    "win_odds": float(row["win_odds"]),
                    "win_prob": prob,
                    "ev_win": ev,
                }
            )

    return out
