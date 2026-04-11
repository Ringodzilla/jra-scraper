from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.ev import compute_ev, load_rows
from strategy.betting import generate_tickets


def load_results(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        return list(csv.DictReader(file_obj))


def _to_float(value: object, default: float = 0.0) -> float:
    if value in (None, "", "None"):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _current_git_commit() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True)
        return out.strip()
    except Exception:
        return "unknown"


def decide_keep_or_revert(before: dict[str, float | int], after: dict[str, float | int]) -> tuple[str, str]:
    before_roi = float(before.get("validation_roi", before.get("roi", 0.0)))
    after_roi = float(after.get("validation_roi", after.get("roi", 0.0)))
    before_score = float(before.get("score", 0.0))
    after_score = float(after.get("score", 0.0))

    if after_roi > before_roi:
        return "keep", "validation ROI improved"
    if after_roi < before_roi:
        return "revert", "validation ROI decreased (primary metric regression)"
    if after_score > before_score:
        return "keep", "validation ROI tied and score improved"
    return "revert", "validation ROI tied and score did not improve"


def evaluate_strategy(
    rows: list[dict[str, str]],
    min_ev: float = 1.05,
    max_bets_per_race: int = 2,
    stake_per_bet: int = 100,
    *,
    results: list[dict[str, str]] | None = None,
) -> dict[str, float | int | str]:
    scored = compute_ev(rows)
    ticket_plan = generate_tickets(
        scored,
        bankroll_per_race=max_bets_per_race * stake_per_bet,
        min_ev=min_ev,
        max_tickets_per_race=max_bets_per_race,
    )
    tickets = list(ticket_plan.get("tickets") or [])

    if not results:
        return {
            "score": 0.0,
            "validation_roi": 0.0,
            "roi": 0.0,
            "hit_rate": 0.0,
            "sharpe_like": 0.0,
            "max_drawdown": 0.0,
            "ticket_count": len(tickets),
            "race_count": len({str(row.get("race_id", "")) for row in scored}),
            "invested": sum(int(_to_float(ticket.get("stake"), 0.0)) for ticket in tickets),
            "returned": 0.0,
            "git_commit": _current_git_commit(),
            "label_status": "missing",
        }

    result_map = {
        (str(row.get("race_id", "")), int(_to_float(row.get("horse_number"), 0.0))): _to_float(row.get("win_payout"), 0.0)
        for row in results
    }
    race_ids = {str(row.get("race_id", "")) for row in results}

    invested = 0
    returned = 0.0
    hit_races: set[str] = set()
    pnls: list[float] = []
    tickets_by_race: dict[str, list[dict[str, object]]] = defaultdict(list)
    for ticket in tickets:
        tickets_by_race[str(ticket.get("race_id", ""))].append(ticket)

    for race_id, race_tickets in tickets_by_race.items():
        race_invested = 0
        race_returned = 0.0
        for ticket in race_tickets:
            horse_number = int(_to_float(ticket.get("horse_number"), 0.0))
            stake = int(_to_float(ticket.get("stake"), 0.0))
            race_invested += stake
            payout_per_100 = result_map.get((race_id, horse_number), 0.0)
            race_returned += payout_per_100 * (stake / 100)
        invested += race_invested
        returned += race_returned
        pnls.append(race_returned - race_invested)
        if race_returned > 0:
            hit_races.add(race_id)

    roi = (returned / invested) if invested > 0 else 0.0
    race_count = max(len(race_ids), len(tickets_by_race), 1)
    hit_rate = len(hit_races) / race_count

    if pnls:
        mean = sum(pnls) / len(pnls)
        var = sum((value - mean) ** 2 for value in pnls) / len(pnls)
        std = var ** 0.5
        sharpe_like = (mean / std) if std > 0 else 0.0
    else:
        sharpe_like = 0.0

    max_drawdown = _max_drawdown(pnls)
    ticket_penalty = min(len(tickets) / race_count, 10.0) * 0.02
    drawdown_penalty = min(max_drawdown / max(invested, 1), 1.0) * 0.10
    score = (
        0.70 * (min(max(roi, 0.0), 2.0) / 2.0)
        + 0.20 * hit_rate
        + 0.10 * (min(max(sharpe_like, -1.0), 3.0) / 3.0)
    ) - ticket_penalty - drawdown_penalty
    score = max(0.0, min(1.0, score))

    return {
        "score": score,
        "validation_roi": roi,
        "roi": roi,
        "hit_rate": hit_rate,
        "sharpe_like": sharpe_like,
        "max_drawdown": max_drawdown,
        "ticket_count": len(tickets),
        "race_count": race_count,
        "invested": invested,
        "returned": returned,
        "git_commit": _current_git_commit(),
        "label_status": "available",
    }


def _max_drawdown(pnls: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    mdd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        mdd = max(mdd, peak - equity)
    return mdd


def _parse_files_changed(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _infer_results_path(input_path: Path) -> Path | None:
    direct = input_path.with_name("results.csv")
    if direct.exists():
        return direct
    candidate = ROOT / "tasks/horse_racing_ev/files/valid/results.csv"
    if candidate.exists():
        return candidate
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate EV strategy with labeled results when available.")
    parser.add_argument("--input", default="data/processed/race_last5.csv")
    parser.add_argument("--results", default="")
    parser.add_argument("--out", default="report/strategy_eval.json")
    parser.add_argument("--min-ev", type=float, default=1.05)
    parser.add_argument("--max-bets-per-race", type=int, default=2)
    parser.add_argument("--stake", type=int, default=100)
    parser.add_argument("--baseline-json", default="")
    parser.add_argument("--experiment-id", default="")
    parser.add_argument("--hypothesis", default="")
    parser.add_argument("--files-changed", default="")
    parser.add_argument("--log-dir", default="experiments")
    args = parser.parse_args()

    input_path = Path(args.input)
    rows = load_rows(input_path)

    results_path = Path(args.results) if args.results else _infer_results_path(input_path)
    results = load_results(results_path) if results_path and results_path.exists() else None
    metrics = evaluate_strategy(
        rows=rows,
        min_ev=args.min_ev,
        max_bets_per_race=args.max_bets_per_race,
        stake_per_bet=args.stake,
        results=results,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.baseline_json:
        before = json.loads(Path(args.baseline_json).read_text(encoding="utf-8"))
        decision, reason = decide_keep_or_revert(before, metrics)
        comparison = {
            "experiment_id": args.experiment_id or datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S"),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit_before": before.get("git_commit", "unknown"),
            "git_commit_after": metrics.get("git_commit", "unknown"),
            "hypothesis": args.hypothesis,
            "files_changed": _parse_files_changed(args.files_changed),
            "before": before,
            "after": metrics,
            "decision": decision,
            "reason": reason,
            "results_path": str(results_path) if results_path else "",
        }
        log_dir = Path(args.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{comparison['experiment_id']}.json"
        log_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

        payload = {"metrics": metrics, "decision": decision, "reason": reason, "log": str(log_path)}
        print(json.dumps(payload, ensure_ascii=False))
        return

    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
