#!/usr/bin/env bash
# Prepare digested papers for the viewer with headless Claude Code (/paper-annotate), one session per paper:
# Korean translation per block, highlights, figure notes, then verify_annotations and build_viewer.
# Usage: scripts/annotate.sh [-n NAME]
#   -n NAME: one paper folder (path, folder name, or path relative to the output root)
#   without -n: digested papers (verify PASS) whose annotations are incomplete, at most max_papers per run.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/internal/_env.sh"
cd "$ROOT"

usage() { echo "usage: scripts/annotate.sh [-n NAME]" >&2; exit 1; }
NAME=""
case "${1:-}" in
  -n|--name) [ $# -eq 2 ] || usage; NAME="$2" ;;
  "") ;;
  *) usage ;;
esac

LIST="$("$PY" -m functions.papers ${NAME:+-n "$NAME"})"
if [ -z "$LIST" ]; then
  echo "[annotate] nothing to annotate"
  exit 0
fi
OUT="$("$PY" -c 'from functions.build_viewer import viewer_root; print(viewer_root())')"

FAILED=0
while IFS= read -r FOLDER; do
  echo "[annotate] === $FOLDER"
  # stdin from /dev/null so claude does not consume the folder list; Read is needed to look at figure crops.
  claude -p "/paper-annotate -n \"$FOLDER\"" \
    --add-dir "$OUT" \
    --permission-mode acceptEdits \
    --allowedTools "Bash(scripts/internal/*)" "Read" \
    < /dev/null || { echo "[annotate] FAILED: $FOLDER" >&2; FAILED=$((FAILED + 1)); }
done <<< "$LIST"

echo "[annotate] done, $FAILED failed"
[ "$FAILED" -eq 0 ]
