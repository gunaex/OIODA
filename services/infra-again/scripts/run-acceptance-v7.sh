#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GATES_DIR="$SCRIPT_DIR/acceptance/v7"; cd "$PROJECT_DIR"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
LOG_DIR="$PROJECT_DIR/.ai/acceptance/v7/latest"; rm -rf "$LOG_DIR"; mkdir -p "$LOG_DIR"
REQ_PASS=0; REQ_FAIL=0; REQ_SKIP=0
GT1=0;GT2=0;GT3=0;GT4=0;GT5=0;GT6=0;GT7=0;GT8=0;GT8b=0;GT8c=0;GT9=0;GT10=0;GT11=0;GT12=0;GT13=0;GT14=0;GT15=0
TOOL="$SCRIPT_DIR/acceptance/run_with_timeout.py"

run_gate() {
    local num="$1"; local name="$2"; local cmd="$3"; local timeout="${4:-60}"
    echo ""; printf "[%2s/17] %-40s " "$num" "$name"
    local start=$(date +%s); local exit_code=0
    python3.11 "$TOOL" --timeout "$timeout" -- bash -c "$cmd '$LOG_DIR'" > "$LOG_DIR/gate-$(printf '%s' "$num").log" 2>&1 || exit_code=$?
    local elapsed=$(($(date +%s)-start)); eval "GT${num}=$elapsed"
    if [ "$exit_code" -eq 124 ]; then echo -e "${RED}TIMEOUT${NC} ${elapsed}s"; REQ_FAIL=$((REQ_FAIL+1))
    elif [ "$exit_code" -ne 0 ]; then echo -e "${RED}FAIL${NC} ${elapsed}s"; REQ_FAIL=$((REQ_FAIL+1)); tail -5 "$LOG_DIR/gate-$(printf '%s' "$num").log"
    else echo -e "${GREEN}PASS${NC} ${elapsed}s"; REQ_PASS=$((REQ_PASS+1)); fi
}

echo "INFRA-AGAIN V7 ACCEPTANCE"; echo "Logs: $LOG_DIR"; echo ""

run_gate 1 "V6 regression"              "bash $GATES_DIR/01-v6-regression.sh" 1200 || true
run_gate 2 "Execution models"           "python3.11 $GATES_DIR/02-execution-models.py" 30 || true
run_gate 3 "Plan mapper"                "python3.11 $GATES_DIR/03-plan-mapper.py" 30 || true
run_gate 4 "Preflight + Policy"         "python3.11 $GATES_DIR/04-preflight-policy.py" 30 || true
run_gate 5 "Plan-only execution"        "python3.11 $GATES_DIR/05-plan-only.py" 120 || true
run_gate 6 "Fakecloud execution"        "python3.11 $GATES_DIR/06-fakecloud-execution.py" 180 || true
run_gate 7 "Kind execution"             "python3.11 $GATES_DIR/07-kind-execution.py" 240 || true
run_gate 8 "Safety blocks"              "python3.11 $GATES_DIR/08-safety-blocks.py" 30 || true
run_gate "8b" "Ownership safety"          "python3.11 $GATES_DIR/08b-ownership.py" 120 || true
run_gate "8c" "Checksum + cloud safety"   "python3.11 $GATES_DIR/08c-checksum.py" 30 || true
run_gate 9 "Idempotency"                  "python3.11 $GATES_DIR/09-idempotency.py" 60 || true
run_gate 10 "Runner loss"                 "python3.11 $GATES_DIR/10-runner-loss.py" 30 || true
run_gate 11 "Persistence"                 "python3.11 $GATES_DIR/11-persistence.py" 120 || true
run_gate 12 "API /execute E2E"            "python3.11 $GATES_DIR/12-api-runtime.py" 300 || true
run_gate 13 "Evidence"                    "python3.11 $GATES_DIR/13-evidence.py" 30 || true
run_gate 14 "Frontend truth"              "python3.11 $GATES_DIR/14-frontend-truth.py" 30 || true
run_gate 15 "Frontend build"              "bash $GATES_DIR/15-frontend.sh" 180 || true

TOTAL=$((GT1+GT2+GT3+GT4+GT5+GT6+GT7+GT8+GT8b+GT8c+GT9+GT10+GT11+GT12+GT13+GT14+GT15))
echo ""; echo "========================================"; echo "INFRA-AGAIN V7 ACCEPTANCE"; echo "========================================"
echo ""; echo "Required: PASS=$REQ_PASS FAIL=$REQ_FAIL SKIP=$REQ_SKIP"; echo "TOTAL=${TOTAL}s"; echo ""
[ "$REQ_FAIL" -eq 0 ] && [ "$REQ_SKIP" -eq 0 ] && { echo "Phase 7 = LOCAL_VERIFIED"; exit 0; } || { echo "Phase 7 = PARTIAL/FAILED"; exit 1; }
