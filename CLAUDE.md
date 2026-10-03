# Paper Digest

Turns paper PDFs into a source-verified report and summary (Korean, then English).
For any paper request, follow the `/paper-digest` skill exactly.

## Layout
```
configs/cfg.yaml   out_dir (empty = out/), title_words, max_papers (per run without -n)
functions/         prepare, paper_name, extract_pdf, verify, selftest
scripts/           user entry points: setup.sh, digest.sh [-n NAME]
scripts/internal/  prepare, verify, selftest (.sh; _env.sh is a sourced helper)
src/               input queue; a PDF is moved out once prepared (subfolders are mirrored)
<out_dir>/<subfolders>/<Short Title (Year)>/
  <name>.pdf, "<name> - report.md", "<name> - summary.md"
  .work/           pages.md (citation basis), captions.md, evidence.md; hidden from Obsidian
```

## Rules
- Run Python only through `scripts/` (they use `.venv`). New dependencies go in `requirements.txt`, then `scripts/setup.sh`.
- Everything in `functions/`, `scripts/`, `.claude/`, and this file is written in English.
- Paper facts come only from `.work/evidence.md`; quotes stay in the paper's language. Never fill in numbers from memory.
- Tag your own opinions `[INTERP]`.
- A digest is not done while `scripts/internal/verify.sh "<paper folder>"` shows ERRORs.
- After changing `functions/`, keep `scripts/internal/selftest.sh` passing.
- Do not modify `functions/`, `scripts/`, or `.claude/skills/` unless the user asks.
