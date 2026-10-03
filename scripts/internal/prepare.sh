#!/usr/bin/env bash
# Prepare papers from src/: name them, move each PDF into its output folder and extract text.
# Usage: scripts/internal/prepare.sh [-n NAME] [--list] [--force] [--dry-run] [--offline]
#   without -n: every PDF in src/, at most max_papers (configs/cfg.yaml) per run.
# Exit codes: 0 ok, 1 nothing selected / input error; with -n only: 2 scanned PDF, 3 folder exists.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"
exec "$PY" -m functions.prepare "$@"
