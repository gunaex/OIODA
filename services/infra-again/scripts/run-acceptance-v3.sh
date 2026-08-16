#!/usr/bin/env bash
# INFRA-AGAIN Phase 3 Deterministic Acceptance Runner
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; N='\033[0m'

PYTHON="${PYTHON:-python3.11}"; command -v "$PYTHON" &>/dev/null || PYTHON="$(command -v python3 || echo '')"
[ -z "$PYTHON" ] && { echo -e "${R}FAIL: python3${N}"; exit 1; }

FC_PID=""; KC="ia-accept-$(date +%s)"
cleanup() { [ -n "$FC_PID" ] && kill "$FC_PID" 2>/dev/null || true; kind delete cluster --name "$KC" 2>/dev/null || true; }
trap cleanup EXIT

FAIL=0; PASS=0; SKIP=0; OPT_UNAVAIL=0

log_pass() { echo -e "  ${G}PASS${N}: $1"; PASS=$((PASS+1)); }
log_fail() { echo -e "  ${R}FAIL${N}: $1"; FAIL=$((FAIL+1)); }
log_skip() { echo -e "  ${Y}SKIP${N}: $1"; SKIP=$((SKIP+1)); }
log_opt()  { echo -e "  ${Y}NOT_INSTALLED${N}: $1"; OPT_UNAVAIL=$((OPT_UNAVAIL+1)); }

echo "INFRA-AGAIN Phase 3 Acceptance"; echo ""

# --- Detect tools ---
echo "=== Environment ==="
echo "Python: $($PYTHON --version)"
for t in fakecloud kind kubectl tofu node npm docker; do
    v=$(command -v "$t" 2>/dev/null && $t --version 2>&1 | head -1 || echo "NOT_FOUND")
    echo "  $t: $v"
done
echo ""

# --- Start fakecloud ---
FC_BIN="${FAKECLOUD_BIN:-$(command -v fakecloud || echo '')}"
if [ -n "$FC_BIN" ]; then
    lsof -ti :4566 &>/dev/null && kill "$(lsof -ti :4566)" 2>/dev/null || true; sleep 1
    "$FC_BIN" &>/tmp/fc-accept-v3.log & FC_PID=$!
    for i in $(seq 1 20); do curl -s http://localhost:4566/_fakecloud/health &>/dev/null && break; sleep 1; done
    curl -s http://localhost:4566/_fakecloud/health | "$PYTHON" -c "import sys,json; print('fakecloud:', json.load(sys.stdin)['status'])" 2>/dev/null || log_fail "fakecloud health"
else
    log_fail "fakecloud not found"
fi

# --- Start kind ---
if command -v kind &>/dev/null; then
    kind delete cluster --name "$KC" 2>/dev/null || true
    kind create cluster --name "$KC" 2>&1 | tail -1
    log_pass "kind cluster created"
else
    log_fail "kind not found"
fi

# --- Run tests ---
cd "$PROJECT_DIR"
echo ""; echo "=== Tests ==="
TEST_EXIT=0
"$PYTHON" -m pytest tests/ -q 2>&1 || TEST_EXIT=$?

[ "$TEST_EXIT" -eq 0 ] && log_pass "All tests passed" || log_fail "Tests failed"

# --- Optional targets ---
if command -v minikube &>/dev/null; then log_pass "minikube READY"; else log_opt "minikube"; fi
if command -v crc &>/dev/null; then log_pass "CRC READY"; else log_opt "CRC"; fi

# --- API test ---
echo ""; echo "=== API ==="
"$PYTHON" -c "
from infra_again.api import app; from fastapi.testclient import TestClient
c = TestClient(app)
assert c.get('/health').status_code == 200
assert c.get('/api/v1/capabilities').status_code == 200
assert c.get('/api/v1/targets').status_code == 200
print('API: OK')
" 2>&1 && log_pass "API acceptance" || log_fail "API acceptance"

# --- UI build ---
echo ""; echo "=== UI ==="
if [ -d ui ]; then
    cd ui && npm ci --silent 2>&1 | tail -1 && npx vite build 2>&1 | tail -1 && cd ..
    log_pass "UI build"
else
    log_skip "UI directory not found"
fi

# --- Report ---
echo ""; echo "============================================"
echo " Phase 3 Acceptance Results"
echo "============================================"
echo "  Required PASS:   $PASS"
echo "  Required FAIL:   $FAIL"
echo "  Required SKIP:   $SKIP"
echo "  Optional N/A:    $OPT_UNAVAIL"
echo ""

if [ "$FAIL" -eq 0 ] && [ "$SKIP" -eq 0 ]; then
    echo -e "${G}ACCEPTED${N}"; exit 0
else
    echo -e "${R}PARTIAL/FAILED${N}"; exit 1
fi
