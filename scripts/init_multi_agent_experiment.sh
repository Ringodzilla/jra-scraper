#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EXP_ID="${1:-$(date -u +%Y-%m-%d_%H%M%S)}"
EXP_DIR="${ROOT_DIR}/experiments/${EXP_ID}"

mkdir -p "${EXP_DIR}"

cat > "${EXP_DIR}/01_researcher.md" <<'MD'
# Researcher Report

- Related files:
- Current implementation:
- Impact scope:
- Risks:
- Unknowns:
- Hypothesis (tentative):
MD

cat > "${EXP_DIR}/02_planner.md" <<'MD'
# Planner Report

- Tasks:
- Completion criteria per task:
- Test criteria:
- Prohibited actions:
MD

cat > "${EXP_DIR}/03_implementer.md" <<'MD'
# Implementer Report

- Changes made:
- Commands executed:
- Test results:
- Unresolved items:
MD

cat > "${EXP_DIR}/04_reviewer.md" <<'MD'
# Reviewer Report

- Verdict (OK/NG):
- Reasons:
- Required fixes (if NG):
MD

cat > "${EXP_DIR}/OWNERSHIP.lock" <<'TXT'
# Declare files each role touched to avoid concurrent overlap.
researcher:
planner:
implementer:
reviewer:
TXT

echo "Initialized multi-agent experiment workspace: ${EXP_DIR}"
