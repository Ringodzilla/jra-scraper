from __future__ import annotations

import argparse
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

    def execute(self, task: str, max_retries: int = 1) -> dict[str, str]:
        research = self.run("researcher", task)
        plan = self.run("planner", research)
        impl = self.run("implementer", plan)
        review = self.run("reviewer", impl)

        retries = 0
        while "NG" in review and retries < max_retries:
            impl = self.run("implementer", review)
            review = self.run("reviewer", impl)
            retries += 1

        return {
            "research": research,
            "plan": plan,
            "implementation": impl,
            "review": review,
        }


def _write_outputs(out_dir: Path, outputs: dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, value in outputs.items():
        (out_dir / f"{key}.md").write_text(value, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run role-separated Codex orchestration.")
    parser.add_argument("--task", required=True, help="Task request for the agent team")
    parser.add_argument("--model", default="gpt-5-codex")
    parser.add_argument("--out-dir", default="experiments/orchestrator_latest")
    parser.add_argument("--max-retries", type=int, default=1)
    args = parser.parse_args()

    orchestrator = CodexOrchestrator(model=args.model)
    outputs = orchestrator.execute(task=args.task, max_retries=args.max_retries)
    _write_outputs(Path(args.out_dir), outputs)

    print("==== FINAL RESULT ====")
    print(outputs["review"])


if __name__ == "__main__":
    main()
