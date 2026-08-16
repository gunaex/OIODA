#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GATES_DIR="$SCRIPT_DIR/acceptance/v5-1"; cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
LOG_DIR="$PROJECT_DIR/.ai/acceptance/v5-1/latest"; rm -rf "$LOG_DIR"; mkdir -p "$LOG_DIR"
REQ_PASS=0; REQ_FAIL=0; REQ_SKIP=0
GT1=0; GT2=0; GT3=0; GT4=0; GT5=0; GT6=0
GR1=""; GR2=""; GR3=""; GR4=""; GR5=""; GR6=""
TOOL="$SCRIPT_DIR/acceptance/run_with_timeout.py"

run_gate() {
    local num="$1"; local name="$2"; local cmd="$3"; local timeout="${4:-60}"
    echo ""; printf "[%d/6] %-30s " "$num" "$name"
    local start=$(date +%s); local exit_code=0
    python3.11 "$TOOL" --timeout "$timeout" -- bash -c "$cmd '$LOG_DIR'" > "$LOG_DIR/gate-$(printf '%02d' "$num").log" 2>&1 || exit_code=$?
    local elapsed=$(($(date +%s) - start))
    eval "GT$num=$elapsed"
    if [ "$exit_code" -eq 124 ]; then result="TIMEOUT"; REQ_FAIL=$((REQ_FAIL+1))
    elif [ "$exit_code" -ne 0 ]; then result="FAIL"; REQ_FAIL=$((REQ_FAIL+1))
    else result="PASS"; REQ_PASS=$((REQ_PASS+1)); fi
    eval "GR$num=\$result"
    if [ "$result" = "PASS" ]; then echo -e "${GREEN}PASS${NC} ${elapsed}s"
    elif [ "$result" = "TIMEOUT" ]; then echo -e "${RED}TIMEOUT${NC} ${elapsed}s"; tail -5 "$LOG_DIR/gate-$(printf '%02d' "$num").log"
    else echo -e "${RED}FAIL${NC} ${elapsed}s"; tail -10 "$LOG_DIR/gate-$(printf '%02d' "$num").log"; fi
}

echo "INFRA-AGAIN V5.1 ACCEPTANCE"; echo "Logs: $LOG_DIR"; echo ""

run_gate 1 "V5 regression"       "bash $GATES_DIR/01-v5-regression.sh" 900 || true
run_gate 2 "Flow projections"    "python3.11 $GATES_DIR/02-flow-projections.py" 30 || true
run_gate 3 "Scenario UI truth"   "python3.11 $GATES_DIR/03-scenario-ui-truth.py" 30 || true
run_gate 4 "Design review truth" "python3.11 $GATES_DIR/04-design-review-truth.py" 30 || true
run_gate 5 "Large graph"         "python3.11 $GATES_DIR/05-large-graph.py" 30 || true
run_gate 6 "Frontend build"      "bash $GATES_DIR/06-frontend.sh" 180 || true

TOTAL_DUR=$((GT1+GT2+GT3+GT4+GT5+GT6))
echo ""; echo "========================================"; echo "INFRA-AGAIN V5.1 ACCEPTANCE"; echo "========================================"
echo ""; echo "Required:"; echo "  PASS = $REQ_PASS"; echo "  FAIL = $REQ_FAIL"; echo "  SKIP = $REQ_SKIP"
echo ""; echo "Optional:"; echo "  BROWSER_VISUAL_QA = NOT_EXECUTED"
echo "  REAL_CLOUD = NOT_EXECUTED"; echo "  OBSERVED_RUNTIME = NOT_EXECUTED"
echo ""; echo "TOTAL_DURATION = ${TOTAL_DUR}s"; echo ""

cat > "$LOG_DIR/summary.json" << EOFJSON
{"phase":"5.1.1","gates":[
{"name":"v5-regression","result":"${GR1:-SKIP}","durationSeconds":$GT1},
{"name":"flow-projections","result":"${GR2:-SKIP}","durationSeconds":$GT2},
{"name":"scenario-ui-truth","result":"${GR3:-SKIP}","durationSeconds":$GT3},
{"name":"design-review-truth","result":"${GR4:-SKIP}","durationSeconds":$GT4},
{"name":"large-graph","result":"${GR5:-SKIP}","durationSeconds":$GT5},
{"name":"frontend","result":"${GR6:-SKIP}","durationSeconds":$GT6}
],"requiredPass":$REQ_PASS,"requiredFail":$REQ_FAIL,"requiredSkip":$REQ_SKIP,"totalDurationSeconds":$TOTAL_DUR,"exitCode":$([ "$REQ_FAIL" -eq 0 ] && echo 0 || echo 1)}
EOFJSON

if [ "$REQ_FAIL" -eq 0 ] && [ "$REQ_SKIP" -eq 0 ]; then
    echo "Phase 5.1 = LOCAL_VERIFIED"; echo "exit = 0"; exit 0
else
    echo "Phase 5.1 = PARTIAL/FAILED"; echo "exit = 1"; exit 1
fi
