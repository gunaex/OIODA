#!/usr/bin/env bash
# ==============================================================================
# INFRA-AGAIN Phase 2B Acceptance Runner
# OpenTofu Integration + Architecture Visualization
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

# ---------------------------------------------------------------------------
# 1. Detect Python
# ---------------------------------------------------------------------------
PYTHON="${PYTHON:-python3.11}"
if ! command -v "$PYTHON" &>/dev/null; then
    PYTHON="$(command -v python3 2>/dev/null || echo '')"
fi
if [ -z "$PYTHON" ]; then echo -e "${RED}FAIL: python3 not found${NC}"; exit 1; fi
echo -e "${GREEN}OK:${NC} Python: $("$PYTHON" --version)"

# ---------------------------------------------------------------------------
# 2. Detect OpenTofu
# ---------------------------------------------------------------------------
TOFU="${TOFU:-tofu}"
if ! command -v "$TOFU" &>/dev/null; then echo -e "${RED}FAIL: OpenTofu not found${NC}"; exit 1; fi
TOFU_VER="$("$TOFU" version 2>&1)"
echo -e "${GREEN}OK:${NC} $TOFU_VER"

# ---------------------------------------------------------------------------
# 3. Detect fakecloud
# ---------------------------------------------------------------------------
FAKECLOUD_BIN="${FAKECLOUD_BIN:-}"
if [ -z "$FAKECLOUD_BIN" ]; then FAKECLOUD_BIN="$(command -v fakecloud 2>/dev/null || echo '')"; fi
if [ -z "$FAKECLOUD_BIN" ]; then
    for c in /opt/homebrew/bin/fakecloud /usr/local/bin/fakecloud; do
        [ -x "$c" ] && { FAKECLOUD_BIN="$c"; break; }
    done
fi
if [ -z "$FAKECLOUD_BIN" ]; then echo -e "${RED}FAIL: fakecloud not found${NC}"; exit 1; fi
FC_VER="$("$FAKECLOUD_BIN" --version 2>&1)"
echo -e "${GREEN}OK:${NC} fakecloud: $FC_VER"

# ---------------------------------------------------------------------------
# 4. Start fakecloud
# ---------------------------------------------------------------------------
FAKECLOUD_PID=""
cleanup() { [ -n "$FAKECLOUD_PID" ] && kill "$FAKECLOUD_PID" 2>/dev/null || true; }
trap cleanup EXIT

PORT=4566
lsof -ti :$PORT &>/dev/null && { echo -e "${YELLOW}Port $PORT busy — killing${NC}"; kill "$(lsof -ti :$PORT)" 2>/dev/null || true; sleep 1; }
"$FAKECLOUD_BIN" &>/tmp/infra-again-fc-v2b.log &
FAKECLOUD_PID=$!

for i in $(seq 1 30); do
    curl -s "http://localhost:$PORT/_fakecloud/health" &>/dev/null && break
    [ "$i" -eq 30 ] && { echo -e "${RED}FAIL: fakecloud timeout${NC}"; exit 1; }
    sleep 1
done
echo -e "${GREEN}OK:${NC} fakecloud healthy"

# ---------------------------------------------------------------------------
# 5. Run tests
# ---------------------------------------------------------------------------
cd "$PROJECT_DIR"
echo ""; echo "=== Phase 2B Acceptance ==="; echo ""

EXIT=0
"$PYTHON" -m pytest tests/ --tb=short -q 2>&1 || EXIT=$?

echo ""
if [ "$EXIT" -eq 0 ]; then
    echo -e "${GREEN}PASS: All tests passed${NC}"
else
    echo -e "${RED}FAIL: Tests failed (exit=$EXIT)${NC}"
fi

echo ""; echo "OpenTofu: $TOFU_VER"; echo "fakecloud: $FC_VER"
echo "Evidence: $PROJECT_DIR/.ai/infra-runs/"
exit $EXIT
