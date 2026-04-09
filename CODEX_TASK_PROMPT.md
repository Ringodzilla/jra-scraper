You are improving a horse-racing EV betting system.

Follow the project constitution in `CODEX_STRATEGY.md`.

Task:
Improve the current implementation with the goal of increasing validation ROI, while avoiding overfitting and keeping ticket counts reasonable.

Instructions:
- First inspect the current pipeline and identify the highest-leverage bottleneck.
- Do not rewrite the whole project.
- Make the smallest meaningful change.
- Run `python scripts/evaluate_strategy.py` after changes.
- If validation ROI does not improve, revert the idea and try a different one.
- Do not touch evaluation logic or dataset split.
- Summarize:
  1. root cause
  2. code changes
  3. before/after metrics
  4. whether the patch should be kept
- Record one experiment log JSON in `experiments/` with before/after/decision.

Focus areas in priority order:
1. probability calibration
2. EV filtering thresholds
3. stake sizing
4. pace/weight adjustments
5. ticket construction

Do exactly one conceptual improvement per patch.
Use diffs that are easy to review.


Role execution order:
1. Researcher
2. Planner
3. Implementer
4. Reviewer

Do not merge roles in one output.