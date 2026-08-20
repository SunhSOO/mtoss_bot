import Link from "next/link";
import type { ReactNode } from "react";

import { isNegative, isZero, money, quantity, signedMoney, signedPercent } from "@/lib/format";
import type { Tone } from "@/lib/types";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-secondary",
  ok: "text-ok",
  warning: "text-warn",
  critical: "text-critical",
};

export const TONE_BORDER: Record<Tone, string> = {
  neutral: "border-line",
  ok: "border-ok/45",
  warning: "border-warn/50",
  critical: "border-critical/55",
};

/* -------------------------------------------------------------- 아이콘 */
// 단순한 outline 아이콘. 상태는 색상만이 아니라 형태로도 구분된다 (§4).

function Svg({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      width="14"
      height="14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={label ? undefined : true}
      role={label ? "img" : undefined}
      aria-label={label}
      className="shrink-0"
    >
      {children}
    </svg>
  );
}

export const Icon = {
  ok: () => (
    <Svg>
      <circle cx="8" cy="8" r="6" />
      <path d="M5.4 8.2 7.2 10l3.4-3.8" />
    </Svg>
  ),
  warning: () => (
    <Svg>
      <path d="M8 2.2 14.4 13H1.6z" />
      <path d="M8 6.4v3" />
      <path d="M8 11.2h.01" />
    </Svg>
  ),
  critical: () => (
    <Svg>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 4.8v3.6" />
      <path d="M8 10.9h.01" />
    </Svg>
  ),
  stopped: () => (
    <Svg>
      <circle cx="8" cy="8" r="6" />
      <path d="M5.6 5.6h4.8v4.8H5.6z" />
    </Svg>
  ),
  pending: () => (
    <Svg>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 4.6V8l2.2 1.4" />
    </Svg>
  ),
  link: () => (
    <Svg>
      <path d="M6.6 9.4 9.4 6.6" />
      <path d="M7.2 4.6 9 2.8a2.6 2.6 0 0 1 3.7 3.7l-1.8 1.8" />
      <path d="M8.8 11.4 7 13.2a2.6 2.6 0 0 1-3.7-3.7l1.8-1.8" />
    </Svg>
  ),
  chevron: () => (
    <Svg>
      <path d="M6 3.5 10.5 8 6 12.5" />
    </Svg>
  ),
};

export function toneIcon(tone: Tone) {
  if (tone === "ok") return <Icon.ok />;
  if (tone === "warning") return <Icon.warning />;
  if (tone === "critical") return <Icon.critical />;
  return <Icon.pending />;
}

/* -------------------------------------------------------------- 레이아웃 */

