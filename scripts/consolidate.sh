#!/usr/bin/env bash
# OIDA monorepo consolidation (R16 Phase 2-3). HISTORY-PRESERVING.
#
# WARNING — read before running:
#   * This CHECKPOINT-COMMITS any uncommitted work in each source repo first
#     (so the R12–R16 work is not lost), then imports each repo with
#     `git subtree add` (full history preserved).
#   * It NEVER resets, force-checkouts, or deletes the original repos.
#   * Secrets are excluded via each repo's existing .gitignore; the exported
#     package (scripts/migration/export) is also secret-scanned.
#
# Usage: bash scripts/consolidate.sh /path/to/oiioda-target
set -euo pipefail

TARGET="${1:-/Users/kanphong/OIODA}"
SRC="${OIDA_SRC_ROOT:-/Users/kanphong}"

mkdir -p "$TARGET"
cd "$TARGET"
if [ ! -d .git ]; then git init -q; fi

declare -a SERVICES=(
  "ACCOUNT-AGAIN|account-again|services/account-again"
  "DOCUMENT-AGAIN|document-again|services/document-again"
  "CONDUCTOR-AGAIN|conductor-again|services/conductor-again"
  "PM-AGAIN|pm-again|services/pm-again"
  "QA-AGAIN|qa-again|services/qa-again"
  "INFRA-AGAIN|infra-again|services/infra-again"
)

for entry in "${SERVICES[@]}"; do
  dir="${entry%%|*}"; rest="${entry#*|}"; branch="${rest%%|*}"; prefix="${rest#*|}"
  repo="$SRC/$dir"
  [ -d "$repo" ] || { echo "skip missing $repo"; continue; }

  # 1) checkpoint-commit uncommitted work (never destructive).
  if ( cd "$repo" && git rev-parse --is-inside-work-tree >/dev/null 2>&1 ); then
    ( cd "$repo" && \
      if [ -n "$(git status --porcelain)" ]; then
        git add -A && git commit -q -m "checkpoint: R16 consolidation $(date -u +%Y-%m-%dT%H:%MZ)" || true
      fi )
    branch="$(cd "$repo" && git rev-parse --abbrev-ref HEAD)"
  else
    echo "skip $repo (not a git repo)"; continue
  fi

  # 2) history-preserving subtree merge.
  if git ls-files --error-unmatch "$prefix" >/dev/null 2>&1; then
    echo "already imported: $prefix"
  else
    echo "importing $dir -> $prefix (history preserved)"
    git subtree add --prefix="$prefix" "$repo" "$branch"
  fi
done

# 3) OIDA Web shell is not a git repo — copy source (no history to preserve).
if [ ! -d "$TARGET/apps/oida-web/src" ]; then
  mkdir -p "$TARGET/apps/oida-web"
  rsync -a --exclude node_modules --exclude dist --exclude .vite \
    "$SRC/OIDA-WORKSPACE/" "$TARGET/apps/oida-web/"
  echo "copied OIDA-WORKSPACE -> apps/oida-web (no history)"
fi

echo "Consolidation complete at $TARGET"
echo "Verify with: git -C $TARGET log --oneline | head"
