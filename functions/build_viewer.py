"""Bundle a paper's layout and annotations into .work/viewer.json, the only file the viewer frontend reads.

Schema: docs/viewer-plan.md §4.8 (mirrored in web/src/types.ts). Deterministic apart from `built_at`; no LLM calls.
Phase 2 bundles the layout only: translations, highlights and figure notes stay empty until Phase 3.

Usage (via wrapper): scripts/internal/build_viewer.sh "<paper folder>"
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from functions.layout import build_layout
from functions.papers import digest_verify, find_pdf, paper_id
from functions.prepare import load_config, out_root
from functions.verify import WORK_DIR, output_path

VERSION = 1
CITE_RE = re.compile(r"\s*\[[^\]]*\]")


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
    return [f for f in files if f and f.exists()] + sorted((work / "translate").glob("p*.ko.md"))


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

    blocks = [{"id": b["id"], "page": p["page"], "kind": b["kind"], "bbox": b["bbox"], "column": b["column"],
               "order": b["order"], "text": b["text"], "translate": b["translate"], "tr": None, "figure_id": b["figure_id"]}
              for p in layout["pages"] for b in p["blocks"]]
    translate_total = sum(b["translate"] for b in blocks)
    data = {
        "version": VERSION,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "paper": {"id": pid, "name": paper_dir.name, "folder_rel": rel.as_posix(), **report_meta(paper_dir),
                  "num_pages": len(layout["pages"]), "pdf_url": f"{api}/pdf", "digest_verify": digest_verify(paper_dir)},
        "pages": [{k: p[k] for k in ("page", "width", "height", "rotation", "columns", "column_split", "body_font_size")}
                  for p in layout["pages"]],
        "blocks": blocks,
        "figures": [{"id": f["id"], "page": f["page"], "kind": f["kind"], "label": f["label"], "bbox": f["bbox"],
                     "caption_block": f["caption_block"], "image_url": f"{api}/figures/{f['id']}.png",
                     "confidence": f["confidence"], "bbox_source": f["bbox_source"], "refs": f["refs"], "note": None}
                    for f in figures],
        "highlights": [],
        "evidence": {},
        "outline": layout["outline"],
        "status": {"layout": True, "translation": {"done": 0, "total": translate_total}, "highlights": 0,
                   "figure_notes": {"done": 0, "total": len(figures)}, "annotations_verify": None, "warnings": 0},
    }
    out = work / "viewer.json"
    out.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return out


def ensure_viewer(paper_dir: Path, root: Path | None = None) -> Path:
    """viewer.json, rebuilt first when missing or older than any of its inputs (including a stale layout)."""
    paper_dir = paper_dir.resolve()
    build_layout(paper_dir)
    out = paper_dir / WORK_DIR / "viewer.json"
    if out.exists() and all(out.stat().st_mtime >= f.stat().st_mtime for f in inputs(paper_dir)):
        return out
    return build_viewer(paper_dir, root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build .work/viewer.json for the paper viewer")
    parser.add_argument("paper_dir", type=Path)
    args = parser.parse_args()
    if find_pdf(args.paper_dir.resolve()) is None:
        print(f"[build-viewer] ERROR: no PDF in {args.paper_dir}", file=sys.stderr)
        return 1
    out = build_viewer(args.paper_dir)
    data = json.loads(out.read_text(encoding="utf-8"))
    print(f"[build-viewer] {out} pages={data['paper']['num_pages']} blocks={len(data['blocks'])} figures={len(data['figures'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
