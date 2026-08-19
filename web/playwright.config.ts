import { defineConfig, devices } from "@playwright/test";

const WEB = "http://127.0.0.1:3100";
const API = "http://127.0.0.1:8100";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  timeout: 60_000,
  use: {
    baseURL: WEB,
    locale: "ko-KR",
    timezoneId: "Asia/Seoul",
    // 절제된 전환만 쓰므로 애니메이션을 꺼도 화면이 동일하다 (§11).
    contextOptions: { reducedMotion: "reduce" },
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "tablet", use: { ...devices["Desktop Chrome"], viewport: { width: 1024, height: 768 } } },
    {
      name: "mobile",
      use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: false },
    },
  ],
  webServer: [
    {
      command:
        "uv run --env-file .env uvicorn mtoss.api.app:create_app --factory --host 127.0.0.1 --port 8100",
      cwd: "..",
      url: `${API}/health/live`,
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "npm run dev",
      url: WEB,
      reuseExistingServer: true,
      timeout: 180_000,
    },
  ],
});
