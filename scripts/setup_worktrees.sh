#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${1:-..}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "${ROOT_DIR}"

git worktree add "${BASE_DIR}/wt-data_collector" || true
git worktree add "${BASE_DIR}/wt-analyzer" || true
git worktree add "${BASE_DIR}/wt-simulator" || true
git worktree add "${BASE_DIR}/wt-ev_calculator" || true
git worktree add "${BASE_DIR}/wt-bet_builder" || true
git worktree add "${BASE_DIR}/wt-reviewer" || true

echo "Worktrees initialized under ${BASE_DIR}"
