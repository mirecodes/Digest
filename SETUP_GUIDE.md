# Paper Digest: Setup Guide

Turns paper PDFs into a source-verified report and one-page summary, each written in Korean, then English.
Every fact carries a citation `[E#, p.N]` that `verify.py` checks against the extracted text.

## Setup

1. Python 3.10+ (`python3 --version`).
2. `scripts/setup.sh` creates `.venv` and installs `requirements.txt`. Use `PYTHON_BIN=python3.12` to choose the interpreter.
3. `scripts/internal/selftest.sh` must print `[selftest] PASS`.
4. Edit `configs/cfg.yaml`: `out_dir` (empty = `out/`, e.g. an Obsidian vault folder), `max_papers` per run.

## Usage

Put PDFs in `src/` (subfolders allowed). Each processed PDF is moved out of `src/` into its output folder.

| Where | All of src/ (up to `max_papers`) | One paper |
|---|---|---|
| Claude Code | `/paper-digest` | `/paper-digest -n 2606.25965v2` |
| Terminal (headless `claude -p`, one session per paper) | `scripts/digest.sh` | `scripts/digest.sh -n rsl/2606.25965v2.pdf` |

`NAME` is a src/ relative path, file name or stem, or a PDF path.

Output:

```
<out_dir>/rsl/<Short Title (Year)>/
  <Short Title (Year)>.pdf
  <Short Title (Year)> - report.md
  <Short Title (Year)> - summary.md
  .work/  pages.md, captions.md, evidence.md   (hidden, not indexed by Obsidian)
```

The name comes from arXiv → Crossref → PDF metadata, falling back to the file name.
Preview names without moving anything: `scripts/internal/prepare.sh --dry-run [-n NAME]`.
Re-check a digest after edits: `scripts/internal/verify.sh "<paper folder>"`.

## Pipeline

Prepare (name, move, extract with one `<!-- PAGE N -->` marker per page) → collect evidence → verify evidence
→ write report → write summary → verify all.
Citation markers: `[E#, p.N]`, `[CALC: ...]`, `[EXT]`, `[INTERP]`. Language sections: `<!-- LANG: ko -->`, `<!-- LANG: en -->`.

## Exit codes

| Script | Code | Meaning |
|---|---|---|
| prepare.sh | 1 | nothing to process, or bad `-n NAME` |
| prepare.sh `-n` | 2 | PDF looks scanned; stays in src/, OCR needed |
| prepare.sh `-n` | 3 | output folder exists; re-run with `--force` after asking |
| verify.sh | 1 | at least one ERROR |
| digest.sh | 1 | usage error, nothing to process, or a paper session failed |

In batch runs, prepare.sh skips scanned/existing papers (they stay in src/) and reports them.
