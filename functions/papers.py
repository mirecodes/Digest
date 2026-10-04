"""Paper folders under the output root: discovery, stable ids, status, and viewer settings.

A paper folder is any folder below out_root that holds .work/pages.md (written by prepare.py).
"""
import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from functions.prepare import load_config, out_root
from functions.verify import WORK_DIR, output_path

VIEWER_DEFAULTS = {
    "host": "127.0.0.1",
    "port": 8765,
    "target_lang": "ko",
    "translate_references": False,
    "llm_backend": "claude_cli",
    "model_interactive": "sonnet",
    "model_vision": "sonnet",
    "max_context_chars": 250000,
    "highlight_default_categories": ["problem", "contribution", "insight", "method", "result", "limitation"],
    "auto_annotate": False,
}
VERIFY_RE = re.compile(r"verify:\s*(PASS|FAIL)")


def viewer_cfg(cfg: dict | None = None) -> dict:
    """The `viewer:` section of configs/cfg.yaml over the defaults; missing keys fall back."""
    cfg = load_config() if cfg is None else cfg
    return {**VIEWER_DEFAULTS, **(cfg.get("viewer") or {})}


def paper_id(folder_rel: Path) -> str:
    return hashlib.sha1(Path(folder_rel).as_posix().encode("utf-8")).hexdigest()[:12]


def find_pdf(folder: Path) -> Path | None:
    """`<folder name>.pdf`, else the first other PDF that is not an exported annotated copy."""
    named = folder / f"{folder.name}.pdf"
    if named.is_file():
        return named
    pdfs = sorted(p for p in folder.glob("*.pdf") if not p.name.endswith(" - annotated.pdf"))
    return pdfs[0] if pdfs else None


def is_evicted(folder: Path) -> bool:
    """iCloud "optimize storage" replaced the PDF with a .<name>.pdf.icloud placeholder."""
    return find_pdf(folder) is None and any(folder.glob(".*.pdf.icloud"))


def digest_verify(folder: Path) -> str | None:
    report = output_path(folder, "report")
    if not report.is_file():
        return None
    m = VERIFY_RE.search(report.read_text(encoding="utf-8")[:2000])
    return m.group(1) if m else None


def _count(path: Path, pattern: str) -> int:
    return len(re.findall(pattern, path.read_text(encoding="utf-8"), re.M)) if path.is_file() else 0


@dataclass
class PaperEntry:
    id: str
    name: str
    folder: str
    folder_rel: str
    num_pages: int
    has_report: bool
    digest_verify: str | None
    has_layout: bool
    translation: dict = field(default_factory=dict)
    highlights: int = 0
    figure_notes: dict = field(default_factory=dict)
    status: str = "ok"          # ok | evicted

    def to_dict(self) -> dict:
        return asdict(self)


def entry(folder: Path, root: Path) -> PaperEntry:
    work = folder / WORK_DIR
    rel = folder.relative_to(root)
    tr = work / "translate"
    figures = work / "layout" / "figures.json"
    return PaperEntry(
        id=paper_id(rel),
        name=folder.name,
        folder=str(folder),
        folder_rel=rel.as_posix(),
        num_pages=_count(work / "pages.md", r"^<!-- PAGE \d+ -->"),
        has_report=output_path(folder, "report").is_file(),
        digest_verify=digest_verify(folder),
        has_layout=(work / "layout" / "blocks.json").is_file(),
        translation={"done": sum(_count(p, r"^<!-- BLOCK ") for p in tr.glob("p*.ko.md")),
                     "total": sum(_count(p, r"^<!-- BLOCK ") for p in tr.glob("p*.src.md"))},
        highlights=_count(work / "highlights.md", r"^###\s+H\d+\s*$"),
        figure_notes={"done": _count(work / "figure_notes.md", r"^###\s+F\d+\s*$"),
                      "total": _count(figures, r'"id":')},
        status="evicted" if is_evicted(folder) else "ok",
    )


def scan(root: Path | None = None) -> list[PaperEntry]:
    """Every paper folder below root (default: out_root from the config), sorted by relative path."""
    root = (root or out_root(load_config())).resolve()
    if not root.is_dir():
        return []
    folders = {p.parent.parent for p in root.rglob("pages.md") if p.parent.name == WORK_DIR}
    return sorted((entry(f, root) for f in folders), key=lambda e: e.folder_rel)


def resolve_for_annotate(name: str, root: Path | None = None) -> Path:
    """A paper folder path, folder name, or path relative to out_root. Raises ValueError unless exactly one matches."""
    path = Path(name).expanduser()
    if (path / WORK_DIR / "pages.md").is_file():
        return path.resolve()
    hits = [Path(e.folder) for e in scan(root) if name.rstrip("/") in (e.folder_rel, e.name)]
    if len(hits) != 1:
        raise ValueError(f"{name!r} matches {len(hits)} paper folders" + (f": {[str(h) for h in hits]}" if hits else ""))
    return hits[0]
