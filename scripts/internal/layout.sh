#!/usr/bin/env bash
# Layout analysis for the viewer: blocks, columns, reading order, figure regions, translation sources.
# Usage: scripts/internal/layout.sh "<paper folder or folder name>" [--force]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"
exec "$PY" -m functions.layout "$@"
