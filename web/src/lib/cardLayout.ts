// Translation "replica" page cards (docs/viewer-plan.md §8.3): which items a card shows, where each column
// sits horizontally, and how measured items are stacked vertically.
import type { Block, Column, Figure, PageInfo, Rect } from "../types";

export const ITEM_GAP = 4; // px between stacked items in one column
export const COLUMN_GUTTER = 6; // pt on each side of the column split

export type CardItem =
  | { key: string; type: "block"; column: Column; bbox: Rect; block: Block }
  | { key: string; type: "equation"; column: Column; bbox: Rect; block: Block }
  | { key: string; type: "figure"; column: Column; bbox: Rect; figure: Figure };

const HIDDEN = new Set(["header_footer", "figure_text", "table_text"]);

function figureColumn(f: Figure, page: PageInfo): Column {
  const s = page.column_split;
  if (page.columns === 1 || s === null) return 0;
  if (f.bbox[0] < s - 10 && f.bbox[2] > s + 10) return -1;
  return (f.bbox[0] + f.bbox[2]) / 2 < s ? 0 : 1;
}

/**
 * Items of one page in reading order. Figures go right before their caption when they sit above it
 * (right after it otherwise); caption-less figures go before the first item at or below them in their column.
 */
export function cardItems(page: PageInfo, blocks: Block[], figures: Figure[]): CardItem[] {
  const items: CardItem[] = [...blocks]
    .sort((a, b) => a.order - b.order)
    .filter((b) => !HIDDEN.has(b.kind))
    .map((b) => ({ key: b.id, type: b.kind === "equation" ? "equation" : "block", column: b.column, bbox: b.bbox, block: b }) as CardItem);
  for (const f of figures) {
    const item: CardItem = { key: f.id, type: "figure", column: figureColumn(f, page), bbox: f.bbox, figure: f };
    let at = items.findIndex((it) => it.type !== "figure" && it.block.id === f.caption_block);
    if (at >= 0) {
      if (f.bbox[1] > items[at].bbox[1]) at += 1;
    } else {
      at = items.findIndex((it) => it.bbox[1] >= f.bbox[1] && (it.column === item.column || it.column === -1 || item.column === -1));
      if (at < 0) at = items.length;
    }
    items.splice(at, 0, item);
  }
  return items;
}

/** Horizontal box (pt) of a column: page text margins, split at column_split. */
export function columnBox(page: PageInfo, blocks: Block[], column: Column): { left: number; width: number } {
  const visible = blocks.filter((b) => b.kind !== "header_footer");
  const left = visible.length ? Math.min(...visible.map((b) => b.bbox[0])) : page.width * 0.1;
  const right = visible.length ? Math.max(...visible.map((b) => b.bbox[2])) : page.width * 0.9;
  const s = page.column_split;
  if (page.columns === 1 || s === null || column === -1) return { left, width: right - left };
  return column === 0 ? { left, width: s - COLUMN_GUTTER - left } : { left: s + COLUMN_GUTTER, width: right - s - COLUMN_GUTTER };
}

/**
 * Vertical positions (px) for measured items, in order. Each item sits at its original height (y0 * s) when there
 * is room, otherwise right below the previous item of its column. Column-spanning items start below both columns.
 */
export function layoutCard(items: { column: Column; y0: number; height: number }[], s: number): number[] {
  const bottom = [0, 0];
  return items.map((it) => {
    const floor = it.column === -1 ? Math.max(bottom[0], bottom[1]) : bottom[it.column];
    const top = Math.max(floor > 0 ? floor + ITEM_GAP : 0, it.y0 * s);
    const end = top + it.height;
    if (it.column === -1) bottom[0] = bottom[1] = end;
    else bottom[it.column] = end;
    return top;
  });
}
