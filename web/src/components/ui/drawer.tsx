import Link from "next/link";
import type { ReactNode } from "react";

import type { TimelineStep } from "@/lib/types";

import { Icon, cx } from "./primitives";

/**
 * 오른쪽 상세 드로어. 열림 상태가 URL에 있으므로 뒤로 가기로 닫히고
 * 스크린샷도 URL만으로 재현된다 (§5).
 */
export function DetailDrawer({
  title,
  subtitle,
  closeHref,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  closeHref: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <>
      <Link
        href={closeHref}
        aria-label="상세 닫기"
        className="fixed inset-0 z-30 bg-black/25 backdrop-blur-[1px]"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="fixed inset-y-0 right-0 z-40 flex w-full max-w-[560px] flex-col border-l border-line bg-surface shadow-xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate">{title}</h2>
            {subtitle && <p className="mt-0.5 text-xs text-secondary">{subtitle}</p>}
          </div>
          <Link
            href={closeHref}
            className="inline-flex h-10 min-w-[44px] shrink-0 items-center justify-center whitespace-nowrap rounded-md border border-line px-3 text-sm hover:bg-subtle"
          >
            닫기
          </Link>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <footer className="border-t border-line px-5 py-4">{footer}</footer>
        )}
      </aside>
    </>
  );
}

const STEP_STYLE: Record<TimelineStep["state"], { dot: string; text: string }> = {
  DONE: { dot: "border-ok bg-ok", text: "text-primary" },
  CURRENT: { dot: "border-warn bg-warn", text: "text-primary font-semibold" },
  PENDING: { dot: "border-line bg-transparent", text: "text-secondary" },
  BRANCH: { dot: "border-critical bg-surface", text: "text-critical font-semibold" },
};

/** 생성 → 승인 → 실행 대기 → 접수 → 부분 체결 → 체결. 분기는 따로 표시한다 (§6). */
export function OrderStatusTimeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol className="relative flex flex-col gap-0">
      {steps.map((step, index) => {
        const style = STEP_STYLE[step.state];
        const last = index === steps.length - 1;
        return (
          <li key={step.key} className="relative flex gap-3 pb-4 last:pb-0">
            {!last && (
              <span
                aria-hidden
                className="absolute left-[5px] top-4 h-full w-px bg-line"
              />
            )}
            <span
              aria-hidden
              className={cx("relative mt-1 h-2.5 w-2.5 shrink-0 rounded-full border-2", style.dot)}
            />
            <div className="min-w-0 flex-1">
              <p className={cx("text-sm", style.text)}>
                {step.label}
                {step.state === "BRANCH" && (
                  <span className="ml-1.5 text-xs font-normal">· 분기 상태</span>
                )}
              </p>
              <p className="num mt-0.5 text-xs text-secondary">
                {step.at ?? "아직 진행되지 않음"}
              </p>
              {step.note && <p className="mt-0.5 text-xs text-secondary">{step.note}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function DrawerSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="border-b border-line py-4 first:pt-0 last:border-0">
      <h3 className="mb-2.5 flex items-center gap-1.5 text-sm">
        <span className="text-secondary">
          <Icon.chevron />
        </span>
        {title}
      </h3>
      {children}
    </section>
  );
}
