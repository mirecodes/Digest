#!/usr/bin/env bash
# Create the project virtual environment (.venv) and install dependencies.
# Usage: scripts/setup.sh            (set PYTHON_BIN to choose the interpreter, default python3)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d .venv ]; then
  echo "[setup] creating .venv with $PYTHON_BIN"
  "$PYTHON_BIN" -m venv .venv
fi

source "$ROOT/scripts/internal/_env.sh"
"$PY" -m pip install --upgrade pip --quiet
"$PY" -m pip install -r requirements.txt --quiet
"$PY" -c "import pymupdf; print('[setup] PyMuPDF', pymupdf.__version__)"
echo "[setup] done. Next: scripts/internal/selftest.sh"
