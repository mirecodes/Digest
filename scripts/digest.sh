#!/usr/bin/env bash
# Digest papers from src/ with headless Claude Code, one session per paper.
# Usage: scripts/digest.sh [-n NAME]
#   -n NAME: one paper (src/ relative path, file name or stem, or a PDF path)
#   without -n: every PDF in src/, at most max_papers (configs/cfg.yaml) per run.
# Each processed PDF is moved from src/ into its output folder.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/internal/_env.sh"
cd "$ROOT"

usage() { echo "usage: scripts/digest.sh [-n NAME]" >&2; exit 1; }
NAME=""
case "${1:-}" in
  -n|--name) [ $# -eq 2 ] || usage; NAME="$2" ;;
  "") ;;
  *) usage ;;
esac

LIST="$("$PY" -m functions.prepare --list ${NAME:+-n "$NAME"})"
OUT="$("$PY" -c 'from functions.prepare import load_config, out_root; print(out_root(load_config()))')"
mkdir -p "$OUT"

FAILED=0
while IFS= read -r PAPER; do
  echo "[digest] === $PAPER"
  # stdin from /dev/null so claude does not consume the paper list.
  claude -p "/paper-digest -n \"$PAPER\"" \
    --add-dir "$OUT" \
    --permission-mode acceptEdits \
    --allowedTools "Bash(scripts/internal/*)" \
    < /dev/null || { echo "[digest] FAILED: $PAPER" >&2; FAILED=$((FAILED + 1)); }
done <<< "$LIST"

echo "[digest] done, $FAILED failed"
[ "$FAILED" -eq 0 ]
