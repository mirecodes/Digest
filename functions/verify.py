"""Citation verifier for paper digests.

Checks that:
  1. every evidence quote in .work/evidence.md exists verbatim on its stated page of .work/pages.md;
  2. every [E#, p.N] citation in "<name> - report.md" and "<name> - summary.md" points to an existing
     evidence block and page (<name> is the paper folder name);
  3. each output contains a Korean and an English section, citing the same evidence IDs;
  4. no number appears without a citation outside exempt sections (warning).

Usage (via wrapper): scripts/internal/verify.sh "<paper_dir>" [--evidence-only]
Exit code: 0 = pass (warnings allowed), 1 = errors found.
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

PAGE_RE = re.compile(r"<!-- PAGE (\d+) -->(.*?)(?=<!-- PAGE \d+ -->|\Z)", re.S)
EVID_BLOCK_RE = re.compile(r"^###\s+(E\d+)\s*$(.*?)(?=^###\s+E\d+\s*$|\Z)", re.M | re.S)
CITE_RE = re.compile(r"\[(E\d+)(?:\s*,\s*p\.\s*(\d+))?[^\]]*\]")
CALC_RE = re.compile(r"\[CALC:[^\]]*\]")
LANG_RE = re.compile(r"<!--\s*LANG:\s*(ko|en)\s*-->")
TABLE_SEP_RE = re.compile(r"\|?[\s:\-|]+\|?")
# Numbers that need a source: decimals, percentages, multipliers, percentage points.
NUMBER_RE = re.compile(r"\d+\.\d+|\d+\s*(?:%|x\b|×|pp\b|%p)")
DECIMAL_RE = re.compile(r"\d+\.\d+")
# Headings of sections that hold opinions or the source table; numbers there are not flagged.
EXEMPT_HEADING_RE = re.compile(r"comment|discussion|sources|코멘트|토론|출처", re.I)
EXEMPT_TAGS = ("[INTERP]", "[EXT]", "[CALC:")
# Paper folder layout. Obsidian does not index dot-folders, so work files stay out of the vault search.
WORK_DIR = ".work"
OUTPUT_KINDS = ("report", "summary")
LANGS = ("ko", "en")
MIN_QUOTE_LEN = 15  # characters after loose normalization


def loose(s: str) -> str:
    """Normalize text so line breaks, hyphenation, spacing and symbols do not affect matching."""
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", s)


def load_pages(path: Path) -> dict[int, str]:
    raw = path.read_text(encoding="utf-8")
    return {int(m.group(1)): loose(m.group(2)) for m in PAGE_RE.finditer(raw)}


def load_evidence(path: Path) -> dict[str, dict]:
    raw = path.read_text(encoding="utf-8")
    evidence = {}
    for m in EVID_BLOCK_RE.finditer(raw):
        body = m.group(2)
        page = re.search(r"^-\s*page:\s*(\d+)", body, re.M)
        quote = re.search(r'^-\s*quote:\s*"(.*)"\s*$', body, re.M)
        status = re.search(r"^-\s*status:\s*(\S+)", body, re.M)
        evidence[m.group(1)] = {
            "page": int(page.group(1)) if page else None,
            "quote": quote.group(1) if quote else None,
            "not_reported": bool(status and status.group(1).upper() == "NOT_REPORTED"),
        }
    return evidence


def check_evidence(evidence: dict, pages: dict, errors: list, warnings: list) -> None:
    for eid, e in evidence.items():
        if e["not_reported"]:
            continue
        if e["page"] is None or e["quote"] is None:
            errors.append(f"{eid}: missing 'page' or 'quote' field")
            continue
        q = loose(e["quote"])
        if len(q) < MIN_QUOTE_LEN:
            warnings.append(f"{eid}: quote is too short to verify reliably ({e['quote']!r})")
        if q in pages.get(e["page"], ""):
            continue
        found = [p for p, text in pages.items() if q in text]
        if found:
            errors.append(f"{eid}: not on p.{e['page']}; actually on p.{found} -> fix the page")
        else:
            errors.append(f"{eid}: quote not found in the source (fabricated or paraphrased?): {e['quote'][:80]!r}")


def check_output(path: Path, evidence: dict, errors: list, warnings: list) -> None:
    if not path.exists():
        errors.append(f"{path.name}: file not found")
        return

    text = path.read_text(encoding="utf-8")
    markers = set(LANG_RE.findall(text))
    lang = None
    exempt = False
    cited = {l: set() for l in LANGS}
    decimals = {l: set() for l in LANGS}

    for n, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        marker = LANG_RE.search(stripped)
        if marker:
            lang, exempt = marker.group(1), False
            continue
        if stripped.startswith("#"):
            exempt = bool(EXEMPT_HEADING_RE.search(stripped))
            continue
        if not stripped or TABLE_SEP_RE.fullmatch(stripped):
            continue

        cites = CITE_RE.findall(line)
        for eid, page in cites:
            if lang:
                cited[lang].add(eid)
            if eid not in evidence:
                errors.append(f"{path.name}:{n}: unknown evidence {eid}")
            elif page and evidence[eid]["page"] and int(page) != evidence[eid]["page"]:
                errors.append(f"{path.name}:{n}: page mismatch for {eid} (text p.{page}, evidence p.{evidence[eid]['page']})")
            elif evidence[eid]["not_reported"]:
                warnings.append(f"{path.name}:{n}: cites NOT_REPORTED evidence {eid}; make sure it says 'not reported'")

        if exempt:
            continue
        if lang:
            decimals[lang].update(DECIMAL_RE.findall(line))
        if NUMBER_RE.search(line) and not cites and not CALC_RE.search(line) and not any(t in line for t in EXEMPT_TAGS):
            warnings.append(f"{path.name}:{n}: number without a source -> {stripped[:90]}")

    for l in LANGS:
        if l not in markers:
            errors.append(f"{path.name}: missing '<!-- LANG: {l} -->' section")
    if markers.issuperset(LANGS):
        only_ko, only_en = cited["ko"] - cited["en"], cited["en"] - cited["ko"]
        if only_ko or only_en:
            errors.append(
                f"{path.name}: Korean and English versions cite different evidence "
                f"(ko only: {sorted(only_ko)}, en only: {sorted(only_en)})"
            )
        diff = decimals["ko"] ^ decimals["en"]
        if diff:
            warnings.append(f"{path.name}: numbers differ between Korean and English versions: {sorted(diff)}")


def output_path(paper_dir: Path, kind: str) -> Path:
    """"<name> - report.md": named after the paper so each note is unique in Obsidian search."""
    return paper_dir / f"{paper_dir.name} - {kind}.md"


def verify_paper(paper_dir: Path, evidence_only: bool = False) -> tuple[list, list, int]:
    """Return (errors, warnings, evidence_count) for one paper directory."""
    errors, warnings = [], []
    paper_dir = paper_dir.resolve()  # a trailing "." or "/" would otherwise hide the folder name
    pages_path, evidence_path = paper_dir / WORK_DIR / "pages.md", paper_dir / WORK_DIR / "evidence.md"
    for p in (pages_path, evidence_path):
        if not p.exists():
            return [f"required file not found: {p}"], [], 0

    pages = load_pages(pages_path)
    evidence = load_evidence(evidence_path)
    if not evidence:
        errors.append("no evidence blocks ('### E1' ...) found in evidence.md")
    check_evidence(evidence, pages, errors, warnings)
    if not evidence_only:
        for kind in OUTPUT_KINDS:
            check_output(output_path(paper_dir, kind), evidence, errors, warnings)
    return errors, warnings, len(evidence)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify citations of a paper digest")
    parser.add_argument("paper_dir", type=Path)
    parser.add_argument("--evidence-only", action="store_true", help="check evidence.md only")
    args = parser.parse_args()

    errors, warnings, count = verify_paper(args.paper_dir, args.evidence_only)
    print(f"[verify] {count} evidence blocks")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    print(f"[verify] {'PASS' if not errors else 'FAIL'} - errors {len(errors)}, warnings {len(warnings)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
