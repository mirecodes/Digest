import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { parseCitations } from "../../src/lib/citations";
import { categoryByBlock, visible } from "../../src/lib/highlights";
import { CLOSE_MS, OPEN_MS, closePop, enterPanel, hover, leavePanel, pin, placePanel } from "../../src/lib/popover";
import { useStore } from "../../src/lib/store";
import type { Block, Highlight, Rect } from "../../src/types";

describe("popover timing", () => {
  const fig = { kind: "figure" as const, id: "fig-p2-0", page: 2 };
  const hl = { kind: "highlight" as const, id: "E1", page: 1 };
  const pop = () => useStore.getState().pop;
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    closePop();
    vi.useRealTimers();
  });

  it("opens after the dwell, not before", () => {
    hover(fig);
    vi.advanceTimersByTime(OPEN_MS.figure - 1);
    expect(pop()).toBeNull();
    vi.advanceTimersByTime(1);
    expect(pop()).toMatchObject({ id: "fig-p2-0", pinned: false });
  });
  it("a quick pass does not open; highlights wait longer", () => {
    hover(fig);
    vi.advanceTimersByTime(100);
    hover(null);
    vi.advanceTimersByTime(1000);
    expect(pop()).toBeNull();
    hover(hl);
    vi.advanceTimersByTime(OPEN_MS.figure);
    expect(pop()).toBeNull();
    vi.advanceTimersByTime(OPEN_MS.highlight - OPEN_MS.figure);
    expect(pop()?.id).toBe("E1");
  });
  it("stays open while the pointer moves from the target into the panel", () => {
    hover(fig, true);
    hover(null);
    vi.advanceTimersByTime(CLOSE_MS / 2);
    enterPanel();
    vi.advanceTimersByTime(CLOSE_MS * 2);
    expect(pop()?.id).toBe("fig-p2-0");
    leavePanel();
    vi.advanceTimersByTime(CLOSE_MS);
    expect(pop()).toBeNull();
  });
  it("a pinned panel ignores hover changes until closed", () => {
    pin(fig);
    hover(null);
    hover(hl);
    vi.advanceTimersByTime(2000);
    expect(pop()).toMatchObject({ id: "fig-p2-0", pinned: true });
    closePop();
    expect(pop()).toBeNull();
  });
});

describe("placePanel", () => {
  const vw = 1400, vh = 900;
  const box = (left: number, top: number, right: number, bottom: number) => ({ left, top, right, bottom });
  it("goes right of a figure when there is room, keeping inside the viewport vertically", () => {
    expect(placePanel(box(100, 850, 500, 1000), 420, 300, vw, vh, true)).toEqual({ left: 512, top: 588 });
  });
  it("falls back to the left, then below, then above", () => {
    expect(placePanel(box(900, 100, 1300, 300), 420, 200, vw, vh, true)).toEqual({ left: 468, top: 100 });
    expect(placePanel(box(300, 100, 1300, 300), 420, 200, vw, vh, true)).toEqual({ left: 300, top: 306 });
    expect(placePanel(box(300, 600, 1300, 800), 420, 200, vw, vh, true)).toEqual({ left: 300, top: 394 });
  });
  it("puts a tooltip below its highlight and clamps it horizontally", () => {
    expect(placePanel(box(1300, 100, 1380, 112), 320, 60, vw, vh, false)).toEqual({ left: 1068, top: 118 });
  });
});

describe("citations", () => {
  it("parses every marker kind and keeps the text between", () => {
    expect(parseCitations("acc 61.4 [E2, p.2] vs ~0.8 [FIG: fig-p3-0] [CALC: a/b, E2] [INTERP] [EXT] [E7] end")).toEqual([
      { type: "text", text: "acc 61.4 " },
      { type: "cite", eid: "E2", page: 2 },
      { type: "text", text: " vs ~0.8 " },
      { type: "tag", tag: "FIG", arg: "fig-p3-0" },
      { type: "text", text: " " },
      { type: "tag", tag: "CALC", arg: "a/b, E2" },
      { type: "text", text: " " },
      { type: "tag", tag: "INTERP", arg: "" },
      { type: "text", text: " " },
      { type: "tag", tag: "EXT", arg: "" },
      { type: "text", text: " " },
      { type: "cite", eid: "E7", page: null },
      { type: "text", text: " end" },
    ]);
  });
  it("leaves reference numbers like [12] as text", () => {
    expect(parseCitations("as in [12]")).toEqual([{ type: "text", text: "as in [12]" }]);
  });
});

describe("highlights", () => {
  const h = (id: string, category: Highlight["category"], rects: Rect[], page = 1) =>
    ({ id, category, page, rects, quote: "", note_tr: null, note_en: null }) as Highlight;
  const blocks = [
    { id: "col", page: 1, kind: "paragraph", bbox: [50, 100, 300, 400] },
    { id: "para", page: 1, kind: "paragraph", bbox: [50, 100, 300, 200] },
    { id: "p2", page: 2, kind: "paragraph", bbox: [50, 100, 300, 200] },
  ] as Block[];

  it("maps a highlight to the smallest block holding it, on its own page", () => {
    const m = categoryByBlock([h("E1", "method", [[60, 150, 200, 160]]), h("E2", "result", [[60, 150, 200, 160]], 2)], blocks);
    expect([...m]).toEqual([["para", "method"], ["p2", "result"]]);
  });
  it("filters by the layer switch and hidden categories", () => {
    const all = [h("E1", "method", []), h("E2", "result", [])];
    expect(visible(all, false, []).length).toBe(0);
    expect(visible(all, true, ["result"]).map((x) => x.id)).toEqual(["E1"]);
  });
});
