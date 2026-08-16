#!/usr/bin/env bash
# Gate 01: Frozen V4 regression — must pass before Phase 5 gates
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_DIR"

echo "  Running: ./scripts/run-acceptance-v4.sh"
START=$(date +%s)
set +e
bash "$PROJECT_DIR/scripts/run-acceptance-v4.sh" > "$1/v4.log" 2>&1
V4_EXIT=$?
set -e
ELAPSED=$(($(date +%s) - START))

if [ "$V4_EXIT" -eq 0 ]; then
    echo "PASS ${ELAPSED}s"
    exit 0
else
    echo "FAIL ${ELAPSED}s (V4 exit=$V4_EXIT)"
    echo "  See: $1/v4.log"
    tail -20 "$1/v4.log"
    exit 1
fi
