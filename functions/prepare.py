"""Select papers from src/, create their output folders, copy the PDFs there and extract page-tagged text.

Selection: `-n NAME` picks one paper (a path, or a src/ PDF matched by relative path, file name or stem);
without it, every src/ PDF that has no output folder yet, at most `max_papers` (configs/cfg.yaml) per run.
src/ is never modified. Papers are identified by content (functions/registry.py, <out_root>/.paper-registry.yaml),
so a renamed or duplicated PDF is not processed twice.

Layout (mirrors src/; a folder follows its PDF to another src/ folder, functions/registry.py relocate()):
<out_root>/<path of the PDF relative to src/>/<Paper Name>/
  <Paper Name>.pdf                                     (a copy; the original stays where it is)
  <Paper Name> [summary].md                            (written later)
  .work/pages.md, .work/captions.md, .work/evidence.md (hidden from Obsidian; evidence written later)

<out_root> is `out_dir` from configs/cfg.yaml, or <project>/out when it is empty.

Usage (via wrapper): scripts/internal/prepare.sh [-n NAME] [--list] [--force] [--ensure] [--dry-run] [--offline]
Each prepared paper prints `[prepare] ready: <folder>`; skipped ones print `[prepare] skip ...`.
A PDF whose folder exists but whose digest is missing or failed is resumed: `ready` again, without re-extracting.
--ensure: the first step of every processing job (viewer, annotate.sh): prepare if needed, and report an already
digested paper as `ready` (exit 0) instead of exit 4, so translation, highlights and figure notes never wait for the
digest.
Exit codes: 0 ok, 1 nothing selected / input error.
  With -n only: 2 PDF looks scanned (needs OCR), 3 another paper's folder has the same name,
  4 already digested (verify PASS; --force redoes it).
"""
import argparse
import fcntl
import shutil
import sys
from pathlib import Path

import yaml

from functions.extract_pdf import EXIT_SCANNED, extract
from functions.paper_name import DEFAULT_TITLE_WORDS, paper_name
from functions.verify import WORK_DIR

ROOT = Path(__file__).resolve().parent.parent
CFG_PATH = ROOT / "configs" / "cfg.yaml"
SRC_DIR = ROOT / "src"
DEFAULT_OUT = ROOT / "out"
EXIT_EXISTS = 3
EXIT_DONE = 4
LOCK_NAME = ".paper-prepare.lock"


def load_config() -> dict:
    if not CFG_PATH.exists():
        return {}
    return yaml.safe_load(CFG_PATH.read_text(encoding="utf-8")) or {}


def out_root(cfg: dict) -> Path:
    """`out_dir` from the config (absolute, ~, or relative to the project root); default <project>/out."""
    value = cfg.get("out_dir")
    if not value:
        return DEFAULT_OUT
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else ROOT / path


def in_src(pdf: Path) -> bool:
    return SRC_DIR in pdf.resolve().parents


def target_dir(pdf: Path, name: str, root: Path) -> Path:
    """Mirror the PDF's folder below src/ inside the output root."""
    rel = pdf.resolve().parent.relative_to(SRC_DIR) if in_src(pdf) else Path()
    return root / rel / name


