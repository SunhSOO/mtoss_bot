import "server-only";

import { headers } from "next/headers";

import { resolveState, type StateSlug } from "./states";
import type { Role } from "./types";

export interface RequestContext {
  pathname: string;
  search: string;
  state: StateSlug;
  role: Role;
}

/** 미들웨어가 넣어 준 x-url 헤더에서 현재 화면 맥락을 복원한다. */
export async function requestContext(): Promise<RequestContext> {
  const store = await headers();
  const raw = store.get("x-url") ?? "/dashboard";
  const [pathname, search = ""] = raw.split("?");
  const params = new URLSearchParams(search);
  const roleParam = params.get("role");
  const role: Role =
    roleParam === "TRADER" ? "TRADER" : roleParam === "VIEWER" ? "VIEWER" : "ADMIN";
  return {
    pathname,
    search: search ? `?${search}` : "",
    state: resolveState(params.get("state") ?? undefined),
    role,
  };
}

/** 상태·역할 쿼리를 유지한 채 링크를 만든다. */
export function keepQuery(
  href: string,
  context: { state: StateSlug; role: Role },
  extra: Record<string, string | undefined> = {},
): string {
  const [base, existing = ""] = href.split("?");
  const params = new URLSearchParams(existing);
  if (context.state !== "normal") params.set("state", context.state);
  if (context.role !== "ADMIN") params.set("role", context.role);
  for (const [key, value] of Object.entries(extra)) {
    if (value === undefined) params.delete(key);
    else params.set(key, value);
  }
  const query = params.toString();
  return query ? `${base}?${query}` : base;
}
