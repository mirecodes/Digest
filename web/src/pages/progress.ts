import type { JobInfo } from "../types";

export type RunProgress = { done: number; failed: number; total: number; eta: number | null };

const active = (j: JobInfo) => j.status === "queued" || j.status === "running";

/** Progress of the current run: every queued or running job, plus the jobs that ended since the earliest of them was
 * submitted (older jobs belong to an earlier run). eta = seconds left, null until a job of the run has finished.
 * Times are epoch seconds; null when nothing is queued or running. */
export function runProgress(jobs: JobInfo[], parallel: number, now: number): RunProgress | null {
  const left = jobs.filter((j) => active(j) && j.submitted);
  if (!left.length) return null;
  const start = Math.min(...left.map((j) => j.submitted!));
  const ended = jobs.filter((j) => !active(j) && (j.ended ?? 0) >= start);
  const took = ended.filter((j) => j.status === "done" && j.started && j.ended).map((j) => j.ended! - j.started!);
  let eta: number | null = null;
  if (took.length) {
    // ponytail: the mean of this run's finished jobs whatever their step, spread over the parallel slots; a rough hint
    const mean = took.reduce((a, b) => a + b, 0) / took.length;
    const work = left.reduce((s, j) => s + (j.status === "running" && j.started ? Math.max(mean - (now - j.started), 0) : mean), 0);
    eta = work / Math.max(1, Math.min(parallel, left.length));
  }
  return { done: ended.length, failed: ended.filter((j) => j.status !== "done").length, total: ended.length + left.length, eta };
}
