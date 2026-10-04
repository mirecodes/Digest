"""Bundle a paper's layout and annotations into .work/viewer.json, the only file the viewer frontend reads.

Schema: docs/viewer-plan.md §4.8 (mirrored in web/src/types.ts). Deterministic apart from `built_at`; no LLM calls.
Translations, highlights and figure notes come from verify_annotations, so only anchored highlights and valid notes
are bundled; `status` carries its PASS/FAIL and warning count.

Usage (via wrapper): scripts/internal/build_viewer.sh "<paper folder>"
                     scripts/internal/build_viewer.sh --update-golden   (regenerate tests/fixtures/viewer.sample.json)
"""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from functions.annotations import parse_translation
from functions.layout import build_layout
from functions.papers import digest_verify, find_pdf, paper_id, tr_files
from functions.prepare import ROOT, load_config, out_root
from functions.verify import WORK_DIR, output_path
from functions.verify_annotations import verify_annotations

VERSION = 3   # bump on schema changes: ensure_viewer rebuilds bundles of another version
              # (2: tr/note_tr keys, lang; 3: highlights are H blocks only, big-picture categories, no `source`)
CITE_RE = re.compile(r"\s*\[[^\]]*\]")
GOLDEN = ROOT / "tests" / "fixtures" / "viewer.sample.json"


def viewer_root() -> Path:
    """Output root the viewer serves: $PAPER_VIEWER_OUT (tests) or out_dir from the config."""
    return Path(os.environ.get("PAPER_VIEWER_OUT") or out_root(load_config())).resolve()


def report_meta(paper_dir: Path) -> dict:
    """Title, authors, venue/year from the report header ("# Title" and "> Authors · Venue, Year [E1, p.1]")."""
    meta = {"title": None, "authors": None, "venue_year": None}
    report = output_path(paper_dir, "report")
    if not report.is_file():
        return meta
    for line in report.read_text(encoding="utf-8").splitlines()[:10]:
        if line.startswith("# ") and not meta["title"]:
            meta["title"] = line[2:].strip()
        elif line.startswith(">") and " · " in line and not meta["authors"] and "verify:" not in line:
            authors, venue = CITE_RE.sub("", line.lstrip("> ")).split(" · ", 1)
            meta["authors"], meta["venue_year"] = authors.strip() or None, venue.strip() or None
    return meta


def inputs(paper_dir: Path) -> list[Path]:
    """Files whose change makes viewer.json stale."""
    work = paper_dir / WORK_DIR
    files = [find_pdf(paper_dir), work / "layout" / "blocks.json", work / "layout" / "figures.json",
             output_path(paper_dir, "report"), work / "evidence.md", work / "highlights.md", work / "figure_notes.md",
             work / "viewer" / "figure_overrides.json"]
    return [f for f in files if f and f.exists()] + tr_files(work)


