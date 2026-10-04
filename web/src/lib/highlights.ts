// Highlight helpers: visibility filter, bounding box, and the block each highlight falls in (for the 3px bars in the
// translation pane, §8.6 — block level, not sentence level).
import type { Block, Category, Highlight, Rect } from "../types";

export const CATEGORIES: Category[] = [
  "problem", "assumption", "prior_work", "contribution", "method", "result", "insight", "limitation",
];

export const visible = (hls: Highlight[], show: boolean, hidden: Category[]) =>
  show ? hls.filter((h) => !hidden.includes(h.category)) : [];

export function union(rects: Rect[]): Rect {
  return [
    Math.min(...rects.map((r) => r[0])), Math.min(...rects.map((r) => r[1])),
    Math.max(...rects.map((r) => r[2])), Math.max(...rects.map((r) => r[3])),
  ];
}

/** Block id -> category of the first highlight whose rect centres fall inside it (smallest containing block). */
export function categoryByBlock(hls: Highlight[], blocks: Block[]): Map<string, Category> {
  const out = new Map<string, Category>();
  for (const h of hls) {
    for (const [x0, y0, x1, y1] of h.rects) {
      const cx = (x0 + x1) / 2;
      const cy = (y0 + y1) / 2;
      let best: Block | null = null;
      for (const b of blocks) {
        const [a, c, d, e] = b.bbox;
        if (b.page === h.page && b.kind !== "header_footer" && cx >= a && cx <= d && cy >= c && cy <= e &&
            (!best || (d - a) * (e - c) < (best.bbox[2] - best.bbox[0]) * (best.bbox[3] - best.bbox[1]))) best = b;
      }
      if (best && !out.has(best.id)) out.set(best.id, h.category);
    }
  }
  return out;
}
