#!/usr/bin/env bash
# Anchor every evidence quote of one paper to PDF coordinates and print the success rate (debugging).
# Usage: scripts/internal/anchor_check.sh "<paper folder>"
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"
exec "$PY" -m functions.anchor "$@"
