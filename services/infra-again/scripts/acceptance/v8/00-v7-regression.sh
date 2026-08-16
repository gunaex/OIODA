#!/bin/bash
# V7 Regression — run before Phase 8 gates to verify no regressions
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LOG_DIR="${1:-/tmp/infra-again-acceptance-v8-regression}"
mkdir -p "$LOG_DIR"
PYTHON="$PROJECT/.venv/bin/python"

echo "Running V7 Regression..."
echo "PROJECT=$PROJECT"
echo ""

FAIL_COUNT=0

run_test() {
    local name=$1
    local script=$2
    echo -n "  ${name}... "
    if PYTHONPATH="$PROJECT/src" "$PYTHON" "$SCRIPT_DIR/../v7/$script" "$LOG_DIR" > "$LOG_DIR/v7reg_${name}.log" 2>&1; then
        echo "PASS"
    else
        echo "FAIL"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

run_test "models" "02-execution-models.py"
run_test "mapper" "03-plan-mapper.py"
run_test "preflight" "04-preflight-policy.py"
run_test "plan-only" "05-plan-only.py"
run_test "safety" "08-safety-blocks.py"
run_test "ownership" "08b-ownership.py"
run_test "checksum" "08c-checksum.py"
run_test "idempotency" "09-idempotency.py"
run_test "runner-loss" "10-runner-loss.py"
run_test "persistence" "11-persistence.py"
run_test "evidence" "13-evidence.py"

echo ""
if [ "$FAIL_COUNT" -eq 0 ]; then
    echo "V7 Regression: ALL PASS"
    exit 0
else
    echo "V7 Regression: ${FAIL_COUNT} FAILED"
    exit 1
fi
