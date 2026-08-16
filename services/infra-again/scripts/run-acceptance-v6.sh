#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GATES_DIR="$SCRIPT_DIR/acceptance/v6"; cd "$PROJECT_DIR"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
LOG_DIR="$PROJECT_DIR/.ai/acceptance/v6/latest"; rm -rf "$LOG_DIR"; mkdir -p "$LOG_DIR"
REQ_PASS=0; REQ_FAIL=0; REQ_SKIP=0
GT1=0;GT2=0;GT3=0;GT4=0;GT5=0;GT6=0;GT7=0;GT8=0;GT9=0;GT10=0;GT11=0;GT12=0
TOOL="$SCRIPT_DIR/acceptance/run_with_timeout.py"

run_gate() {
    local num="$1"; local name="$2"; local cmd="$3"; local timeout="${4:-60}"
    echo ""; printf "[%d/12] %-35s " "$num" "$name"
    local start=$(date +%s); local exit_code=0
    python3.11 "$TOOL" --timeout "$timeout" -- bash -c "$cmd '$LOG_DIR'" > "$LOG_DIR/gate-$(printf '%02d' "$num").log" 2>&1 || exit_code=$?
    local elapsed=$(($(date +%s)-start)); eval "GT$num=$elapsed"
    if [ "$exit_code" -eq 124 ]; then echo -e "${RED}TIMEOUT${NC} ${elapsed}s"; REQ_FAIL=$((REQ_FAIL+1))
    elif [ "$exit_code" -ne 0 ]; then echo -e "${RED}FAIL${NC} ${elapsed}s"; REQ_FAIL=$((REQ_FAIL+1)); tail -5 "$LOG_DIR/gate-$(printf '%02d' "$num").log"
    else echo -e "${GREEN}PASS${NC} ${elapsed}s"; REQ_PASS=$((REQ_PASS+1)); fi
}

echo "INFRA-AGAIN V6 ACCEPTANCE"; echo "Logs: $LOG_DIR"; echo ""
run_gate 1 "V5.1 regression"          "bash $GATES_DIR/01-v5-1-regression.sh" 1200 || true
run_gate 2 "Plan models"              "python3.11 $GATES_DIR/02-plan-models.py" 30 || true
run_gate 3 "Golden planner"           "python3.11 $GATES_DIR/03-golden-planner.py" 30 || true
run_gate 4 "Dependencies"             "python3.11 $GATES_DIR/04-dependencies.py" 30 || true
run_gate 5 "Readiness"                "python3.11 $GATES_DIR/05-readiness.py" 30 || true
run_gate 6 "Persistence"              "python3.11 $GATES_DIR/06-persistence.py" 30 || true
run_gate 7 "API runtime"              "python3.11 $GATES_DIR/07-api-runtime.py" 90 || true
run_gate 8 "Handoff"                  "python3.11 $GATES_DIR/08-handoff.py" 30 || true
run_gate 9 "Frontend build"             "bash $GATES_DIR/09-frontend.sh" 180 || true
run_gate 10 "Frontend truth"             "python3.11 $GATES_DIR/10-frontend-truth.py" 30 || true
run_gate 11 "API/UI contract"            "python3.11 $GATES_DIR/11-api-ui-contract.py" 60 || true
run_gate 12 "Design derivation"          "python3.11 $GATES_DIR/12-design-derivation.py" 30 || true
TOTAL=$((GT1+GT2+GT3+GT4+GT5+GT6+GT7+GT8+GT9+GT10+GT11+GT12))
echo ""; echo "========================================"; echo "INFRA-AGAIN V6 ACCEPTANCE"; echo "========================================"
echo ""; echo "Required: PASS=$REQ_PASS FAIL=$REQ_FAIL SKIP=$REQ_SKIP"; echo "TOTAL=${TOTAL}s"; echo ""
[ "$REQ_FAIL" -eq 0 ] && [ "$REQ_SKIP" -eq 0 ] && { echo "Phase 6 = LOCAL_VERIFIED"; exit 0; } || { echo "Phase 6 = PARTIAL/FAILED"; exit 1; }
