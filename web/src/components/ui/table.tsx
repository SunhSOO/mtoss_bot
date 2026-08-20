import Link from "next/link";
import type { ReactNode } from "react";

import { cx } from "./primitives";

export interface Column<T> {
  key: string;
  header: string;
  /** 숫자는 오른쪽 정렬한다 (§4). */
  numeric?: boolean;
  /** 태블릿 이하에서 숨기고 상세 드로어로 넘긴다 (§5). */
  secondary?: boolean;
  render: (row: T) => ReactNode;
}

/**
 * 고정 헤더, 숫자 오른쪽 정렬, 행 클릭 시 상세 드로어.
 * 드로어는 URL(`?detail=`)로 열리므로 뒤로 가기와 스크린샷이 모두 동작한다 (§6).
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  detailHref,
  caption,
  empty,
  dense = false,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  detailHref?: (row: T) => string;
  caption: string;
  empty?: ReactNode;
  dense?: boolean;
}) {
  if (rows.length === 0 && empty) {
    return <>{empty}</>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 z-[1] bg-subtle">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cx(
                  "whitespace-nowrap border-b border-line px-3 py-2 text-xs font-semibold text-secondary",
                  column.numeric && "text-right",
                  column.secondary && "hidden xl:table-cell",
                )}
              >
                {column.header}
              </th>
            ))}
            {detailHref && (
              <th scope="col" className="border-b border-line px-3 py-2">
                <span className="sr-only">상세</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-line last:border-0 hover:bg-subtle/60">
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cx(
                    "px-3 align-top",
                    dense ? "py-1.5" : "py-2.5",
                    column.numeric && "num text-right",
                    column.secondary && "hidden xl:table-cell",
                  )}
                >
                  {column.render(row)}
                </td>
              ))}
              {detailHref && (
                <td className={cx("px-3 text-right", dense ? "py-1.5" : "py-2.5")}>
                  <Link
                    href={detailHref(row)}
                    className="text-xs font-medium text-action underline underline-offset-2"
                  >
                    상세 검토
                  </Link>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function FilterRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
      {children}
    </div>
  );
}

export function Tabs({
  items,
  current,
  hrefFor,
}: {
  items: { id: string; label: string; count?: number }[];
  current: string;
  hrefFor: (id: string) => string;
}) {
  return (
    <nav className="flex flex-wrap gap-1 border-b border-line" aria-label="하위 화면">
      {items.map((item) => {
        const active = item.id === current;
        return (
          <Link
            key={item.id}
            href={hrefFor(item.id)}
            aria-current={active ? "page" : undefined}
            className={cx(
              "-mb-px inline-flex h-10 items-center gap-1.5 border-b-2 px-3 text-sm transition-colors duration-150",
              active
                ? "border-action font-semibold text-primary"
                : "border-transparent text-secondary hover:text-primary",
            )}
          >
            {item.label}
            {typeof item.count === "number" && (
              <span className="num rounded bg-subtle px-1.5 text-xs text-secondary">
                {item.count}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
