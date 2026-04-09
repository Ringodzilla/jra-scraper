from __future__ import annotations

import argparse
import json
from pathlib import Path

from openai import OpenAI


class CodexOrchestrator:
    def __init__(self, model: str = "gpt-5-codex") -> None:
        self.client = OpenAI()
        self.model = model

    def run(self, agent: str, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=f"[{agent}]\n{prompt}",
        )
        return response.output_text

    @staticmethod
    def _is_ng(review_text: str) -> bool:
        try:
            data = json.loads(review_text)
            return str(data.get("status", "")).upper() == "NG"
        except json.JSONDecodeError:
            return "NG" in review_text.upper()

    def execute(self, race_context: str, max_retries: int = 1) -> dict[str, str]:
        data = self.run("data_collector", race_context)
        analysis = self.run("analyzer", data)
        sim = self.run("simulator", analysis)
        ev = self.run("ev_calculator", sim)
        bet = self.run("bet_builder", ev)
        review = self.run("reviewer", bet)

        retries = 0
        while self._is_ng(review) and retries < max_retries:
            bet = self.run("bet_builder", review)
            review = self.run("reviewer", bet)
            retries += 1

        return {
            "data_collector": data,
            "analyzer": analysis,
            "simulator": sim,
            "ev_calculator": ev,
            "bet_builder": bet,
            "reviewer": review,
        }


def _write_outputs(out_dir: Path, outputs: dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, value in outputs.items():
        (out_dir / f"{key}.json").write_text(value, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run role-separated horse-racing Codex orchestration.")
    parser.add_argument("--race", required=True, help="Race/task context for the multi-agent system")
    parser.add_argument("--model", default="gpt-5-codex")
    parser.add_argument("--out-dir", default="experiments/orchestrator_latest")
    parser.add_argument("--max-retries", type=int, default=1)
    args = parser.parse_args()

    orchestrator = CodexOrchestrator(model=args.model)
    outputs = orchestrator.execute(race_context=args.race, max_retries=args.max_retries)
    _write_outputs(Path(args.out_dir), outputs)

    print("==== FINAL RESULT ====")
    print(outputs["reviewer"])


if __name__ == "__main__":
    main()
