#!/usr/bin/env bash
# Create the project virtual environment (.venv), install dependencies and build the viewer frontend.
# Usage: scripts/setup.sh [--with-e2e]   (set PYTHON_BIN to choose the interpreter, default python3)
#   The viewer build (web/) needs Node >= 20; without it only a warning is printed.
#   --with-e2e: also install the Playwright browser used by scripts/internal/viewer_test.sh --e2e.
# Safe to run repeatedly.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python3}"
WITH_E2E=0
case "${1:-}" in
  --with-e2e) WITH_E2E=1 ;;
  "") ;;
  *) echo "usage: scripts/setup.sh [--with-e2e]" >&2; exit 1 ;;
esac

if [ ! -d .venv ]; then
  echo "[setup] creating .venv with $PYTHON_BIN"
  "$PYTHON_BIN" -m venv .venv
fi

source "$ROOT/scripts/internal/_env.sh"
"$PY" -m pip install --upgrade pip --quiet
"$PY" -m pip install -r requirements.txt --quiet
"$PY" -c "import pymupdf; print('[setup] PyMuPDF', pymupdf.__version__)"

if [ -f web/package.json ]; then
  NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  if [ "$NODE_MAJOR" -ge 20 ]; then
    echo "[setup] building the viewer frontend (node $(node --version))"
    (cd web && npm ci --no-audit --no-fund && npm run build)
    if [ "$WITH_E2E" -eq 1 ]; then
      (cd web && npx playwright install chromium)
    fi
  else
    echo "[setup] WARNING: Node >= 20 not found; skipped the viewer frontend build (web/)." >&2
  fi
fi
echo "[setup] done. Next: scripts/internal/selftest.sh"
