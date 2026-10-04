"""Self-test: build a tiny synthetic paper and confirm extract + verify + naming + viewer layout behave as expected.

Usage (via wrapper): scripts/internal/selftest.sh
"""
import json
import sys
import tempfile
from pathlib import Path

import pymupdf

from functions.anchor import anchor_quote
from functions.extract_pdf import extract
from functions.fixtures import build_foonet
from functions.layout import build_layout
from functions.paper_name import Meta, find_arxiv_id, format_name
from functions.papers import paper_id, resolve_for_annotate, scan
from functions.prepare import SRC_DIR, select, target_dir
from functions.verify import OUTPUT_KINDS, WORK_DIR, output_path, verify_paper

GOOD_EVIDENCE = """### E1
- category: problem
- page: 1
- loc: Abstract
- quote: "Existing methods scale quadratically with sequence length, which limits long-context modeling."
- note: problem statement

### E2
- category: result
- page: 2
- loc: Table 2
- quote: "FooNet achieves 61.4 average accuracy, compared to 54.4 for the Transformer baseline."
- note: main result

### E3
- category: cost
- status: NOT_REPORTED
- note: training cost is not reported
"""

GOOD_OUTPUT = """# FooNet

<!-- LANG: ko -->
## 1. 문제 (Problem)
- 기존 방법은 시퀀스 길이에 대해 quadratic [E1, p.1]
## 2. 결과 (Results)
- FooNet 61.4 vs Transformer 54.4 [E2, p.2]
- 상대 개선 12.9% [CALC: (61.4-54.4)/54.4, E2]
## 3. 코멘트 (Comments)
- [INTERP] 약 70% 수준까지 확장 가능해 보임

<!-- LANG: en -->
## 1. Problem
- Existing methods scale quadratically with sequence length [E1, p.1]
## 2. Results
- FooNet 61.4 vs Transformer 54.4 [E2, p.2]
- Relative gain 12.9% [CALC: (61.4-54.4)/54.4, E2]
## 3. Comments
- [INTERP] Could plausibly scale to around 70%

## Sources
| ID | Location | Quote |
|---|---|---|
| E1 | p.1, Abstract | "Existing methods scale quadratically ..." |
"""

BAD_EVIDENCE = GOOD_EVIDENCE.replace("- page: 2", "- page: 1") + """
### E4
- category: result
- page: 2
- quote: "FooNet achieves 65.0 average accuracy on all tasks"
"""

BAD_OUTPUT = GOOD_OUTPUT.replace("- 상대 개선 12.9% [CALC: (61.4-54.4)/54.4, E2]", "- 7.0%p 개선\n- 없는 근거 [E9, p.3]")

# Each expected error/warning is identified by a substring of its message.
EXPECTED_BAD_ERRORS = [
    "E2: not on p.1; actually on p.[2]",
    "E4: quote not found",
    "unknown evidence E9",
    "cite different evidence",
]
EXPECTED_BAD_WARNINGS = ["number without a source"]


def build_paper(root: Path) -> tuple[Path, dict]:
    paper = root / "out" / "Demo (2024)"
    (paper / WORK_DIR).mkdir(parents=True)
    return paper, build_foonet(paper / "paper.pdf")


def write_case(paper: Path, evidence: str, report: str) -> None:
    (paper / WORK_DIR / "evidence.md").write_text(evidence, encoding="utf-8")
    # The summary uses the same format and checks, so the report doubles as the summary here.
    for kind in OUTPUT_KINDS:
        output_path(paper, kind).write_text(report, encoding="utf-8")


