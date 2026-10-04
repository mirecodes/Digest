"""Parsers for the viewer's pre-generated annotations (formats: docs/viewer-plan.md §4.4-4.6).

  .work/evidence.md         ### E{n} blocks (written by /paper-digest)
  .work/highlights.md       ### H{n} blocks (written by /paper-annotate), notes in `note_<lang>` / `note_en`
  .work/figure_notes.md     ### F{n} blocks with "#### <lang>" / "#### en" sections
  .work/translate/pNNN.src.md / pNNN.<lang>.md   <!-- BLOCK <id> ... --> markers

<lang> is target_lang from configs/cfg.yaml (papers.target_lang). Parsed results use the language-neutral keys
`tr` (target language) and `en`. Parsing only; checks live in verify_annotations.py.
"""
import re
from pathlib import Path

# Big-picture highlight categories, in reading order (the viewer lists them this way). Highlights are only the
# curated H blocks; evidence quotes stay internal (report citations, figure-note chips) and are not highlighted.
HIGHLIGHT_CATEGORIES = ("problem", "assumption", "prior_work", "contribution", "method", "result", "insight", "limitation")
CORE_CATEGORIES = ("problem", "prior_work", "contribution", "method", "result")   # every paper should cover these
BLOCK_MARK_RE = re.compile(r"^<!--\s*BLOCK\s+(\S+)([^>]*?)-->\s*$", re.M)
KIND_RE = re.compile(r"kind=(\S+)")
SUMMARY_RE = re.compile(r"^\s*(?:요약|Summary)\s*:\s*(.*)$", re.I)


def read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _blocks(md: str, letter: str) -> list[tuple[str, str]]:
    pattern = re.compile(rf"^###\s+({letter}\d+)\s*$(.*?)(?=^###\s+{letter}\d+\s*$|\Z)", re.M | re.S)
    return [(m.group(1), m.group(2)) for m in pattern.finditer(md)]


def _field(body: str, name: str) -> str | None:
    m = re.search(rf"^-\s*{name}:\s*(.*?)\s*$", body, re.M)
    return m.group(1) if m else None


def _quote(body: str) -> str | None:
    m = re.search(r'^-\s*quote:\s*"(.*)"\s*$', body, re.M)
    return m.group(1) if m else None


def _int(value: str | None) -> int | None:
    return int(value) if value and value.strip().isdigit() else None


def parse_evidence(md: str) -> dict[str, dict]:
    """{E#: page, loc, quote, category, note, not_reported} — the same block grammar verify.py checks."""
    out = {}
    for eid, body in _blocks(md, "E"):
        status = _field(body, "status")
        out[eid] = {"page": _int(_field(body, "page")), "loc": _field(body, "loc"), "quote": _quote(body),
                    "category": (_field(body, "category") or "").lower(), "note": _field(body, "note"),
                    "not_reported": bool(status and status.upper() == "NOT_REPORTED")}
    return out


def parse_highlights(md: str, lang: str) -> list[dict]:
    return [{"id": hid, "category": (_field(body, "category") or "").lower(), "page": _int(_field(body, "page")),
             "quote": _quote(body), "note_tr": _field(body, f"note_{lang}"), "note_en": _field(body, "note_en")}
            for hid, body in _blocks(md, "H")]


def _note_section(text: str) -> dict:
    """'요약: ...' / 'Summary: ...' first line -> summary; the rest -> body_md."""
    lines = text.strip("\n").splitlines()
    summary, rest = "", lines
    for i, line in enumerate(lines):
        m = SUMMARY_RE.match(line)
        if m:
            summary, rest = m.group(1).strip(), lines[:i] + lines[i + 1:]
            break
    return {"summary": summary, "body_md": "\n".join(rest).strip()}


def parse_figure_notes(md: str, lang: str) -> list[dict]:
    notes = []
    for fid, body in _blocks(md, "F"):
        head, *sections = re.split(r"^####\s+([a-z]{2,3}(?:-\w+)?)\s*$", body, flags=re.M)
        by_lang = {code: _note_section(text) for code, text in zip(sections[::2], sections[1::2])}
        notes.append({"id": fid, "figure": _field(head, "figure"), "status": (_field(head, "status") or "").upper(),
                      "reason": _field(head, "reason"), "tr": by_lang.get(lang), "en": by_lang.get("en")})
    return notes


def parse_translation(md: str) -> dict[str, str]:
    """{block id: text between this marker and the next}; attributes after the id are ignored."""
    marks = list(BLOCK_MARK_RE.finditer(md))
    return {m.group(1): md[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(md)].strip()
            for i, m in enumerate(marks)}


def parse_src(md: str) -> list[tuple[str, str, str]]:
    """[(block id, kind, text)] in file order."""
    marks = list(BLOCK_MARK_RE.finditer(md))
    out = []
    for i, m in enumerate(marks):
        kind = KIND_RE.search(m.group(2))
        end = marks[i + 1].start() if i + 1 < len(marks) else len(md)
        out.append((m.group(1), kind.group(1) if kind else "", md[m.end():end].strip()))
    return out
