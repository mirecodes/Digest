import { defineConfig } from "@playwright/test";

// Started by scripts/internal/viewer_test.sh --e2e, which prepares a fixture output root and exports
// PAPER_VIEWER_OUT, PY (the .venv interpreter) and ROOT (the project root).
const port = 8799;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  workers: 1,
  use: { baseURL: `http://127.0.0.1:${port}`, viewport: { width: 1400, height: 900 } },
  webServer: {
    command: `"${process.env.PY}" -m uvicorn functions.viewer.server:app --host 127.0.0.1 --port ${port}`,
    cwd: process.env.ROOT,
    url: `http://127.0.0.1:${port}/api/papers`,
    reuseExistingServer: false,
    env: { PAPER_VIEWER_OUT: process.env.PAPER_VIEWER_OUT ?? "", PAPER_VIEWER_LLM: "fake", PYTHONPATH: process.env.ROOT ?? "" },
  },
});