def check_naming(failures: list) -> None:
    long_title = Meta(title="Robust Recovery Controller for a Quadrupedal Robot using Deep Reinforcement Learning", year="2019")
    cases = [
        (format_name(long_title), "Robust Recovery Controller Quadrupedal Robot (2019)"),
        (format_name(Meta(title="Attention: Is All?", year="")), "Attention Is All"),
        (find_arxiv_id("2606.25965v2", "", None), "2606.25965"),
        (find_arxiv_id("paper", "see arXiv:1901.07517v1 [cs.RO]", None), "1901.07517"),
        (target_dir(SRC_DIR / "rsl" / "x.pdf", "N (2019)", Path("/o")), Path("/o/rsl/N (2019)")),
        (target_dir(Path("/elsewhere/x.pdf"), "N", Path("/o")), Path("/o/N")),
        (output_path(Path("/o/N (2019)"), "report"), Path("/o/N (2019)/N (2019) - report.md")),
    ]
    for got, want in cases:
        if got != want:
            failures.append(f"naming: expected {want!r}, got {got!r}")


def check_selection(failures: list) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp)
        for rel in ("rsl/a.pdf", "rsl/b.pdf", "c.PDF", "notes.txt"):
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).touch()
        names = lambda pdfs: [str(p.relative_to(src)) for p in pdfs]
        cases = [
            (names(select(None, 0, src)), ["c.PDF", "rsl/a.pdf", "rsl/b.pdf"]),
            (names(select(None, 2, src)), ["c.PDF", "rsl/a.pdf"]),
            (names(select("b", 2, src)), ["rsl/b.pdf"]),
            (names(select("rsl/a.pdf", 0, src)), ["rsl/a.pdf"]),
            (names(select("missing", 0, src)), []),
        ]
    for got, want in cases:
        if got != want:
            failures.append(f"selection: expected {want!r}, got {got!r}")


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix
    return ix / union if union else 0.0


def check_layout(paper: Path, truth: dict, failures: list) -> None:
    def fail(msg):
        failures.append(f"layout: {msg}")

    build_layout(paper, force=True)
    lay = paper / WORK_DIR / "layout"
    first = (lay / "blocks.json").read_bytes()
    build_layout(paper, force=True)
    if (lay / "blocks.json").read_bytes() != first:
        fail("blocks.json differs between two runs")
    data = json.loads(first)
    figures = {f["label"]: f for f in json.loads((lay / "figures.json").read_text(encoding="utf-8"))["figures"]}
    blocks = [b for p in data["pages"] for b in p["blocks"]]

    for p in data["pages"]:
        if p["columns"] != truth["columns"][p["page"]]:
            fail(f"p.{p['page']}: expected {truth['columns'][p['page']]} columns, got {p['columns']}")
        col0 = [b["order"] for b in p["blocks"] if b["column"] == 0 and b["kind"] == "paragraph"]
        col1 = [b["order"] for b in p["blocks"] if b["column"] == 1 and b["kind"] == "paragraph"]
        if col0 and col1 and max(col0) > min(col1):
            fail(f"p.{p['page']}: reading order does not finish column 0 before column 1")
    for prefix, kind in truth["kinds"].items():
        got = [b["kind"] for b in blocks if b["text"].startswith(prefix)]
        if not got or any(k != kind for k in got):
            fail(f"block {prefix!r}: expected {kind}, got {got}")
    if sum(b["kind"] == "caption" for b in blocks) != 3:
        fail("expected 3 captions")
    for label, (page, rect) in truth["figures"].items():
        f = figures.get(label)
        if not f or f["page"] != page:
            fail(f"{label} not detected on p.{page}")
            continue
        if label == "Table 1":
            if not all(f["bbox"][i] <= rect[i] + 1 for i in (0, 1)) or not all(f["bbox"][i] >= rect[i] - 1 for i in (2, 3)):
                fail(f"Table 1 bbox {f['bbox']} does not contain the table {rect}")
        elif iou(f["bbox"], rect) < (0.8 if label == "Figure 2" else 0.7):
            fail(f"{label} IoU {iou(f['bbox'], rect):.2f} too low ({f['bbox']} vs {rect})")
    if any(b["translate"] for b in blocks if b["kind"] in ("figure_text", "table_text")):
        fail("figure_text/table_text blocks must not be translated")
    refs = figures.get("Figure 1", {}).get("refs", [])
    body = {b["id"] for b in blocks if b["kind"] == "paragraph"}
    if not any(r["page"] == 2 and r["block"] in body for r in refs):
        fail(f"Figure 1 refs should include the p.2 body block, got {refs}")
    if not (paper / WORK_DIR / "translate" / "p001.src.md").is_file():
        fail("translate/p001.src.md not written")
    if not (lay / "figures" / f"{figures.get('Figure 1', {}).get('id')}.png").is_file():
        fail("Figure 1 crop not rendered")


