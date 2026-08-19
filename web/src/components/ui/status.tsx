import type { ReactNode } from "react";

import { barWidth, percent } from "@/lib/format";
import { levelTone } from "@/lib/labels";
import type { MetricTile as MetricTileData, Notice, StatusInfo, Tone } from "@/lib/types";

import { Button, LinkButton, TONE_BORDER, TONE_TEXT, cx, toneIcon } from "./primitives";

/**
 * 작은 점만 쓰지 않는다. 아이콘 + 텍스트 + 마지막 확인 시각을 함께 보여준다 (§6).
 */
export function StatusBadge({
  status,
  showTime = true,
}: {
  status: StatusInfo;
  showTime?: boolean;
}) {
  const tone = levelTone(status.level);
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium",
        TONE_BORDER[tone],
        TONE_TEXT[tone],
      )}
      title={status.detail}
    >
      {toneIcon(tone)}
      <span>{status.label}</span>
      {showTime && <span className="num text-secondary">· {status.as_of}</span>}
    </span>
  );
}

export function ToneBadge({
  tone,
  children,
}: {
  tone: Tone;
  children: ReactNode;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium",
        TONE_BORDER[tone],
        TONE_TEXT[tone],
      )}
    >
      {toneIcon(tone)}
      {children}
    </span>
  );
}

/** 라벨, 값, 단위, 기준 시각, 필요 시 한도 진행률만. 장식용 화살표는 없다 (§6). */
export function MetricSummary({ tile }: { tile: MetricTileData }) {
  return (
    <div className={cx("rounded-panel border bg-surface p-4", TONE_BORDER[tile.tone])}>
      <p className="text-xs text-secondary">{tile.label}</p>
      <p className={cx("mt-1.5 flex items-baseline gap-1", TONE_TEXT[tile.tone])}>
        <span className="num text-xl font-semibold">{tile.value}</span>
        {tile.unit && <span className="text-sm text-secondary">{tile.unit}</span>}
      </p>
      {tile.usage_percent && (
        <RiskUsageBar usage={tile.usage_percent} compact label={tile.label} />
      )}
      {tile.hint && <p className="mt-1.5 text-xs text-secondary">{tile.hint}</p>}
      <p className="num mt-2 text-xs text-secondary">기준 {tile.as_of}</p>
    </div>
  );
}

/**
 * 현재값과 한도를 함께 보여준다. 70% 미만 정상, 70~90% 주의, 90% 이상 작업 필요이며
 * 색상 외에 텍스트와 패턴을 함께 사용한다 (§6).
 */
