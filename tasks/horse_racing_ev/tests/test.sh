#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "$0")/../../.." && pwd)}"

mkdir -p "$ROOT_DIR/output"
python "$ROOT_DIR/agent.py"
python "$ROOT_DIR/tasks/horse_racing_ev/tests/test.py"
