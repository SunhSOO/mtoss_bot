import { test, type Page } from "@playwright/test";

import { SHOTS, STATE_SHOTS, THEMES, type Theme } from "./routes";

async function useTheme(page: Page, theme: Theme) {
  await page.context().addCookies([
    { name: "stc-theme", value: theme, url: "http://127.0.0.1:3100" },
  ]);
}

async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
}

test.beforeAll(async ({ request }) => {
  // 목업 상태를 초기화해 이전 실행의 변경이 남지 않게 한다.
  await request.post("http://127.0.0.1:8100/console/v1/controls/reset", {
    headers: { "X-Internal-Key": process.env.INTERNAL_API_KEY ?? "local-dev-console-key-2f8a1c94b7e6" },
  });
});

for (const theme of THEMES) {
  for (const shot of [...SHOTS, ...STATE_SHOTS]) {
    test(`${theme} ${shot.id}`, async ({ page }, testInfo) => {
      test.skip(testInfo.project.name === "mobile" && !shot.mobile, "모바일 범위가 아님");
      await useTheme(page, theme);
      await page.goto(shot.path);
      await settle(page);
      await page.screenshot({
        path: `screenshots/${testInfo.project.name}/${theme}/${shot.id}.png`,
        // 모바일은 하단 고정 내비가 제자리에 보이도록 뷰포트만 찍는다.
        fullPage: testInfo.project.name !== "mobile",
      });
    });
  }
}
