import { describe, expect, it } from "vitest";
import { runProgress } from "../../src/pages/progress";
import type { JobInfo } from "../../src/types";

const job = (status: JobInfo["status"], submitted: number, started: number | null = null, ended: number | null = null): JobInfo =>
  ({ id: `${status}${submitted}`, paper: "p", action: "translation", status, lines: [], model: "", effort: "", submitted, started, ended });

describe("runProgress", () => {
  it("is null when nothing is queued or running", () => {
    expect(runProgress([job("done", 0, 1, 2)], 3, 10)).toBeNull();
  });

  it("counts the jobs of the current run only, and waits for one to finish before estimating", () => {
    const old = job("done", 0, 1, 50); // ended before the run started
    expect(runProgress([old, job("running", 100, 101), job("queued", 100)], 2, 110)).toEqual({ done: 0, failed: 0, total: 2, eta: null });
  });

  it("estimates the time left from the finished jobs, spread over the parallel slots", () => {
    const jobs = [
      job("done", 100, 100, 160), // 60 s
      job("failed", 100, 100, 105), // counted as processed, not used for the estimate
      job("running", 100, 160), // 20 s in: 40 s left
      job("queued", 100), // 60 s
    ];
    expect(runProgress(jobs, 2, 180)).toEqual({ done: 2, failed: 1, total: 4, eta: 50 });
    expect(runProgress(jobs, 1, 180)?.eta).toBe(100);
  });
});
