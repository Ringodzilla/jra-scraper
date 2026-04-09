from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from src.betting import save_tickets


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict], delimiter: str = ",") -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def save_outputs(df: list[dict], probs: list[dict], tickets: list[dict], out_dir: str | Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    predictions = [
        {
            "race_id": row["race_id"],
            "horse_id": row["horse_id"],
            "horse_number": row["horse_number"],
            "horse_name": row["horse_name"],
            "win_prob": row["win_prob"],
            "win_odds": row["win_odds"],
            "ev_win": row["ev_win"],
        }
        for row in probs
    ]
    _write_csv(
        out_dir / "predictions.csv",
        ["race_id", "horse_id", "horse_number", "horse_name", "win_prob", "win_odds", "ev_win"],
        predictions,
    )

    ev_ranking = sorted(predictions, key=lambda r: (r["race_id"], -float(r["ev_win"])))
    _write_csv(
        out_dir / "ev_ranking.csv",
        ["race_id", "horse_id", "horse_number", "horse_name", "win_prob", "win_odds", "ev_win"],
        ev_ranking,
    )

    race_count = len({str(row["race_id"]) for row in df})
    mean_ev = sum(float(r["ev_win"]) for r in probs) / len(probs) if probs else 0.0
    log_rows = [
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "num_rows": len(df),
            "num_races": race_count,
            "num_tickets": len(tickets),
            "mean_ev": mean_ev,
        }
    ]
    _write_csv(out_dir / "experiment_log.tsv", ["timestamp_utc", "num_rows", "num_races", "num_tickets", "mean_ev"], log_rows, delimiter="\t")

    save_tickets(tickets=tickets, out_path=out_dir / "tickets.json")
