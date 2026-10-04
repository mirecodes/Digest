import { describe, expect, it } from "vitest";
import { cardItems, columnBox, ITEM_GAP, layoutCard } from "../../src/lib/cardLayout";
import type { Block, Figure, PageInfo, Rect } from "../../src/types";

const page: PageInfo = { page: 2, width: 612, height: 792, rotation: 0, columns: 2, column_split: 305, body_font_size: 9 };
const block = (id: string, kind: string, column: -1 | 0 | 1, order: number, bbox: Rect): Block =>
  ({ id, page: 2, kind, bbox, column, order, text: id, translate: true, tr: null, figure_id: null });

describe("layoutCard", () => {
  const s = 1.5;
  it("keeps the original height when there is room, pushes down when the previous item is taller", () => {
    const tops = layoutCard([
      { column: 0, y0: 100, height: 40 },
      { column: 0, y0: 120, height: 300 }, // would overlap: pushed below the first item
      { column: 0, y0: 600, height: 20 },  // room left: stays at y0 * s
    ], s);
    expect(tops[0]).toBe(150);
    expect(tops[1]).toBe(150 + 40 + ITEM_GAP);
    expect(tops[2]).toBe(900);
  });
  it("keeps tops monotonic within each column and starts spanning items below both columns", () => {
    const items = [
      { column: -1 as const, y0: 50, height: 30 },
      { column: 0 as const, y0: 100, height: 500 },
      { column: 0 as const, y0: 200, height: 100 },
      { column: 1 as const, y0: 100, height: 80 },
      { column: -1 as const, y0: 300, height: 30 },
      { column: 1 as const, y0: 500, height: 10 },
    ];
    const tops = layoutCard(items, s);
    expect(tops[2]).toBeGreaterThan(tops[1]);
    expect(tops[3]).toBe(150); // column 1 is independent of column 0
    expect(tops[4]).toBeGreaterThanOrEqual(tops[2] + 100 + ITEM_GAP); // band starts below the taller column
    expect(tops[5]).toBeGreaterThanOrEqual(tops[4] + 30 + ITEM_GAP);
  });
});

describe("cardItems", () => {
  const blocks = [
    block("p2-b0", "header_footer", -1, 0, [72, 30, 100, 40]),
    block("p2-b2", "figure_text", 0, 1, [90, 110, 200, 120]),
    block("p2-b4", "caption", 0, 2, [72, 230, 257, 243]),
    block("p2-b5", "paragraph", 0, 3, [72, 260, 294, 317]),
    block("p2-b7", "equation", 1, 4, [375, 160, 423, 171]),
  ];
  const fig: Figure = {
    id: "fig-p2-0", page: 2, kind: "figure", label: "Figure 1", bbox: [85, 100, 245, 220], caption_block: "p2-b4",
    image_url: "", confidence: 0.9, bbox_source: "auto", refs: [], note: null,
  };
  it("hides headers and figure text, places the figure before its caption, marks equations", () => {
    const items = cardItems(page, blocks, [fig]);
    expect(items.map((i) => i.key)).toEqual(["fig-p2-0", "p2-b4", "p2-b5", "p2-b7"]);
    expect(items[0].type).toBe("figure");
    expect(items[3].type).toBe("equation");
  });
  it("places a table after its caption when the caption is above", () => {
    const table = { ...fig, id: "fig-p2-1", kind: "table" as const, bbox: [72, 250, 290, 300] as Rect, caption_block: "p2-b4" };
    expect(cardItems(page, blocks, [table]).map((i) => i.key)).toEqual(["p2-b4", "fig-p2-1", "p2-b5", "p2-b7"]);
  });
});

describe("columnBox", () => {
  const blocks = [block("a", "paragraph", 0, 0, [72, 100, 296, 200]), block("b", "paragraph", 1, 1, [315, 100, 540, 200])];
  it("splits at column_split with a gutter and spans both columns for -1", () => {
    expect(columnBox(page, blocks, 0)).toEqual({ left: 72, width: 305 - 6 - 72 });
    expect(columnBox(page, blocks, 1)).toEqual({ left: 311, width: 540 - 311 });
    expect(columnBox(page, blocks, -1)).toEqual({ left: 72, width: 468 });
  });
});
