"""Convert a PDF into page-tagged text (pages.md) and a caption index (captions.md).

Page tags make citations deterministic: Claude cites pages from pages.md,
and verify.py checks citations against the same file.

Called by functions/prepare.py; standalone: python -m functions.extract_pdf <paper.pdf> [out_dir]
"""
import argparse
import re
import sys
from pathlib import Path

import pymupdf

CAPTION_RE = re.compile(r"^\s*((?:Table|Tab\.|Figure|Fig\.)\s*\d+[.:]?.*)$", re.M | re.I)
# Below this average number of characters per page, the PDF is probably a scan.
MIN_CHARS_PER_PAGE = 200
EXIT_SCANNED = 2


def extract(pdf_path: Path, out_dir: Path) -> dict:
    """Write pages.md and captions.md into out_dir and return extraction stats."""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    pages, captions, total_chars = [], [], 0

    for i, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        total_chars += len(text)
        # The HTML comment is the machine-readable marker; the heading is for humans.
        pages.append(f"<!-- PAGE {i} -->\n# [p.{i}]\n\n{text}\n")
        for m in CAPTION_RE.finditer(text):
            captions.append(f"- p.{i}: {m.group(1).strip()[:200]}")

    (out_dir / "pages.md").write_text("\n\n".join(pages), encoding="utf-8")
    (out_dir / "captions.md").write_text(
        "# Figure / Table captions\n\n" + ("\n".join(captions) or "(no captions found)") + "\n",
        encoding="utf-8",
    )

    n_pages = len(doc)
    return {
        "pages": n_pages,
        "chars": total_chars,
        "captions": len(captions),
        "scanned": n_pages > 0 and total_chars / n_pages < MIN_CHARS_PER_PAGE,
        "out_dir": out_dir,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF -> page-tagged pages.md + captions.md")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("out_dir", type=Path, nargs="?", help="default: <pdf dir>/.work")
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"[extract] ERROR: file not found: {args.pdf}", file=sys.stderr)
        return 1

    stats = extract(args.pdf, args.out_dir or args.pdf.parent / ".work")
    print(f"[extract] {stats['pages']} pages, {stats['chars']} chars -> {stats['out_dir']}/pages.md")
    print(f"[extract] {stats['captions']} captions -> {stats['out_dir']}/captions.md")
    if stats["scanned"]:
        print("[extract] WARNING: very little text per page. The PDF is probably a scan; run OCR first.")
        return EXIT_SCANNED
    return 0


if __name__ == "__main__":
    sys.exit(main())
