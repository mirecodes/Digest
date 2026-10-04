"""Quote matching shared by the citation verifier and the viewer (anchoring, annotation checks).

All matching runs on loose() text, so line breaks, hyphenation, spacing and symbols do not matter.
"""
import re
import unicodedata
from pathlib import Path

PAGE_RE = re.compile(r"<!-- PAGE (\d+) -->(.*?)(?=<!-- PAGE \d+ -->|\Z)", re.S)


def loose(s: str) -> str:
    """Normalize text so line breaks, hyphenation, spacing and symbols do not affect matching."""
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", s)


def load_pages(path: Path) -> dict[int, str]:
    """pages.md -> {page number: loose page text}."""
    raw = path.read_text(encoding="utf-8")
    return {int(m.group(1)): loose(m.group(2)) for m in PAGE_RE.finditer(raw)}


def find_quote_pages(quote: str, pages: dict[int, str]) -> list[int]:
    """Pages (ascending) whose loose text contains the loose quote; [] for an empty quote."""
    q = loose(quote)
    return sorted(p for p, text in pages.items() if q and q in text)
