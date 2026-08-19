import Link from "next/link";
import type { ReactNode } from "react";

import { mobileNavFor, navFor } from "@/lib/nav";
import { STATE_LABELS, STATE_SLUGS, isSimulatorEnabled, type StateSlug } from "@/lib/states";
import { ROLE } from "@/lib/labels";
import { setThemeAction } from "@/lib/actions";
import type { ThemeChoice } from "@/lib/theme";
import type { AccountSummary, SessionPayload } from "@/lib/types";

import { Icon, cx } from "../ui/primitives";
import { StatusBadge } from "../ui/status";

const WORDMARK = "시스템 트레이딩 콘솔";

function SideNav({
  session,
  pathname,
  state,
}: {
  session: SessionPayload;
  pathname: string;
  state: StateSlug;
}) {
  const items = navFor(session.role);
  return (
    <nav
      aria-label="주요 메뉴"
      className="hidden w-[240px] shrink-0 flex-col border-r border-line bg-surface lg:flex"
    >
      <div className="flex h-16 items-center border-b border-line px-5">
        <Link href="/dashboard" className="text-sm font-bold tracking-tight">
          {WORDMARK}
        </Link>
      </div>
      <ul className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-3">
        {items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const href = state === "normal" ? item.href : `${item.href}?state=${state}`;
          return (
            <li key={item.id}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "flex min-h-[44px] flex-col justify-center rounded-md px-3 py-2 text-sm transition-colors duration-150",
                  active
                    ? "bg-subtle font-semibold text-primary"
                    : "text-secondary hover:bg-subtle hover:text-primary",
                )}
              >
                <span>{item.label}</span>
                {active && (
                  <span className="text-xs font-normal text-secondary">{item.description}</span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="border-t border-line p-3">
        <p className="px-3 text-sm font-medium">{session.user_name}</p>
        <p className="px-3 text-xs text-secondary">{ROLE[session.role]}</p>
        <ThemeToggle />
        <Link
          href="/login"
          className="mt-1 flex min-h-[36px] items-center rounded-md px-3 text-xs text-secondary hover:bg-subtle"
        >
          로그아웃
        </Link>
      </div>
    </nav>
  );
}

/** 라이트·다크·시스템 3단계. 서버 액션이라 JS 없이도 동작한다. */
function ThemeToggle() {
  const options: { value: ThemeChoice; label: string }[] = [
    { value: "light", label: "라이트" },
    { value: "dark", label: "다크" },
    { value: "system", label: "시스템" },
  ];
  return (
    <form action={setThemeAction} className="mt-3 px-3">
      <fieldset>
        <legend className="mb-1.5 text-xs text-secondary">테마</legend>
        <div className="flex gap-1">
          {options.map((option) => (
            <button
              key={option.value}
              type="submit"
              name="theme"
              value={option.value}
              className="min-h-[32px] flex-1 rounded border border-line px-1.5 text-xs text-secondary transition-colors duration-150 hover:bg-subtle hover:text-primary"
            >
              {option.label}
            </button>
          ))}
        </div>
      </fieldset>
    </form>
  );
}

function AccountScopePicker({ accounts }: { accounts: AccountSummary[] }) {
  const stopped = accounts.filter((account) => account.order_stopped).length;
  return (
    <div className="flex min-w-0 items-center gap-2">
      <span className="text-xs text-secondary">계좌 범위</span>
      <details className="relative">
        <summary className="flex h-8 cursor-pointer list-none items-center gap-1.5 rounded-md border border-line px-2.5 text-xs">
          전체 내 계좌
          <span className="num text-secondary">({accounts.length})</span>
          <Icon.chevron />
        </summary>
        <div className="absolute left-0 top-9 z-20 w-[280px] rounded-panel border border-line bg-surface p-2 shadow-lg">
          <p className="px-2 pb-1.5 text-xs text-secondary">
            이 화면의 모든 숫자와 행동이 선택한 범위에 적용됩니다.
          </p>
          <ul className="flex flex-col gap-0.5">
            <li className="rounded bg-subtle px-2 py-1.5 text-xs font-medium">전체 내 계좌</li>
            {accounts.map((account) => (
              <li key={account.account_id} className="px-2 py-1.5 text-xs">
                <span className="font-medium">{account.alias}</span>
                <span className="ml-1.5 text-secondary">
                  {account.order_stopped ? "· 주문 정지" : `· ${account.status.label}`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </details>
      {stopped > 0 && (
        <span className="num text-xs text-critical">주문 정지 {stopped}개</span>
      )}
    </div>
  );
}

function StateSimulator({ pathname, state }: { pathname: string; state: StateSlug }) {
  if (!isSimulatorEnabled()) return null;
  return (
    <details className="relative">
      <summary className="flex h-8 cursor-pointer list-none items-center gap-1.5 rounded-md border border-dashed border-line px-2.5 text-xs text-secondary">
        상태 시뮬레이터
        <span className={state === "normal" ? "" : "text-warn"}>{STATE_LABELS[state]}</span>
        <Icon.chevron />
      </summary>
      <div className="absolute right-0 top-9 z-20 max-h-[420px] w-[220px] overflow-y-auto rounded-panel border border-line bg-surface p-1.5 shadow-lg">
        {STATE_SLUGS.map((slug) => (
          <Link
            key={slug}
            href={slug === "normal" ? pathname : `${pathname}?state=${slug}`}
            className={cx(
              "block rounded px-2 py-1.5 text-xs hover:bg-subtle",
              slug === state && "bg-subtle font-semibold",
            )}
          >
            {STATE_LABELS[slug]}
          </Link>
        ))}
      </div>
    </details>
  );
}

function TopBar({
  session,
  pathname,
  state,
}: {
  session: SessionPayload;
  pathname: string;
  state: StateSlug;
}) {
  return (
    <header className="flex min-h-16 shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line bg-surface px-4 py-2 lg:px-6">
      <div className="flex min-w-0 items-center gap-4">
        <span className="text-sm font-bold lg:hidden">{WORDMARK}</span>
        <AccountScopePicker accounts={session.accounts} />
      </div>
      <div className="flex items-center gap-3">
        <p className="num hidden text-xs text-secondary sm:block">
          KST {session.kst_time} · ET {session.et_time}
        </p>
        <StateSimulator pathname={pathname} state={state} />
        <Link href="/admin" className="shrink-0">
          <StatusBadge status={session.system_status} />
        </Link>
      </div>
    </header>
  );
}

/** 긴급 정지 상태에서는 모든 페이지 상단에 닫을 수 없는 배너를 표시한다 (§6). */
function EmergencyBanner() {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-critical bg-critical/10 px-4 py-2.5 text-sm lg:px-6"
    >
      <span className="flex items-center gap-1.5 font-semibold text-critical">
        <Icon.stopped />
        전체 긴급 정지 적용 중
      </span>
      <span className="text-secondary">
        신규 주문이 차단되고 미체결 주문이 취소되었습니다. 보유 포지션은 청산하지 않았습니다.
      </span>
      <Link href="/admin?tab=emergency" className="ml-auto text-xs font-medium text-action underline">
        전체 제어 열기
      </Link>
    </div>
  );
}

function MobileTabBar({
  session,
  pathname,
  state,
}: {
  session: SessionPayload;
  pathname: string;
  state: StateSlug;
}) {
  const items = mobileNavFor(session.role);
  return (
    <nav
      aria-label="모바일 메뉴"
      className="sticky bottom-0 z-20 flex border-t border-line bg-surface lg:hidden"
    >
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        const href = state === "normal" ? item.href : `${item.href}?state=${state}`;
        return (
          <Link
            key={item.id}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cx(
              "flex min-h-[52px] flex-1 items-center justify-center px-2 text-xs",
              active ? "font-semibold text-primary" : "text-secondary",
            )}
          >
            {item.id === "dashboard" ? "홈" : item.label}
          </Link>
        );
      })}
      <Link
        href="/admin"
        className="flex min-h-[52px] flex-1 items-center justify-center px-2 text-xs text-secondary"
      >
        더보기
      </Link>
    </nav>
  );
}

export function AppShell({
  session,
  pathname,
  state,
  children,
}: {
  session: SessionPayload;
  pathname: string;
  state: StateSlug;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-canvas">
      <SideNav session={session} pathname={pathname} state={state} />
      <div className="flex min-w-0 flex-1 flex-col">
        {session.emergency_stop && <EmergencyBanner />}
        <TopBar session={session} pathname={pathname} state={state} />
        <main className="flex-1 px-4 py-5 lg:px-6 lg:py-6">
          <div className="flex flex-col gap-5">{children}</div>
        </main>
        <MobileTabBar session={session} pathname={pathname} state={state} />
      </div>
    </div>
  );
}
