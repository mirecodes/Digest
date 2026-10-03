---
name: paper-digest
description: Read a research paper PDF and produce a source-verified detailed report and one-page summary, written in Korean followed by English. Use when the user asks to summarize or digest a paper, or invokes /paper-digest.
argument-hint: [-n NAME]
---

# Paper Digest

Input: `$ARGUMENTS`
- `-n NAME`: one paper (a src/ relative path, file name or stem, or a PDF path). A bare name or path without `-n` means the same.
- empty: every PDF in `src/`, at most `max_papers` (configs/cfg.yaml) per run.

Core principle: **evidence first, writing second.** Collect evidence from the source text,
verify it with a script, then write the report from verified evidence only. Never change this order.

All commands go through `scripts/internal/*.sh`, which use the project `.venv`.
Never call the system `python` directly. If a script reports that `.venv` is missing, run `scripts/setup.sh`.

## Procedure

### 1. Prepare
1. Run `scripts/internal/prepare.sh` (with `-n "NAME"` if given). For each paper it picks the name
   `Short Title (Year)` from arXiv/Crossref/PDF metadata, creates the folder, moves the PDF out of `src/`,
   and prints `[prepare] ready: <folder>`. Paths contain spaces: always quote them.
   - `skip (folder exists ...)` / exit 3: ask the user before re-running that paper with `-n "NAME" --force`.
     In a non-interactive run (`claude -p`), do not use `--force`; just report it.
   - `skip (PDF looks scanned ...)` / exit 2: the PDF stays in `src/`; tell the user OCR is needed.
   - Exit 1: nothing to process; tell the user and stop.
2. Run steps 2-8 for each `ready` folder, one paper at a time, finishing one before starting the next.
   Below, `<paper>` means that folder and `<name>` its folder name.
3. Work files live in the hidden `<paper>/.work/` (Obsidian does not index it).
   From now on, all page numbers refer to the `<!-- PAGE N -->` markers in `.work/pages.md`,
   not the page numbers printed in the PDF.

### 2. Read
- Read all of `.work/pages.md`, in chunks, from start to end. Do not write from the abstract alone.
- Use `.work/captions.md` to locate key figures and tables.
- Table columns can get mixed up during extraction. If the row/column mapping is unclear,
  write `table parsing uncertain` in that evidence block's note.

### 3. Collect evidence → `.work/evidence.md`
Follow `.claude/skills/paper-digest/templates/evidence.md`.
- Cover every checklist category. Record missing information as a `status: NOT_REPORTED` block.
- Copy quotes **verbatim** from pages.md, in the original language. No paraphrasing, translation or summarizing.
- Keep each quote to 1-2 sentences. For numbers, choose text that also shows the baseline and metric.

### 4. Verify evidence
Run `scripts/internal/verify.sh "<paper>" --evidence-only` and fix until there are no ERRORs.
"quote not found" means the quote was invented or paraphrased: find the exact text in pages.md,
or delete the block if it does not exist.

### 5. Write the report → `<name> - report.md`
The exact file name matters: verify.sh looks for it, and it keeps notes unique in Obsidian search.
Follow `.claude/skills/paper-digest/templates/report.md`.
1. Write the **complete Korean version** first. Technical terms stay in English (e.g. attention, ablation).
2. Then write the **complete English version** below it, as a faithful translation of the Korean version:
   same sections, same evidence IDs, same numbers. Do not add or drop content.
3. End with one shared Sources table listing only the evidence actually cited.
- Explain in depth: a reader should grasp the paper without the original. Prefer paragraphs, and explain every symbol in equations.

### 6. Write the summary → `<name> - summary.md`
Follow `.claude/skills/paper-digest/templates/summary.md`. Condense the report to one page:
same languages, same markers, no new facts. Every citation must already appear in the report.

### 7. Final verification
Run `scripts/internal/verify.sh "<paper>"` (checks both the report and the summary).
- Fix every ERROR. If ERRORs remain after 3 rounds, report them to the user as they are.
- For each WARN "number without a source": add a citation, or tag it `[INTERP]` (opinion) or `[CALC: ...]` (computed).
- For WARN "numbers differ between Korean and English": make the two versions match.

### 8. Report back
Tell the user briefly, per paper: the paper folder, verify result (PASS/FAIL, warning count),
NOT_REPORTED items, and any tables whose parsing was uncertain. List skipped papers and why.
Reply in the user's language.

## Citation rules

| Content | Marker | Allowed in |
|---|---|---|
| Facts, numbers, authors' claims from the paper | `[E#, p.N]` | anywhere |
| Values computed from cited numbers | `[CALC: formula, E#, E#]` | anywhere |
| General knowledge from outside the paper | `[EXT]` | Background, Comments |
| Your own assessment or inference | `[INTERP]` | Limitations, Comments, Discussion |

- Use the same markers in both language versions.
- Numbers must match the quoted evidence **exactly**. Rounding or unit conversion counts as `[CALC: ...]`.
- Never state numbers or claims about other papers from memory; use only what this paper cites.
- Evaluative wording ("state of the art", "significant improvement") must be either the authors' quoted words or tagged `[INTERP]`.
- When unsure, leave it out. "Not reported" / "논문에 명시되지 않음" is better than a wrong statement.
