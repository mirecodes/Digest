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
web/               viewer frontend (React + Vite + pdf.js); docs/ viewer plan and decision log
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

## Viewer
- Plan: docs/viewer-plan.md. Work phase by phase; each phase must pass its acceptance, selftest.sh, and viewer_test.sh.
- Never generate paper content (translations, highlights, figure notes) in code; tests use fixtures and PAPER_VIEWER_LLM=fake. No real LLM calls in tests.
- Pre-generated annotations are written only via /paper-annotate (or translate_page), then verify_annotations.sh, then build_viewer.sh.
- Coordinates: PDF points, top-left origin, 1-based pages (docs/viewer-plan.md §4.1).
- Record design decisions in docs/decisions.md.
