// Split between the PDF pane and the translation pane (docs/viewer-plan.md §8.1): the divider snaps to 1/3, 1/2
// and 2/3 of the panes' width; with the PDF pane past 2/3 the translation cards switch to one column.

export const SPLIT_MIN = 0.2;
export const SPLIT_MAX = 0.8;
export const SNAPS = [1 / 3, 1 / 2, 2 / 3];
export const SNAP_PX = 20; // the divider snaps once it is this close to a snap point

/** Split for a divider at x px of a `width` px wide pane area: clamped, and snapped when near a snap point. */
export function snapSplit(x: number, width: number): number {
  const raw = Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, x / width));
  return SNAPS.find((s) => Math.abs(s - raw) * width <= SNAP_PX) ?? raw;
}

/** Next snap point left (-1) or right (+1) of the split, for the arrow keys on the divider. */
export function stepSplit(split: number, dir: -1 | 1): number {
  const next = dir > 0 ? SNAPS.find((s) => s > split + 1e-6) : [...SNAPS].reverse().find((s) => s < split - 1e-6);
  return next ?? (dir > 0 ? SPLIT_MAX : SPLIT_MIN);
}

/** The translation pane is narrower than a third: two-column pages read better as one column. */
export const singleColumn = (split: number) => split > 2 / 3 + 1e-6;
