#!/bin/bash
# Phase 8 Version-Aware Regression
# 
# Verifies Phase 7 invariants that MUST remain true in Phase 8,
# while explicitly acknowledging intentional policy evolution.
#
# Runs:
#   A. Phase 7 non-policy invariants against Phase 8 runtime (must PASS)
#   B. Phase 7 historical policy assertions (SANDBOX=BLOCK - will FAIL intentionally)
#   C. Phase 8 current policy assertions (SANDBOX=ASK - must PASS)
#   D. Cross-phase invariants (PRODUCTION=BLOCK, CONTROLLED_REAL=BLOCK)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LOG_DIR="${1:-/tmp/infra-again-acceptance-v8-regression}"
mkdir -p "$LOG_DIR"
PYTHON="$PROJECT/.venv/bin/python"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

TOTAL=0
PASS=0
FAIL=0
INTENTIONAL_FAIL=0

run_check() {
    local category=$1
    local name=$2
    local script=$3
    local expect=$4  # "pass" or "intentional-fail"
    TOTAL=$((TOTAL + 1))
    echo -n "  [$category] ${name}... "
    if PYTHONPATH="$PROJECT/src" "$PYTHON" "$SCRIPT_DIR/../v7/$script" "$LOG_DIR" > "$LOG_DIR/${category}_${name}.log" 2>&1; then
        if [ "$expect" = "pass" ]; then
            echo -e "${GREEN}PASS${NC}"
            PASS=$((PASS + 1))
        else
            echo -e "${YELLOW}PASS (expected FAIL — policy transition?)${NC}"
            PASS=$((PASS + 1))
        fi
    else
        if [ "$expect" = "intentional-fail" ]; then
            echo -e "${YELLOW}INTENTIONAL_FAIL${NC} (Phase 7 policy evolved in Phase 8)"
            INTENTIONAL_FAIL=$((INTENTIONAL_FAIL + 1))
        else
            echo -e "${RED}FAIL${NC}"
            FAIL=$((FAIL + 1))
        fi
    fi
}

echo "INFRA-AGAIN Phase 8 Version-Aware Regression"
echo "Log: $LOG_DIR"
echo ""

# ============================================================================
# A. Phase 7 non-policy invariants (must PASS against Phase 8 runtime)
# ============================================================================
echo -e "${CYAN}── A. Phase 7 Non-Policy Invariants (must PASS) ──${NC}"
run_check "A" "execution-models"    "02-execution-models.py"    "pass"
run_check "A" "plan-mapper"         "03-plan-mapper.py"         "pass"
run_check "A" "plan-only-execution" "05-plan-only.py"           "pass"
run_check "A" "ownership"           "08b-ownership.py"          "pass"
run_check "A" "idempotency"         "09-idempotency.py"         "pass"
run_check "A" "runner-loss"         "10-runner-loss.py"         "pass"
run_check "A" "persistence"         "11-persistence.py"         "pass"
run_check "A" "evidence"            "13-evidence.py"            "pass"

# ============================================================================
# B. Phase 7 historical policy assertions (will FAIL — intentional evolution)
# ============================================================================
echo ""
echo -e "${YELLOW}── B. Phase 7 Historical Policy (SANDBOX=BLOCK — intentional evolution) ──${NC}"
run_check "B" "preflight-policy-historical"  "04-preflight-policy.py"  "intentional-fail"
run_check "B" "safety-blocks-historical"     "08-safety-blocks.py"     "intentional-fail"
run_check "B" "checksum-historical"          "08c-checksum.py"         "intentional-fail"

# ============================================================================
# C. Phase 8 current policy assertions (must PASS)
# ============================================================================
echo ""
echo -e "${CYAN}── C. Phase 8 Current Policy (SANDBOX=ASK) ──${NC}"
PYTHONPATH="$PROJECT/src" "$PYTHON" -c "
import sys
sys.path.insert(0, '$PROJECT/src')
from infra_again.execution.policy_version import (
    PolicyProfile, PHASE7_HISTORICAL_BLOCK, PHASE7_HISTORICAL_ASK, PHASE7_HISTORICAL_ALLOW,
    PHASE8_CURRENT_BLOCK, PHASE8_CURRENT_ASK, PHASE8_CURRENT_ALLOW,
    INVARIANT_BLOCK_ALWAYS, INVARIANT_ALLOW_ALWAYS,
    policy_transition_summary,
)
from infra_again.execution.phase7_models import ExecutionFidelity
from infra_again.execution.policy import (
    ExecutionPolicyEngine, PHASE7_ALLOWED, PHASE7_ASK, PHASE7_BLOCK, PHASE8_ASK,
)

# Verify policy constants
passed = 0
failed = 0