def check_anchor(pdf: Path, truth: dict, failures: list) -> None:
    doc = pymupdf.open(pdf)
    q = truth["quotes"]
    a = anchor_quote(doc[0], q["hyphen"][1])
    if not a or len(a["rects"]) != 2 or a["rects"][0][1] == a["rects"][1][1]:
        failures.append(f"anchor: hyphenated quote should give 2 rects on different lines, got {a}")
    if not anchor_quote(doc[0], q["ligature"][1]):
        failures.append("anchor: ligature quote not matched")
    if anchor_quote(doc[0], q["result"][1]) is not None:
        failures.append("anchor: a p.2 quote must not anchor on p.1")
    a = anchor_quote(doc[0], q["repeated"][1])
    if not a or not a["ambiguous"]:
        failures.append(f"anchor: repeated quote should be ambiguous, got {a}")
    if anchor_quote(doc[0], q["problem"][1]) is None or anchor_quote(doc[1], q["result"][1]) is None:
        failures.append("anchor: evidence quotes should anchor on their pages")

    # rotated page: rects must land on the text as rendered (pdf.js renders rotation like MuPDF)
    rot = pymupdf.open()
    page = rot.new_page(width=612, height=792)
    page.insert_text((72, 100), "Rotated page anchor test sentence", fontsize=14)
    page.set_rotation(90)
    a = anchor_quote(page, "anchor test sentence")
    if not a:
        failures.append("anchor: rotated page quote not matched")
        return
    r = pymupdf.Rect(a["rects"][0])
    pix = page.get_pixmap(dpi=72, clip=r)
    if not (page.rect.contains(r) and min(pix.samples) < 128):
        failures.append(f"anchor: rotated page rect {r} does not cover the rendered text")


def check_papers(root: Path, paper: Path, failures: list) -> None:
    entries = scan(root)
    if [e.name for e in entries] != [paper.name] or entries[0].id != paper_id(Path(paper.name)):
        failures.append(f"papers: scan found {[e.name for e in entries]}")
    if resolve_for_annotate(paper.name, root) != paper.resolve():
        failures.append("papers: resolve_for_annotate by folder name failed")
    if entries and (entries[0].num_pages != 3 or not entries[0].has_layout or entries[0].status != "ok"):
        failures.append(f"papers: unexpected entry {entries[0]}")


def main() -> int:
    failures = []
    check_naming(failures)
    check_selection(failures)
    with tempfile.TemporaryDirectory() as tmp:
        paper, truth = build_paper(Path(tmp))

        stats = extract(paper / "paper.pdf", paper / WORK_DIR)
        if stats["pages"] != 3 or stats["scanned"]:
            failures.append(f"extract: unexpected stats {stats}")

        write_case(paper, GOOD_EVIDENCE, GOOD_OUTPUT)
        errors, warnings, _ = verify_paper(paper)
        if errors:
            failures.append(f"good case should pass but got errors: {errors}")

        write_case(paper, BAD_EVIDENCE, BAD_OUTPUT)
        errors, warnings, _ = verify_paper(paper)
        for expected in EXPECTED_BAD_ERRORS:
            if not any(expected in e for e in errors):
                failures.append(f"bad case: expected error containing {expected!r}")
        for expected in EXPECTED_BAD_WARNINGS:
            if not any(expected in w for w in warnings):
                failures.append(f"bad case: expected warning containing {expected!r}")

        check_layout(paper, truth, failures)
        check_anchor(paper / "paper.pdf", truth, failures)
        check_papers(Path(tmp) / "out", paper, failures)

    for f in failures:
        print(f"  FAIL  {f}")
    print(f"[selftest] {'PASS' if not failures else 'FAIL'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
