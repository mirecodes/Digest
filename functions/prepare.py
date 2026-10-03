"""Select papers from src/, create their output folders, move the PDFs there and extract page-tagged text.

Selection: `-n NAME` picks one paper (a path, or a src/ PDF matched by relative path, file name or stem);
without it, every PDF under src/ is taken, at most `max_papers` (configs/cfg.yaml) per run.

Layout: <out_root>/<path of the PDF relative to src/>/<Paper Name>/
  <Paper Name>.pdf                                     (moved out of src/; copied if it lives elsewhere)
  <Paper Name> - report.md, <Paper Name> - summary.md   (written later)
  .work/pages.md, .work/captions.md, .work/evidence.md (hidden from Obsidian; evidence written later)

<out_root> is `out_dir` from configs/cfg.yaml, or <project>/out when it is empty.

Usage (via wrapper): scripts/internal/prepare.sh [-n NAME] [--list] [--force] [--dry-run] [--offline]
Each prepared paper prints `[prepare] ready: <folder>`; skipped ones print `[prepare] skip ...`.
Exit codes: 0 ok, 1 nothing selected / input error.
  With -n only: 2 PDF looks scanned (needs OCR), 3 folder already exists.
"""
import argparse
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


def select(name: str | None, limit: int, src: Path) -> list[Path]:
    if name:
        return find_pdf(name, src)
    pdfs = src_pdfs(src)
    return pdfs[:limit] if limit > 0 else pdfs


def prepare_one(pdf: Path, cfg: dict, args) -> int:
    name, source = paper_name(pdf, cfg.get("title_words") or DEFAULT_TITLE_WORDS, args.offline)
    dest = target_dir(pdf, name, out_root(cfg))
    print(f"[prepare] {pdf.name} -> {name}   [{source}]")
    if args.dry_run:
        print(f"[prepare] folder: {dest}")
        return 0

    existed = dest.exists()
    if existed and not args.force:
        print(f"[prepare] skip (folder exists; ask the user before using --force): {dest}")
        return EXIT_EXISTS

    stats = extract(pdf, dest / WORK_DIR)
    print(f"[extract] {stats['pages']} pages, {stats['chars']} chars, {stats['captions']} captions")
    if stats["scanned"]:
        # Leave the PDF in src/ and drop the half-made folder so the paper can be retried after OCR.
        if not existed:
            shutil.rmtree(dest)
        print(f"[prepare] skip (PDF looks scanned; run OCR first): {pdf}")
        return EXIT_SCANNED

    pdf_out = dest / f"{name}.pdf"
    if in_src(pdf):
        shutil.move(pdf, pdf_out)
    elif pdf.resolve() != pdf_out.resolve():
        shutil.copy2(pdf, pdf_out)
    print(f"[prepare] ready: {dest}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare output folders for papers in src/")
    parser.add_argument("-n", "--name", help="one paper: path, or src/ relative path / file name / stem")
    parser.add_argument("--list", action="store_true", help="print the selected src/ papers and exit")
    parser.add_argument("--force", action="store_true", help="reuse an existing output folder")
    parser.add_argument("--dry-run", action="store_true", help="print names and folders only")
    parser.add_argument("--offline", action="store_true", help="skip arXiv/Crossref, use PDF metadata only")
    args = parser.parse_args()

    cfg = load_config()
    pdfs = select(args.name, int(cfg.get("max_papers") or 0), SRC_DIR)
    if args.name and len(pdfs) > 1:
        print(f"[prepare] ERROR: '{args.name}' matches several PDFs: {[str(p) for p in pdfs]}", file=sys.stderr)
        return 1
    if not pdfs:
        print(f"[prepare] ERROR: no PDF found{f' for {args.name!r}' if args.name else ' in src/'}", file=sys.stderr)
        return 1

    if args.list:
        for p in pdfs:
            print(p.relative_to(SRC_DIR) if in_src(p) else p)
        return 0

    codes = [prepare_one(p, cfg, args) for p in pdfs]
    if args.name:
        return codes[0]
    print(f"[prepare] {codes.count(0)}/{len(codes)} ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
