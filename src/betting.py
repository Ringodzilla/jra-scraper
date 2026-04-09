from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def build_tickets(
    df: list[dict],
    probs: list[dict],
    bankroll_per_race: int = 1000,
    min_ev: float = 1.05,
    max_bets: int = 2,
) -> list[dict]:
    del df
    by_race: dict[str, list[dict]] = defaultdict(list)
    for row in probs:
        by_race[str(row["race_id"])].append(row)

    tickets: list[dict] = []
    for race_id, rows in by_race.items():
        cand = sorted((r for r in rows if float(r["ev_win"]) >= min_ev), key=lambda r: r["ev_win"], reverse=True)[:max_bets]
        if not cand:
            continue

        total_edge = sum(max(float(r["ev_win"]) - 1.0, 0.0) for r in cand)
        if total_edge <= 0:
            continue

        for row in cand:
            edge = max(float(row["ev_win"]) - 1.0, 0.0)
            stake = int((edge / total_edge) * bankroll_per_race / 100) * 100
            if stake < 100:
                continue
            tickets.append(
                {
                    "race_id": str(race_id),
                    "bet_type": "win",
                    "horse_number": int(row["horse_number"]),
                    "horse_name": row["horse_name"],
                    "stake": int(stake),
                    "win_prob": float(row["win_prob"]),
                    "win_odds": float(row["win_odds"]),
                    "ev_win": float(row["ev_win"]),
                }
            )

    return tickets


def save_tickets(tickets: list[dict], out_path: str | Path = "/workspace/output/tickets.json") -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(tickets, ensure_ascii=False, indent=2), encoding="utf-8")
