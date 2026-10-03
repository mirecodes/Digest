"""Derive a human-readable paper name "Short Title (Year)" from a PDF.

Ported from the standalone rename-paper tool (Zotero / Better BibTeX style naming).
Long titles keep the first `title_words` non-stopwords (configs/cfg.yaml).

Metadata lookup order:
  1) arXiv ID (filename, then PDF text) -> arXiv API
  2) DOI (filename, PDF metadata, then text) -> Crossref API
  3) Embedded PDF metadata (title / creationDate)
  4) Otherwise the original file name is kept

Used by functions/prepare.py; preview a name with `scripts/internal/prepare.sh --dry-run [-n NAME]`.
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import certifi
import pymupdf

STOPWORDS = set(
    "a an the of in on at to for from by with and or but is are was were be as via into onto "
    "using towards toward than that this these those its it vs".split())
DEFAULT_TITLE_WORDS = 5
PAGES_TO_SCAN = 2        # leading pages scanned for IDs/DOIs
ARXIV_DELAY = 3.0        # arXiv API recommended gap (s)
TIMEOUT = 20
USER_AGENT = "paper-digest/1.0"
# python.org macOS builds ship no CA bundle, so use certifi's.
SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# new: 2301.12345v2 / old: hep-th/9901001, math.AG/0601001
ARXIV_NEW = r"(?<![\d.])(\d{4}\.\d{4,5})(?:v\d+)?(?![\d])"
ARXIV_OLD = r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?"
ARXIV_TEXT_RE = re.compile(r"arXiv:\s*(?:" + ARXIV_NEW + r"|" + ARXIV_OLD + r")", re.I)
ARXIV_NAME_RE = re.compile(
    r"^(?:arxiv[_\-.: ]?)?(?:" + ARXIV_NEW + r"|" + ARXIV_OLD.replace("/", "[/_]") + r")", re.I)
ARXIV_DOI_RE = re.compile(r"10\.48550/arxiv\.(.+)", re.I)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)


@dataclass
class Meta:
    title: str = ""
    year: str = ""
    source: str = "none"


# --------------------------------------------------------------------------- #
# Metadata sources
# --------------------------------------------------------------------------- #
_last_arxiv_call = 0.0


def http_get(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as r:
            return r.read()
    except Exception as e:  # network failure: fall through to the next source
        print(f"[name] request failed: {url} ({e})", file=sys.stderr)
        return None


def fetch_arxiv(arxiv_id: str) -> Meta | None:
    global _last_arxiv_call
    wait = ARXIV_DELAY - (time.time() - _last_arxiv_call)
    if wait > 0:
        time.sleep(wait)
    _last_arxiv_call = time.time()

    data = http_get("https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(arxiv_id))
    if not data:
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = ET.fromstring(data).find("a:entry", ns)
    if entry is None:
        return None
    title = (entry.findtext("a:title", "", ns) or "").strip()
    if not title or title.lower() == "error":
        return None
    published = entry.findtext("a:published", "", ns) or ""
    return Meta(title=title, year=published[:4], source=f"arXiv:{arxiv_id}")


def fetch_crossref(doi: str) -> Meta | None:
    data = http_get("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/"))
    if not data:
        return None
    try:
        msg = json.loads(data)["message"]
    except (ValueError, KeyError):
        return None
    title = (msg.get("title") or [""])[0]
    subtitle = msg.get("subtitle") or [""]
    if subtitle and subtitle[0]:
        title = f"{title}: {subtitle[0]}"
    year = ""
    for key in ("issued", "published-print", "published-online", "created"):
        parts = (msg.get(key) or {}).get("date-parts") or [[None]]
        if parts[0] and parts[0][0]:
            year = str(parts[0][0])
            break
    return Meta(title=title, year=year, source=f"DOI:{doi}")


def read_pdf(path: Path) -> tuple[str, dict]:
    """Return (text of the first pages, PDF metadata dict)."""
    try:
        with pymupdf.open(path) as doc:
            text = "\n".join(doc[i].get_text() for i in range(min(PAGES_TO_SCAN, len(doc))))
            return text, dict(doc.metadata or {})
    except Exception as e:
        print(f"[name] PDF read failed: {e}", file=sys.stderr)
        return "", {}


def clean_doi(doi: str) -> str:
    return doi.rstrip(".,;)]}").strip()


def find_arxiv_id(stem: str, text: str, doi: str | None) -> str | None:
    m = ARXIV_NAME_RE.search(stem)
    if m:
        return (m.group(1) or m.group(2)).replace("_", "/")
    if doi:
        m = ARXIV_DOI_RE.match(doi)
        if m:
            return re.sub(r"v\d+$", "", m.group(1))
    m = ARXIV_TEXT_RE.search(text)
    if m:
        return m.group(1) or m.group(2)
    return None


def find_doi(stem: str, text: str, info: dict) -> str | None:
    # File names cannot contain '/', so DOIs in names may use '_'.
    m = DOI_RE.search(stem.replace("_", "/", 1)) if stem.startswith("10.") else None
    if m:
        return clean_doi(m.group(1))
    for key in ("subject", "keywords"):
        m = DOI_RE.search(info.get(key) or "")
        if m:
            return clean_doi(m.group(1))
    m = DOI_RE.search(text)
    return clean_doi(m.group(1)) if m else None


def meta_from_pdf_info(info: dict) -> Meta | None:
    title = (info.get("title") or "").strip()
    # Skip junk titles like "Microsoft Word - x.docx" or "untitled".
    if not title or re.search(r"(\.docx?|\.tex|\.dvi|untitled|^Microsoft Word)", title, re.I):
        return None
    m = re.match(r"D:(\d{4})", info.get("creationDate") or "")
    return Meta(title=title, year=m.group(1) if m else "", source="PDF metadata")


def resolve(path: Path, offline: bool = False) -> Meta:
    text, info = read_pdf(path)
    doi = find_doi(path.stem, text, info)
    arxiv_id = find_arxiv_id(path.stem, text, doi)
    if not offline:
        if arxiv_id:
            m = fetch_arxiv(arxiv_id)
            if m:
                return m
        if doi and not ARXIV_DOI_RE.match(doi):
            m = fetch_crossref(doi)
            if m and m.title:
                return m
    return meta_from_pdf_info(info) or Meta()


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
def valid_filename(name: str) -> str:
    """Sanitize like Zotero.File.getValidFileName."""
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r'[\\/?*:|"<>]', "", name)
    name = re.sub(r"[\r\n\t]+", " ", name)
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name.lstrip(".")


def short_title(title: str, title_words: int = DEFAULT_TITLE_WORDS) -> str:
    """Long titles keep the first `title_words` non-stopwords (like BBT shorttitle)."""
    words = title.split()
    if len(words) <= title_words:
        return title
    kept = [w for w in words if w.lower().strip(",.:;()") not in STOPWORDS]
    return " ".join(kept[:title_words])


def format_name(meta: Meta, title_words: int = DEFAULT_TITLE_WORDS) -> str:
    title = short_title(re.sub(r"\s+", " ", meta.title).strip(), title_words)
    return valid_filename(f"{title} ({meta.year})" if meta.year else title)


def paper_name(pdf: Path, title_words: int = DEFAULT_TITLE_WORDS, offline: bool = False) -> tuple[str, str]:
    """Return (name, metadata source). Falls back to the file stem when no title is found."""
    meta = resolve(pdf, offline)
    name = format_name(meta, title_words) if meta.title else ""
    return (name or pdf.stem), meta.source
