from __future__ import annotations

import argparse
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


def _to_float(value: str | None, default: float = 0.0) -> float:
    if value in (None, "", "None"):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _race_id(row: dict[str, str | None]) -> str:
    rid = str(row.get("race_id") or "").strip()
    if rid:
        return rid
    return f"{row.get('date', '')}_{row.get('race_name', '')}"


def _position_int(row: dict[str, str | None]) -> int:
    return int(_to_float(str(row.get("position") or "0"), 0.0))


def _max_drawdown(pnls: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    mdd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        mdd = max(mdd, peak - equity)
    return mdd


def _current_git_commit() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True)
        return out.strip()
    except Exception:
        return "unknown"


def decide_keep_or_revert(before: dict[str, float | int], after: dict[str, float | int]) -> tuple[str, str]:
    """
    Primary metric first:
      - if validation ROI drops => revert
      - if validation ROI improves => keep
      - tie-break using score
    """
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
) -> dict[str, float | int | str]:
    scored = compute_ev(rows)

    grouped: dict[str, list[dict[str, str | None]]] = defaultdict(list)
    for row in scored:
        grouped[_race_id(row)].append(row)

    invested = 0
    returned = 0.0
    ticket_count = 0
    hit_races = 0
    pnls: list[float] = []

    race_ids = sorted(grouped.keys())
    for rid in race_ids:
        candidates = [r for r in grouped[rid] if _to_float(str(r.get("ev")), 0.0) >= min_ev]
        candidates = sorted(candidates, key=lambda r: _to_float(str(r.get("ev")), 0.0), reverse=True)[:max_bets_per_race]

        race_invested = len(candidates) * stake_per_bet
        race_returned = 0.0
        race_hit = False

        for pick in candidates:
            ticket_count += 1
            odds = _to_float(str(pick.get("odds")), 0.0)
            if _position_int(pick) == 1:
                race_hit = True
                race_returned += stake_per_bet * odds

        invested += race_invested
        returned += race_returned
        pnls.append(race_returned - race_invested)
        if race_hit:
            hit_races += 1

    race_count = len(race_ids)
    roi = (returned / invested) if invested > 0 else 0.0
    hit_rate = (hit_races / race_count) if race_count > 0 else 0.0

    if pnls:
        mean = sum(pnls) / len(pnls)
        var = sum((x - mean) ** 2 for x in pnls) / len(pnls)
        std = var ** 0.5
        sharpe_like = (mean / std) if std > 0 else 0.0
    else:
        sharpe_like = 0.0

    max_drawdown = _max_drawdown(pnls)
    avg_tickets = (ticket_count / race_count) if race_count > 0 else 0.0
    ticket_penalty = max(0.0, avg_tickets - max_bets_per_race) * 0.02
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
        "ticket_count": ticket_count,
        "race_count": race_count,
        "invested": invested,
        "returned": returned,
        "git_commit": _current_git_commit(),
    }


def _parse_files_changed(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate EV strategy with fixed metrics.")
    parser.add_argument("--input", default="data/processed/race_last5.csv")
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

    rows = load_rows(Path(args.input))
    metrics = evaluate_strategy(
        rows=rows,
        min_ev=args.min_ev,
        max_bets_per_race=args.max_bets_per_race,
        stake_per_bet=args.stake,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.baseline_json:
        before = json.loads(Path(args.baseline_json).read_text(encoding="utf-8"))
        decision, reason = decide_keep_or_revert(before, metrics)
        comparison = {
            "experiment_id": args.experiment_id
            or datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S"),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit_before": before.get("git_commit", "unknown"),
            "git_commit_after": metrics.get("git_commit", "unknown"),
            "hypothesis": args.hypothesis,
            "files_changed": _parse_files_changed(args.files_changed),
            "before": before,
            "after": metrics,
            "decision": decision,
            "reason": reason,
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
