#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BASELINE_JSON="${ROOT_DIR}/report/baseline_eval.json"
CANDIDATE_JSON="${ROOT_DIR}/report/candidate_eval.json"
INPUT_PATH="${1:-${ROOT_DIR}/data/processed/race_last5.csv}"

mkdir -p "${ROOT_DIR}/report" "${ROOT_DIR}/experiments"

if [[ ! -f "${BASELINE_JSON}" ]]; then
  echo "[1/3] baseline evaluation"
  python "${ROOT_DIR}/scripts/evaluate_strategy.py" \
    --input "${INPUT_PATH}" \
    --out "${BASELINE_JSON}"
  echo "Baseline created at ${BASELINE_JSON}. Apply your patch, then rerun this script."
  exit 0
fi

echo "[1/3] candidate evaluation"
python "${ROOT_DIR}/scripts/evaluate_strategy.py" \
  --input "${INPUT_PATH}" \
  --out "${CANDIDATE_JSON}" \
  --baseline-json "${BASELINE_JSON}" \
  --experiment-id "$(date -u +%Y-%m-%d_%H%M%S)" \
  --hypothesis "${HYPOTHESIS:-}" \
  --files-changed "${FILES_CHANGED:-}" \
  --log-dir "${ROOT_DIR}/experiments"

echo "[2/3] decision written to experiments/*.json"

echo "[3/3] see report/candidate_eval.json and experiments log for keep/revert"
