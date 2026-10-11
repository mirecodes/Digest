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
    "auto_annotate": False,
}
VERIFY_RE = re.compile(r"verify:\s*(PASS|FAIL)")
AGENTS = ("claude", "codex", "gemini")
# Model suggestions for the viewer's picker (any name the CLI accepts works; agent.models in cfg.yaml replaces them)
# and the effort levels each CLI takes (claude --effort, codex model_reasoning_effort; Gemini CLI has no flag).
AGENT_MODELS = {
    "claude": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-haiku-4-5-20251001"],
    "codex": [],
    "gemini": [],
}
AGENT_EFFORTS = {
    "claude": ["low", "medium", "high", "xhigh", "max"],
    "codex": ["minimal", "low", "medium", "high"],
    "gemini": [],
}
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,99}$")


def agent_cfg(cfg: dict | None = None) -> dict:
    """The `agent:` section of configs/cfg.yaml: backend (claude | codex | gemini), model and effort ("" = CLI
    default), plus the model suggestions and effort levels of that backend. For one run, $PAPER_AGENT overrides
    the backend, $PAPER_AGENT_MODEL the model and $PAPER_AGENT_EFFORT the effort."""
    cfg = load_config() if cfg is None else cfg
    agent = {"backend": "claude", "model": "", "effort": "", **(cfg.get("agent") or {})}
    for key, env in (("backend", "PAPER_AGENT"), ("model", "PAPER_AGENT_MODEL"), ("effort", "PAPER_AGENT_EFFORT")):
        agent[key] = str(os.environ.get(env) or agent[key] or "").strip()
    agent["backend"] = agent["backend"].lower()
    agent["models"] = [str(m) for m in agent.get("models") or AGENT_MODELS.get(agent["backend"], [])]
    agent["efforts"] = AGENT_EFFORTS.get(agent["backend"], [])
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
    report = output_path(folder)
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
    sha: str | None = None      # PDF content hash (registry): stays the same when the folder moves or is prepared

    def to_dict(self) -> dict:
        return asdict(self)


def highlight_count(work: Path) -> int:
    """H blocks in highlights.md (the only highlights; evidence quotes are not highlighted)."""
    return _count(work / "highlights.md", r"^###\s+H\d+\s*$")


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
        has_report=output_path(folder).is_file(),
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
    """A paper folder path, folder name, path relative to out_root, or a prepared PDF (a path, or a src/ relative
    path / file name / stem; found by content). Raises ValueError unless exactly one matches."""
    from functions.prepare import SRC_DIR, find_pdf as find_src_pdf
    from functions.registry import folder_for     # registry imports this module

    path = Path(name).expanduser()
    if (path / WORK_DIR / "pages.md").is_file():
        return path.resolve()
    hits = [Path(e.folder) for e in scan(root) if name.rstrip("/") in (e.folder_rel, e.name)]
    if not hits:
        pdfs = find_src_pdf(name, SRC_DIR)   # an existing path, or src/ matches
        if len(pdfs) == 1 and pdfs[0].suffix.lower() == ".pdf":
            folder = folder_for(pdfs[0], root)
            if folder is None:
                raise ValueError(f"{name!r} is not prepared yet (scripts/internal/prepare.sh --ensure -n NAME)")
            return folder
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
