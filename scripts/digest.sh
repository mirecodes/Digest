#!/usr/bin/env bash
# Digest papers from src/ with headless Claude Code, one session per paper.
# Usage: scripts/digest.sh [-n NAME]
#   -n NAME: one paper (src/ relative path, file name or stem, or a PDF path)
#   without -n: every src/ PDF without an output folder yet, at most max_papers (configs/cfg.yaml) per run.
# src/ is left as it is; the registry (<out_dir>/.paper-registry.yaml) records which PDFs are done.
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

RC=0
LIST="$("$PY" -m functions.prepare --list ${NAME:+-n "$NAME"})" || RC=$?
[ "$RC" -eq 4 ] && exit 0     # already digested (prepare printed why)
[ "$RC" -eq 0 ] || exit "$RC"
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

# viewer.auto_annotate: continue with /paper-annotate for digested papers that passed verify.
AUTO="$("$PY" -c 'from functions.papers import viewer_cfg; print(int(bool(viewer_cfg()["auto_annotate"])))')"
if [ "$AUTO" = "1" ]; then
  "$ROOT/scripts/annotate.sh" || FAILED=$((FAILED + 1))
fi
[ "$FAILED" -eq 0 ]
