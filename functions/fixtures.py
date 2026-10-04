"""Synthetic 3-page paper "FooNet" for the self-test and the viewer end-to-end tests.

build_foonet(pdf) writes the PDF and returns ground truth (figure/table rects in PDF points,
expected block kinds, test quotes). Layout (US letter, two columns at x 72-297 / 315-540):
  p1  header "Preprint", spanning title + authors, Abstract (contribution sentence, hyphenated
      "rein-/forcement", ligature "ﬁ") in the left column, Introduction in the right column.
  p2  vector Figure 1 (boxes + arrows) and its caption in the left column; the right column cites
      "Fig. 1", reports the main result and holds the equation "L = Σt rt (1)".
  p3  spanning raster Figure 2 + caption, Table 1 (caption above a ruled 3x3 grid) in the left
      column, References [1] [2] in the right column.
Every page has the header "Preprint" and a page-number footer.

build_long(pdf, pages) writes a plain two-column paper for scroll-performance tests.
CLI (end-to-end tests): python -m functions.fixtures <out_root>   -> "Demo (2024)" and "long/Long Paper (2024)",
both prepared (pages.md, layout) as if digested.
"""
import sys
from pathlib import Path

import pymupdf

from functions.papers import target_lang

W, H = 612.0, 792.0
LEFT, RIGHT = 72.0, 315.0          # column x0
COL_W = 225.0
BODY, LEAD = 9.0, 11.0              # body font size and line spacing
LIG_FONT = "F0"                     # built-in Droid Sans Fallback: keeps "ﬁ" and "Σ" as text

HYPHEN_QUOTE = "The router is trained with reinforcement learning to select a small set of keys"
LIGATURE_QUOTE = "which gives a fine control over the memory budget"
CONTRIBUTION_QUOTE = "We propose FooNet, a sparse attention model for long inputs."
PROBLEM_QUOTE = "Existing methods scale quadratically with sequence length, which limits long-context modeling."
RESULT_QUOTE = "FooNet achieves 61.4 average accuracy, compared to 54.4 for the Transformer baseline."
REPEATED_QUOTE = "memory stays linear"   # appears twice on p1 -> ambiguous anchor

P1_LEFT = ("We propose FooNet, a sparse attention model for long inputs. Existing methods scale quadratically "
           "with sequence length, which limits long-context modeling. In FooNet the memory stays linear in the "
           "input length at all times.")
P1_LEFT_2 = [  # explicit lines: hyphenated word across a line break, then a ligature
    ("The router is trained with rein-", "helv"),
    ("forcement learning to select a small set of keys,", "helv"),
    ("which gives a \ufb01ne control over the memory budget.", LIG_FONT),
]
P1_RIGHT = ("Long documents, genomes and audio need models that read thousands of tokens at once. Dense attention "
            "compares every token with every other token, so its cost grows with the square of the input length "
            "and soon exceeds the memory of a single accelerator. We keep the useful part of attention and drop "
            "the rest, and in our design the memory stays linear.")
P1_RIGHT_2 = ("Our experiments cover text, images and byte-level inputs and compare FooNet with dense and sparse "
              "baselines under the same training budget and the same number of parameters.")
P2_LEFT = ("The encoder maps tokens to vectors and the router picks the keys that each query may attend to during "
           "the forward pass. The output head mixes the selected values into one vector and passes it on to the "
           "next layer of the network.")
P2_RIGHT = ("As shown in Fig. 1, the router feeds the sparse attention block and the output head. On LRA, FooNet "
            "achieves 61.4 average accuracy, compared to 54.4 for the Transformer baseline. The training "
            "objective sums the rewards of the router over time.")
P2_RIGHT_2 = "Here r_t is the reward at step t and L is the total objective that the router maximizes in training."
P3_LEFT = ("Table 1 shows that removing the router lowers the accuracy of the model by a clear margin while the "
           "memory use stays exactly the same. This confirms that the learned sparsity pattern is what matters "
           "most for the final accuracy of the model.")
