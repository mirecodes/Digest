# Paper Digest

Turn research-paper PDFs into:

- a **source-verified report and one-page summary** (Korean, then English), where every fact cites `[E#, p.N]` and a
  script checks each citation against the extracted text;
- a **side-by-side reader** (local web app): the PDF on the left, a full translation on the right with page-synced
  scrolling, highlights of key sentences, and figure notes.

The reading and writing is done by an AI coding agent of your choice: **Claude Code, Codex CLI (ChatGPT) or Gemini
CLI**. You bring your own account or API key. The project never stores or sends keys itself.

## Requirements

- macOS or Linux, Python 3.10+
- Node.js 20+ (for the reader web app)
- One of the agent CLIs below, logged in

## Quick start

```bash
git clone <this repo> paper-digest && cd paper-digest
scripts/setup.sh                    # .venv, Python packages, reader build
scripts/internal/selftest.sh        # must print [selftest] PASS
# pick and log in to an AI (next section), then:
scripts/internal/agent.sh --check   # shows the backend, its version and how to log in
cp ~/Downloads/some-paper.pdf src/
scripts/digest.sh                   # report + summary for every new PDF in src/
scripts/viewer.sh                   # opens http://127.0.0.1:8765
```

## Choose your AI

Set the backend in `configs/cfg.yaml`:

```yaml
agent:
  backend: claude    # claude | codex | gemini
  model: ""          # empty = the CLI's default; otherwise any model name that CLI accepts
```

To try another backend for a single run without editing the file, use `PAPER_AGENT=gemini scripts/digest.sh`.

