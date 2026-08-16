#!/usr/bin/env bash
# OIDA monorepo — local ecosystem starter (R16 Phase 4).
# Starts every bounded service + OIDA Web. Idempotent: skips services already
# listening. Secrets (API keys, signing keys) are NOT stored here.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="${TMPDIR:-/tmp}/oida-logs"
mkdir -p "$LOG_DIR"

DOC_SECRET="${DOCUMENT_AGAIN_CLIENT_SECRET:-dev}"

# Account Again signing key (ephemeral local-only, generated if missing).
ACCOUNT_KEY="/tmp/oida-account-signing-key.pem"
if [ ! -f "$ACCOUNT_KEY" ]; then
  openssl genpkey -algorithm RSA -out "$ACCOUNT_KEY" -pkeyopt rsa_keygen_bits:2048 >/dev/null 2>&1
fi
ACCOUNT_KEY_B64="$(base64 < "$ACCOUNT_KEY" | tr -d '\n')"

start() {
  name="$1"; port="$2"; cwd="$3"; shift 3
  if lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "  [skip] $name already on :$port"; return 0
  fi
  ( cd "$cwd" && nohup "$@" > "$LOG_DIR/$name.log" 2>&1 & )
  echo "  [start] $name -> :$port"
}

echo "Starting OIDA local ecosystem…"

start "account-again" 8011 "$ROOT/ACCOUNT-AGAIN" \
  env ACCOUNT_AGAIN_DATABASE_URL="sqlite:////Users/kanphong/ACCOUNT-AGAIN/account_again_full_loop.db" \
      ACCOUNT_AGAIN_SIGNING_KEY_B64="$ACCOUNT_KEY_B64" \
      ACCOUNT_AGAIN_SIGNING_KEY_ID="account-again-local-ssso" \
      .venv/bin/python -m uvicorn account_again.main:app --host 127.0.0.1 --port 8011 --app-dir /Users/kanphong/ACCOUNT-AGAIN

start "document-again" 8003 "$ROOT/DOCUMENT-AGAIN/backend" \
  env AUTH_MODE=local ACCOUNT_AGAIN_URL=http://127.0.0.1:8011 \
      CONDUCTOR_MAIN_URL=http://127.0.0.1:8010/api \
      DOCUMENT_AGAIN_CLIENT_SECRET="$DOC_SECRET" \
      .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8003

start "pm-again" 8000 "$ROOT/PM-AGAIN/backend" \
  env AUTH_MODE=local ACCOUNT_AGAIN_URL=http://127.0.0.1:8011 \
      .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

start "qa-again" 8002 "$ROOT/QA-AGAIN/backend" \
  env AUTH_MODE=local ACCOUNT_AGAIN_URL=http://127.0.0.1:8011 \
      .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8002

start "infra-again" 18090 "$ROOT/INFRA-AGAIN" \
  env PYTHONPATH=src .venv/bin/python -m uvicorn infra_again.api.app:app --host 127.0.0.1 --port 18090

start "conductor-again" 8010 "$ROOT/CONDUCTOR-AGAIN/backend" \
  env AUTH_MODE=local .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010

echo "Done. Run scripts/dev/status.sh to inspect health."
