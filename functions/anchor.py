"""Anchor quotes to PDF coordinates: quote -> highlight rects on its page.

pages.md comes from page.get_text("text") without sorting, so the word list of get_text("words") has the same
internal order and a quote verified against pages.md is found here in the same way (loose() matching).
Rects are in displayed page space (docs/viewer-plan.md §4.1), one per text line.

Usage (via wrapper): scripts/internal/anchor_check.sh "<paper folder>"   (debugging: anchoring success rate)
"""
import argparse
import sys
from pathlib import Path

import pymupdf

from functions.papers import find_pdf
from functions.textmatch import loose
from functions.verify import WORK_DIR, load_evidence


def anchor_quote(page, quote: str) -> dict | None:
    """{page, rects, ambiguous} for the first occurrence of the quote on the page, or None."""
    words = page.get_text("words", sort=False)
    text, owner = [], []
    for i, w in enumerate(words):
        n = loose(w[4])
        text.append(n)
        owner += [i] * len(n)
    s, q = "".join(text), loose(quote)
    pos = s.find(q) if q else -1
    if pos < 0:
        return None
    lines = {}
    for w in words[owner[pos]:owner[pos + len(q) - 1] + 1]:
        key, r = (w[5], w[6]), tuple(w[:4])
        lines[key] = r if key not in lines else (min(lines[key][0], r[0]), min(lines[key][1], r[1]),
                                                  max(lines[key][2], r[2]), max(lines[key][3], r[3]))
    rects = []
    for r in lines.values():
        if page.rotation:
            r = tuple(pymupdf.Rect(r) * page.rotation_matrix)
        rects.append([round(v, 2) for v in r])
    return {"page": page.number + 1, "rects": rects, "ambiguous": s.find(q, pos + 1) >= 0}


def anchor_check(paper_dir: Path) -> tuple[int, int, int, list[str]]:
    """Anchor every reported evidence quote on its page: (anchored, total, ambiguous, failure messages)."""
    paper_dir = paper_dir.resolve()
    doc = pymupdf.open(find_pdf(paper_dir))
    evidence = load_evidence(paper_dir / WORK_DIR / "evidence.md")
    ok = total = ambiguous = 0
    failures = []
    for eid, e in evidence.items():
        if e["not_reported"] or not e["page"] or not e["quote"] or not 1 <= e["page"] <= len(doc):
            continue
        total += 1
        a = anchor_quote(doc[e["page"] - 1], e["quote"])
        if a:
            ok += 1
            ambiguous += a["ambiguous"]
        else:
            failures.append(f"{eid} p.{e['page']}: {e['quote'][:80]!r}")
    return ok, total, ambiguous, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Anchor evidence quotes to PDF coordinates and report the success rate")
    parser.add_argument("paper_dir", type=Path)
    args = parser.parse_args()
    if not (args.paper_dir / WORK_DIR / "evidence.md").is_file() or not find_pdf(args.paper_dir.resolve()):
        print(f"[anchor] ERROR: need the PDF and .work/evidence.md in {args.paper_dir}", file=sys.stderr)
        return 1
    ok, total, ambiguous, failures = anchor_check(args.paper_dir)
    for f in failures:
        print(f"  FAIL  {f}")
    rate = 100.0 * ok / total if total else 100.0
    print(f"[anchor] evidence {ok}/{total} anchored ({rate:.1f}%), ambiguous {ambiguous}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
