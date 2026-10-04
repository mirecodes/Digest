"""Verify the viewer's pre-generated annotations (docs/viewer-plan.md §5.5).

  translation   .work/translate/pNNN.ko.md against pNNN.src.md (pages without a .ko.md are just not done yet)
  highlights    evidence-derived highlights + .work/highlights.md H blocks: verbatim on their page and anchorable
  figures       .work/figure_notes.md: one F block per figure in layout/figures.json, valid citation markers

A missing highlights.md / figure_notes.md is "not generated yet", not an error. Every check that runs follows the
same quote rules as verify.py (loose matching against .work/pages.md).

Usage (via wrapper): scripts/internal/verify_annotations.sh "<paper folder>" [--translation] [--highlights] [--figures]
Exit code: 0 = pass (warnings allowed), 1 = errors found.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf

from functions.anchor import anchor_quote
from functions.annotations import (EVIDENCE_TO_HIGHLIGHT, HIGHLIGHT_CATEGORIES, parse_evidence, parse_figure_notes,
                                   parse_highlights, parse_src, parse_translation, read)
from functions.layout import build_layout
from functions.papers import find_pdf
from functions.textmatch import find_quote_pages, load_pages, loose
from functions.verify import CALC_RE, CITE_RE, EXEMPT_TAGS, NUMBER_RE, WORK_DIR

PARTS = ("translation", "highlights", "figures")
TR_NUMBER_RE = re.compile(r"\d+\.\d+\s*%?|\d+\s*%|\d+(?:\.\d+)?\s*×")   # decimals, percentages, multipliers
REF_NUM_RE = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]")
HANGUL_RE = re.compile(r"[가-힣]")
FIG_RE = re.compile(r"\[FIG:\s*([^\]\s]+)\s*\]")
LENGTH_RATIO = (0.25, 3.0)
DENSITY = {"min": 15, "max": 40, "per_page_factor": 1.5, "per_page_max": 4}
SUMMARY_MAX_KO = 120


def _numbers(text: str, pattern: re.Pattern) -> set[str]:
    return {re.sub(r"\s+", "", m) for m in pattern.findall(text)}


def check_translation(work: Path, errors: list, warnings: list) -> dict:
    done = total = 0
    for src in sorted((work / "translate").glob("p*.src.md")):
        blocks = parse_src(src.read_text(encoding="utf-8"))
        total += len(blocks)
        ko_path = src.with_name(src.name.replace(".src.md", ".ko.md"))
        if not ko_path.is_file():
            continue
        ko = parse_translation(ko_path.read_text(encoding="utf-8"))
        name = ko_path.name
        for bid in sorted(ko.keys() - {b[0] for b in blocks}):
            errors.append(f"{name}: unknown block {bid} (not in {src.name})")
        for bid, kind, text in blocks:
            tr = ko.get(bid, "")
            if not tr:
                errors.append(f"{name}: missing translation for {bid}")
                continue
            done += 1
            if kind == "paragraph" and not HANGUL_RE.search(tr):
                warnings.append(f"{name}: {bid} has no Korean text (untranslated?)")
            missing = _numbers(text, TR_NUMBER_RE) - _numbers(tr, TR_NUMBER_RE)
            if missing:
                warnings.append(f"{name}: {bid} drops numbers {sorted(missing)}")
            missing = _numbers(text, REF_NUM_RE) - _numbers(tr, REF_NUM_RE)
            if missing:
                warnings.append(f"{name}: {bid} drops citation numbers {sorted(missing)}")
            ratio = len(tr) / max(1, len(text))
            if not LENGTH_RATIO[0] <= ratio <= LENGTH_RATIO[1]:
                warnings.append(f"{name}: {bid} length ratio {ratio:.2f} (summarized or padded?)")
    return {"done": done, "total": total}


def _anchor(doc, page: int, quote: str):
    return anchor_quote(doc[page - 1], quote) if 1 <= page <= len(doc) else None


def check_highlights(work: Path, doc, pages: dict, evidence: dict, errors: list, warnings: list) -> list[dict]:
    """Anchored highlights for the bundle: evidence-derived first, then H blocks."""
    items = []
    for eid, e in evidence.items():
        cat = EVIDENCE_TO_HIGHLIGHT.get(e["category"])
        if not cat or e["not_reported"] or not e["page"] or not e["quote"]:
            continue
        a = _anchor(doc, e["page"], e["quote"])
        if not a:
            warnings.append(f"{eid}: evidence quote could not be anchored on p.{e['page']}; left out of the viewer")
            continue
        if a["ambiguous"]:
            warnings.append(f"{eid}: quote occurs more than once on p.{e['page']}; the first match is highlighted")
        items.append({"id": eid, "source": "evidence", "category": cat, "page": e["page"], "rects": a["rects"],
                      "quote": e["quote"], "note_ko": e["note"], "note_en": None})

    md = read(work / "highlights.md")
    if md is None:
        return items
    for h in parse_highlights(md):
        hid = h["id"]
        if h["category"] not in HIGHLIGHT_CATEGORIES:
            errors.append(f"{hid}: category {h['category']!r} is not one of {', '.join(HIGHLIGHT_CATEGORIES)}")
            continue
        if h["page"] is None or not h["quote"]:
            errors.append(f"{hid}: missing 'page' or 'quote' field")
            continue
        found = find_quote_pages(h["quote"], pages)
        if h["page"] not in found:
            errors.append(f"{hid}: not on p.{h['page']}; actually on p.{found} -> fix the page" if found else
                          f"{hid}: quote not found in the source (fabricated or paraphrased?): {h['quote'][:80]!r}")
            continue
        a = _anchor(doc, h["page"], h["quote"])
        if not a:
            errors.append(f"{hid}: quote could not be anchored to PDF coordinates on p.{h['page']}")
            continue
        if a["ambiguous"]:
            warnings.append(f"{hid}: quote occurs more than once on p.{h['page']}; the first match is highlighted")
        q = loose(h["quote"])
        for item in items:
            other = loose(item["quote"])
            if item["source"] == "evidence" and item["page"] == h["page"] and (q in other or other in q):
                warnings.append(f"{hid}: duplicates evidence {item['id']} (evidence quotes are highlighted automatically)")
        items.append({"id": hid, "source": "highlight", "category": h["category"], "page": h["page"], "rects": a["rects"],
                      "quote": h["quote"], "note_ko": h["note_ko"], "note_en": h["note_en"]})

    n_pages = len(doc)
    limit = int(min(DENSITY["max"], DENSITY["per_page_factor"] * n_pages))
    low = min(DENSITY["min"], limit)  # short papers: the per-page cap wins
    if not low <= len(items) <= limit:
        warnings.append(f"highlights: {len(items)} in total; aim for {low}-{limit} for {n_pages} pages")
    per_page = {}
    for item in items:
        per_page[item["page"]] = per_page.get(item["page"], 0) + 1
    for page, n in sorted(per_page.items()):
        if n > DENSITY["per_page_max"]:
            warnings.append(f"highlights: {n} on p.{page}; at most {DENSITY['per_page_max']} per page")
    return items


def _check_note_text(label: str, text: str, evidence: dict, fig_ids: set, errors: list, warnings: list) -> None:
    for line in text.splitlines():
        cites = CITE_RE.findall(line)
        for eid, page in cites:
            if eid not in evidence:
                errors.append(f"{label}: unknown evidence {eid}")
            elif page and evidence[eid]["page"] and int(page) != evidence[eid]["page"]:
                errors.append(f"{label}: page mismatch for {eid} (text p.{page}, evidence p.{evidence[eid]['page']})")
        figs = FIG_RE.findall(line)
        for fid in figs:
            if fid not in fig_ids:
                errors.append(f"{label}: [FIG: {fid}] refers to an unknown figure")
        if NUMBER_RE.search(line) and not cites and not figs and not CALC_RE.search(line) \
                and not any(t in line for t in EXEMPT_TAGS):
            warnings.append(f"{label}: number without a marker -> {line.strip()[:90]}")


def check_figure_notes(work: Path, figures: list[dict], evidence: dict, errors: list, warnings: list) -> dict[str, dict]:
    """{figure id: note} for valid F blocks."""
    md = read(work / "figure_notes.md")
    if md is None:
        return {}
    fig_ids = {f["id"] for f in figures}
    by_fig = {}
    for n in parse_figure_notes(md):
        label = f"{n['id']} ({n['figure']})"
        if n["figure"] not in fig_ids:
            errors.append(f"{n['id']}: figure {n['figure']!r} is not in layout/figures.json")
            continue
        if n["figure"] in by_fig:
            warnings.append(f"{label}: second F block for the same figure; the first one is used")
            continue
        if n["status"] not in ("OK", "SKIP"):
            errors.append(f"{label}: status must be OK or SKIP")
            continue
        if n["status"] == "SKIP":
            if not n["reason"]:
                warnings.append(f"{label}: SKIP without a reason")
        else:
            if not n["ko"]:
                errors.append(f"{label}: status OK but no '#### ko' section")
                continue
            if not n["en"]:
                warnings.append(f"{label}: no '#### en' section")
            if not n["ko"]["summary"]:
                warnings.append(f"{label}: no '요약:' line (popover headline)")
            elif len(n["ko"]["summary"]) > SUMMARY_MAX_KO:
                warnings.append(f"{label}: Korean summary is {len(n['ko']['summary'])} chars (max {SUMMARY_MAX_KO})")
            for lang in ("ko", "en"):
                if n[lang]:
                    text = f"{n[lang]['summary']}\n{n[lang]['body_md']}"
                    _check_note_text(f"{label} {lang}", text, evidence, fig_ids, errors, warnings)
        by_fig[n["figure"]] = n
    for f in figures:
        if f["id"] not in by_fig:
            errors.append(f"{f['id']}: no F block in figure_notes.md (write status: SKIP with a reason if it cannot be explained)")
    return by_fig


def verify_annotations(paper_dir: Path, parts=PARTS) -> dict:
    """Run the selected checks; returns errors, warnings and the parsed data build_viewer bundles."""
    paper_dir = paper_dir.resolve()
    build_layout(paper_dir)
    work = paper_dir / WORK_DIR
    errors, warnings = [], []
    evidence = parse_evidence(read(work / "evidence.md") or "")
    figures = json.loads((work / "layout" / "figures.json").read_text(encoding="utf-8"))["figures"]
    result = {"errors": errors, "warnings": warnings, "evidence": evidence, "translation": None, "highlights": [],
              "notes": {}, "figures": figures}
    if "translation" in parts:
        result["translation"] = check_translation(work, errors, warnings)
    if "highlights" in parts:
        doc = pymupdf.open(find_pdf(paper_dir))
        result["highlights"] = check_highlights(work, doc, load_pages(work / "pages.md"), evidence, errors, warnings)
    if "figures" in parts:
        result["notes"] = check_figure_notes(work, figures, evidence, errors, warnings)
    result["present"] = any((work / "translate").glob("p*.ko.md")) or (work / "highlights.md").is_file() \
        or (work / "figure_notes.md").is_file()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify translations, highlights and figure notes of one paper")
    parser.add_argument("paper_dir", type=Path)
    for part in PARTS:
        parser.add_argument(f"--{part}", action="store_true", help=f"check {part} only (combinable)")
    args = parser.parse_args()
    if find_pdf(args.paper_dir.resolve()) is None or not (args.paper_dir / WORK_DIR / "pages.md").is_file():
        print(f"[verify-annotations] ERROR: need the PDF and .work/pages.md in {args.paper_dir}", file=sys.stderr)
        return 1
    parts = [p for p in PARTS if getattr(args, p)] or list(PARTS)
    r = verify_annotations(args.paper_dir, parts)
    summary = []
    if r["translation"] is not None:
        summary.append(f"translation {r['translation']['done']}/{r['translation']['total']}")
    if "highlights" in parts:
        cats = {}
        for h in r["highlights"]:
            cats[h["category"]] = cats.get(h["category"], 0) + 1
        summary.append(f"highlights {len(r['highlights'])} " + json.dumps(cats, ensure_ascii=False, sort_keys=True))
    if "figures" in parts:
        ok = sum(n["status"] == "OK" for n in r["notes"].values())
        summary.append(f"figure notes {len(r['notes'])}/{len(r['figures'])} (OK {ok}, SKIP {len(r['notes']) - ok})")
    print(f"[verify-annotations] {', '.join(summary)}")
    for w in r["warnings"]:
        print(f"  WARN  {w}")
    for e in r["errors"]:
        print(f"  ERROR {e}")
    status = "PASS" if not r["errors"] else "FAIL"
    print(f"[verify-annotations] {status} errors={len(r['errors'])} warnings={len(r['warnings'])}")
    return 0 if not r["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
