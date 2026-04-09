# Codex Horse-Racing Optimization Runbook

## Scope
This runbook defines how to run one-patch-at-a-time strategy optimization safely.

## Files you MAY edit
- `analysis/ev.py`
- `strategy/betting.py`
- `scripts/evaluate_strategy.py` (only with explicit human approval)
- other strategy-related code explicitly requested for an experiment

## Files you MUST NOT edit in normal optimization runs
- dataset split definitions
- evaluation criteria / score weights
- task fixtures used as validation labels
- schemas without explicit request

## Optimization priority order
1. EV threshold (`min_ev`)
2. Stake sizing
3. Ability score coefficients
4. Weight adjustment
5. Pace adjustment
6. Ticket type expansion (last)

## Experiment procedure (single patch)
1. Create or confirm baseline:
   - `bash scripts/run_codex_experiment.sh <input_csv>`
2. Apply exactly one conceptual change.
3. Re-run:
   - `HYPOTHESIS="..." FILES_CHANGED="analysis/ev.py" bash scripts/run_codex_experiment.sh <input_csv>`
4. Read decision in `experiments/<experiment_id>.json`.
5. Confirm leakage check passed (`scripts/check_feature_leakage.py`).

## Keep / Revert rule
- Primary: validation ROI (`validation_roi`)
- Secondary: score (only as tie-break when ROI is equal)
- If validation ROI decreases, revert even if score increases.

## Baseline policy
- Baseline is the latest *kept* result (normally from main or previous keep).
- Keep decision updates `report/baseline_eval.json`.
- Revert decision never updates baseline.


## Multi-agent operation
- Follow `MULTI_AGENT_SYSTEM_PROMPT.md` and keep roles separated.
- Initialize per-experiment role artifacts with:
  - `bash scripts/init_multi_agent_experiment.sh <experiment_id>`
- Store role outputs in:
  - `experiments/<id>/01_researcher.md`
  - `experiments/<id>/02_planner.md`
  - `experiments/<id>/03_implementer.md`
  - `experiments/<id>/04_reviewer.md`
- If reviewer verdict is NG, re-implement using reviewer instructions only.

## Pre-merge checklist
- [ ] One conceptual change only
- [ ] `PYTHONPATH=. pytest -q` passed
- [ ] Baseline and candidate metrics recorded
- [ ] Decision log written to `experiments/`
- [ ] Overfitting / leakage risk reviewed