export function RiskUsageBar({
  usage,
  label,
  compact = false,
}: {
  usage: string;
  label: string;
  compact?: boolean;
}) {
  const width = barWidth(usage);
  const tone: Tone = width >= 90 ? "critical" : width >= 70 ? "warning" : "ok";
  const status = width >= 90 ? "작업 필요" : width >= 70 ? "주의" : "정상";
  const fill =
    tone === "critical"
      ? "bg-critical pattern-critical"
      : tone === "warning"
        ? "bg-warn pattern-warn"
        : "bg-ok";
  return (
    <div className={compact ? "mt-2" : "mt-1"}>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-subtle"
        role="meter"
        aria-valuenow={width}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label} 한도 사용률 ${percent(usage)} · ${status}`}
      >
        <div className={cx("h-full rounded-full", fill)} style={{ width: `${width}%` }} />
      </div>
      {!compact && (
        <p className="mt-1 text-xs">
          <span className={TONE_TEXT[tone]}>{status}</span>
          <span className="num text-secondary"> · 한도의 {percent(usage)} 사용</span>
        </p>
      )}
    </div>
  );
}

export function NoticeBanner({ notice }: { notice: Notice }) {
  return (
    <div
      className={cx(
        "rounded-panel border px-4 py-3",
        TONE_BORDER[notice.tone],
        notice.tone === "critical" && "bg-critical/5",
        notice.tone === "warning" && "bg-warn/5",
      )}
      role={notice.tone === "critical" ? "alert" : "status"}
    >
      <div className="flex items-start gap-2.5">
        <span className={cx("mt-0.5", TONE_TEXT[notice.tone])}>{toneIcon(notice.tone)}</span>
        <div className="min-w-0 flex-1">
          <p className={cx("text-sm font-semibold", TONE_TEXT[notice.tone])}>{notice.title}</p>
          <p className="mt-1 text-sm text-secondary">{notice.body}</p>
        </div>
        {notice.action_href && notice.action_label && (
          <LinkButton href={notice.action_href} dense>
            {notice.action_label}
          </LinkButton>
        )}
      </div>
    </div>
  );
}

export function NoticeList({ notices }: { notices: Notice[] }) {
  if (notices.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      {notices.map((notice) => (
        <NoticeBanner key={notice.notice_id} notice={notice} />
      ))}
    </div>
  );
}

/** 단순한 빈 일러스트 대신 다음 행동을 제시한다 (§6). */
export function EmptyState({
  title,
  body,
  actionLabel,
  actionHref,
}: {
  title: string;
  body: string;
  actionLabel?: string;
  actionHref?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <p className="text-sm font-semibold">{title}</p>
      <p className="max-w-md text-sm text-secondary">{body}</p>
      {actionHref && actionLabel && (
        <LinkButton href={actionHref} variant="primary">
          {actionLabel}
        </LinkButton>
      )}
    </div>
  );
}

export function ErrorState({
  title,
  body,
  retryHref,
}: {
  title: string;
  body: string;
  retryHref: string;
}) {
  return (
    <div className="rounded-panel border border-critical/55 bg-critical/5 px-6 py-10 text-center">
      <p className="text-sm font-semibold text-critical">{title}</p>
      <p className="mx-auto mt-2 max-w-lg text-sm text-secondary">{body}</p>
      <div className="mt-4 flex justify-center">
        <LinkButton href={retryHref}>다시 시도</LinkButton>
      </div>
    </div>
  );
}

export function ForbiddenState({ backHref = "/dashboard" }: { backHref?: string }) {
  return (
    <div className="rounded-panel border border-line bg-surface px-6 py-12 text-center">
      <p className="text-sm font-semibold">이 화면을 볼 권한이 없습니다</p>
      <p className="mx-auto mt-2 max-w-lg text-sm text-secondary">
        계정에 부여된 역할로는 이 화면에 접근할 수 없습니다. 필요하면 관리자에게 권한을
        요청하세요.
      </p>
      <div className="mt-4 flex justify-center">
        <LinkButton href={backHref} variant="primary">
          대시보드로 돌아가기
        </LinkButton>
      </div>
    </div>
  );
}

export function SkeletonBlock({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2 p-4" aria-hidden>
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="h-4 rounded bg-subtle"
          style={{ width: `${100 - index * 7}%` }}
        />
      ))}
    </div>
  );
}

export function SkeletonPage({ title }: { title: string }) {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-live="polite">
      <span className="sr-only">{title} 데이터를 불러오는 중입니다.</span>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-panel border border-line bg-surface p-4">
            <div className="h-3 w-20 rounded bg-subtle" />
            <div className="mt-3 h-6 w-28 rounded bg-subtle" />
            <div className="mt-3 h-3 w-16 rounded bg-subtle" />
          </div>
        ))}
      </div>
      <div className="rounded-panel border border-line bg-surface">
        <SkeletonBlock rows={7} />
      </div>
    </div>
  );
}

export function InlineAction({
  label,
  formAction,
  variant = "secondary",
}: {
  label: string;
  formAction: (formData: FormData) => Promise<void>;
  variant?: "primary" | "secondary" | "critical";
}) {
  return (
    <form action={formAction}>
      <Button type="submit" variant={variant} dense>
        {label}
      </Button>
    </form>
  );
}
