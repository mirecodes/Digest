"""Self-test: build a tiny synthetic paper and confirm extract + verify + naming behave as expected.

Usage (via wrapper): scripts/internal/selftest.sh
"""
import sys
import tempfile
from pathlib import Path

import pymupdf

from functions.extract_pdf import extract
from functions.paper_name import Meta, find_arxiv_id, format_name
from functions.prepare import SRC_DIR, select, target_dir
from functions.verify import OUTPUT_KINDS, WORK_DIR, output_path, verify_paper

FILLER = "filler text " * 30

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


def build_paper(root: Path) -> Path:
    paper = root / "out" / "Demo (2024)"
    (paper / WORK_DIR).mkdir(parents=True)
    doc = pymupdf.open()
    doc.new_page().insert_text(
        (50, 72),
        "Abstract. We propose FooNet, a sparse attention model.\n"
        "Existing methods scale quadratically with sequence length,\n"
        "which limits long-context modeling.\n" + FILLER,
        fontsize=9,
    )
    doc.new_page().insert_text(
        (50, 72),
        "Table 2: Results on LRA. FooNet achieves 61.4 average accuracy,\n"
        "compared to 54.4 for the Transformer baseline.\n" + FILLER,
        fontsize=9,
    )
    doc.save(paper / "paper.pdf")
    return paper


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


def main() -> int:
    failures = []
    check_naming(failures)
    check_selection(failures)
    with tempfile.TemporaryDirectory() as tmp:
        paper = build_paper(Path(tmp))

        stats = extract(paper / "paper.pdf", paper / WORK_DIR)
        if stats["pages"] != 2 or stats["scanned"]:
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

    for f in failures:
        print(f"  FAIL  {f}")
    print(f"[selftest] {'PASS' if not failures else 'FAIL'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
