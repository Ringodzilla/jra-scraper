#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EXP_ID="${1:-$(date -u +%Y-%m-%d_%H%M%S)}"
EXP_DIR="${ROOT_DIR}/experiments/${EXP_ID}"

mkdir -p "${EXP_DIR}"

cat > "${EXP_DIR}/01_data_collector.json" <<'JSON'
{
  "race_info": {},
  "horses": []
}
JSON

cat > "${EXP_DIR}/02_analyzer.json" <<'JSON'
{
  "scores": []
}
JSON

cat > "${EXP_DIR}/03_simulator.json" <<'JSON'
{
  "probabilities": []
}
JSON

cat > "${EXP_DIR}/04_ev_calculator.json" <<'JSON'
{
  "ev_table": []
}
JSON

cat > "${EXP_DIR}/05_bet_builder.json" <<'JSON'
{
  "core": [],
  "partner": [],
  "long": [],
  "tickets": []
}
JSON

cat > "${EXP_DIR}/06_reviewer.json" <<'JSON'
{
  "status": "OK",
  "reason": "",
  "fix": ""
}
JSON

cat > "${EXP_DIR}/OWNERSHIP.lock" <<'TXT'
# Declare files each role touched to avoid concurrent overlap.
data_collector:
analyzer:
simulator:
ev_calculator:
bet_builder:
reviewer:
TXT

echo "Initialized multi-agent experiment workspace: ${EXP_DIR}"
