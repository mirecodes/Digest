import { defineConfig } from "@playwright/test";

// Started by scripts/internal/viewer_test.sh --e2e, which prepares a fixture output root and src/ and exports
// PAPER_VIEWER_OUT, PAPER_VIEWER_SRC, PY (the .venv interpreter) and ROOT (the project root).
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
    env: {
      PAPER_VIEWER_OUT: process.env.PAPER_VIEWER_OUT ?? "",
      PAPER_VIEWER_SRC: process.env.PAPER_VIEWER_SRC ?? "",
      PAPER_VIEWER_LLM: "fake",
      PYTHONPATH: process.env.ROOT ?? "",
      // stub for scripts/digest.sh and annotate.sh: echoes the script and its arguments, no Claude call
      PAPER_VIEWER_JOB_CMD: `"${process.env.PY}" -c "import sys, time; print('stub', *sys.argv[1:]); time.sleep(0.5); print('finished')"`,
    },
  },
});
