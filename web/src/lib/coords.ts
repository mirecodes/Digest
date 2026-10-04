// PDF point <-> CSS pixel conversions (docs/viewer-plan.md §4.1): cssPx = pt * scale.
import type { Rect } from "../types";

export const PAGE_GAP = 16; // px between pages, identical in both panes
export const PANE_PAD = 16; // px padding above the first page

/** Page-relative PDF point of a client (viewport) position over a page element. */
export function clientToPt(clientX: number, clientY: number, pageRect: DOMRect, scale: number): [number, number] {
  return [(clientX - pageRect.left) / scale, (clientY - pageRect.top) / scale];
}

export function ptToClient(x: number, y: number, pageRect: DOMRect, scale: number): [number, number] {
  return [pageRect.left + x * scale, pageRect.top + y * scale];
}

export function rectStyle(r: Rect, scale: number) {
  return { left: r[0] * scale, top: r[1] * scale, width: (r[2] - r[0]) * scale, height: (r[3] - r[1]) * scale };
}

/** Content-coordinate tops of stacked pages: padding, then height + gap per page. */
export function stackTops(heights: number[], gap = PAGE_GAP, pad = PANE_PAD): number[] {
  const tops: number[] = [];
  let y = pad;
  for (const h of heights) {
    tops.push(y);
    y += h + gap;
  }
  return tops;
}