TABLE = [["Variant", "Acc", "Mem"], ["FooNet", "61.4", "1.0"], ["No router", "57.2", "1.0"]]


def _wrap(text: str, size=BODY, width=COL_W) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if cur and pymupdf.get_text_length(cand, "helv", size) > width:
            lines.append(cur)
            cand = word
        cur = cand
    return lines + [cur]


def _lines(page, x, y, lines, font="helv", size=BODY):
    """Insert a wrapped paragraph (str) or explicit lines at baseline y; returns the next baseline."""
    for line in _wrap(lines, size) if isinstance(lines, str) else lines:
        text, f = line if isinstance(line, tuple) else (line, font)
        page.insert_text((x, y), text, fontname=f, fontsize=size)
        y += LEAD
    return y


def _frame(page, n):
    page.insert_text((LEFT, 40), "Preprint", fontname="helv", fontsize=8)
    page.insert_text((W / 2 - 3, 765), str(n), fontname="helv", fontsize=8)


def _arrow(page, a, b):
    page.draw_line(a, b, width=1)
    page.draw_polyline([(b[0] - 4, b[1] - 3), b, (b[0] - 4, b[1] + 3)], width=1)


def _raster() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 234, 80), False)
    for x in range(234):
        for y in range(80):
            pix.set_pixel(x, y, ((x * 7) % 256, (y * 3) % 256, 160))
    return pix.tobytes("png")


