#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BASELINE_JSON="${ROOT_DIR}/report/baseline_eval.json"
CANDIDATE_JSON="${ROOT_DIR}/report/candidate_eval.json"
INPUT_PATH="${1:-${ROOT_DIR}/data/processed/race_last5.csv}"
RESULTS_PATH="${RESULTS_PATH:-}"

if [[ -z "${RESULTS_PATH}" ]]; then
  if [[ -f "$(dirname "${INPUT_PATH}")/results.csv" ]]; then
    RESULTS_PATH="$(dirname "${INPUT_PATH}")/results.csv"
  elif [[ -f "${ROOT_DIR}/tasks/horse_racing_ev/files/valid/results.csv" ]]; then
    RESULTS_PATH="${ROOT_DIR}/tasks/horse_racing_ev/files/valid/results.csv"
  fi
fi

RESULTS_ARGS=()
if [[ -n "${RESULTS_PATH}" ]]; then
  RESULTS_ARGS=(--results "${RESULTS_PATH}")
fi

mkdir -p "${ROOT_DIR}/report" "${ROOT_DIR}/experiments"

echo "[0/4] leakage guard"
python "${ROOT_DIR}/scripts/check_feature_leakage.py"

if [[ ! -f "${BASELINE_JSON}" ]]; then
  echo "[1/4] baseline evaluation"
  python "${ROOT_DIR}/scripts/evaluate_strategy.py" \
    --input "${INPUT_PATH}" \
    "${RESULTS_ARGS[@]}" \
    --out "${BASELINE_JSON}"
  echo "Baseline created at ${BASELINE_JSON}. Apply your patch, then rerun this script."
  exit 0
fi

echo "[1/4] candidate evaluation"
EVAL_OUTPUT=$(python "${ROOT_DIR}/scripts/evaluate_strategy.py" \
  --input "${INPUT_PATH}" \
  "${RESULTS_ARGS[@]}" \
  --out "${CANDIDATE_JSON}" \
  --baseline-json "${BASELINE_JSON}" \
  --experiment-id "$(date -u +%Y-%m-%d_%H%M%S)" \
  --hypothesis "${HYPOTHESIS:-}" \
  --files-changed "${FILES_CHANGED:-}" \
  --log-dir "${ROOT_DIR}/experiments")

echo "${EVAL_OUTPUT}"

DECISION=$(python -c 'import json,sys; print(json.loads(sys.argv[1])["decision"])' "${EVAL_OUTPUT}")

if [[ "${DECISION}" == "keep" ]]; then
  cp "${CANDIDATE_JSON}" "${BASELINE_JSON}"
  echo "[2/4] decision=keep -> baseline updated"
else
  echo "[2/4] decision=revert -> baseline unchanged"
fi

echo "[3/4] decision log written to experiments/*.json"
echo "[4/4] see report/candidate_eval.json and report/baseline_eval.json"
