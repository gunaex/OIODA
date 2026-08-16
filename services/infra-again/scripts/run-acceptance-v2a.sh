#!/usr/bin/env bash
# INFRA-AGAIN Phase 2A.1 Deterministic Acceptance Runner
# Portable: macOS and Linux/Ubuntu compatible.
# Uses: FAKECLOUD_BIN env var or finds fakecloud in PATH.
# Does NOT assume Homebrew path.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo " INFRA-AGAIN Phase 2A.1 Acceptance Runner"
echo "============================================"
echo ""

# ------------------------------------------------------------------
# 1. Find fakecloud binary
# ------------------------------------------------------------------
FAKECLOUD_BIN="${FAKECLOUD_BIN:-}"
if [ -z "$FAKECLOUD_BIN" ]; then
    FAKECLOUD_BIN="$(command -v fakecloud 2>/dev/null || echo '')"
fi

if [ -z "$FAKECLOUD_BIN" ]; then
    echo -e "${RED}FAIL: fakecloud not found in PATH. Set FAKECLOUD_BIN env var.${NC}"
    exit 1
fi

FAKECLOUD_VERSION="$("$FAKECLOUD_BIN" --version 2>&1)"
echo -e "${GREEN}OK:${NC} fakecloud found at $FAKECLOUD_BIN"
echo "    Version: $FAKECLOUD_VERSION"
echo ""

# ------------------------------------------------------------------
# 2. Find Python
# ------------------------------------------------------------------
PYTHON="${PYTHON:-python3.11}"
if ! command -v "$PYTHON" &>/dev/null; then
    PYTHON="$(command -v python3 2>/dev/null || echo '')"
fi
if [ -z "$PYTHON" ] || ! command -v "$PYTHON" &>/dev/null; then
    echo -e "${RED}FAIL: python3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}OK:${NC} Python: $("$PYTHON" --version 2>&1)"
echo ""

# ------------------------------------------------------------------
# 3. Clean up any stale fakecloud
# ------------------------------------------------------------------
FAKECLOUD_PID=""
cleanup() {
    if [ -n "$FAKECLOUD_PID" ] && kill -0 "$FAKECLOUD_PID" 2>/dev/null; then
        echo ""
        echo "Stopping fakecloud (PID=$FAKECLOUD_PID)..."
        kill "$FAKECLOUD_PID" 2>/dev/null || true
        wait "$FAKECLOUD_PID" 2>/dev/null || true
        echo "fakecloud stopped."
    fi
}
trap cleanup EXIT

# ------------------------------------------------------------------
# 4. Start fakecloud
# ------------------------------------------------------------------
FAKECLOUD_PORT="${FAKECLOUD_PORT:-4566}"
FAKECLOUD_ENDPOINT="http://localhost:${FAKECLOUD_PORT}"
echo "Starting fakecloud on port $FAKECLOUD_PORT..."
"$FAKECLOUD_BIN" &>/tmp/infra-again-fakecloud-acceptance.log &
FAKECLOUD_PID=$!
echo "fakecloud PID: $FAKECLOUD_PID"

# ------------------------------------------------------------------
# 5. Wait for health
# ------------------------------------------------------------------
echo -n "Waiting for fakecloud health..."
for i in $(seq 1 30); do
    if curl -s "${FAKECLOUD_ENDPOINT}/_fakecloud/health" >/dev/null 2>&1; then
        echo -e " ${GREEN}OK${NC}"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e " ${RED}FAIL${NC}"
        echo "fakecloud did not become healthy within 30s"
        cat /tmp/infra-again-fakecloud-acceptance.log
        exit 1
    fi
    sleep 1
done
echo ""

# ------------------------------------------------------------------
# 6. Verify fakecloud health endpoint
# ------------------------------------------------------------------
echo "Verifying fakecloud endpoint..."
HEALTH_RESP=$(curl -s "${FAKECLOUD_ENDPOINT}/_fakecloud/health")
if echo "$HEALTH_RESP" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}OK:${NC} fakecloud healthy at ${FAKECLOUD_ENDPOINT}"
else
    echo -e "${RED}FAIL:${NC} unexpected health response: $HEALTH_RESP"
    exit 1
fi
echo ""

# ------------------------------------------------------------------
# 7. Run tests
# ------------------------------------------------------------------
echo "============================================"
echo " Running Phase 2A.1 Acceptance Tests"
echo "============================================"
echo ""

cd "$PROJECT_DIR"

# Run ALL tests. SIMULATED tests must NOT skip.
TEST_EXIT=0
"$PYTHON" -m pytest tests/ \
    --tb=short \
    -v \
    -p no:warnings \
    2>&1 || TEST_EXIT=$?

echo ""
echo "============================================"
echo " Results"
echo "============================================"

if [ "$TEST_EXIT" -eq 0 ]; then
    echo -e "${GREEN}PASS: All tests passed${NC}"
else
    echo -e "${RED}FAIL: Tests failed (exit=$TEST_EXIT)${NC}"
fi

echo ""
echo "fakecloud log: /tmp/infra-again-fakecloud-acceptance.log"
echo "Evidence dir: $PROJECT_DIR/.ai/infra-runs/"
echo ""

exit $TEST_EXIT
