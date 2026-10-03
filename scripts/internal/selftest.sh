#!/usr/bin/env bash
# Run the pipeline self-test on a synthetic paper. Run after setup or after changing functions/.
# Usage: scripts/internal/selftest.sh
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"
exec "$PY" -m functions.selftest
