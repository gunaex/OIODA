#!/usr/bin/env bash
# Gate 06: Frontend fresh build
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_DIR"
START=$(date +%s)

if [ ! -d ui ]; then
    echo "SKIP: No ui/ directory"
    exit 0
fi

# Remove stale dist
rm -rf ui/dist

# npm ci (fail-closed: no fallback)
echo "  npm ci..."
set +e
(cd ui && npm ci --silent 2>&1) > "$1/npm-ci.log" 2>&1
NPM_EXIT=$?
set -e
if [ "$NPM_EXIT" -ne 0 ]; then
    echo "FAIL: npm ci exit=$NPM_EXIT"
    tail -10 "$1/npm-ci.log"
    exit 1
fi

# Build
echo "  vite build..."
set +e
(cd ui && npx vite build 2>&1) > "$1/vite-build.log" 2>&1
BUILD_EXIT=$?
set -e
if [ "$BUILD_EXIT" -ne 0 ]; then
    echo "FAIL: vite build exit=$BUILD_EXIT"
    tail -10 "$1/vite-build.log"
    exit 1
fi

if [ ! -f ui/dist/index.html ]; then
    echo "FAIL: dist/index.html missing after build"
    exit 1
fi

ELAPSED=$(($(date +%s) - START))
echo "PASS ${ELAPSED}s"
echo "  UI_TEST_SCRIPT = NOT_CONFIGURED"
exit 0
