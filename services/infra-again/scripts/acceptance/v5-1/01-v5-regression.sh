#!/usr/bin/env bash
# Gate 01: Official V5 regression
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_DIR"
START=$(date +%s)
bash "$PROJECT_DIR/scripts/run-acceptance-v5.sh" > "$1/v5-regression.log" 2>&1
ELAPSED=$(($(date +%s) - START))
echo "PASS ${ELAPSED}s"
exit 0
