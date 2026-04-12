from __future__ import annotations

import json
from pathlib import Path

from strategy.betting import generate_tickets


def build_tickets(
    df: list[dict],
    probs: list[dict],
    bankroll_per_race: int = 1000,
    min_ev: float = 1.05,
    max_bets: int = 2,
) -> list[dict]:
    del df
    ticket_plan = generate_tickets(
        probs,
        bankroll_per_race=bankroll_per_race,
        min_ev=min_ev,
        max_tickets_per_race=max_bets,
        prefer_wide=False,
    )
    return list(ticket_plan.get("tickets", []))


def save_tickets(tickets: list[dict], out_path: str | Path = "/workspace/output/tickets.json") -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(tickets, ensure_ascii=False, indent=2), encoding="utf-8")
