// Open/close timing of the floating panel (docs/viewer-plan.md §8.6-8.7): hovering a figure for 350 ms (a
// highlight: 500 ms) opens it; leaving both the target and the panel for 200 ms closes it; a click pins it until
// Esc, an outside click, or the close button. Only one panel at a time.
import { useStore, type Pop } from "./store";

export type PopTarget = { kind: "figure" | "highlight"; id: string; page: number };

export const OPEN_MS = { figure: 350, highlight: 500 } as const;
export const CLOSE_MS = 200;

let openTimer: ReturnType<typeof setTimeout> | undefined;
let closeTimer: ReturnType<typeof setTimeout> | undefined;
let hovered: PopTarget | null = null;
let overPanel = false;

const same = (a: PopTarget | Pop | null, b: PopTarget | Pop | null) => !!a && !!b && a.kind === b.kind && a.id === b.id;
const current = () => useStore.getState().pop;
const show = (p: Pop) => useStore.getState().setPop(p);

function scheduleClose() {
  clearTimeout(closeTimer);
  closeTimer = setTimeout(() => {
    const p = current();
    if (p && !p.pinned && !overPanel && !same(p, hovered)) show(null);
  }, CLOSE_MS);
}

/** The pointer is now over this target (null: over nothing). `now` opens without the dwell (the ⓘ badge). */
export function hover(target: PopTarget | null, now = false) {
  if (same(target, hovered) && !now) return;
  hovered = target;
  clearTimeout(openTimer);
  const p = current();
  if (!target) {
    if (p && !p.pinned) scheduleClose();
    return;
  }
  if (same(p, target)) {
    clearTimeout(closeTimer);
    return;
  }
  if (p?.pinned) return; // a pinned panel stays until it is closed explicitly
  if (p) scheduleClose();
  if (now) show({ ...target, pinned: false });
  else openTimer = setTimeout(() => show({ ...target, pinned: false }), OPEN_MS[target.kind]);
}

export function enterPanel() {
  overPanel = true;
  clearTimeout(closeTimer);
}

export function leavePanel() {
  overPanel = false;
  scheduleClose();
}

export function pin(target: PopTarget) {
  clearTimeout(openTimer);
  clearTimeout(closeTimer);
  show({ ...target, pinned: true });
}

export type Box = { left: number; top: number; right: number; bottom: number };
const M = 12; // px from the anchor and from the viewport edges

/** Viewport position of a w × h panel for an anchor box: beside it (right, then left) when `side`, otherwise or
 * when there is no room, below, then above; always clamped into the viewport. */
export function placePanel(a: Box, w: number, h: number, vw: number, vh: number, side: boolean) {
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, hi));
  if (side) {
    const top = clamp(a.top, M, vh - h - M);
    if (a.right + M + w <= vw - M) return { left: a.right + M, top };
    if (a.left - M - w >= M) return { left: a.left - M - w, top };
  }
  const left = clamp(a.left, M, vw - w - M);
  if (a.bottom + M / 2 + h <= vh - M) return { left, top: a.bottom + M / 2 };
  if (a.top - M / 2 - h >= M) return { left, top: a.top - M / 2 - h };
  return { left, top: clamp(a.bottom + M / 2, M, vh - h - M) };
}

export function closePop() {
  clearTimeout(openTimer);
  clearTimeout(closeTimer);
  overPanel = false;
  hovered = null;
  show(null);
}
