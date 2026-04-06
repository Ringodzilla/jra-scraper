from __future__ import annotations

from pathlib import Path

from src.betting import build_tickets
from src.evaluator import save_outputs
from src.features import build_features
from src.model import estimate_win_probs


class AutoAgent:
    """Minimal horse-racing EV agent scaffold for AutoAgent/Harbor tasks."""

    def run(self, inputs: dict[str, str], out_dir: str | Path = "output") -> dict[str, str]:
        race_last5_path = inputs["race_last5"]
        entries_path = inputs["entries"]
        odds_path = inputs["odds"]

        df = build_features(race_last5_path, entries_path, odds_path)
        probs = estimate_win_probs(df)
        tickets = build_tickets(df, probs)

        save_outputs(df=df, probs=probs, tickets=tickets, out_dir=Path(out_dir))
        return {"status": "ok"}


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    default_inputs = {
        "race_last5": str(root / "tasks/horse_racing_ev/files/valid/race_last5.csv"),
        "entries": str(root / "tasks/horse_racing_ev/files/valid/entries.csv"),
        "odds": str(root / "tasks/horse_racing_ev/files/valid/odds.csv"),
    }
    AutoAgent().run(default_inputs, out_dir=root / "output")
