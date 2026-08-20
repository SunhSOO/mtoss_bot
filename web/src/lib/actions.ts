"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";

import { consolePatch, consolePost, ConsoleApiError } from "./api";
import { THEME_COOKIE } from "./theme";
import type { ActionResult } from "./types";

async function refresh(): Promise<void> {
  revalidatePath("/", "layout");
}

function text(value: FormDataEntryValue | null): string {
  return typeof value === "string" ? value : "";
}

function checked(value: FormDataEntryValue | null): boolean {
  return value === "on" || value === "true" || value === "1";
}

export async function setThemeAction(formData: FormData): Promise<void> {
  const raw = text(formData.get("theme"));
  const store = await cookies();
  if (raw === "light" || raw === "dark") {
    store.set(THEME_COOKIE, raw, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
    });
  } else {
    store.delete(THEME_COOKIE);
  }
  await refresh();
}

/** 스텁 호출을 감싸 화면에 그대로 보여줄 수 있는 결과로 바꾼다. */
async function run(call: () => Promise<ActionResult>): Promise<void> {
  try {
    await call();
  } catch (error) {
    if (!(error instanceof ConsoleApiError)) throw error;
    // 오류는 다음 렌더에서 서버가 내려주는 상태로 드러난다.
  }
  await refresh();
}

export async function recheckApprovalAction(formData: FormData): Promise<void> {
  const id = text(formData.get("approval_id"));
  await run(() => consolePost<ActionResult>(`/console/v1/approvals/${id}/recheck`));
}

export async function decideApprovalAction(formData: FormData): Promise<void> {
  const id = text(formData.get("approval_id"));
  const action = text(formData.get("decision")) === "APPROVE" ? "APPROVE" : "REJECT";
  await run(() =>
    consolePost<ActionResult>(`/console/v1/approvals/${id}/decide`, { action }),
  );
}

export async function recheckBrokerAction(formData: FormData): Promise<void> {
  const id = text(formData.get("order_id"));
  await run(() => consolePost<ActionResult>(`/console/v1/orders/${id}/recheck-broker`));
}

export async function toggleStrategyAction(formData: FormData): Promise<void> {
  const id = text(formData.get("strategy_id"));
  await run(() => consolePost<ActionResult>(`/console/v1/strategies/${id}/toggle`));
}

export async function toggleSourceAction(formData: FormData): Promise<void> {
  const id = text(formData.get("source_id"));
  await run(() => consolePost<ActionResult>(`/console/v1/copy-sources/${id}/toggle`));
}

export async function updateRiskLimitAction(formData: FormData): Promise<void> {
  const id = text(formData.get("rule_id"));
  await run(() =>
    consolePatch<ActionResult>(`/console/v1/risk-rules/${id}`, {
      limit: text(formData.get("limit")),
      reauthenticated: checked(formData.get("reauthenticated")),
    }),
  );
}

export async function testTossAction(formData: FormData): Promise<void> {
  const scenario = text(formData.get("scenario"));
  await run(() =>
    consolePost<ActionResult>("/console/v1/connections/toss/test", {
      scenario: scenario || null,
    }),
  );
}

export async function stopAccountAction(formData: FormData): Promise<void> {
  const id = text(formData.get("account_id"));
  await run(() => consolePost<ActionResult>(`/console/v1/connections/accounts/${id}/stop`));
}

export async function resumeAccountAction(formData: FormData): Promise<void> {
  const id = text(formData.get("account_id"));
  await run(() => consolePost<ActionResult>(`/console/v1/connections/accounts/${id}/resume`));
}

export async function resumeNodeAction(formData: FormData): Promise<void> {
  const id = text(formData.get("node_id"));
  await run(() => consolePost<ActionResult>(`/console/v1/connections/mt5/${id}/resume`));
}

export async function emergencyStopAction(formData: FormData): Promise<void> {
  await run(() =>
    consolePost<ActionResult>("/console/v1/controls/emergency-stop", {
      reauthenticated: checked(formData.get("reauthenticated")),
    }),
  );
}

export async function resumeAllAction(): Promise<void> {
  await run(() => consolePost<ActionResult>("/console/v1/controls/resume"));
}

export async function liquidateAllAction(formData: FormData): Promise<void> {
  await run(() =>
    consolePost<ActionResult>("/console/v1/controls/liquidate-all", {
      confirm_phrase: text(formData.get("confirm_phrase")),
      reauthenticated: checked(formData.get("reauthenticated")),
    }),
  );
}

export async function resetConsoleAction(): Promise<void> {
  await run(() => consolePost<ActionResult>("/console/v1/controls/reset"));
}
