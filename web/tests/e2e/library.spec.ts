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

test("a new src/ paper is listed once and any step runs on its own, preparing the paper first", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("[data-paper-id]")).toHaveCount(3); // demo, long paper, fresh.pdf; dup.pdf is the demo
  const row = page.locator("[data-paper-id]", { hasText: "fresh" });
  await expect(row).toContainText("New");
  await expect(row.getByRole("button", { name: "Open" })).toBeDisabled();
  await row.getByRole("button", { name: "Process" }).click();
  for (const name of ["Run all", "Summary & report", "Translation", "Highlights", "Figure notes"]) {
    await expect(row.getByRole("menuitem", { name })).toBeEnabled();
  }
  await row.getByRole("menuitem", { name: "Highlights" }).click();
  const log = row.getByTestId("job-log");
  await expect(log.locator("pre")).toContainText("stub internal/prepare.sh --ensure -n");
  await expect(log.locator("pre")).toContainText("--only highlights");
  await expect(log.locator("pre")).not.toContainText("digest.sh");
  await expect(log.locator("[data-status]")).toHaveAttribute("data-status", "done", { timeout: 15_000 });
});

test("the chosen model and effort reach the job", async ({ page }) => {
  await page.goto("/");
  const model = page.getByLabel("Model");
  await expect(model).toHaveAttribute("list", "agent-models");
  await expect(page.locator("#agent-models option[value='claude-sonnet-5-5']")).toHaveCount(1);
  await model.fill("claude-sonnet-5-5");
  await page.getByLabel("Effort").selectOption("high");
  const row = page.locator("[data-paper-id]", { hasText: "Long Paper (2024)" });
  await row.getByRole("button", { name: "Process" }).click();
  await row.getByRole("menuitem", { name: "Translation" }).click();
  const log = row.getByTestId("job-log");
  await expect(log.locator("pre")).toContainText("PAPER_AGENT_EFFORT=high  PAPER_AGENT_MODEL=claude-sonnet-5-5");
  await expect(log.locator("[data-status]")).toHaveAttribute("data-status", "done", { timeout: 15_000 });
  await page.reload();
  await expect(page.getByLabel("Model")).toHaveValue("claude-sonnet-5-5"); // remembered in this browser
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
