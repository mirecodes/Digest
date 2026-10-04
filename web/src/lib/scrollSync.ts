// Page-synchronized scrolling between the PDF pane and the translation pane (docs/viewer-plan.md §8.4).
// Both panes stack one element per page; a position inside page i (plus the gap after it) maps to the same
// relative position inside page i of the other pane.

export type PaneLayout = { tops: number[]; heights: number[]; gap: number };
export type ScrollBox = { scrollTop: number; clientHeight: number; scrollHeight: number };

export const REF_RATIO = 0.3;

/** Index of the page whose [top, top + height + gap) span contains y, clamped to the page range. */
export function pageAt(y: number, l: PaneLayout, n = l.tops.length): number {
  let lo = 0;
  let hi = n - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (l.tops[mid] <= y) lo = mid;
    else hi = mid - 1;
  }
  return Math.max(0, lo);
}

/** Map a content y coordinate of pane `from` to the matching y of pane `to`. */
export function mapRef(y: number, from: PaneLayout, to: PaneLayout): number {
  const n = Math.min(from.tops.length, to.tops.length);
  if (n === 0) return y;
  if (y < from.tops[0]) return to.tops[0] - (from.tops[0] - y); // above the first page: keep the offset
  const i = pageAt(y, from, n);
  const span = from.heights[i] + from.gap;
  const t = (y - from.tops[i]) / span;
  if (t > 1) return to.tops[i] + to.heights[i] + to.gap + (y - from.tops[i] - span); // past the last page
  return to.tops[i] + t * (to.heights[i] + to.gap);
}

/** scrollTop for the follower pane so both reference lines (30% from the top) show the same place. */
export function followerScrollTop(driver: ScrollBox, follower: ScrollBox, from: PaneLayout, to: PaneLayout): number {
  const maxFollower = Math.max(0, follower.scrollHeight - follower.clientHeight);
  if (driver.scrollTop <= 0) return 0;
  if (driver.scrollTop + driver.clientHeight >= driver.scrollHeight - 1) return maxFollower;
  const y = mapRef(driver.scrollTop + REF_RATIO * driver.clientHeight, from, to) - REF_RATIO * follower.clientHeight;
  return Math.min(maxFollower, Math.max(0, y));
}

/** Page (1-based) under the reference line of a pane. */
export function refPage(box: ScrollBox, l: PaneLayout): number {
  return l.tops.length ? pageAt(box.scrollTop + REF_RATIO * box.clientHeight, l) + 1 : 1;
}

/**
 * Wire two scroll containers together. Only the pane the user is interacting with (wheel, pointer, touch,
 * keys within the last 150 ms, or a held pointer such as a scrollbar drag) drives; scroll events of the other
 * pane are ignored, which prevents feedback loops. Follower updates are coalesced into one animation frame.
 * Returns `align(from)` for programmatic alignment and a cleanup function.
 */
export function bindScrollSync(
  a: HTMLElement,
  b: HTMLElement,
  layouts: () => { a: PaneLayout | null; b: PaneLayout | null },
  enabled: () => boolean,
): { align: (from: "a" | "b") => void; dispose: () => void } {
  const ACTIVE_MS = 150;
  let active: HTMLElement | null = null;
  let until = 0;
  let holding = false;
  let frame = 0;

  const align = (from: "a" | "b") => {
    const { a: la, b: lb } = layouts();
    if (!la || !lb) return;
    const [driver, follower, ld, lf] = from === "a" ? [a, b, la, lb] : [b, a, lb, la];
    follower.scrollTop = followerScrollTop(driver, follower, ld, lf);
  };
  const touch = (el: HTMLElement) => () => {
    active = el;
    until = performance.now() + ACTIVE_MS;
  };
  const press = (el: HTMLElement) => () => {
    touch(el)();
    holding = true;
  };
  const release = () => {
    if (holding) until = performance.now() + ACTIVE_MS;
    holding = false;
  };
  const onScroll = (el: HTMLElement) => () => {
    if (!enabled() || active !== el || (!holding && performance.now() > until)) return;
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => align(el === a ? "a" : "b"));
  };

  const off: (() => void)[] = [];
  for (const el of [a, b]) {
    const handlers: [string, EventListener][] = [
      ["wheel", touch(el)], ["touchstart", touch(el)], ["keydown", touch(el)],
      ["pointerdown", press(el)], ["scroll", onScroll(el)],
    ];
    for (const [type, fn] of handlers) {
      el.addEventListener(type, fn, { passive: true });
      off.push(() => el.removeEventListener(type, fn));
    }
  }
  window.addEventListener("pointerup", release);
  window.addEventListener("pointercancel", release);
  off.push(() => window.removeEventListener("pointerup", release), () => window.removeEventListener("pointercancel", release));
  return { align, dispose: () => { cancelAnimationFrame(frame); off.forEach((f) => f()); } };
}