def build_viewer(paper_dir: Path, root: Path | None = None) -> Path:
    paper_dir = paper_dir.resolve()
    root = (root or viewer_root()).resolve()
    build_layout(paper_dir)
    work = paper_dir / WORK_DIR
    layout = json.loads((work / "layout" / "blocks.json").read_text(encoding="utf-8"))
    figures = json.loads((work / "layout" / "figures.json").read_text(encoding="utf-8"))["figures"]
    rel = paper_dir.relative_to(root) if root in paper_dir.parents else Path(paper_dir.name)
    pid = paper_id(rel)
    api = f"/api/papers/{pid}"
    checked = verify_annotations(paper_dir)
    tr = {}
    for path in tr_files(work, checked["lang"]):
        tr.update(parse_translation(path.read_text(encoding="utf-8")))

    blocks = [{"id": b["id"], "page": p["page"], "kind": b["kind"], "bbox": b["bbox"], "column": b["column"],
               "order": b["order"], "text": b["text"], "translate": b["translate"], "tr": tr.get(b["id"]) or None,
               "figure_id": b["figure_id"]}
              for p in layout["pages"] for b in p["blocks"]]
    translate_total = sum(b["translate"] for b in blocks)
    notes = {fid: {k: v for k, v in (("status", n["status"]), ("reason", n["reason"]), ("tr", n["tr"]), ("en", n["en"]))
                   if v is not None} for fid, n in checked["notes"].items()}
    present = checked["present"]
    data = {
        "version": VERSION,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lang": checked["lang"],
        "paper": {"id": pid, "name": paper_dir.name, "folder_rel": rel.as_posix(), **report_meta(paper_dir),
                  "num_pages": len(layout["pages"]), "pdf_url": f"{api}/pdf", "digest_verify": digest_verify(paper_dir)},
        "pages": [{k: p[k] for k in ("page", "width", "height", "rotation", "columns", "column_split", "body_font_size")}
                  for p in layout["pages"]],
        "blocks": blocks,
        "figures": [{"id": f["id"], "page": f["page"], "kind": f["kind"], "label": f["label"], "bbox": f["bbox"],
                     "caption_block": f["caption_block"], "image_url": f"{api}/figures/{f['id']}.png",
                     "confidence": f["confidence"], "bbox_source": f["bbox_source"], "refs": f["refs"],
                     "note": notes.get(f["id"])}
                    for f in figures],
        "highlights": checked["highlights"],
        "evidence": {eid: {"page": e["page"], "loc": e["loc"], "quote": e["quote"], "category": e["category"]}
                     for eid, e in checked["evidence"].items() if not e["not_reported"] and e["page"] and e["quote"]},
        "outline": layout["outline"],
        "status": {"layout": True,
                   "translation": {"done": sum(1 for b in blocks if b["translate"] and b["tr"]), "total": translate_total},
                   "highlights": len(checked["highlights"]),
                   "figure_notes": {"done": len(notes), "total": len(figures)},
                   "annotations_verify": ("FAIL" if checked["errors"] else "PASS") if present else None,
                   "warnings": len(checked["warnings"]) if present else 0},
    }
    out = work / "viewer.json"
    out.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return out


def ensure_viewer(paper_dir: Path, root: Path | None = None) -> Path:
    """viewer.json, rebuilt first when missing or older than any of its inputs (including a stale layout)."""
    paper_dir = paper_dir.resolve()
    build_layout(paper_dir)
    out = paper_dir / WORK_DIR / "viewer.json"
    if out.exists() and _version(out) == VERSION and all(out.stat().st_mtime >= f.stat().st_mtime for f in inputs(paper_dir)):
        return out
    return build_viewer(paper_dir, root)


def _version(path: Path) -> int | None:
    """Schema version of an existing bundle (keys are sorted, so "version" is the last one: read the tail only)."""
    with open(path, "rb") as f:
        f.seek(max(0, path.stat().st_size - 64))
        m = re.search(rb'"version":\s*(\d+)\s*}\s*$', f.read())
    return int(m.group(1)) if m else None


def golden_bundle() -> dict:
    """viewer.json of the annotated FooNet fixture, without `built_at` (compared by selftest)."""
    from functions.fixtures import prepare_demo

    with tempfile.TemporaryDirectory() as tmp:
        paper = prepare_demo(Path(tmp) / "Demo (2024)")
        data = json.loads(build_viewer(paper, Path(tmp)).read_text(encoding="utf-8"))
    data.pop("built_at")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Build .work/viewer.json for the paper viewer")
    parser.add_argument("paper_dir", type=Path, nargs="?")
    parser.add_argument("--update-golden", action="store_true", help=f"regenerate {GOLDEN.relative_to(ROOT)}")
    args = parser.parse_args()
    if args.update_golden:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(golden_bundle(), ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8")
        print(f"[build-viewer] wrote {GOLDEN}")
        return 0
    if args.paper_dir is None:
        parser.error("paper_dir is required unless --update-golden is given")
    if find_pdf(args.paper_dir.resolve()) is None:
        print(f"[build-viewer] ERROR: no PDF in {args.paper_dir}", file=sys.stderr)
        return 1
    out = build_viewer(args.paper_dir)
    data = json.loads(out.read_text(encoding="utf-8"))
    print(f"[build-viewer] {out} pages={data['paper']['num_pages']} blocks={len(data['blocks'])} figures={len(data['figures'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
