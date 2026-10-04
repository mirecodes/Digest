#!/usr/bin/env bash
# Build .work/viewer.json (the viewer's bundle) for one paper folder; runs the layout first if needed.
# Usage: scripts/internal/build_viewer.sh "<paper folder>"
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"
exec "$PY" -m functions.build_viewer "$@"
