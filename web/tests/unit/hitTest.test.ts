import { describe, expect, it } from "vitest";
import { hitTest } from "../../src/lib/hitTest";
import type { Rect } from "../../src/types";

describe("hitTest", () => {
  const figures = [{ id: "fig-p2-0", bbox: [80, 100, 250, 220] as Rect }];
  const highlights = [{ id: "E3", rects: [[60, 300, 290, 311], [60, 312, 200, 323]] as Rect[] }];
  const blocks = [
    { id: "big", bbox: [50, 50, 300, 400] as Rect, kind: "paragraph" },
    { id: "small", bbox: [60, 290, 295, 330] as Rect, kind: "paragraph" },
    { id: "hf", bbox: [0, 0, 612, 40] as Rect, kind: "header_footer" },
  ];
  const layers = { figures, highlights, blocks };

  it("prefers figure > highlight > block", () => {
    expect(hitTest(100, 150, layers)).toEqual({ type: "figure", id: "fig-p2-0" });
    expect(hitTest(100, 305, layers)).toEqual({ type: "highlight", id: "E3" });
    expect(hitTest(250, 320, layers)).toEqual({ type: "block", id: "small" });
  });
  it("picks the smallest overlapping block and skips headers/footers", () => {
    expect(hitTest(70, 295, { blocks })).toEqual({ type: "block", id: "small" });
    expect(hitTest(70, 60, { blocks })).toEqual({ type: "block", id: "big" });
    expect(hitTest(10, 10, { blocks })).toBeNull();
  });
});
