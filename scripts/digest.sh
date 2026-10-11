#!/usr/bin/env bash
# Digest papers from src/ with a headless coding agent (agent.backend in configs/cfg.yaml: claude | codex | gemini),
# one session per paper (scripts/internal/agent.sh).
# Usage: scripts/digest.sh [-n NAME] [--resume]
#   -n NAME:  one paper (src/ relative path, file name or stem, or a PDF path)
#   --resume: continue an interrupted or failed run, keeping evidence / report work that already passes verify
#   without -n: every src/ PDF without an output folder yet, at most max_papers (configs/cfg.yaml) per run.
# src/ is left as it is; the registry (<out_dir>/.paper-registry.yaml) records which PDFs are done.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/internal/_env.sh"
cd "$ROOT"

usage() { echo "usage: scripts/digest.sh [-n NAME] [--resume]" >&2; exit 1; }
NAME=""; RESUME=""
while [ $# -gt 0 ]; do
  case "$1" in
    -n|--name) [ $# -ge 2 ] || usage; NAME="$2"; shift ;;
    --resume) RESUME=" --resume" ;;
    *) usage ;;
  esac
  shift
done

RC=0
LIST="$("$PY" -m functions.prepare --list ${NAME:+-n "$NAME"})" || RC=$?
[ "$RC" -eq 4 ] && exit 0     # already digested (prepare printed why)
[ "$RC" -eq 0 ] || exit "$RC"
"$ROOT/scripts/internal/agent.sh" --check     # fail once, with install/login help, if the agent CLI is missing

FAILED=0
while IFS= read -r PAPER; do
  echo "[digest] === $PAPER"
  "$ROOT/scripts/internal/agent.sh" paper-digest "-n \"$PAPER\"$RESUME" \
    || { echo "[digest] FAILED: $PAPER" >&2; FAILED=$((FAILED + 1)); }
done <<< "$LIST"

echo "[digest] done, $FAILED failed"

# viewer.auto_annotate: continue with /paper-annotate for digested papers that passed verify.
AUTO="$("$PY" -c 'from functions.papers import viewer_cfg; print(int(bool(viewer_cfg()["auto_annotate"])))')"
if [ "$AUTO" = "1" ]; then
  "$ROOT/scripts/annotate.sh" || FAILED=$((FAILED + 1))
fi
[ "$FAILED" -eq 0 ]
