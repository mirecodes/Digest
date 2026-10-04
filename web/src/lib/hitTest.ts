// Hover hit-testing in page points instead of overlay elements, so the text layer stays selectable (§8.2).
import type { Rect } from "../types";

export type Hit = { type: "figure" | "highlight" | "block"; id: string } | null;

type Layers = {
  figures?: { id: string; bbox: Rect }[];
  highlights?: { id: string; rects: Rect[] }[];
  blocks?: { id: string; bbox: Rect; kind?: string }[];
};

const inside = (x: number, y: number, r: Rect) => x >= r[0] && x <= r[2] && y >= r[1] && y <= r[3];
const area = (r: Rect) => (r[2] - r[0]) * (r[3] - r[1]);

/** Priority figure > highlight > block; among overlapping blocks the smallest wins. */
export function hitTest(x: number, y: number, layers: Layers): Hit {
  const fig = layers.figures?.find((f) => inside(x, y, f.bbox));
  if (fig) return { type: "figure", id: fig.id };
  const hl = layers.highlights?.find((h) => h.rects.some((r) => inside(x, y, r)));
  if (hl) return { type: "highlight", id: hl.id };
  let best: { id: string; bbox: Rect } | null = null;
  for (const b of layers.blocks ?? []) {
    if (b.kind !== "header_footer" && inside(x, y, b.bbox) && (!best || area(b.bbox) < area(best.bbox))) best = b;
  }
  return best ? { type: "block", id: best.id } : null;
}
