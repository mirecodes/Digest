#!/usr/bin/env bash
# Prepare digested papers for the viewer with headless Claude Code (/paper-annotate), one session per paper:
# translation per block (target_lang in configs/cfg.yaml), highlights, figure notes, then verify_annotations and
# build_viewer.
# Usage: scripts/annotate.sh [-n NAME] [--only PARTS]
#   -n NAME:      one paper folder (path, folder name, path relative to the output root, or its PDF)
#   --only PARTS: comma-separated subset of translation,highlights,figures (default: every part not complete yet)
#   without -n:   digested papers (verify PASS) whose annotations are incomplete, at most max_papers per run.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/internal/_env.sh"
cd "$ROOT"

usage() { echo "usage: scripts/annotate.sh [-n NAME] [--only translation,highlights,figures]" >&2; exit 1; }
NAME=""; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    -n|--name) [ $# -ge 2 ] || usage; NAME="$2"; shift ;;
    --only) [ $# -ge 2 ] || usage; ONLY="$2"; shift ;;
    *) usage ;;
  esac
  shift
done
if [ -n "$ONLY" ]; then
  for PART in ${ONLY//,/ }; do
    case "$PART" in translation|highlights|figures) ;; *) usage ;; esac
  done
fi

LIST="$("$PY" -m functions.papers ${NAME:+-n "$NAME"})"
if [ -z "$LIST" ]; then
  echo "[annotate] nothing to annotate"
  exit 0
fi
OUT="$("$PY" -c 'from functions.build_viewer import viewer_root; print(viewer_root())')"

FAILED=0
while IFS= read -r FOLDER; do
  echo "[annotate] === $FOLDER${ONLY:+ (only $ONLY)}"
  # stdin from /dev/null so claude does not consume the folder list; Read is needed to look at figure crops.
  claude -p "/paper-annotate -n \"$FOLDER\"${ONLY:+ --only $ONLY}" \
    --add-dir "$OUT" \
    --permission-mode acceptEdits \
    --allowedTools "Bash(scripts/internal/*)" "Read" \
    < /dev/null || { echo "[annotate] FAILED: $FOLDER" >&2; FAILED=$((FAILED + 1)); }
done <<< "$LIST"

echo "[annotate] done, $FAILED failed"
[ "$FAILED" -eq 0 ]
