#!/usr/bin/env bash
# One command to start: sets the project up when needed, then opens the reader (library page) in the browser.
# Usage: ./run.sh [--port N] [--no-open]     (options go to scripts/viewer.sh)
#   first run (no .venv or no reader build): scripts/setup.sh
#   reader sources changed since the last build (e.g. after git pull): rebuilds web/dist
#   the AI agent CLI is checked, but a missing one only warns (reading works without it; processing does not)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ ! -x .venv/bin/python ] && [ ! -x .venv/Scripts/python.exe ] || [ ! -f web/dist/index.html ]; then
  scripts/setup.sh
elif [ -n "$(find web/src web/index.html -newer web/dist/index.html -print -quit)" ]; then
  echo "[run] the reader changed since its last build; rebuilding"
  (cd web && npm run build --silent)
fi

scripts/internal/agent.sh --check || echo "[run] WARNING: the AI agent is not ready, so Process will fail (see README.md, \"Choose your AI\")" >&2
exec scripts/viewer.sh "$@"
