#!/usr/bin/env bash
# OIDA monorepo — status of every bounded service + OIDA Web.
# Shows service / URL / health / auth mode. Never exposes credentials.
set -uo pipefail

echo "OIDA local ecosystem status"
echo "==========================="
printf "%-18s %-24s %-12s %s\n" "SERVICE" "URL" "HEALTH" "AUTH MODE"

check() {
  name="$1"; url="$2"; auth="$3"
  code="$(curl -s -o /dev/null -m 2 -w "%{http_code}" "$url" 2>/dev/null || echo "DOWN")"
  printf "%-18s %-24s %-12s %s\n" "$name" "$url" "$code" "$auth"
}

check "account-again" "http://127.0.0.1:8011/health" "local+SSO-issuer"
check "document-again" "http://127.0.0.1:8003/api/health" "local"
check "pm-again" "http://127.0.0.1:8000/health" "local+ecosystem-JWT"
check "qa-again" "http://127.0.0.1:8002/health" "local+ecosystem-JWT"
check "infra-again" "http://127.0.0.1:18090/api/v1/health" "read-only"
check "conductor-again" "http://127.0.0.1:8010/api/health" "local"
check "oida-web" "http://localhost:5190/" "web"
check "local-llm" "http://localhost:11434/api/tags" "ollama"

echo
echo "Note: HTTP 404 on a /health path means the service is up but has no health route."