| | Claude | ChatGPT / OpenAI | Gemini |
|---|---|---|---|
| CLI | [Claude Code](https://claude.com/claude-code) | [Codex CLI](https://github.com/openai/codex) | [Gemini CLI](https://github.com/google-gemini/gemini-cli) |
| Install | `npm install -g @anthropic-ai/claude-code` (or `curl -fsSL https://claude.ai/install.sh \| bash`) | `npm install -g @openai/codex` | `npm install -g @google/gemini-cli` |
| Log in with a subscription | run `claude` once and log in (Claude Pro/Max) | `codex login` (ChatGPT Plus/Pro) | run `gemini` once, "Login with Google" |
| …or with an API key | `export ANTHROPIC_API_KEY=...` | `printenv OPENAI_API_KEY \| codex login --with-api-key` | `export GEMINI_API_KEY=...` |
| `backend:` | `claude` | `codex` | `gemini` |
| Model examples | `sonnet`, `opus` | see `codex --help` / OpenAI docs | see Gemini CLI docs |

Keys belong in your shell profile (e.g. `~/.zshrc`) or the CLI's own login store, **never in `cfg.yaml`**, which is
committed. API-key usage is billed per token by your provider, and a full paper (report, translation and figure notes)
is a long agent session. Check your provider's usage page after the first paper. One 9-page paper took about 5
minutes to annotate with Claude Code.

### What the agent is allowed to do

`scripts/internal/agent.sh` starts the CLI headless (no questions asked), with permissions limited to what the job
needs:

| Backend | Command | Permissions |
|---|---|---|
| claude | `claude -p /<skill> …` | file edits auto-accepted; shell **only** `scripts/internal/*`; output folder added |
| codex | `codex exec …` | `workspace-write` sandbox (writes only inside the project and the output folder), network on for arXiv/Crossref lookups, never asks for approval |
| gemini | `gemini -p …` | edits auto-approved; shell **only** `scripts/internal/` (`configs/gemini-policy.toml`); output folder included |

To see the exact command without running anything, use `scripts/internal/agent.sh --dry-run paper-digest '-n "x.pdf"'`.

### How the three backends share one workflow

The procedure lives in plain-markdown skills: `.claude/skills/paper-digest/SKILL.md` (report and summary) and
`.claude/skills/paper-annotate/SKILL.md` (translation, highlights, figure notes). Project rules are in `CLAUDE.md`.
Claude Code runs a skill as a slash command. Codex and Gemini are told to read the same skill file and follow it.
Correctness never depends on the model: `verify.sh` and `verify_annotations.sh` check every quote, citation, page
number and translated block, and a step counts as done only when they report no ERROR. The skills were developed
with Claude, so another model may need more fix-up rounds, but it cannot slip in unverified citations.

## Using it

### Terminal

| Task | Command |
|---|---|
| Report and summary for new PDFs in `src/` (up to `max_papers`) | `scripts/digest.sh` |
| …for one paper | `scripts/digest.sh -n "my-paper.pdf"` |
| Reader annotations (translation, highlights, figure notes); no summary needed | `scripts/annotate.sh -n "<paper folder name or src/ PDF>"` |
| …only some parts | `scripts/annotate.sh -n "<name>" --only translation,highlights,figures` |
| Start the reader | `scripts/viewer.sh` |
| List all papers and their state | `scripts/internal/registry.sh` |

With Claude Code you can also type `/paper-digest` or `/paper-annotate -n NAME` inside a session.

### Reader

`scripts/viewer.sh` lists every paper: processed ones and new PDFs from `src/` (marked **New**). Each row has
**Process ▾**:

- **Run all**: summary (if missing), then every missing translation, highlight and figure-note step;
- **Summary & report**, **Translation**, **Highlights**, **Figure notes**: one step each, in any order. None needs
  another: every job first prepares the paper (copies the PDF, extracts the text, registers it), which is instant
  when already done.

Finished steps show a check mark. The job log streams under the row. **Open** shows the PDF and its translation side
by side:

- **Highlights**: key sentences are tinted on the PDF by category (problem, contribution, insight, method, result,
  limitation). Hover one for its note. Toggle them with the **Highlights** button or `H`, and filter by category in
  the sidebar's Highlights tab.
- **Figure notes**: hover a figure (or its ⓘ badge) for a floating explanation. Click to keep it open, `Esc` to
  close. The sidebar's Figures tab lists them all.
- Keys: `H` highlights, `T` translation pane, `S` sync, `[` sidebar, `J`/`K` next/previous page, `/` search.

## Configuration (`configs/cfg.yaml`)

| Key | Meaning | Default |
|---|---|---|
| `out_dir` | where paper folders go (absolute, `~`, or relative to the project), e.g. an Obsidian vault folder | `out/` |
| `target_lang` | language of reader translations and figure notes (`ko`, `ja`, `de`, …); each language keeps its own files | `ko` |
| `agent.backend` / `agent.model` | AI coding agent and model, see above | `claude` / CLI default |
| `title_words` | words kept from a long title in the folder name | 5 |
| `max_papers` | papers per run without `-n` (0 = no limit) | 5 |
| `viewer.host` / `viewer.port` | reader address | `127.0.0.1` / `8765` |
| `viewer.auto_annotate` | run `annotate.sh` automatically after `digest.sh` | `false` |

The report and summary are always Korean, then English. `target_lang` only affects the reader annotations.

## Files

```text
src/                                   your PDFs (subfolders allowed); never modified
<out_dir>/.paper-registry.yaml         every paper by PDF content hash: src/ path, folder, state (rebuilt from disk)
<out_dir>/<subfolders>/<Short Title (Year)>/
  <Short Title (Year)>.pdf             copy of the PDF
  <Short Title (Year)> - report.md
  <Short Title (Year)> - summary.md
  .work/                               hidden working files: pages.md (citation basis), evidence.md, layout/,
                                       translate/pNNN.<lang>.md, highlights.md, figure_notes.md, viewer.json
```

The folder name comes from arXiv, then Crossref, then the PDF metadata. A paper is recognised by its content, so a
renamed or duplicate PDF is not processed twice. Deleting a paper folder makes the paper "new" again.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `[agent] ERROR: the … CLI is not installed` | install and log in as shown in the message, then `scripts/internal/agent.sh --check` |
| Job fails right after starting with an auth error | log in again with the CLI (`claude`, `codex login`, `gemini`) or check the API key variable |
| "The viewer server is out of date" / *Method Not Allowed* | an old `scripts/viewer.sh` is still running; stop it (Ctrl+C) and start it again |
| `address already in use` on port 8765 | update and run `scripts/viewer.sh` again: it stops a leftover viewer on that port, or moves to the next free port if another program uses it (printed at start). Or set `viewer.port` in `cfg.yaml` |
| `skip (PDF looks scanned …)` | the PDF has no text layer; run OCR first (e.g. `ocrmypdf in.pdf out.pdf`) |
| `skip (already digested …)` | nothing to do; delete the paper folder to redo it |
| "Not downloaded from iCloud" in the reader | open the folder in Finder and download the PDF |

## Development

- `scripts/internal/selftest.sh`: Python pipeline, registry, server, annotation checks (no AI calls)
- `scripts/internal/viewer_test.sh [--e2e]`: reader unit tests and Playwright end-to-end tests (`scripts/setup.sh --with-e2e` once)
- Design notes: `implementation.md`, `docs/viewer-plan.md`, `docs/decisions.md` (Korean)
