#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_DIR"
START=$(date +%s)
bash "$PROJECT_DIR/scripts/run-acceptance-v5-1.sh" > "$1/v5-1-regression.log" 2>&1
echo "PASS $(($(date +%s)-START))s"
