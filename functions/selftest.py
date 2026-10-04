"""Self-test: build a tiny synthetic paper and confirm extract + verify + naming + viewer layout behave as expected.

Usage (via wrapper): scripts/internal/selftest.sh
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pymupdf

from functions.anchor import anchor_quote
from functions.build_viewer import GOLDEN, build_viewer
from functions.extract_pdf import extract
from functions.fixtures import build_foonet, build_long, prepare_demo, write_annotations
from functions.verify_annotations import verify_annotations
from functions.layout import build_layout
from functions.paper_name import Meta, find_arxiv_id, format_name
from functions.papers import paper_id, resolve_for_annotate, scan
from functions.prepare import EXIT_DONE, SRC_DIR, prepare_one, select, target_dir
from functions.registry import REGISTRY, done_sources, folder_for, library, sync
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


EXPECTED_ANNOTATION_ERRORS = [
    "missing translation for p2-b5", "unknown block p9-b9", "H3: quote not found", "H4: category 'novelty'",
    "figure 'fig-p9-0' is not in", "unknown evidence E9", "[FIG: fig-nope] refers to an unknown figure",
]
EXPECTED_ANNOTATION_WARNINGS = ["p2-b6 drops numbers ['61.4']"]


def check_annotations(root: Path, failures: list) -> None:
    paper = prepare_demo(root / "annotated" / "Demo (2024)")
    r = verify_annotations(paper)
    if r["errors"]:
        failures.append(f"verify_annotations: good case should pass but got {r['errors']}")
    if r["translation"] != {"done": 16, "total": 16} or len(r["highlights"]) != 6 or len(r["notes"]) != 3:
        failures.append(f"verify_annotations: unexpected counts {r['translation']}, {len(r['highlights'])}, {len(r['notes'])}")

    golden = json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.is_file() else None
    got = json.loads(build_viewer(paper, root / "annotated").read_text(encoding="utf-8"))
    got.pop("built_at")
    if got != golden:
        diff = sorted(k for k in set(got) | set(golden or {}) if got.get(k) != (golden or {}).get(k))
        failures.append(f"build_viewer: bundle differs from {GOLDEN.name} in {diff} "
                        "(if the schema changed on purpose: scripts/internal/build_viewer.sh --update-golden)")

    write_annotations(paper, "bad")
    r = verify_annotations(paper)
    for expected in EXPECTED_ANNOTATION_ERRORS:
        if not any(expected in e for e in r["errors"]):
            failures.append(f"verify_annotations bad case: expected error containing {expected!r}")
    for expected in EXPECTED_ANNOTATION_WARNINGS:
        if not any(expected in w for w in r["warnings"]):
            failures.append(f"verify_annotations bad case: expected warning containing {expected!r}")


def make_src(src: Path, paper: Path) -> None:
    """src/ with a new paper (inbox/fresh.pdf) and a copy of an already prepared one (dup.pdf)."""
    (src / "inbox").mkdir(parents=True, exist_ok=True)
    build_long(src / "inbox" / "fresh.pdf", pages=2)
    shutil.copy2(paper / "paper.pdf", src / "dup.pdf")


def check_registry(root: Path, paper: Path, src: Path, failures: list) -> None:
    papers, _ = sync(root, src)
    by_folder = {p["folder"]: p for p in papers.values()}
    demo = by_folder.get(paper.name, {})
    if len(papers) != 2 or demo.get("sources", {}).keys() != {"dup.pdf"} or None not in by_folder:
        failures.append(f"registry: expected the demo (with src dup.pdf) and one new paper, got {papers}")
    if not (root / REGISTRY).is_file():
        failures.append("registry: file not written")
    if [p.name for p in select(None, 0, src, done_sources(papers))] != ["fresh.pdf"]:
        failures.append("registry: selection should skip the already prepared dup.pdf")
    if folder_for(src / "dup.pdf", root, src) != root / paper.name:
        failures.append("registry: folder_for(dup.pdf) should find the demo folder")
    if sorted(e.status for e in library(root, src)) != ["new", "ok"]:
        failures.append("registry: library should list the demo and one new paper")

    # prepare copies (src/ stays as it is), then resumes instead of redoing, and stops once the digest passed
    import contextlib
    import io
    from argparse import Namespace
    args = Namespace(force=False, dry_run=False, offline=True)
    cfg = {"out_dir": str(root)}
    fresh = src / "inbox" / "fresh.pdf"
    with contextlib.redirect_stdout(io.StringIO()) as out:
        codes = [prepare_one(fresh, cfg, args, papers)]
        made = folder_for(fresh, root, src)
        codes.append(prepare_one(fresh, cfg, args, sync(root, src)[0]))
        if made:
            output_path(made, "report").write_text("> verify: PASS\n", encoding="utf-8")
        codes.append(prepare_one(fresh, cfg, args, sync(root, src)[0]))
    if not fresh.is_file() or made is None or codes != [0, 0, EXIT_DONE] or "resuming" not in out.getvalue():
        failures.append(f"prepare: expected copy, resume, already-digested; got codes {codes}, folder {made}, "
                        f"src kept {fresh.is_file()}")
    elif made:
        shutil.rmtree(made)     # leave the tree as the server check expects it
        sync(root, src)


def check_server(root: Path, src: Path, failures: list) -> None:
    os.environ["PAPER_VIEWER_OUT"] = str(root)
    os.environ["PAPER_VIEWER_SRC"] = str(src)
    os.environ["PAPER_VIEWER_LLM"] = "fake"
    from fastapi.testclient import TestClient
    from functions.viewer.server import app

    client = TestClient(app)
    papers = client.get("/api/papers").json()
    ready = [p for p in papers if p["status"] == "ok"]
    new = [p for p in papers if p["status"] == "new"]
    if len(ready) != 1 or len(new) != 1:
        failures.append(f"server: /api/papers should list 1 prepared and 1 new paper, got {papers}")
        return
    api = f"/api/papers/{ready[0]['id']}"
    data = client.get(f"{api}/viewer.json").json()
    if data.get("paper", {}).get("num_pages") != 3 or not data.get("blocks") or len(data.get("figures", [])) != 3:
        failures.append("server: viewer.json is incomplete")
    fid = data["figures"][0]["id"] if data.get("figures") else "fig-p2-0"
    cases = [
        (client.get(f"{api}/pdf").status_code, 200, "pdf"),
        (client.get(f"{api}/pdf", headers={"Range": "bytes=0-99"}).status_code, 206, "pdf range"),
        (client.get(f"{api}/figures/{fid}.png").status_code, 200, "figure png"),
        (client.get(f"{api}/figures/..%2F..%2Fpages.md.png").status_code, 404, "figure path escape"),
        (client.get(f"{api}/figures/fig-p2-0%2F..%2F..%2F..%2Fpages.md.png").status_code, 404, "figure path escape 2"),
        (client.get("/api/papers/000000000000/pdf").status_code, 404, "unknown paper"),
        (client.get(f"{api}/crop", params={"page": 2, "bbox": "85,100,245,220"}).status_code, 200, "crop"),
        (client.get(f"{api}/crop", params={"page": 2, "bbox": "0,0,9999,10"}).status_code, 400, "crop outside page"),
        (client.get(f"{api}/crop", params={"page": 9, "bbox": "0,0,10,10"}).status_code, 400, "crop page range"),
        (client.get(f"{api}/crop", params={"page": 1, "bbox": "0,0,10,10", "dpi": 2000}).status_code, 400, "crop dpi"),
    ]
    for got, want, name in cases:
        if got != want:
            failures.append(f"server: {name}: expected {want}, got {got}")

    # processing jobs with a stub instead of the scripts (no Claude call); it echoes the script and its arguments
    os.environ["PAPER_VIEWER_JOB_CMD"] = f'"{sys.executable}" -c "import sys; print(\'stub\', *sys.argv[1:])"'
    new_api = f"/api/papers/{new[0]['id']}"
    run = lambda url, action: client.post(f"{url}/run", json={"action": action})
    cases = [
        (run(new_api, "translation").status_code, 409, "annotate part on a new paper"),
        (run(api, "everything").status_code, 422, "unknown action"),
        (client.get(f"{new_api}/pdf").status_code, 409, "pdf of a new paper"),
    ]
    for got, want, name in cases:
        if got != want:
            failures.append(f"server: {name}: expected {want}, got {got}")
    for url, action, expected in [
        (new_api, "all", ["stub digest.sh -n " + str(src / "inbox" / "fresh.pdf"), "stub annotate.sh -n "]),
        (api, "figures", [f"stub annotate.sh -n {root / 'Demo (2024)'} --only figures"]),
    ]:
        job = run(url, action).json()
        events = client.get(f"/api/jobs/{job.get('job_id')}/events").text
        if any(e not in events for e in expected) or \
                'event: done\ndata: {"status": "done", "returncode": 0}' not in events:
            failures.append(f"server: {action} job stream unexpected: {events[:400]!r}")
    if client.get("/api/jobs/nope/events").status_code != 404:
        failures.append("server: unknown job should be 404")


def main() -> int:
    failures = []
    check_naming(failures)
    check_selection(failures)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp).resolve()   # macOS: /var -> /private/var; the registry and server report resolved paths
        paper, truth = build_paper(tmp)

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
        make_src(Path(tmp) / "src", paper)
        check_registry(Path(tmp) / "out", paper, Path(tmp) / "src", failures)
        check_server(Path(tmp) / "out", Path(tmp) / "src", failures)
        check_annotations(Path(tmp), failures)

    for f in failures:
        print(f"  FAIL  {f}")
    print(f"[selftest] {'PASS' if not failures else 'FAIL'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
