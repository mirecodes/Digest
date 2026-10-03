#!/usr/bin/env bash
# Verify citations of one paper digest.
# Usage: scripts/internal/verify.sh "<paper folder>" [--evidence-only]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"
exec "$PY" -m functions.verify "$@"
