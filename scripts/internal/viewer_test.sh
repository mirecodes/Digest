#!/usr/bin/env bash
# Viewer frontend tests: vitest unit tests; with --e2e also Playwright end-to-end tests against a temporary
# output root with synthetic papers (server started by Playwright with PAPER_VIEWER_LLM=fake).
# Usage: scripts/internal/viewer_test.sh [--e2e]
#   Needs web/node_modules (scripts/setup.sh); --e2e also needs the Playwright browser (scripts/setup.sh --with-e2e).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"
cd "$ROOT/web"

E2E=0
case "${1:-}" in
  --e2e) E2E=1 ;;
  "") ;;
  *) echo "usage: scripts/internal/viewer_test.sh [--e2e]" >&2; exit 1 ;;
esac

npm run test --silent
if [ "$E2E" -eq 1 ]; then
  npm run build --silent
  OUT_TMP="$(mktemp -d)"
  trap 'rm -rf "$OUT_TMP"' EXIT
  "$PY" -m functions.fixtures "$OUT_TMP"
  PAPER_VIEWER_OUT="$OUT_TMP" PY="$PY" ROOT="$ROOT" npx playwright test
fi
echo "[viewer-test] PASS"
