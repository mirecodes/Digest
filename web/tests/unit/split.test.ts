import { describe, expect, it } from "vitest";
import { enqueue, keepRange } from "../../src/lib/pageRender";
import { singleColumn, snapSplit, stepSplit } from "../../src/lib/split";
import { useStore } from "../../src/lib/store";

describe("snapSplit", () => {
  it("snaps within 20 px of 1/3, 1/2 and 2/3 and clamps to 0.2-0.8", () => {
    expect(snapSplit(510, 1200)).toBe(0.425); // far from every snap point
    expect(snapSplit(615, 1200)).toBe(1 / 2);
    expect(snapSplit(385, 1200)).toBe(1 / 3);
    expect(snapSplit(819, 1200)).toBe(2 / 3);
    expect(snapSplit(825, 1200)).toBe(825 / 1200);
    expect(snapSplit(5, 1200)).toBe(0.2);
    expect(snapSplit(1190, 1200)).toBe(0.8);
  });

  it("steps between snap points, and the translation goes single-column only past 2/3", () => {
    expect(stepSplit(0.5, 1)).toBe(2 / 3);
    expect(stepSplit(0.4, -1)).toBe(1 / 3);
    expect(stepSplit(2 / 3, 1)).toBe(0.8);
    expect(stepSplit(1 / 3, -1)).toBe(0.2);
    expect(singleColumn(2 / 3)).toBe(false);
    expect(singleColumn(0.7)).toBe(true);
  });
});

describe("page rendering", () => {
  it("keeps mounted pages within the slack and drops them after a jump", () => {
    expect(keepRange([0, 2], 0, 1, 50)).toEqual([0, 3]);
    expect(keepRange([0, 3], 3, 4, 50)).toEqual([0, 6]); // pages 0-2 are still within 4 of the view
    expect(keepRange([0, 6], 5, 6, 50)).toEqual([3, 8]);
    expect(keepRange([3, 8], 2, 3, 50)).toEqual([0, 5]); // scrolling back up; page 8 is past the slack
    expect(keepRange([0, 7], 30, 31, 50)).toEqual([28, 33]);
    expect(keepRange([45, 49], 48, 49, 50)).toEqual([45, 49]);
  });

  it("runs one job at a time, nearest page first, canvas before text layer", async () => {
    useStore.setState({ page: 10 });
    const order: string[] = [];
    let release!: () => void;
    enqueue(1, 0, () => new Promise<void>((r) => { order.push("1c"); release = r; }));
    await new Promise((r) => setTimeout(r, 0)); // started: the queue was empty
    const job = (name: string) => () => { order.push(name); return Promise.resolve(); };
    enqueue(12, 0, job("12c"));
    enqueue(10, 1, job("10t"));
    enqueue(10, 0, job("10c"));
    const drop = enqueue(11, 0, job("11c"));
    drop();
    await new Promise((r) => setTimeout(r, 0));
    expect(order).toEqual(["1c"]);
    release();
    await new Promise((r) => setTimeout(r, 0));
    expect(order).toEqual(["1c", "10c", "10t", "12c"]);
  });
});
