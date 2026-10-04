---
name: paper-annotate
description: Prepare a digested paper for the interactive viewer — full Korean translation per layout block, auto-highlights, and figure/table explanations — then verify and build viewer.json. Use with `/paper-annotate -n NAME`.
argument-hint: -n NAME
---

# Paper Annotate

Input: `$ARGUMENTS`
- `-n NAME`: one paper folder — its path, its folder name, or its path relative to the output root.
  A bare name without `-n` means the same.

All commands go through `scripts/internal/*.sh` (project `.venv`). Paths contain spaces: always quote them.
Below, `<paper>` is the paper folder, `<work>` is `<paper>/.work`, `<name>` is the folder name.

Core rule: **evidence first.** Translations must be faithful, highlights must be verbatim quotes, and every
number in a figure note carries a marker. The scripts check this; a step is not done while they report ERRORs.
Write only these files: `<work>/translate/glossary.md`, `<work>/translate/pNNN.ko.md`, `<work>/highlights.md`,
`<work>/figure_notes.md`. Never edit the report, summary, evidence.md, pages.md, the PDF, or anything in `layout/`.

## Preconditions
- `<work>/pages.md` exists (the paper was prepared by /paper-digest). `<work>/evidence.md` and the report are
  strongly preferred. Without evidence.md, highlights come only from H blocks and figure notes cannot use `[E#]`.

## Steps

### 1. Resolve and lay out
Run `scripts/internal/layout.sh "NAME"` with the `-n` value. It accepts a folder path, a folder name, or a path
relative to the output root, and prints `[layout] folder: <paper>` — use that path from now on — followed by
`[layout] pages=… blocks=… figures=… low_conf=…`. If it reports that the name matches 0 or several folders,
stop and report.

### 2. Read context
`<name> - summary.md`, the Glossary section of `<name> - report.md`, `<work>/evidence.md`,
`<work>/layout/figures.json`, and `<work>/pages.md` (all of it, in chunks).

### 3. Glossary → `<work>/translate/glossary.md`
One line per term: `English → 한국어` (keep the English term when it is conventionally untranslated, e.g.
`attention → attention`). Start from the report Glossary. Use it consistently on every page.

### 4. Translate page by page → `<work>/translate/pNNN.ko.md`
For every `pNNN.src.md`, write `pNNN.ko.md` with exactly the same `<!-- BLOCK id -->` markers, same order, one
translation under each marker (template: `templates/translation.md`). Rules:
- Faithful, sentence by sentence. Never summarize, merge, or drop sentences.
- Keep math, symbols, variable names, citation numbers like `[12]`, URLs, and all numbers exactly.
  "Figure 3 / Table 2 / Eq. (4)" → "그림 3 / 표 2 / 식 (4)" (keep the number).
- First occurrence of a technical term: `한국어(English)`. Afterwards Korean only, per the glossary.
- Headings keep their numbering: `3.1 문제 정식화 (Problem Formulation)`.
- A block may end mid-sentence at a column or page break: end the translation at the matching point so the
  next block continues naturally. Read the neighbouring blocks before translating.
- Captions are translated; author names and affiliations stay as written (add Korean only where natural).

### 5. Check translations
`scripts/internal/verify_annotations.sh "<paper>" --translation`. Fix every ERROR (missing or unknown block
ids). Review each WARN: dropped numbers or citation numbers, untranslated paragraphs, and length ratios outside
0.25–3.0 usually mean a sentence was dropped or summarized. The summary line must read `translation N/N`.

### 6. Highlights → `<work>/highlights.md`
Template: `templates/highlights.md`. Evidence quotes of categories problem / gap / contribution / insight /
method / result / ablation / limitation are highlighted automatically — do **not** repeat them. Add H blocks
only for key sentences the evidence does not cover. Density for the total (evidence-derived + H):
- 15–40 and at most 1.5 × pages (short papers: at most 1.5 × pages); at most 4 on one page;
- each quote one sentence (two at most), 40–300 characters, copied **verbatim** from pages.md (original language);
- coverage: ≥1 problem, ≥1 contribution, ≥2 method, ≥2 result, ≥1 limitation if the paper states any.

### 7. Figure notes → `<work>/figure_notes.md`
Template: `templates/figure_notes.md`. One F block for **every** figure and table in `layout/figures.json`.
For each: open the PNG `<work>/layout/figures/<fid>.png` with the Read tool, read its caption and the blocks
listed in `refs`, then write Korean first, English second:
- `요약:` / `Summary:` — one line, Korean ≤ 120 characters (the popover headline);
- `읽는 법:` / `How to read:` — axes, legend, symbols;
- 2–4 observations as bullets;
- `본문 연결:` / `Link to text:` — which contribution (C#) or claim it supports.
Markers: numbers from the paper text → `[E#, p.N]`; values read off the image → `[FIG: <fid>]`; computed →
`[CALC: …]`; your judgement → `[INTERP]`; outside knowledge → `[EXT]`. A number without a marker is a warning.
If the crop is wrong or unreadable (e.g. the box misses the legend), write `- status: SKIP` with `- reason: …`;
low-confidence boxes are listed in figures.json (`confidence` < 0.6).

### 8. Verify everything
`scripts/internal/verify_annotations.sh "<paper>"`. Fix ERRORs, at most 3 rounds; if ERRORs remain, report them.
Handle WARNs where they point to a real problem (dropped numbers, duplicates of evidence, density).

### 9. Build the viewer bundle
`scripts/internal/build_viewer.sh "<paper>"`.

### 10. Report back
Briefly: the folder, translation done/total, highlight count by category, figure notes OK/SKIP, verify PASS/FAIL
with warning count, and low-confidence figure boxes. Reply in the user's language.

## Headless rules
Same as /paper-digest: under `claude -p`, never ask questions and never pass `--force`; report instead.
