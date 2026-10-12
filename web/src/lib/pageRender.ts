// PDF page rendering schedule (docs/viewer-plan.md §8.2). pdf.js draws on the main thread, so pages render one job
// at a time, the page nearest the reading position first (its canvas before its text layer). Mounted pages get
// slack, so scrolling back a little reuses pages that are already drawn.
import { useStore } from "./store";

type Job = { page: number; rank: number; run: () => Promise<unknown> };
const waiting = new Set<Job>();
let running = false;

function next() {
  if (running || waiting.size === 0) return;
  const here = useStore.getState().page;
  const cost = (j: Job) => Math.abs(j.page - here) * 2 + j.rank;
  let best: Job | undefined;
  for (const j of waiting) if (!best || cost(j) < cost(best)) best = j;
  waiting.delete(best!);
  running = true;
  best!.run().catch(() => {}).finally(() => {
    running = false;
    next();
  });
}

/** Queue a job for a 1-based page (rank 0: canvas, 1: text layer). The returned function drops it if not started. */
export function enqueue(page: number, rank: number, run: () => Promise<unknown>): () => void {
  const job = { page, rank, run };
  waiting.add(job);
  queueMicrotask(next);
  return () => waiting.delete(job);
}

/**
 * Pages (0-based, inclusive) to keep mounted for visible pages first..last of n: the visible ones ±margin, and
 * pages already mounted stay while they are within ±keep (each mounted page holds a canvas, so keep stays small).
 */
export function keepRange(prev: [number, number], first: number, last: number, n: number, margin = 2, keep = 4): [number, number] {
  const lo = Math.max(0, first - margin);
  const hi = Math.min(n - 1, last + margin);
  return [prev[0] >= first - keep && prev[0] <= lo ? prev[0] : lo, prev[1] <= last + keep && prev[1] >= hi ? prev[1] : hi];
}
