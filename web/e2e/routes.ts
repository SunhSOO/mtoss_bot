export interface Shot {
  id: string;
  path: string;
  /** 모바일 뷰포트에서도 찍을 화면인지 (§5의 모바일 범위). */
  mobile: boolean;
}

export const SHOTS: Shot[] = [
  { id: "login", path: "/login", mobile: true },
  { id: "login-mfa", path: "/login?step=mfa", mobile: true },
  { id: "onboarding", path: "/onboarding?step=3", mobile: false },
  { id: "dashboard", path: "/dashboard", mobile: true },
  { id: "strategies", path: "/strategies", mobile: false },
  { id: "strategy-detail", path: "/strategies/str-usdjpy-trend?tab=config", mobile: false },
  { id: "copy-leader", path: "/copy?tab=leader", mobile: false },
  { id: "copy-13f", path: "/copy?tab=form13f&detail=cp-13f-brk", mobile: false },
  { id: "approvals", path: "/approvals", mobile: true },
  { id: "approvals-detail", path: "/approvals?detail=apv-13f-brkb", mobile: true },
  { id: "orders", path: "/orders", mobile: true },
  { id: "orders-unknown", path: "/orders?detail=ord-0864", mobile: true },
  { id: "orders-positions", path: "/orders?tab=positions", mobile: false },
  { id: "orders-reconciliation", path: "/orders?tab=reconciliation", mobile: false },
  { id: "risk", path: "/risk", mobile: false },
  { id: "risk-edit", path: "/risk?edit=risk-symbol-weight", mobile: false },
  { id: "connections-toss", path: "/connections?tab=toss", mobile: false },
  { id: "connections-mt5", path: "/connections?tab=mt5", mobile: false },
  { id: "audit", path: "/audit", mobile: false },
  { id: "admin-users", path: "/admin?tab=users", mobile: false },
  { id: "admin-emergency", path: "/admin?tab=emergency", mobile: true },
  { id: "admin-liquidate", path: "/admin?tab=emergency&step=confirm", mobile: true },
];

/** §9 상태별 화면. 각 상태가 실제로 의미 있는 화면에서만 찍는다. */
export const STATE_SHOTS: Shot[] = [
  { id: "dashboard-empty", path: "/dashboard?state=empty", mobile: false },
  { id: "dashboard-loading", path: "/dashboard?state=loading", mobile: false },
  { id: "dashboard-mt5-offline", path: "/dashboard?state=mt5-offline", mobile: false },
  { id: "dashboard-toss-expired", path: "/dashboard?state=toss-auth-expired", mobile: false },
  { id: "dashboard-emergency", path: "/dashboard?state=emergency-stop", mobile: true },
  { id: "dashboard-forbidden", path: "/dashboard?state=forbidden", mobile: false },
  { id: "dashboard-server-error", path: "/dashboard?state=server-error", mobile: false },
  { id: "dashboard-stale", path: "/dashboard?state=market-data-stale", mobile: false },
  { id: "orders-rate-limited", path: "/orders?state=rate-limited", mobile: false },
  { id: "orders-empty", path: "/orders?state=empty", mobile: false },
  { id: "approvals-empty", path: "/approvals?state=empty", mobile: false },
  { id: "connections-mt5-offline", path: "/connections?tab=mt5&state=mt5-offline", mobile: false },
  { id: "connections-toss-expired", path: "/connections?tab=toss&state=toss-auth-expired", mobile: false },
  { id: "strategies-error", path: "/strategies?state=strategy-error", mobile: false },
  { id: "risk-viewer", path: "/risk?role=VIEWER", mobile: false },
  { id: "dashboard-viewer", path: "/dashboard?role=VIEWER", mobile: false },
];

export const THEMES = ["light", "dark"] as const;
export type Theme = (typeof THEMES)[number];