def build_foonet(pdf: Path) -> dict:
    """Write the FooNet PDF to `pdf` and return its ground truth."""
    doc = pymupdf.open()
    lig_font = pymupdf.Font("cjk").buffer

    # ---- page 1
    p = doc.new_page(width=W, height=H)
    p.insert_font(fontname=LIG_FONT, fontbuffer=lig_font)
    _frame(p, 1)
    p.insert_text((120, 90), "FooNet: Sparse Attention for Long Sequences", fontname="hebo", fontsize=18)
    p.insert_text((200, 112), "Alice Kim and Bob Lee, Example University", fontname="helv", fontsize=BODY)
    p.insert_text((LEFT, 150), "Abstract", fontname="hebo", fontsize=10)
    y = _lines(p, LEFT, 166, P1_LEFT)
    _lines(p, LEFT, y + 10, P1_LEFT_2)
    p.insert_text((RIGHT, 150), "1 Introduction", fontname="hebo", fontsize=10)
    y = _lines(p, RIGHT, 166, P1_RIGHT)
    _lines(p, RIGHT, y + 10, P1_RIGHT_2)

    # ---- page 2
    p = doc.new_page(width=W, height=H)
    p.insert_font(fontname=LIG_FONT, fontbuffer=lig_font)
    _frame(p, 2)
    boxes = [pymupdf.Rect(85, 100, 150, 140), pymupdf.Rect(180, 100, 245, 140), pymupdf.Rect(130, 180, 200, 220)]
    for r, label in zip(boxes, ("Enc", "Attn", "Out")):
        p.draw_rect(r, width=1)
        p.insert_text((r.x0 + 8, r.y0 + 24), label, fontname="helv", fontsize=7)
    _arrow(p, (150, 120), (180, 120))
    _arrow(p, (212, 140), (180, 180))
    fig1 = pymupdf.Rect(boxes[0]) | boxes[1] | boxes[2]
    p.insert_text((LEFT, 240), "Figure 1: Overview of the FooNet architecture.", fontname="helv", fontsize=BODY)
    _lines(p, LEFT, 270, P2_LEFT)
    y = _lines(p, RIGHT, 100, P2_RIGHT)
    p.insert_text((RIGHT + 60, y + 14), "L = Σt rt   (1)", fontname=LIG_FONT, fontsize=BODY)
    _lines(p, RIGHT, y + 40, P2_RIGHT_2)

    # ---- page 3
    p = doc.new_page(width=W, height=H)
    _frame(p, 3)
    fig2 = pymupdf.Rect(LEFT, 70, 540, 230)
    p.insert_image(fig2, stream=_raster(), keep_proportion=False)
    p.insert_text((150, 246), "Figure 2: Attention patterns of FooNet on a long input sequence.", fontname="helv", fontsize=BODY)
    p.insert_text((LEFT, 280), "Table 1: Ablation of the router.", fontname="helv", fontsize=BODY)
    table = pymupdf.Rect(LEFT, 290, 290, 350)
    rows, cols = len(TABLE), len(TABLE[0])
    for i in range(rows + 1):
        yy = table.y0 + i * table.height / rows
        p.draw_line((table.x0, yy), (table.x1, yy), width=0.5)
    for j in range(cols + 1):
        xx = table.x0 + j * table.width / cols
        p.draw_line((xx, table.y0), (xx, table.y1), width=0.5)
    for i, row in enumerate(TABLE):
        for j, cell in enumerate(row):
            p.insert_text((table.x0 + j * table.width / cols + 4, table.y0 + i * table.height / rows + 13),
                          cell, fontname="helv", fontsize=8)
    _lines(p, LEFT, 380, P3_LEFT)
    p.insert_text((RIGHT, 280), "References", fontname="hebo", fontsize=10)
    _lines(p, RIGHT, 298, ["[1] A. Vaswani et al. Attention is all you need.", "In NeurIPS, 2017."], size=8)
    _lines(p, RIGHT, 330, ["[2] I. Beltagy et al. Longformer: the long-document", "transformer. arXiv, 2020."], size=8)

    pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.save(pdf)
    return {
        "pdf": pdf,
        "pages": 3,
        "columns": {1: 2, 2: 2, 3: 2},
        "figures": {"Figure 1": (2, tuple(fig1)), "Figure 2": (3, tuple(fig2)), "Table 1": (3, tuple(table))},
        # first-line prefix of a block -> expected kind
        "kinds": {
            "Preprint": "header_footer", "Abstract": "heading", "1 Introduction": "heading",
            "Figure 1:": "caption", "Figure 2:": "caption", "Table 1:": "caption",
            "L = ": "equation", "References": "heading", "[1]": "reference", "[2]": "reference",
            "We propose FooNet": "paragraph", "As shown in Fig. 1": "paragraph",
        },
        "quotes": {
            "hyphen": (1, HYPHEN_QUOTE), "ligature": (1, LIGATURE_QUOTE), "contribution": (1, CONTRIBUTION_QUOTE),
            "problem": (1, PROBLEM_QUOTE), "result": (2, RESULT_QUOTE), "repeated": (1, REPEATED_QUOTE),
        },
    }


def build_long(pdf: Path, pages: int = 50) -> None:
    """A text-dense two-column paper with a numbered heading per page and a vector figure every fifth page."""
    doc = pymupdf.open()
    paragraph = " ".join([P1_RIGHT, P2_LEFT, P3_LEFT])
    for n in range(1, pages + 1):
        p = doc.new_page(width=W, height=H)
        _frame(p, n)
        p.insert_text((LEFT, 80), f"{n} Section {n}", fontname="hebo", fontsize=10)
        top = 100
        if n % 5 == 0:
            p.draw_rect(pymupdf.Rect(LEFT, 100, LEFT + COL_W, 220), width=1)
            p.insert_text((LEFT, 236), f"Figure {n // 5}: Synthetic figure on page {n}.", fontname="helv", fontsize=BODY)
            top = 260
        lines = _wrap(paragraph)
        for x, y in ((LEFT, top), (RIGHT, 100)):
            i = 0
            while y < 730:
                _lines(p, x, y, [lines[i % len(lines)]])
                y, i = y + LEAD + (10 if i % 12 == 11 else 0), i + 1   # a paragraph break every 12 lines
    pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.save(pdf)


