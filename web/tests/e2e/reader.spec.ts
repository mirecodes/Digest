// End-to-end tests for the reader (docs/viewer-plan.md §12.3, items 1-3 and 9).
import { expect, test, type Page } from "@playwright/test";

async function openDemo(page: Page) {
  await page.goto("/");
  await page.locator("tr", { hasText: "Demo (2024)" }).getByRole("button").click();
  await expect(page.locator('.pdf-page[data-page="1"] canvas')).toBeVisible();
  await expect(page.locator('.tr-card[data-page="3"]')).toBeVisible();
}

const top = async (page: Page, selector: string) => (await page.locator(selector).boundingBox())!.y;

/** Wheel over a pane until `selector` (a page in that pane) sits on the pane's reference line (30% height). */
async function wheelToRef(page: Page, pane: string, selector: string) {
  const box = (await page.locator(pane).boundingBox())!;
  const ref = box.y + 0.3 * box.height;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < 5; i++) {
    const delta = (await top(page, selector)) - ref;
    if (Math.abs(delta) < 2) break;
    await page.mouse.wheel(0, delta);
    await page.waitForTimeout(120);
  }
  await page.waitForTimeout(100); // the follower updates on the next animation frame
}

test("1: library opens the reader with exact page placeholders", async ({ page }) => {
  await openDemo(page);
  const pages = page.locator(".pdf-page");
  await expect(pages).toHaveCount(3);
  for (let i = 0; i < 3; i++) {
    const b = (await pages.nth(i).boundingBox())!;
    expect(Math.abs(b.height - (b.width * 792) / 612)).toBeLessThan(1.5); // US letter, from viewer.json
  }
});

test("2: scrolling the PDF pane brings the matching translation card along", async ({ page }) => {
  await openDemo(page);
  await wheelToRef(page, '[data-testid="pdf-pane"]', '.pdf-page[data-page="2"]');
  const pdfTop = await top(page, '.pdf-page[data-page="2"]');
  const trTop = await top(page, '.tr-card[data-page="2"]');
  expect(Math.abs(pdfTop - trTop)).toBeLessThan(40);
  await expect(page.getByTestId("page-indicator")).toHaveText("2 / 3");
});

test("3: scrolling the translation pane drives the PDF pane; unlocking stops the sync", async ({ page }) => {
  await openDemo(page);
  await wheelToRef(page, '[data-testid="tr-pane"]', '.tr-card[data-page="2"]');
  expect(Math.abs((await top(page, '.pdf-page[data-page="2"]')) - (await top(page, '.tr-card[data-page="2"]')))).toBeLessThan(40);

  await page.getByTestId("toggle-sync").click();
  await expect(page.getByTestId("toggle-sync")).toHaveAttribute("aria-pressed", "false");
  const before = await page.getByTestId("pdf-pane").evaluate((el) => el.scrollTop);
  const tr = (await page.getByTestId("tr-pane").boundingBox())!;
  await page.mouse.move(tr.x + tr.width / 2, tr.y + tr.height / 2);
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(250);
  expect(await page.getByTestId("tr-pane").evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  expect(await page.getByTestId("pdf-pane").evaluate((el) => el.scrollTop)).toBe(before);
});

test("9: hovering a translation block outlines its source block in the PDF", async ({ page }) => {
  await openDemo(page);
  const right = page.locator('.tr-block[data-block-id="p1-b8"]');
  await right.hover();
  const outline = page.locator('.block-link[data-block-id="p1-b8"]');
  await expect(outline).toBeVisible();
  // the outline covers the "1 Introduction" body paragraph of page 1 (right column)
  const pageBox = (await page.locator('.pdf-page[data-page="1"]').boundingBox())!;
  const o = (await outline.boundingBox())!;
  expect(o.x - pageBox.x).toBeGreaterThan(pageBox.width / 2 - 5);
  await page.mouse.move(5, 5);
  await expect(outline).toHaveCount(0);
});
