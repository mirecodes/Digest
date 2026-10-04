"""Paper registry: one YAML log of every paper the project knows, so no paper is processed twice.

<out_root>/.paper-registry.yaml (a dot file, so Obsidian ignores it). Papers are keyed by the SHA-256 of their PDF
(first 16 hex digits), which ties together the copy in src/, the output folder and its processing state:

  papers:
    3f9c0a1b2c3d4e5f:
      name: Short Title (Year)
      folder: rsl/Short Title (Year)        # relative to out_root; null = not prepared yet
      sources: {rsl/paper.pdf: 1234-1728}   # src/ path -> size-mtime_ns (a PDF is re-hashed only when it changes)
      state: annotated                      # new | prepared | digested | annotated
      digest: PASS                          # verify result of the report: PASS | FAIL | null
      translation: 106/106
      highlights: 45
      figure_notes: 13/13

The file is a cache of what is on disk: sync() rebuilds it from the output folders and src/, so deleting it is safe
(it costs one hash per PDF). Deleting an output folder makes its paper new again; moving it keeps the identity.
CLI: python -m functions.registry   (sync and print the table)
"""
import hashlib
import os
import tempfile
from pathlib import Path

import yaml

from functions.papers import PaperEntry, find_pdf, scan
from functions.prepare import SRC_DIR, load_config, out_root, src_pdfs

REGISTRY = ".paper-registry.yaml"
STATES = ("new", "prepared", "digested", "annotated")


def pdf_sha(pdf: Path) -> str:
    h = hashlib.sha256()
    with open(pdf, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _stamp(pdf: Path) -> str:
    st = pdf.stat()
    return f"{st.st_size}-{st.st_mtime_ns}"


def _status(e: PaperEntry) -> dict:
    tr, fn = e.translation, e.figure_notes
    annotated = e.has_layout and 0 < tr["done"] == tr["total"] and e.highlights > 0 and fn["done"] == fn["total"]
    state = "prepared" if not e.has_report else "annotated" if annotated and e.digest_verify == "PASS" else "digested"
    return {"state": state, "digest": e.digest_verify, "translation": f"{tr['done']}/{tr['total']}",
            "highlights": e.highlights, "figure_notes": f"{fn['done']}/{fn['total']}"}


def load(root: Path) -> dict[str, dict]:
    path = root / REGISTRY
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    return (data or {}).get("papers") or {}


def _save(root: Path, papers: dict[str, dict]) -> None:
    """Atomic write, so the viewer and a CLI run never see half a file."""
    text = "# Paper registry, rebuilt from disk by functions/registry.py; safe to delete.\n" + \
        yaml.safe_dump({"papers": papers}, allow_unicode=True, sort_keys=False, width=200)
    fd, tmp = tempfile.mkstemp(dir=root, prefix=".paper-registry.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, root / REGISTRY)


def sync(root: Path | None = None, src: Path = SRC_DIR) -> tuple[dict[str, dict], list[PaperEntry]]:
    """Rebuild the registry from the output folders and src/; returns (papers by sha, scanned output folders)."""
    root = (root or out_root(load_config())).resolve()
    old = load(root)
    by_folder = {e["folder"]: sha for sha, e in old.items() if e.get("folder")}
    papers: dict[str, dict] = {}
    entries = scan(root)
    for e in entries:
        sha = by_folder.get(e.folder_rel)
        if sha is None:
            pdf = find_pdf(Path(e.folder))
            if pdf is None:
                continue        # evicted from iCloud and never hashed: listed by scan, deduplicated once downloaded
            sha = pdf_sha(pdf)
        if sha not in papers:   # two folders of the same PDF: the first one (by path) counts
            papers[sha] = {"name": e.name, "folder": e.folder_rel, "sources": {}, **_status(e)}

    known = {rel: (stamp, sha) for sha, e in old.items() for rel, stamp in (e.get("sources") or {}).items()}
    for pdf in src_pdfs(src) if src.is_dir() else []:
        rel, stamp = pdf.relative_to(src).as_posix(), _stamp(pdf)
        hit = known.get(rel)
        sha = hit[1] if hit and hit[0] == stamp else pdf_sha(pdf)
        papers.setdefault(sha, {"name": pdf.stem, "folder": None, "sources": {}, "state": "new"})["sources"][rel] = stamp

    if root.is_dir() and (papers != old or not (root / REGISTRY).is_file()):
        _save(root, papers)
    return papers, entries


def done_sources(papers: dict[str, dict]) -> set[str]:
    """src/ paths whose PDF already has an output folder."""
    return {rel for e in papers.values() if e.get("folder") for rel in e["sources"]}


def folder_for(pdf: Path, root: Path | None = None, src: Path = SRC_DIR) -> Path | None:
    """The output folder already made from this PDF's content, if any."""
    root = (root or out_root(load_config())).resolve()
    papers, _ = sync(root, src)
    folder = papers.get(pdf_sha(pdf), {}).get("folder")
    return root / folder if folder else None


def library(root: Path | None = None, src: Path = SRC_DIR) -> list[PaperEntry]:
    """Output folders plus src/ PDFs that are not prepared yet (status "new", id from the PDF hash)."""
    root = (root or out_root(load_config())).resolve()
    papers, entries = sync(root, src)
    new = []
    for sha, p in papers.items():
        if p.get("folder"):
            continue
        rel = sorted(p["sources"])[0]
        new.append(PaperEntry(id=sha[:12], name=p["name"], folder="", folder_rel=rel, num_pages=0, has_report=False,
                              digest_verify=None, has_layout=False, translation={"done": 0, "total": 0},
                              figure_notes={"done": 0, "total": 0}, status="new", source=str(src / rel)))
    return sorted(entries + new, key=lambda e: e.folder_rel)


def main() -> int:
    papers, _ = sync()
    for sha, p in papers.items():
        where = p["folder"] or f"src/{sorted(p['sources'])[0]}"
        print(f"{sha}  {p['state']:<9}  {where}")
    print(f"[registry] {len(papers)} papers: " +
          ", ".join(f"{s} {sum(p['state'] == s for p in papers.values())}" for s in STATES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
