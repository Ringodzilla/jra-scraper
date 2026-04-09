#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${1:-..}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "${ROOT_DIR}"

git worktree add "${BASE_DIR}/wt-researcher" || true
git worktree add "${BASE_DIR}/wt-planner" || true
git worktree add "${BASE_DIR}/wt-implementer" || true
git worktree add "${BASE_DIR}/wt-reviewer" || true

echo "Worktrees initialized under ${BASE_DIR}"
