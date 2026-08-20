import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// 화면 설계서 §15와 로드맵 Phase 5 통과 기준을 화면에서 직접 검증한다.

const KEY = process.env.INTERNAL_API_KEY ?? "local-dev-console-key-2f8a1c94b7e6";
const API = "http://127.0.0.1:8100";

test.beforeEach(async ({ request }) => {
  await request.post(`${API}/console/v1/controls/reset`, {
    headers: { "X-Internal-Key": KEY },
  });
});

async function setTheme(page: Page, theme: "light" | "dark") {
  await page.context().addCookies([
    { name: "stc-theme", value: theme, url: "http://127.0.0.1:3100" },
  ]);
}

test("승인함 목록에서 바로 승인할 수 없다", async ({ page }) => {
  await page.goto("/approvals");
  const list = page.locator("main ul").first();
  await expect(list.getByRole("button", { name: "승인" })).toHaveCount(0);
  await expect(list.getByRole("link", { name: "상세 검토" }).first()).toBeVisible();
});

test("승인 드로어에서만 승인·거절이 노출된다", async ({ page }) => {
  await page.goto("/approvals?detail=apv-13f-brkb");
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByRole("button", { name: "승인" })).toBeVisible();
  await expect(drawer.getByRole("button", { name: "거절" })).toBeVisible();
  await expect(drawer.getByRole("button", { name: "가격·계좌 상태 재검사" })).toBeVisible();
});

test("13F 승인에는 분기 기준·공시 지연 경고가 반드시 보인다", async ({ page }) => {
  await page.goto("/approvals?detail=apv-13f-brkb");
  await expect(page.getByText("분기 말 기준 공시이며 최대 45일 지연될 수 있습니다")).toBeVisible();
});

test("재검사 후 조건이 바뀌면 다시 확인받는다", async ({ page }) => {
  await page.goto("/approvals?detail=apv-13f-brkb");
  await page.getByRole("button", { name: "가격·계좌 상태 재검사" }).click();
  await expect(page.getByText("조건이 변경되었습니다")).toBeVisible();
  await expect(page.getByRole("button", { name: "새 값으로 승인" })).toBeVisible();
});

test("UNKNOWN 주문에 재주문 버튼이 없고 브로커 재확인만 있다", async ({ page }) => {
  await page.goto("/orders?detail=ord-0864");
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByText("확인 필요").first()).toBeVisible();
  await expect(drawer.getByRole("button", { name: "브로커 상태 다시 확인" })).toBeVisible();
  for (const forbidden of ["재주문", "다시 주문", "재전송", "재시도"]) {
    await expect(drawer.getByRole("button", { name: forbidden })).toHaveCount(0);
  }
});

test("긴급 정지는 재인증 없이 실행되지 않고 포지션을 청산하지 않는다", async ({ page }) => {
  await page.goto("/admin?tab=emergency");
  await expect(page.getByText("보유 포지션을 청산하지 않습니다")).toBeVisible();

  await page.getByRole("button", { name: "전체 긴급 정지 실행" }).click();
  await expect(page.getByText("전체 긴급 정지 적용 중")).toHaveCount(0);

  await page.getByLabel("MFA 또는 패스키로 재인증했습니다").check();
  await page.getByRole("button", { name: "전체 긴급 정지 실행" }).click();
  await expect(page.getByRole("alert").getByText("전체 긴급 정지 적용 중")).toBeVisible();
});

test("긴급 정지 배너는 모든 화면에 뜨고 닫을 수 없다", async ({ page }) => {
  await page.goto("/admin?tab=emergency");
  await page.getByLabel("MFA 또는 패스키로 재인증했습니다").check();
  await page.getByRole("button", { name: "전체 긴급 정지 실행" }).click();

  for (const path of ["/dashboard", "/approvals", "/orders", "/risk", "/connections", "/audit"]) {
    await page.goto(path);
    const banner = page.getByRole("alert").filter({ hasText: "전체 긴급 정지 적용 중" });
    await expect(banner).toBeVisible();
    await expect(banner.getByRole("button", { name: "닫기" })).toHaveCount(0);
  }
});

