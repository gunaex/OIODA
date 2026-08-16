#!/usr/bin/env bash
# OIDA monorepo — stop the local ecosystem. Kills listeners on the known ports.
set -uo pipefail

for port in 5190 8000 8002 8003 8010 8011 18090; do
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null && echo "stopped :$port"
  fi
done
echo "Done."
