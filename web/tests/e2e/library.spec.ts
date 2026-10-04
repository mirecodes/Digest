// Library preprocessing (Phase 3): the server runs a stub instead of scripts/annotate.sh (PAPER_VIEWER_ANNOTATE_CMD
// in playwright.config.ts), so no Claude call happens.
import { expect, test } from "@playwright/test";

test("preprocess button streams the job log and finishes", async ({ page }) => {
  await page.goto("/");
  const row = page.locator("[data-paper-id]", { hasText: "Long Paper (2024)" });
  await row.getByRole("button", { name: "전처리" }).click();
  const log = row.getByTestId("job-log");
  await expect(log.locator("pre")).toContainText("stub annotate");
  await expect(log.locator("[data-status]")).toHaveAttribute("data-status", "done", { timeout: 15_000 });
  await expect(row.getByRole("button", { name: "전처리" })).toBeEnabled();
});

test("annotated paper shows the bundled translation and status chips", async ({ page }) => {
  await page.goto("/");
  const row = page.locator("[data-paper-id]", { hasText: "Demo (2024)" });
  await expect(row).toContainText("번역 16/16");
  await expect(row).toContainText("피규어 해설 3/3");
  await row.getByRole("button", { name: "열기" }).click();
  await expect(page.locator('.tr-block[data-block-id="p1-b5"]')).toContainText("FooNet을 제안한다");
  await expect(page.locator('.tr-block[data-block-id="p1-b5"]')).not.toHaveClass(/untranslated/);
});
