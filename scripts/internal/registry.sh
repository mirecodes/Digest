#!/usr/bin/env bash
# Rebuild the paper registry (<out_dir>/.paper-registry.yaml) from disk and print every paper with its state.
# Usage: scripts/internal/registry.sh
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"
exec "$PY" -m functions.registry "$@"
