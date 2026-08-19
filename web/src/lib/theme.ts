import "server-only";

import { cookies } from "next/headers";

export type ThemeChoice = "light" | "dark" | "system";

export const THEME_COOKIE = "stc-theme";

/**
 * 서버에서 data-theme을 정해 첫 바이트에 담으므로 잘못된 테마가 깜빡이지 않는다.
 * `system`이면 속성을 비워 CSS의 prefers-color-scheme 규칙이 그대로 적용된다.
 */
export async function readTheme(): Promise<ThemeChoice> {
  const store = await cookies();
  const value = store.get(THEME_COOKIE)?.value;
  return value === "light" || value === "dark" ? value : "system";
}
