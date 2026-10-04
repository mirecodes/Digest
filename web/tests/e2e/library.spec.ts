// Library processing: the server runs a stub instead of scripts/digest.sh / annotate.sh (PAPER_VIEWER_JOB_CMD in
// playwright.config.ts), so no Claude call happens. src/ holds a new paper and a copy of the demo PDF.
import { expect, test } from "@playwright/test";

test("process menu runs one step and streams its log", async ({ page }) => {
  await page.goto("/");
  const row = page.locator("[data-paper-id]", { hasText: "Long Paper (2024)" });
  await row.getByRole("button", { name: "Process" }).click();
  await row.getByRole("menuitem", { name: "Figure notes" }).click();
  const log = row.getByTestId("job-log");
  await expect(log.locator("pre")).toContainText("stub annotate.sh -n");
  await expect(log.locator("pre")).toContainText("--only figures");
  await expect(log.locator("[data-status]")).toHaveAttribute("data-status", "done", { timeout: 15_000 });
  await expect(row.getByRole("button", { name: "Process" })).toBeEnabled();
});

test("a new src/ paper is listed once and can only be summarized or run in full", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("[data-paper-id]")).toHaveCount(3); // demo, long paper, fresh.pdf; dup.pdf is the demo
  const row = page.locator("[data-paper-id]", { hasText: "fresh" });
  await expect(row).toContainText("New");
  await expect(row.getByRole("button", { name: "Open" })).toBeDisabled();
  await row.getByRole("button", { name: "Process" }).click();
  await expect(row.getByRole("menuitem", { name: "Translation" })).toBeDisabled();
  await row.getByRole("menuitem", { name: "Run all" }).click();
  const log = row.getByTestId("job-log");
  await expect(log.locator("pre")).toContainText("stub digest.sh -n");
  await expect(log.locator("pre")).toContainText("stub annotate.sh -n");
  await expect(log.locator("[data-status]")).toHaveAttribute("data-status", "done", { timeout: 15_000 });
});

test("annotated paper shows the bundled translation and status chips", async ({ page }) => {
  await page.goto("/");
  const row = page.locator("[data-paper-id]", { hasText: "Demo (2024)" });
  await expect(row).toContainText("Translation 16/16");
  await expect(row).toContainText("Figure notes 3/3");
  await row.getByRole("button", { name: "Open" }).click();
  await expect(page.locator('.tr-block[data-block-id="p1-b5"]')).toContainText("FooNet을 제안한다");
  await expect(page.locator('.tr-block[data-block-id="p1-b5"]')).not.toHaveClass(/untranslated/);
});
