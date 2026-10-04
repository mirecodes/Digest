import { describe, expect, it } from "vitest";
import { clientToPt, ptToClient, rectStyle, stackTops } from "../../src/lib/coords";

describe("coords", () => {
  const page = { left: 120, top: -300 } as DOMRect;
  it("round-trips pt <-> client px", () => {
    for (const scale of [0.5, 1, 1.37, 3]) {
      const [cx, cy] = ptToClient(72.5, 410.25, page, scale);
      const [x, y] = clientToPt(cx, cy, page, scale);
      expect(x).toBeCloseTo(72.5);
      expect(y).toBeCloseTo(410.25);
    }
  });
  it("converts rects to css boxes", () => {
    expect(rectStyle([10, 20, 110, 70], 2)).toEqual({ left: 20, top: 40, width: 200, height: 100 });
  });
  it("stacks pages with padding and gaps", () => {
    expect(stackTops([100, 200, 50], 16, 16)).toEqual([16, 132, 348]);
  });
});