test("전량 청산은 확인 문구와 재인증을 모두 요구한다", async ({ page }) => {
  await page.goto("/admin?tab=emergency&step=confirm");
  const phrase = page.getByPlaceholder("전량 청산 확인");
  await expect(phrase).toBeVisible();

  const liquidateForm = page.locator("form").filter({ hasText: "전량 청산 최종 실행" });
  await phrase.fill("청산");
  await liquidateForm.getByRole("checkbox").check();
  await page.getByRole("button", { name: "전량 청산 최종 실행" }).click();
  await expect(page.getByText("주문별 결과")).toHaveCount(0);

  await page.goto("/admin?tab=emergency&step=confirm");
  await page.getByPlaceholder("전량 청산 확인").fill("전량 청산 확인");
  await page.getByRole("button", { name: "전량 청산 최종 실행" }).click();
  await expect(page.getByText("주문별 결과")).toHaveCount(0);
});

test("전량 청산은 긴급 정지와 시각적으로 분리된다", async ({ page }) => {
  await page.goto("/admin?tab=emergency");
  await expect(
    page.getByRole("heading", { name: "전량 청산 — 긴급 정지와 별개입니다" }),
  ).toBeVisible();
});

test("MT5 노드는 재연결돼도 자동으로 매매를 재개하지 않는다", async ({ page }) => {
  await page.goto("/connections?tab=mt5&state=mt5-offline");
  await expect(page.getByText("연결 끊김으로 정지").first()).toBeVisible();
  await expect(page.getByText("노드가 다시 연결되어도 자동으로 매매를 재개하지 않습니다")).toBeVisible();
  await expect(page.getByRole("button", { name: "자동매매 재개 승인" })).toBeVisible();
});

test("토스 인증 만료와 MT5 offline은 다른 문제로 구분된다", async ({ page }) => {
  await page.goto("/connections?tab=toss&state=toss-auth-expired");
  await expect(page.getByText("토스 인증이 만료되었습니다")).toBeVisible();
  await page.goto("/connections?tab=mt5&state=mt5-offline");
  await expect(page.getByText("MT5 노드가 30초 동안 응답하지 않았습니다")).toBeVisible();
});

test("조회 전용 역할은 위험 설정·연결 메뉴가 숨겨진다", async ({ page }, testInfo) => {
  await page.goto("/dashboard?role=VIEWER");
  // 데스크톱 좌측 내비는 lg 이상에서만 보이므로 모바일은 하단 내비로 확인한다.
  const mobile = testInfo.project.name === "mobile";
  const nav = page.getByRole("navigation", { name: mobile ? "모바일 메뉴" : "주요 메뉴" });
  await expect(nav.getByRole("link", { name: /위험 설정/ })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: /^연결$/ })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: /^관리자$/ })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: /승인함/ })).toBeVisible();
});

test("대시보드에 매수·매도 버튼을 두지 않는다", async ({ page }) => {
  await page.goto("/dashboard");
  const main = page.getByRole("main");
  await expect(main.getByRole("button", { name: /^매수$/ })).toHaveCount(0);
  await expect(main.getByRole("button", { name: /^매도$/ })).toHaveCount(0);
});

test("손익 값은 색상만이 아니라 부호와 단어로도 구분된다", async ({ page }) => {
  await page.goto("/dashboard");
  // 부호(U+002B / U+2212)와 스크린리더용 단어가 값과 함께 나온다.
  const profit = page.locator("span.text-up", { hasText: "+₩1,542,000" }).first();
  await expect(profit).toBeVisible();
  await expect(profit).toContainText("수익");
  const loss = page.locator("span.text-down", { hasText: "−$731.20" }).first();
  await expect(loss).toBeVisible();
  await expect(loss).toContainText("손실");
});

test("API가 죽어 있으면 오류 상태를 안내한다", async ({ page }) => {
  await page.goto("/dashboard?state=server-error");
  await expect(page.getByText("대시보드를 불러오지 못했습니다")).toBeVisible();
  await expect(page.getByRole("link", { name: "다시 시도" })).toBeVisible();
});

test("권한 없음 상태는 돌아갈 위치를 제공한다", async ({ page }) => {
  await page.goto("/orders?state=forbidden");
  await expect(page.getByText("이 화면을 볼 권한이 없습니다")).toBeVisible();
  await expect(page.getByRole("link", { name: "대시보드로 돌아가기" })).toBeVisible();
});

for (const theme of ["light", "dark"] as const) {
  for (const path of ["/dashboard", "/approvals", "/orders", "/risk", "/connections"]) {
    test(`접근성 위반 없음 · ${theme} ${path}`, async ({ page }) => {
      await setTheme(page, theme);
      await page.goto(path);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      expect(
        results.violations.map((v) => `${v.id}: ${v.nodes.length}건`),
      ).toEqual([]);
    });
  }
}
