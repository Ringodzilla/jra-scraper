from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT_DIR / "output"
VALID_DIR = ROOT_DIR / "tasks/horse_racing_ev/files/valid"


def _read_results(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def compute_payout(tickets: list[dict], results: list[dict]) -> tuple[int, float, int]:
    result_map = {
        (str(r["race_id"]), int(r["horse_number"])): float(r["win_payout"])
        for r in results
    }
    winners = {(str(r["race_id"]), int(r["horse_number"])) for r in results}

    invested = 0
    returned = 0.0
    hit_races: set[str] = set()

    for t in tickets:
        if t.get("bet_type") != "win":
            continue

        race_id = str(t["race_id"])
        horse_number = int(t["horse_number"])
        stake = int(t["stake"])

        invested += stake
        payout_per_100 = result_map.get((race_id, horse_number), 0.0)
        returned += payout_per_100 * (stake / 100)

        if (race_id, horse_number) in winners:
            hit_races.add(race_id)

    return invested, returned, len(hit_races)


def main() -> None:
    tickets_path = OUTPUT_DIR / "tickets.json"
    pred_path = OUTPUT_DIR / "predictions.csv"
    results_path = VALID_DIR / "results.csv"

    score = 0.0
    if tickets_path.exists() and pred_path.exists() and results_path.exists():
        tickets = json.loads(tickets_path.read_text(encoding="utf-8"))
        results = _read_results(results_path)

        invested, returned, hit_race_count = compute_payout(tickets, results)
        roi = (returned / invested) if invested > 0 else 0.0

        race_ids = {str(r["race_id"]) for r in results}
        race_count = max(len(race_ids), 1)
        hit_rate = hit_race_count / race_count

        payout_lookup = {
            (str(r["race_id"]), int(r["horse_number"])): float(r["win_payout"])
            for r in results
        }
        grouped_tickets: dict[str, list[dict]] = defaultdict(list)
        for t in tickets:
            grouped_tickets[str(t["race_id"])].append(t)

        profits: list[float] = []
        for race_id, group in grouped_tickets.items():
            race_stake = sum(int(t["stake"]) for t in group)
            race_return = 0.0
            for t in group:
                payout = payout_lookup.get((str(t["race_id"]), int(t["horse_number"])), 0.0)
                race_return += payout * (int(t["stake"]) / 100)
            profits.append(race_return - race_stake)

        sharpe_like = 0.0
        if profits:
            mean = sum(profits) / len(profits)
            var = sum((x - mean) ** 2 for x in profits) / len(profits)
            std = math.sqrt(var)
            sharpe_like = mean / std if std > 0 else 0.0

        ticket_penalty = min(len(tickets) / race_count, 10) * 0.02
        overfit_penalty = 0.0

        score = (
            0.70 * (min(max(roi, 0.0), 2.0) / 2.0)
            + 0.20 * hit_rate
            + 0.10 * (min(max(sharpe_like, -1.0), 3.0) / 3.0)
        ) - ticket_penalty - overfit_penalty
        score = max(0.0, min(1.0, score))

    log_dir = Path("/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "reward.txt").write_text(str(score), encoding="utf-8")


if __name__ == "__main__":
    main()
