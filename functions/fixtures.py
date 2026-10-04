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
"""
from pathlib import Path

import pymupdf

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