# --------------------------------------------------------------------------- #
# Digest outputs and viewer annotations for FooNet (test data for selftest, the golden bundle and e2e).
# Block ids come from the deterministic layout of build_foonet().
# --------------------------------------------------------------------------- #
EVIDENCE = f"""### E1
- category: problem
- page: 1
- loc: Abstract
- quote: "{PROBLEM_QUOTE}"
- note: 기존 방법의 이차 복잡도 문제

### E2
- category: result
- page: 2
- loc: Sec 2
- quote: "{RESULT_QUOTE}"
- note: LRA 주요 결과

### E3
- category: contribution
- page: 1
- loc: Abstract
- quote: "{CONTRIBUTION_QUOTE}"
- note: 핵심 기여

### E4
- category: method
- page: 1
- loc: Abstract
- quote: "{HYPHEN_QUOTE}"
- note: 강화학습으로 학습되는 라우터

### E5
- category: cost
- status: NOT_REPORTED
- note: 학습 비용은 보고되지 않음
"""

REPORT_HEADER = """# FooNet: Sparse Attention for Long Sequences

> Alice Kim, Bob Lee · Preprint, 2024 [E3, p.1]
> Generated: 2026-10-04 · verify: PASS
"""

TRANSLATION = {
    1: {
        "p1-b2": "FooNet: 긴 시퀀스를 위한 희소 어텐션 (FooNet: Sparse Attention for Long Sequences)",
        "p1-b3": "Alice Kim, Bob Lee (Example 대학교)",
        "p1-b4": "초록 (Abstract)",
        "p1-b5": "우리는 긴 입력을 위한 희소 어텐션(sparse attention) 모델인 FooNet을 제안한다. 기존 방법은 시퀀스 길이에 대해 "
                 "계산량이 이차적으로 늘어나 긴 문맥 모델링이 제한된다. FooNet에서는 메모리가 항상 입력 길이에 선형으로 유지된다.",
        "p1-b6": "라우터는 강화학습(reinforcement learning)으로 학습되어 작은 키 집합을 선택하며, 이를 통해 메모리 예산을 세밀하게 제어할 수 있다.",
        "p1-b7": "1 서론 (Introduction)",
        "p1-b8": "긴 문서, 유전체, 오디오는 수천 개의 토큰을 한 번에 읽는 모델을 필요로 한다. 밀집 어텐션은 모든 토큰을 다른 모든 토큰과 "
                 "비교하므로 비용이 입력 길이의 제곱으로 증가하고, 곧 단일 가속기의 메모리를 넘어선다. 우리는 어텐션의 유용한 부분은 "
                 "유지하고 나머지는 버리며, 우리 설계에서 메모리는 선형으로 유지된다.",
        "p1-b9": "실험은 텍스트, 이미지, 바이트 수준 입력을 다루며, 같은 학습 예산과 같은 파라미터 수에서 FooNet을 밀집 및 희소 기준 모델과 비교한다.",
    },
    2: {
        "p2-b4": "그림 1: FooNet 구조 개요.",
        "p2-b5": "인코더는 토큰을 벡터로 변환하고, 라우터는 순전파 동안 각 쿼리가 주목할 수 있는 키를 고른다. 출력 헤드는 선택된 값을 "
                 "하나의 벡터로 섞어 네트워크의 다음 층으로 전달한다.",
        "p2-b6": "그림 1에서 보듯이 라우터는 희소 어텐션 블록과 출력 헤드에 입력을 공급한다. LRA에서 FooNet은 평균 정확도 61.4를 달성하며, "
                 "Transformer 기준 모델은 54.4이다. 학습 목표는 시간에 따른 라우터의 보상을 합산한다.",
        "p2-b8": "여기서 r_t는 단계 t의 보상이고 L은 학습 중 라우터가 최대화하는 전체 목표이다.",
    },
    3: {
        "p3-b2": "그림 2: 긴 입력 시퀀스에서 FooNet의 어텐션 패턴.",
        "p3-b3": "표 1: 라우터 제거 실험(ablation).",
        "p3-b7": "표 1은 라우터를 제거하면 메모리 사용량은 그대로인 채 모델 정확도가 뚜렷하게 떨어짐을 보여준다. 이는 학습된 희소성 "
                 "패턴이 최종 정확도에 가장 중요하다는 것을 확인해 준다.",
        "p3-b8": "참고문헌 (References)",
    },
}

