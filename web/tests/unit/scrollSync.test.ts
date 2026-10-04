import { describe, expect, it } from "vitest";
import { followerScrollTop, mapRef, pageAt, refPage, type PaneLayout } from "../../src/lib/scrollSync";
import { stackTops } from "../../src/lib/coords";

const pane = (heights: number[]): PaneLayout => ({ tops: stackTops(heights), heights, gap: 16 });
const A = pane([800, 800, 1200, 600, 800]);
const B = pane([700, 1100, 900, 650, 1400]); // translation cards: different heights per page

describe("pageAt", () => {
  it("finds the page whose span (page + gap) contains y and clamps", () => {
    expect(pageAt(-50, A)).toBe(0);
    expect(pageAt(A.tops[2] + 10, A)).toBe(2);
    expect(pageAt(A.tops[2] - 1, A)).toBe(1); // inside the gap after page 2
    expect(pageAt(1e9, A)).toBe(4);
  });
});

describe("mapRef", () => {
  it("maps page tops to page tops and keeps the relative position", () => {
    for (let i = 0; i < 5; i++) expect(mapRef(A.tops[i], A, B)).toBeCloseTo(B.tops[i]);
    const mid = A.tops[2] + (A.heights[2] + A.gap) / 2;
    expect(mapRef(mid, A, B)).toBeCloseTo(B.tops[2] + (B.heights[2] + B.gap) / 2);
  });

  it("is its own inverse within 1px everywhere, including before the first and after the last page", () => {
    const end = A.tops[4] + A.heights[4] + 200;
    for (let y = -40; y < end; y += 7.3) {
      expect(Math.abs(mapRef(mapRef(y, A, B), B, A) - y)).toBeLessThan(1);
    }
  });

  it("returns y unchanged for empty layouts", () => {
    expect(mapRef(123, { tops: [], heights: [], gap: 16 }, B)).toBe(123);
  });
});

describe("followerScrollTop", () => {
  const box = (scrollTop: number, scrollHeight: number) => ({ scrollTop, clientHeight: 900, scrollHeight });
  const hA = A.tops[4] + A.heights[4] + 16;
  const hB = B.tops[4] + B.heights[4] + 16;
  it("pins the top and the bottom", () => {
    expect(followerScrollTop(box(0, hA), box(500, hB), A, B)).toBe(0);
    expect(followerScrollTop(box(hA - 900, hA), box(0, hB), A, B)).toBe(hB - 900);
  });
  it("aligns both reference lines on the same page position", () => {
    const top = A.tops[2] - 0.3 * 900; // page 3 top on the driver's reference line
    expect(followerScrollTop(box(top, hA), box(0, hB), A, B)).toBeCloseTo(B.tops[2] - 0.3 * 900);
    expect(refPage(box(top, hA), A)).toBe(3);
  });
});
