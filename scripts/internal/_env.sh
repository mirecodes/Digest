# Shared helper sourced by the other scripts (not executed directly).
# Resolves the project root and the .venv Python interpreter.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif [ -x "$ROOT/.venv/Scripts/python.exe" ]; then
  PY="$ROOT/.venv/Scripts/python.exe"
else
  echo "[error] .venv not found. Run scripts/setup.sh first." >&2
  exit 1
fi

# Make the 'functions' package importable without changing the caller's working directory.
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