HIGHLIGHTS = f"""### H1
- category: problem
- page: 1
- quote: "{PROBLEM_QUOTE}"
- note_ko: 풀려는 문제: 기존 방법은 입력 길이에 대해 이차 복잡도라 긴 문맥을 다루기 어렵다
- note_en: Problem: existing methods are quadratic in length, which limits long contexts

### H2
- category: prior_work
- page: 1
- quote: "Dense attention compares every token with every other token"
- note_ko: 기존 방법의 한계: dense attention은 모든 토큰 쌍을 비교한다
- note_en: Prior work: dense attention compares every pair of tokens

### H3
- category: contribution
- page: 1
- quote: "{CONTRIBUTION_QUOTE}"
- note_ko: 기여: 긴 입력을 위한 sparse attention 모델 FooNet
- note_en: Contribution: FooNet, a sparse attention model for long inputs

### H4
- category: assumption
- page: 1
- quote: "We keep the useful part of attention and drop the rest"
- note_ko: 핵심 가정: attention의 일부만 유용하고 나머지는 버려도 된다
- note_en: Key assumption: only part of attention is useful

### H5
- category: method
- page: 1
- quote: "{HYPHEN_QUOTE}"
- note_ko: 핵심 방법: 강화학습으로 학습한 router가 소수의 key를 고른다
- note_en: Core method: an RL-trained router selects a few keys

### H6
- category: method
- page: 2
- quote: "the router feeds the sparse attention block and the output head"
- note_ko: 구조: router → sparse attention → output head
- note_en: Architecture: router, then sparse attention, then the output head

### H7
- category: result
- page: 2
- quote: "{RESULT_QUOTE}"
- note_ko: 주요 결과: LRA 평균 61.4로 Transformer(54.4)보다 높다
- note_en: Main result: 61.4 on LRA vs 54.4 for the Transformer

### H8
- category: result
- page: 3
- quote: "removing the router lowers the accuracy of the model by a clear margin"
- note_ko: ablation: router를 빼면 정확도가 떨어진다
- note_en: Ablation: removing the router lowers accuracy

### H9
- category: insight
- page: 3
- quote: "This confirms that the learned sparsity pattern is what matters most for the final accuracy of the model."
- note_ko: 핵심 통찰: 정확도를 좌우하는 것은 학습된 sparsity 패턴이다
- note_en: Insight: the learned sparsity pattern drives accuracy
"""

FIGURE_NOTES = """### F1
- figure: fig-p2-0
- status: OK
#### ko
요약: 인코더 → 어텐션 → 출력으로 이어지는 FooNet 구조 개요도.
읽는 법: 상자는 모듈, 화살표는 데이터 흐름이다.
- LRA 평균 정확도는 61.4이다 [E2, p.2]
- 라우터가 어텐션 앞에 놓인 점이 그림의 요지로 보인다 [INTERP]
본문 연결: C1의 구조적 근거.
#### en
Summary: Overview of FooNet: encoder → attention → output.
How to read: boxes are modules, arrows show the data flow.
- Average LRA accuracy is 61.4 [E2, p.2]
- The router sitting before attention seems to be the point of the figure [INTERP]
Link to text: structural basis for C1.

### F2
- figure: fig-p3-0
- status: OK
#### ko
요약: 긴 입력에서의 어텐션 패턴을 색으로 보여준다.
- 밝은 영역의 가중치가 약 0.8로 보인다 [FIG: fig-p3-0]
#### en
Summary: Attention patterns on a long input, shown as colors.
- Bright regions appear to weigh about 0.8 [FIG: fig-p3-0]

### F3
- figure: fig-p3-1
- status: SKIP
- reason: the table is fully explained by the text on the same page
"""


