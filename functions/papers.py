"""Paper folders under the output root: discovery, stable ids, status, and viewer settings.

A paper folder is any folder below out_root that holds .work/pages.md (written by prepare.py).
CLI (used by scripts/annotate.sh): python -m functions.papers [-n NAME]
"""
import hashlib
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from functions.prepare import load_config, out_root
from functions.verify import WORK_DIR, output_path

DEFAULT_LANG = "ko"
VIEWER_DEFAULTS = {
    "host": "127.0.0.1",
    "port": 8765,
    "translate_references": False,
    "llm_backend": "claude_cli",
    "model_interactive": "sonnet",
    "model_vision": "sonnet",
    "max_context_chars": 250000,
    "highlight_default_categories": ["problem", "contribution", "insight", "method", "result", "limitation"],
    "auto_annotate": False,
}
VERIFY_RE = re.compile(r"verify:\s*(PASS|FAIL)")
AGENTS = ("claude", "codex", "gemini")


def agent_cfg(cfg: dict | None = None) -> dict:
    """The `agent:` section of configs/cfg.yaml: backend (claude | codex | gemini) and model ("" = CLI default).
    $PAPER_AGENT overrides the backend for one run."""
    cfg = load_config() if cfg is None else cfg
    agent = {"backend": "claude", "model": "", **(cfg.get("agent") or {})}
    agent["backend"] = str(os.environ.get("PAPER_AGENT") or agent["backend"]).strip().lower()
    agent["model"] = str(agent["model"] or "").strip()
    return agent


def viewer_cfg(cfg: dict | None = None) -> dict:
    """The `viewer:` section of configs/cfg.yaml over the defaults (missing keys fall back), plus target_lang."""
    cfg = load_config() if cfg is None else cfg
    return {**VIEWER_DEFAULTS, **(cfg.get("viewer") or {}), "target_lang": target_lang(cfg)}


def target_lang(cfg: dict | None = None) -> str:
    """Language code of translations and figure notes (`target_lang` in configs/cfg.yaml, default ko)."""
    cfg = load_config() if cfg is None else cfg
    return str(cfg.get("target_lang") or DEFAULT_LANG).strip().lower()


def tr_files(work: Path, lang: str | None = None) -> list[Path]:
    """.work/translate/pNNN.<lang>.md files, in page order."""
    return sorted((work / "translate").glob(f"p[0-9][0-9][0-9].{lang or target_lang()}.md"))


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
    status: str = "ok"          # ok | evicted | new (in src/ only, not prepared yet)
    source: str | None = None   # src/ PDF of a "new" paper

    def to_dict(self) -> dict:
        return asdict(self)


def highlight_count(work: Path) -> int:
    """Evidence-derived highlights plus H blocks, once the highlight step has run (highlights.md exists; it may hold
    no H block when evidence already covers the density cap). Unanchorable quotes are counted too: an estimate."""
    from functions.annotations import EVIDENCE_TO_HIGHLIGHT, parse_evidence
    md = work / "highlights.md"
    if not md.is_file():
        return 0
    evidence = parse_evidence((work / "evidence.md").read_text(encoding="utf-8")) if (work / "evidence.md").is_file() else {}
    derived = sum(e["category"] in EVIDENCE_TO_HIGHLIGHT and not e["not_reported"] and bool(e["page"] and e["quote"])
                  for e in evidence.values())
    return derived + _count(md, r"^###\s+H\d+\s*$")


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
        translation={"done": sum(_count(p, r"^<!-- BLOCK ") for p in tr_files(work)),
                     "total": sum(_count(p, r"^<!-- BLOCK ") for p in tr.glob("p*.src.md"))},
        highlights=highlight_count(work),
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


def needs_annotation(e: PaperEntry) -> bool:
    """Digested with verify PASS, but translation, highlights or figure notes are not complete yet."""
    if e.status != "ok" or e.digest_verify != "PASS":
        return False
    tr, fn = e.translation, e.figure_notes
    return not e.has_layout or tr["done"] < tr["total"] or e.highlights == 0 or fn["done"] < fn["total"]


def resolve_for_annotate(name: str, root: Path | None = None) -> Path:
    """A paper folder path, folder name, path relative to out_root, or a PDF already prepared (found by content).
    Raises ValueError unless exactly one matches."""
    path = Path(name).expanduser()
    if (path / WORK_DIR / "pages.md").is_file():
        return path.resolve()
    if path.is_file() and path.suffix.lower() == ".pdf":
        from functions.registry import folder_for     # registry imports this module
        folder = folder_for(path, root)
        if folder is None:
            raise ValueError(f"{name!r} is not prepared yet (run the digest first)")
        return folder
    hits = [Path(e.folder) for e in scan(root) if name.rstrip("/") in (e.folder_rel, e.name)]
    if len(hits) != 1:
        raise ValueError(f"{name!r} matches {len(hits)} paper folders" + (f": {[str(h) for h in hits]}" if hits else ""))
    return hits[0]


def main() -> int:
    """Folders for scripts/annotate.sh: `-n NAME` resolves one; otherwise papers needing annotation (max_papers)."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="List paper folders for annotation")
    parser.add_argument("-n", "--name")
    args = parser.parse_args()
    if args.name:
        try:
            print(resolve_for_annotate(args.name))
        except ValueError as e:
            print(f"[papers] ERROR: {e}", file=sys.stderr)
            return 1
        return 0
    cfg = load_config()
    pending = [e.folder for e in scan() if needs_annotation(e)]
    limit = int(cfg.get("max_papers") or 0)
    for folder in pending[:limit] if limit > 0 else pending:
        print(folder)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