def src_pdfs(src: Path) -> list[Path]:
    return sorted(p for p in src.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")


def find_pdf(name: str, src: Path) -> list[Path]:
    """An existing path wins; otherwise match src/ PDFs by relative path, file name or stem."""
    if Path(name).is_file():
        return [Path(name)]
    return [p for p in src_pdfs(src) if name in (str(p.relative_to(src)), p.name, p.stem, str(p.relative_to(src).with_suffix("")))]


def select(name: str | None, limit: int, src: Path, done: set[str] = frozenset()) -> list[Path]:
    """`-n NAME` matches; otherwise src/ PDFs whose relative path is not in `done` (already prepared), up to limit."""
    if name:
        return find_pdf(name, src)
    pdfs = [p for p in src_pdfs(src) if p.relative_to(src).as_posix() not in done]
    return pdfs[:limit] if limit > 0 else pdfs


def prepare_one(pdf: Path, cfg: dict, args, papers: dict) -> int:
    """`papers` is the registry (sha -> entry); it gets the new folder so a duplicate later in the run is caught."""
    from functions.registry import pdf_sha, relocate     # registry imports this module
    from functions.papers import digest_verify

    root = out_root(cfg)
    sha = pdf_sha(pdf)
    if not args.dry_run:
        relocate(root, papers, {sha})       # the PDF moved to another src/ folder: its output folder follows
    known = papers.get(sha, {}).get("folder")
    if known and (root / known).is_dir():
        dest = root / known
        if digest_verify(dest) == "PASS" and not args.force and not getattr(args, "ensure", False):
            print(f"[prepare] skip (already digested, verify PASS): {dest}")
            return EXIT_DONE
        if (dest / WORK_DIR / "pages.md").is_file() and not args.force:
            print(f"[prepare] {pdf.name} is already prepared; resuming")
            print(f"[prepare] ready: {dest}")
            return 0
        name = dest.name
        print(f"[prepare] {pdf.name} -> {name}   [registry]")
    else:
        name, source = paper_name(pdf, cfg.get("title_words") or DEFAULT_TITLE_WORDS, args.offline)
        dest = target_dir(pdf, name, root)
        print(f"[prepare] {pdf.name} -> {name}   [{source}]")
        if dest.exists() and not args.force:
            print(f"[prepare] skip (a folder of another PDF has this name; ask the user before using --force): {dest}")
            return EXIT_EXISTS
    if args.dry_run:
        print(f"[prepare] folder: {dest}")
        return 0

    existed = dest.exists()
    stats = extract(pdf, dest / WORK_DIR)
    print(f"[extract] {stats['pages']} pages, {stats['chars']} chars, {stats['captions']} captions")
    if stats["scanned"]:
        # Drop the half-made folder so the paper can be retried after OCR.
        if not existed:
            shutil.rmtree(dest)
        print(f"[prepare] skip (PDF looks scanned; run OCR first): {pdf}")
        return EXIT_SCANNED

    pdf_out = dest / f"{name}.pdf"
    if pdf.resolve() != pdf_out.resolve():
        shutil.copy2(pdf, pdf_out)
    papers.setdefault(sha, {"sources": {}})["folder"] = dest.relative_to(root).as_posix()
    print(f"[prepare] ready: {dest}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare output folders for papers in src/")
    parser.add_argument("-n", "--name", help="one paper: path, or src/ relative path / file name / stem")
    parser.add_argument("--list", action="store_true", help="print the selected src/ papers and exit")
    parser.add_argument("--force", action="store_true", help="reuse an existing output folder")
    parser.add_argument("--ensure", action="store_true",
                        help="make sure the paper is prepared (copy, extract, register); already done is success")
    parser.add_argument("--dry-run", action="store_true", help="print names and folders only")
    parser.add_argument("--offline", action="store_true", help="skip arXiv/Crossref, use PDF metadata only")
    args = parser.parse_args()

    cfg = load_config()
    root = out_root(cfg)
    root.mkdir(parents=True, exist_ok=True)
    # one prepare at a time per output root (parallel viewer jobs, the viewer's own preparing, the CLI): each reads the
    # registry first and writes it last, and two runs on one new PDF would both make its folder
    with open(root / LOCK_NAME, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _run(args, cfg, root)


def _run(args, cfg: dict, root: Path) -> int:
    from functions.registry import done_sources, sync

    papers, _ = sync(root)
    pdfs = select(args.name, int(cfg.get("max_papers") or 0), SRC_DIR, done_sources(papers))
    if args.name and len(pdfs) > 1:
        print(f"[prepare] ERROR: '{args.name}' matches several PDFs: {[str(p) for p in pdfs]}", file=sys.stderr)
        return 1
    if not pdfs:
        print(f"[prepare] ERROR: no PDF found{f' for {args.name!r}' if args.name else ' in src/ that is not prepared yet'}",
              file=sys.stderr)
        return 1

    if args.list:
        if args.name and not args.force:
            from functions.papers import digest_verify
            from functions.registry import pdf_sha
            folder = papers.get(pdf_sha(pdfs[0]), {}).get("folder")
            if folder and digest_verify(root / folder) == "PASS":
                print(f"[prepare] skip (already digested, verify PASS): {root / folder}", file=sys.stderr)
                return EXIT_DONE
        for p in pdfs:
            print(p.relative_to(SRC_DIR) if in_src(p) else p)
        return 0

    codes = [prepare_one(p, cfg, args, papers) for p in pdfs]
    if not args.dry_run:
        sync(root)
    if args.name:
        return codes[0]
    print(f"[prepare] {codes.count(0)}/{len(codes)} ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
