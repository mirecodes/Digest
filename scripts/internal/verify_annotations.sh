#!/usr/bin/env bash
# Verify the viewer annotations (translations, highlights, figure notes) of one paper.
# Usage: scripts/internal/verify_annotations.sh "<paper folder>" [--translation] [--highlights] [--figures]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"
exec "$PY" -m functions.verify_annotations "$@"
