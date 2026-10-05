#!/usr/bin/env bash
# Run one project skill headless with the configured coding agent (configs/cfg.yaml `agent:`, or $PAPER_AGENT).
# Usage: scripts/internal/agent.sh [--dry-run] SKILL 'SKILL ARGUMENTS'   e.g. agent.sh paper-digest '-n "rsl/x.pdf"'
#        scripts/internal/agent.sh --check     backend, model, effort, CLI version and how to log in
#   one-off model / effort: PAPER_AGENT_MODEL=claude-opus-5-5 PAPER_AGENT_EFFORT=high scripts/digest.sh
#   --dry-run: print the command instead of running it (no CLI needed)
# Backends (each CLI does its own login / API key handling; this script never sees a key):
#   claude  Claude Code `claude -p`   skill as /SKILL; edits auto-accepted, Bash only for scripts/internal/*
#   codex   Codex CLI   `codex exec`  workspace-write sandbox + out_dir, network on (arXiv/Crossref names)
#   gemini  Gemini CLI  `gemini -p`   edits auto-approved, shell only for scripts/internal/ (configs/gemini-policy.toml)
# Codex and Gemini read the skill file (.claude/skills/SKILL/SKILL.md) as their instructions and CLAUDE.md as rules.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"
cd "$ROOT"

usage() { echo "usage: scripts/internal/agent.sh [--dry-run] SKILL 'ARGUMENTS' | --check" >&2; exit 1; }
DRY=0; CHECK=0
case "${1:-}" in
  --dry-run) DRY=1; shift ;;
  --check) CHECK=1; shift ;;
esac

{ read -r BACKEND; read -r MODEL; read -r EFFORT; } < <("$PY" -c '
from functions.papers import agent_cfg
a = agent_cfg(); print(a["backend"]); print(a["model"]); print(a["effort"])')
case "$BACKEND" in
  claude) INSTALL="npm install -g @anthropic-ai/claude-code"
          LOGIN="run 'claude' once and log in (Claude subscription or Console account), or export ANTHROPIC_API_KEY" ;;
  codex)  INSTALL="npm install -g @openai/codex"
          LOGIN="run 'codex login' (ChatGPT account), or: printenv OPENAI_API_KEY | codex login --with-api-key" ;;
  gemini) INSTALL="npm install -g @google/gemini-cli"
          LOGIN="run 'gemini' once and sign in with Google, or export GEMINI_API_KEY" ;;
  *) echo "[agent] ERROR: unknown backend '$BACKEND' (agent.backend in configs/cfg.yaml: claude | codex | gemini)" >&2
     exit 2 ;;
esac
if [ -n "$EFFORT" ] && [ "$BACKEND" = gemini ]; then
  echo "[agent] note: the Gemini CLI has no effort setting; ignoring effort '$EFFORT'" >&2
  EFFORT=""
fi

if [ "$DRY" -eq 0 ] && ! command -v "$BACKEND" >/dev/null; then
  echo "[agent] ERROR: the $BACKEND CLI is not installed. Install: $INSTALL; then $LOGIN" >&2
  exit 127
fi
if [ "$CHECK" -eq 1 ]; then
  echo "[agent] backend: $BACKEND   model: ${MODEL:-(CLI default)}   effort: ${EFFORT:-(CLI default)}   cli: $(command -v "$BACKEND") $("$BACKEND" --version 2>&1 | head -1)"
  echo "[agent] login: $LOGIN"
  exit 0
fi

[ $# -eq 2 ] || usage
SKILL="$1"; ARGS="$2"
SKILL_DIR=".claude/skills/$SKILL"
[ -f "$SKILL_DIR/SKILL.md" ] || { echo "[agent] ERROR: no skill $SKILL_DIR/SKILL.md" >&2; exit 1; }
OUT="$("$PY" -c 'from functions.build_viewer import viewer_root; print(viewer_root())')"
mkdir -p "$OUT"
PROMPT="Read $SKILL_DIR/SKILL.md and follow it exactly; read CLAUDE.md first for the project rules. \
Its \$ARGUMENTS are: $ARGS
Paths like templates/... in the skill are relative to $SKILL_DIR/. Tool names in the skill (Read, Bash) mean your \
own file-reading (including images) and shell tools. Run project commands exactly as the skill writes them \
(scripts/internal/..., from the project root). You run headless: never ask questions and never pass --force; \
finish with the report the skill asks for."

run() {
  if [ "$DRY" -eq 1 ]; then printf '%q ' "$@"; echo; else "$@" < /dev/null; fi
}
case "$BACKEND" in
  claude)
    run claude -p "/$SKILL $ARGS" ${MODEL:+--model "$MODEL"} ${EFFORT:+--effort "$EFFORT"} --add-dir "$OUT" \
      --permission-mode acceptEdits --allowedTools "Bash(scripts/internal/*)" "Read" ;;
  codex)
    run codex exec --skip-git-repo-check --sandbox workspace-write -c approval_policy=never \
      -c sandbox_workspace_write.network_access=true --add-dir "$OUT" ${MODEL:+-m "$MODEL"} \
      ${EFFORT:+-c "model_reasoning_effort=$EFFORT"} "$PROMPT" ;;
  gemini)
    run gemini -p "$PROMPT" --approval-mode auto_edit --policy configs/gemini-policy.toml \
      --include-directories "$OUT" --skip-trust ${MODEL:+-m "$MODEL"} ;;
esac