export function Panel({
  title,
  description,
  actions,
  children,
  className,
  tone = "neutral",
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  tone?: Tone;
}) {
  return (
    <section
      className={cx(
        "rounded-panel border bg-surface",
        tone === "neutral" ? "border-line" : TONE_BORDER[tone],
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
          <div>
            {title && <h2>{title}</h2>}
            {description && (
              <p className="mt-0.5 text-xs text-secondary">{description}</p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1>{title}</h1>
        <p className="mt-1 text-sm text-secondary">{description}</p>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/* -------------------------------------------------------------- 버튼 */

type ButtonVariant = "primary" | "secondary" | "critical" | "ghost";

const BUTTON_STYLE: Record<ButtonVariant, string> = {
  // 전경색을 토큰으로 둬 다크에서도 대비를 유지한다 (라이트는 흰색, 다크는 어두운 캔버스색).
  primary: "bg-action text-action-on border-action hover:opacity-90",
  secondary: "bg-surface text-primary border-line hover:bg-subtle",
  // 파괴 작업은 금융 수익 값과 같은 스타일을 쓰지 않는다 (§4): 채우지 않고 테두리로 표현한다.
  critical: "bg-surface text-critical border-critical hover:bg-critical/10",
  ghost: "bg-transparent text-secondary border-transparent hover:bg-subtle",
};

export function Button({
  children,
  variant = "secondary",
  type = "button",
  dense,
  disabled,
  name,
  value,
  className,
  formAction,
}: {
  children: ReactNode;
  variant?: ButtonVariant;
  type?: "button" | "submit";
  dense?: boolean;
  disabled?: boolean;
  name?: string;
  value?: string;
  className?: string;
  formAction?: (formData: FormData) => void | Promise<void>;
}) {
  return (
    <button
      type={type}
      name={name}
      value={value}
      disabled={disabled}
      formAction={formAction}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors duration-150",
        dense ? "h-8 min-h-8" : "h-11 min-w-[44px] sm:h-10",
        BUTTON_STYLE[variant],
        disabled && "cursor-not-allowed opacity-45",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function LinkButton({
  href,
  children,
  variant = "secondary",
  dense,
}: {
  href: string;
  children: ReactNode;
  variant?: ButtonVariant;
  dense?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors duration-150",
        dense ? "h-8 min-h-8" : "h-11 min-w-[44px] sm:h-10",
        BUTTON_STYLE[variant],
      )}
    >
      {children}
    </Link>
  );
}

/* -------------------------------------------------------------- 값 표시 */

/**
 * 손익·수익률. 붉은색이 금융 상승인지 위험인지 헷갈리지 않도록
 * 항상 부호와 스크린리더용 단어를 함께 낸다 (§4).
 */
export function SignedMoney({
  value,
  currency,
  className,
}: {
  value: string;
  currency: string;
  className?: string;
}) {
  const zero = isZero(value);
  const negative = isNegative(value);
  const tone = zero ? "text-secondary" : negative ? "text-down" : "text-up";
  return (
    <span className={cx("num tabular-nums", tone, className)}>
      <span className="sr-only">{zero ? "변동 없음 " : negative ? "손실 " : "수익 "}</span>
      {zero ? money(value, currency) : signedMoney(value, currency)}
    </span>
  );
}

export function SignedPercent({ value }: { value: string }) {
  const zero = isZero(value);
  const negative = isNegative(value);
  const tone = zero ? "text-secondary" : negative ? "text-down" : "text-up";
  return (
    <span className={cx("num", tone)}>
      <span className="sr-only">{zero ? "변동 없음 " : negative ? "하락 " : "상승 "}</span>
      {signedPercent(value)}
    </span>
  );
}

export function Money({ value, currency }: { value: string; currency: string }) {
  return <span className="num">{money(value, currency)}</span>;
}

export function Quantity({ value, unit }: { value: string; unit?: string }) {
  return (
    <span className="num">
      {quantity(value)}
      {unit ? <span className="text-secondary">{unit}</span> : null}
    </span>
  );
}

export function Timestamp({ value, className }: { value: string; className?: string }) {
  return <span className={cx("num text-secondary", className)}>{value}</span>;
}

/* -------------------------------------------------------------- 기타 */

export function Chip({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-xs",
        tone === "neutral" ? "border-line text-secondary" : TONE_BORDER[tone],
        tone !== "neutral" && TONE_TEXT[tone],
      )}
    >
      {children}
    </span>
  );
}

export function DefinitionList({
  items,
  columns = 2,
}: {
  items: { term: string; value: ReactNode; hint?: string }[];
  columns?: 1 | 2 | 3;
}) {
  const grid =
    columns === 1 ? "sm:grid-cols-1" : columns === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2";
  return (
    <dl className={cx("grid grid-cols-1 gap-x-6 gap-y-3", grid)}>
      {items.map((item) => (
        <div key={item.term} className="border-b border-line pb-2 last:border-0">
          <dt className="text-xs text-secondary">{item.term}</dt>
          <dd className="mt-0.5 text-sm">{item.value}</dd>
          {item.hint && <p className="mt-0.5 text-xs text-secondary">{item.hint}</p>}
        </div>
      ))}
    </dl>
  );
}