def write_digest(paper: Path) -> None:
    """evidence.md and a report header, as /paper-digest would leave them."""
    (paper / ".work" / "evidence.md").write_text(EVIDENCE, encoding="utf-8")
    (paper / f"{paper.name} - report.md").write_text(REPORT_HEADER, encoding="utf-8")


def write_annotations(paper: Path, variant: str = "good") -> None:
    """Translations, highlights and figure notes as /paper-annotate would write them. "bad" plants one defect
    per check: a missing and an unknown block id, a dropped number, an unanchorable H quote, a bad category,
    an unknown figure, an unknown evidence id and an unknown [FIG] id."""
    work = paper / ".work"
    pages = {p: dict(blocks) for p, blocks in TRANSLATION.items()}
    highlights, notes = HIGHLIGHTS, FIGURE_NOTES
    if variant == "bad":
        del pages[2]["p2-b5"]
        pages[2]["p9-b9"] = "없는 블록"
        pages[2]["p2-b6"] = pages[2]["p2-b6"].replace("61.4", "육십일 점 사")
        highlights += ('\n### H98\n- category: result\n- page: 1\n- quote: "FooNet is the best model ever built by anyone"\n'
                       '\n### H99\n- category: novelty\n- page: 1\n- quote: "We propose FooNet"\n')
        notes = notes.replace("[E2, p.2]", "[E9, p.2]").replace("[FIG: fig-p3-0]", "[FIG: fig-nope]")
        notes += "\n### F4\n- figure: fig-p9-0\n- status: SKIP\n- reason: does not exist\n"
    # The fixture text is Korean; files and section names follow target_lang so the checks run under any config.
    lang = target_lang()
    for page, blocks in pages.items():
        body = "".join(f"<!-- BLOCK {bid} -->\n{text}\n\n" for bid, text in blocks.items())
        (work / "translate" / f"p{page:03d}.{lang}.md").write_text(body, encoding="utf-8")
    (work / "highlights.md").write_text(highlights.replace("- note_ko:", f"- note_{lang}:"), encoding="utf-8")
    (work / "figure_notes.md").write_text(notes.replace("#### ko", f"#### {lang}"), encoding="utf-8")


def prepare_demo(folder: Path, annotated: bool = True) -> Path:
    """A digested FooNet paper folder (PDF, pages.md, layout, evidence, report header, optional annotations)."""
    from functions.extract_pdf import extract
    from functions.layout import build_layout

    pdf = folder / f"{folder.name}.pdf"
    build_foonet(pdf)
    extract(pdf, folder / ".work")
    build_layout(folder, force=True)
    write_digest(folder)
    if annotated:
        write_annotations(folder)
    return folder


def prepare_e2e(root: Path, src: Path | None = None) -> None:
    """Papers for the viewer end-to-end tests: annotated FooNet and a long paper under root; with src, also a src/
    folder holding a new paper (inbox/fresh.pdf) and a copy of the FooNet PDF (dup.pdf, must not show up as new)."""
    import shutil

    from functions.extract_pdf import extract
    from functions.layout import build_layout

    demo = prepare_demo(root / "Demo (2024)")
    folder = root / "long" / "Long Paper (2024)"
    build_long(folder / f"{folder.name}.pdf")
    extract(folder / f"{folder.name}.pdf", folder / ".work")
    build_layout(folder, force=True)
    if src:
        (src / "inbox").mkdir(parents=True, exist_ok=True)
        build_long(src / "inbox" / "fresh.pdf", pages=4)
        shutil.copy2(demo / f"{demo.name}.pdf", src / "dup.pdf")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: python -m functions.fixtures <out_root> [<src_dir>]")
    prepare_e2e(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) == 3 else None)
