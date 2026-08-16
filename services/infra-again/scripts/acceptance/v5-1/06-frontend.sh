#!/usr/bin/env bash
# Gate 06: Frontend fresh build
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_DIR"
START=$(date +%s)
if [ ! -d ui ]; then echo "SKIP: No ui/"; exit 0; fi
rm -rf ui/dist
set +e
(cd ui && npm ci --silent 2>&1) > "$1/npm-ci.log" 2>&1; NPM_EXIT=$?
(cd ui && npx vite build 2>&1) > "$1/vite-build.log" 2>&1; BUILD_EXIT=$?
set -e
[ "$NPM_EXIT" -ne 0 ] && { echo "FAIL: npm ci exit=$NPM_EXIT"; tail -10 "$1/npm-ci.log"; exit 1; }
[ "$BUILD_EXIT" -ne 0 ] && { echo "FAIL: vite build exit=$BUILD_EXIT"; tail -10 "$1/vite-build.log"; exit 1; }
[ ! -f ui/dist/index.html ] && { echo "FAIL: dist/index.html missing"; exit 1; }
ELAPSED=$(($(date +%s) - START))
echo "PASS ${ELAPSED}s"
