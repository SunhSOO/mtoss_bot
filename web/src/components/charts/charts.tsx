import type { ReactNode } from "react";

import { money, plotValue, ratioToPercent } from "@/lib/format";
import type { ChartSeries, WeightRow } from "@/lib/types";

import { cx } from "../ui/primitives";

/**
 * 모든 차트는 축, 단위, 시간대, 데이터 기준 시각, 접근 가능한 요약을 가진다 (§10).
 * 라이브러리를 쓰지 않고 서버에서 SVG를 그리므로 렌더 결과가 결정적이다.
 */
function ChartFrame({
  series,
  children,
  table,
}: {
  series: ChartSeries;
  children: ReactNode;
  table: ReactNode;
}) {
  return (
    <figure className="flex flex-col gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3>{series.title}</h3>
        <p className="num text-xs text-secondary">
          단위 {series.unit} · 기준 {series.as_of}
        </p>
      </div>
      <div role="img" aria-label={`${series.title}. ${series.summary}`}>
        {children}
      </div>
      <figcaption className="text-xs text-secondary">
        {series.source_note} · {series.summary}
      </figcaption>
      <div className="sr-only">{table}</div>
    </figure>
  );
}

function DataFallback({ series }: { series: ChartSeries }) {
  return (
    <table>
      <caption>{series.title}</caption>
      <thead>
        <tr>
          <th scope="col">기간</th>
          <th scope="col">값</th>
        </tr>
      </thead>
      <tbody>
        {series.points.map((point) => (
          <tr key={point.label}>
            <th scope="row">{point.label}</th>
            <td>{point.value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function EmptyChart({ height = 160 }: { height?: number }) {
  return (
    <div
      className="flex items-center justify-center rounded border border-dashed border-line text-xs text-secondary"
      style={{ height }}
    >
      표시할 데이터가 없습니다
    </div>
  );
}

const W = 720;
const H = 180;
const PAD_X = 8;
const PAD_Y = 12;

function scale(values: number[]): { min: number; max: number } {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return { min: min - 1, max: max + 1 };
  const margin = (max - min) * 0.12;
  return { min: min - margin, max: max + margin };
}

function xAt(index: number, count: number): number {
  if (count <= 1) return W / 2;
  return PAD_X + (index * (W - PAD_X * 2)) / (count - 1);
}

function yAt(value: number, min: number, max: number): number {
  const ratio = (value - min) / (max - min);
  return H - PAD_Y - ratio * (H - PAD_Y * 2);
}

function AxisLabels({ points }: { points: { label: string }[] }) {
  return (
    <div className="mt-1 flex justify-between px-1">
      {points.map((point) => (
        <span key={point.label} className="num text-[11px] text-secondary">
          {point.label}
        </span>
      ))}
    </div>
  );
}

/** 순자산 선 차트 (§10). */
export function NetAssetLine({ series }: { series: ChartSeries }) {
  if (series.points.length === 0) {
    return (
      <ChartFrame series={series} table={<DataFallback series={series} />}>
        <EmptyChart />
      </ChartFrame>
    );
  }
  const values = series.points.map((point) => plotValue(point.value));
  const { min, max } = scale(values);
  const path = values
    .map((value, index) => `${index === 0 ? "M" : "L"}${xAt(index, values.length).toFixed(1)} ${yAt(value, min, max).toFixed(1)}`)
    .join(" ");
  const area = `${path} L${xAt(values.length - 1, values.length).toFixed(1)} ${H - PAD_Y} L${PAD_X} ${H - PAD_Y} Z`;
  return (
    <ChartFrame series={series} table={<DataFallback series={series} />}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-[180px] w-full" preserveAspectRatio="none">
        <path d={area} fill="var(--t-action-primary)" opacity="0.1" />
        <path d={path} fill="none" stroke="var(--t-action-primary)" strokeWidth="2" />
        {values.map((value, index) => (
          <circle
            key={series.points[index].label}
            cx={xAt(index, values.length)}
            cy={yAt(value, min, max)}
            r="2.5"
            fill="var(--t-action-primary)"
          />
        ))}
      </svg>
      <AxisLabels points={series.points} />
      <p className="num mt-1 text-xs text-secondary">
        최근값 {money(series.points[series.points.length - 1].value, "KRW")}
      </p>
    </ChartFrame>
  );
}

/** 0 기준선을 가진 일일 손익 막대 차트. 한국식으로 수익이 빨강이다 (§10). */
export function DailyPnlBars({ series }: { series: ChartSeries }) {
  if (series.points.length === 0) {
    return (
      <ChartFrame series={series} table={<DataFallback series={series} />}>
        <EmptyChart />
      </ChartFrame>
    );
  }
  const values = series.points.map((point) => plotValue(point.value));
  const extent = Math.max(...values.map(Math.abs)) || 1;
  const zeroY = H / 2;
  const barWidthPx = (W - PAD_X * 2) / values.length - 8;
  return (
    <ChartFrame series={series} table={<DataFallback series={series} />}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-[180px] w-full" preserveAspectRatio="none">
        <line
          x1={PAD_X}
          x2={W - PAD_X}
          y1={zeroY}
          y2={zeroY}
          stroke="var(--t-border-default)"
          strokeWidth="1"
        />
        {values.map((value, index) => {
          const height = (Math.abs(value) / extent) * (H / 2 - PAD_Y);
          const x = PAD_X + index * ((W - PAD_X * 2) / values.length) + 4;
          const positive = value >= 0;
          return (
            <rect
              key={series.points[index].label}
              x={x}
              y={positive ? zeroY - height : zeroY}
              width={barWidthPx}
              height={Math.max(height, 1)}
              fill={positive ? "var(--t-financial-up)" : "var(--t-financial-down)"}
              opacity="0.85"
            />
          );
        })}
      </svg>
      <AxisLabels points={series.points} />
      <p className="mt-1 text-xs text-secondary">
        <span className="text-up">■ 수익(+)</span>
        <span className="ml-3 text-down">■ 손실(−)</span>
        <span className="ml-3">0 기준선 표시</span>
      </p>
    </ChartFrame>
  );
}

/** 최대 낙폭 영역 차트 (§10). */
export function DrawdownArea({ series }: { series: ChartSeries }) {
  if (series.points.length === 0) {
    return (
      <ChartFrame series={series} table={<DataFallback series={series} />}>
        <EmptyChart height={120} />
      </ChartFrame>
    );
  }
  const values = series.points.map((point) => plotValue(point.value));
  const worst = Math.min(...values, 0);
  const height = 120;
  const y = (value: number) => 6 + (value / (worst || -1)) * (height - 18);
  const path = values
    .map((value, index) => `${index === 0 ? "M" : "L"}${xAt(index, values.length).toFixed(1)} ${y(value).toFixed(1)}`)
    .join(" ");
  return (
    <ChartFrame series={series} table={<DataFallback series={series} />}>
      <svg viewBox={`0 0 ${W} ${height}`} className="h-[120px] w-full" preserveAspectRatio="none">
        <line x1={PAD_X} x2={W - PAD_X} y1="6" y2="6" stroke="var(--t-border-default)" />
        <path
          d={`${path} L${xAt(values.length - 1, values.length).toFixed(1)} 6 L${PAD_X} 6 Z`}
          fill="var(--t-financial-down)"
          opacity="0.18"
        />
        <path d={path} fill="none" stroke="var(--t-financial-down)" strokeWidth="2" />
      </svg>
      <AxisLabels points={series.points} />
    </ChartFrame>
  );
}

/** 목표와 현재 비중을 겹치지 않게 병렬 가로 막대로 (§10). */
export function WeightCompareBars({
  rows,
  asOf,
}: {
  rows: WeightRow[];
  asOf: string;
}) {
  if (rows.length === 0) {
    return <p className="px-4 py-6 text-sm text-secondary">비교할 종목이 없습니다.</p>;
  }
  const maxWeight = Math.max(
    ...rows.flatMap((row) => [plotValue(row.target_weight), plotValue(row.current_weight)]),
    0.01,
  );
  return (
    <figure className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3 text-xs text-secondary">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded-sm bg-action" />
          목표 비중
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded-sm border border-line bg-subtle" />
          현재 비중
        </span>
        <span className="num">기준 {asOf}</span>
      </div>
      <ul className="flex flex-col gap-3">
        {rows.map((row) => {
          const target = (plotValue(row.target_weight) / maxWeight) * 100;
          const current = (plotValue(row.current_weight) / maxWeight) * 100;
          const diff = plotValue(row.target_weight) - plotValue(row.current_weight);
          return (
            <li key={row.symbol}>
              <div className="flex items-baseline justify-between gap-2 text-xs">
                <span className="font-medium">
                  {row.symbol_name}
                  <span className="num ml-1.5 text-secondary">{row.symbol}</span>
                </span>
                <span className="num text-secondary">
                  목표 {ratioToPercent(row.target_weight)}% · 현재{" "}
                  {ratioToPercent(row.current_weight)}% · 차이{" "}
                  <span className={cx(diff >= 0 ? "text-up" : "text-down")}>
                    {diff >= 0 ? "+" : "−"}
                    {ratioToPercent(String(Math.abs(diff)))}%
                  </span>
                </span>
              </div>
              <div className="mt-1 flex flex-col gap-1">
                <div className="h-2.5 w-full rounded-sm bg-subtle/60">
                  <div className="h-full rounded-sm bg-action" style={{ width: `${target}%` }} />
                </div>
                <div className="h-2.5 w-full rounded-sm bg-subtle/60">
                  <div
                    className="h-full rounded-sm border border-line bg-subtle"
                    style={{ width: `${current}%` }}
                  />
                </div>
              </div>
            </li>
          );
        })}
      </ul>
      <figcaption className="sr-only">
        종목별 목표 비중과 현재 비중을 나란히 비교한 가로 막대입니다.
      </figcaption>
    </figure>
  );
}
