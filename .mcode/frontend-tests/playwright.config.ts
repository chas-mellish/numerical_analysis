import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 45000,
  retries: 1,
  workers: 2,
  use: {
    baseURL: process.env.GERALD_NA_E2E_BASE_URL || "http://127.0.0.1:8000",
    headless: true,
    viewport: { width: 1280, height: 800 },
    screenshot: "on",
    video: "retain-on-failure",
    trace: "retain-on-failure",
  },
  reporter: [
    ["list"],
    ["json", { outputFile: `${process.env.MCODE_DIR}/fe_testing/playwright-results.json` }],
  ],
});
