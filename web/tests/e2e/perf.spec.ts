// Scroll performance on a 50-page text-dense paper (Phase 2 acceptance): records main-thread long tasks
// (> 50 ms, PerformanceObserver "longtask") while both panes are wheel-scrolled from top to bottom.
import { expect, test } from "@playwright/test";

test("perf: scrolling 50 pages stays free of long tasks", async ({ page }, info) => {
  await page.goto("/");
  await page.locator("[data-paper-id]", { hasText: "Long Paper (2024)" }).getByRole("button", { name: "열기" }).click();
  await expect(page.locator('.pdf-page[data-page="1"] canvas')).toBeVisible();
  await expect(page.locator('.tr-card[data-page="50"]')).toBeAttached();
  await page.waitForTimeout(1000); // initial render done

  type W = { __long: number[]; __loaf: number[] };
  await page.evaluate(() => {
    const w = window as unknown as W;
    w.__long = [];
    w.__loaf = [];
    new PerformanceObserver((list) => list.getEntries().forEach((e) => w.__long.push(e.duration))).observe({ type: "longtask" });
    new PerformanceObserver((list) => list.getEntries().forEach((e) => w.__loaf.push(e.duration))).observe({ type: "long-animation-frame" });
  });
  // calibration: a deliberate 120 ms in-page task must be observed, otherwise "0 long tasks" would mean nothing
  await page.evaluate(() => setTimeout(() => { const end = performance.now() + 120; while (performance.now() < end); }, 0));
  await page.waitForTimeout(300);
  expect(await page.evaluate(() => (window as unknown as W).__long.length)).toBeGreaterThan(0);

  const results: Record<string, { tasks: number; max: number; loaf: number; loafMax: number; pageReached: string }> = {};
  for (const pane of ["pdf-pane", "tr-pane"]) {
    for (const p of ["pdf-pane", "tr-pane"]) await page.getByTestId(p).evaluate((el) => (el.scrollTop = 0));
    await page.waitForTimeout(500);
    const box = (await page.getByTestId(pane).boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.evaluate(() => { const w = window as unknown as W; w.__long = []; w.__loaf = []; });
    const atEnd = () => page.getByTestId(pane).evaluate((el) => el.scrollTop + el.clientHeight >= el.scrollHeight - 1);
    for (let i = 0; i < 600 && !(i % 20 === 0 && (await atEnd())); i++) {
      await page.mouse.wheel(0, 300);
      await page.waitForTimeout(16);
    }
    await page.waitForTimeout(500);
    const { long, loaf } = await page.evaluate(() => { const w = window as unknown as W; return { long: w.__long, loaf: w.__loaf }; });
    results[pane] = {
      tasks: long.length, max: Math.round(Math.max(0, ...long)), loaf: loaf.length, loafMax: Math.round(Math.max(0, ...loaf)),
      pageReached: await page.getByTestId("page-indicator").innerText(),
    };
  }
  await info.attach("perf.json", { body: JSON.stringify(results, null, 2), contentType: "application/json" });
  console.log("[perf]", JSON.stringify(results));
  for (const r of Object.values(results)) {
    expect(r.pageReached).toBe("50 / 50"); // the PDF pane reached the end (driven directly or by sync)
    expect(r.tasks).toBe(0);
  }
});
