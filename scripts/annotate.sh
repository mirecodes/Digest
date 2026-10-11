#!/usr/bin/env bash
# Prepare digested papers for the viewer with a headless coding agent running /paper-annotate (agent.backend in
# configs/cfg.yaml: claude | codex | gemini; scripts/internal/agent.sh), one session per paper:
# translation per block (target_lang in configs/cfg.yaml), highlights, figure notes, then verify_annotations and
# build_viewer.
# Usage: scripts/annotate.sh [-n NAME] [--only PARTS] [--resume]
#   -n NAME:      one paper: its folder (path, name, path relative to the output root) or its PDF (a path, or a src/
#                 relative path / file name / stem). A PDF not prepared yet is prepared first (copy, extract,
#                 register); the digest is not needed.
#   --only PARTS: comma-separated subset of translation,highlights,figures (default: every part not complete yet)
#   --resume:     continue an interrupted or failed run: keep the pages and notes that already pass verify
#   without -n:   digested papers (verify PASS) whose annotations are incomplete, at most max_papers per run.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/internal/_env.sh"
cd "$ROOT"

usage() { echo "usage: scripts/annotate.sh [-n NAME] [--only translation,highlights,figures] [--resume]" >&2; exit 1; }
NAME=""; ONLY=""; RESUME=""
while [ $# -gt 0 ]; do
  case "$1" in
    -n|--name) [ $# -ge 2 ] || usage; NAME="$2"; shift ;;
    --only) [ $# -ge 2 ] || usage; ONLY="$2"; shift ;;
    --resume) RESUME=" --resume" ;;
    *) usage ;;
  esac
  shift
done
if [ -n "$ONLY" ]; then
  for PART in ${ONLY//,/ }; do
    case "$PART" in translation|highlights|figures) ;; *) usage ;; esac
  done
fi

# file copy and registration come first, whatever is asked for
if [ -n "$NAME" ] && ! "$PY" -m functions.papers -n "$NAME" >/dev/null 2>&1; then
  "$PY" -m functions.prepare --ensure -n "$NAME"
fi
LIST="$("$PY" -m functions.papers ${NAME:+-n "$NAME"})"
if [ -z "$LIST" ]; then
  echo "[annotate] nothing to annotate"
  exit 0
fi
"$ROOT/scripts/internal/agent.sh" --check     # fail once, with install/login help, if the agent CLI is missing

FAILED=0
while IFS= read -r FOLDER; do
  echo "[annotate] === $FOLDER${ONLY:+ (only $ONLY)}"
  "$ROOT/scripts/internal/agent.sh" paper-annotate "-n \"$FOLDER\"${ONLY:+ --only $ONLY}$RESUME" \
    || { echo "[annotate] FAILED: $FOLDER" >&2; FAILED=$((FAILED + 1)); }
done <<< "$LIST"

echo "[annotate] done, $FAILED failed"
[ "$FAILED" -eq 0 ]