def check(name, cond, detail=''):
    global passed, failed
    if cond: print(f'  PASS: {name}'); passed += 1
    else: print(f'  FAIL: {name} {detail}'); failed += 1

print()
print('Phase 8 policy constants:')
check('SANDBOX in PHASE8_ASK', ExecutionFidelity.SANDBOX in PHASE8_ASK)
check('SANDBOX NOT in PHASE7_BLOCK', ExecutionFidelity.SANDBOX not in PHASE7_BLOCK)
check('CONTROLLED_REAL in PHASE7_BLOCK', ExecutionFidelity.CONTROLLED_REAL in PHASE7_BLOCK)
check('PRODUCTION in PHASE7_BLOCK', ExecutionFidelity.PRODUCTION in PHASE7_BLOCK)

print()
print('Invariants:')
check('CONTROLLED_REAL always BLOCK', ExecutionFidelity.CONTROLLED_REAL in INVARIANT_BLOCK_ALWAYS)
check('PRODUCTION always BLOCK', ExecutionFidelity.PRODUCTION in INVARIANT_BLOCK_ALWAYS)
check('PLAN_ONLY always ALLOW', ExecutionFidelity.PLAN_ONLY in INVARIANT_ALLOW_ALWAYS)
check('SIMULATED always ALLOW', ExecutionFidelity.SIMULATED in INVARIANT_ALLOW_ALWAYS)
check('LOCAL_RUNTIME always ALLOW', ExecutionFidelity.LOCAL_RUNTIME in INVARIANT_ALLOW_ALWAYS)

print()
print('Policy transition:')
summary = policy_transition_summary()
check('PHASE7_SANDBOX=BLOCK', summary['PHASE7_SANDBOX_POLICY'] == 'BLOCK')
check('PHASE8_SANDBOX=ASK', summary['PHASE8_SANDBOX_POLICY'] == 'ASK')
check('TRANSITION_INTENTIONAL', summary['POLICY_TRANSITION_INTENTIONAL'] == True)

print()
print('Phase 7 historical profile:')
check('SANDBOX in P7 BLOCK', ExecutionFidelity.SANDBOX in PHASE7_HISTORICAL_BLOCK)
check('CONTROLLED_REAL in P7 BLOCK', ExecutionFidelity.CONTROLLED_REAL in PHASE7_HISTORICAL_BLOCK)
check('PRODUCTION in P7 BLOCK', ExecutionFidelity.PRODUCTION in PHASE7_HISTORICAL_BLOCK)

print()
print('Phase 8 current profile:')
check('SANDBOX in P8 ASK', ExecutionFidelity.SANDBOX in PHASE8_CURRENT_ASK)
check('CONTROLLED_REAL in P8 BLOCK', ExecutionFidelity.CONTROLLED_REAL in PHASE8_CURRENT_BLOCK)
check('PRODUCTION in P8 BLOCK', ExecutionFidelity.PRODUCTION in PHASE8_CURRENT_BLOCK)
check('PLAN_ONLY in P8 ALLOW', ExecutionFidelity.PLAN_ONLY in PHASE8_CURRENT_ALLOW)

print()
print(f'Phase 8 policy assertions: {passed} PASS / {failed} FAIL')
sys.exit(0 if failed == 0 else 1)
" 2>&1
C_RESULT=$?
TOTAL=$((TOTAL + 1))
if [ $C_RESULT -eq 0 ]; then
    echo -e "${GREEN}PASS${NC}: Phase 8 policy assertions"
    PASS=$((PASS + 1))
else
    echo -e "${RED}FAIL${NC}: Phase 8 policy assertions"
    FAIL=$((FAIL + 1))
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Version-Aware Regression Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  ${GREEN}PASS:${NC}              ${PASS}"
echo -e "  ${RED}FAIL:${NC}              ${FAIL}"
echo -e "  ${YELLOW}INTENTIONAL FAIL:${NC}  ${INTENTIONAL_FAIL}"
echo -e "  TOTAL:             ${TOTAL}"
echo ""
echo "Policy Evolution:"
echo "  PHASE7_HISTORICAL_SANDBOX_POLICY=BLOCK"
echo "  PHASE8_CURRENT_SANDBOX_POLICY=ASK"
echo "  POLICY_TRANSITION_INTENTIONAL=true"
echo ""
echo "Invariants Preserved:"
echo "  CONTROLLED_REAL=BLOCK"
echo "  PRODUCTION=BLOCK"
echo "  PLAN_ONLY=ALLOW"
echo "  SIMULATED=ALLOW"
echo "  LOCAL_RUNTIME=ALLOW"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Real regressions detected — review FAIL items${NC}"
    exit 1
fi

exit 0
