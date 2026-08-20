import { notFound } from "next/navigation";

import {
  Button,
  Chip,
  DefinitionList,
  LinkButton,
  PageHeader,
  Panel,
  Timestamp,
} from "@/components/ui/primitives";
import {
  ErrorState,
  ForbiddenState,
  MetricSummary,
  NoticeList,
  SkeletonPage,
  StatusBadge,
} from "@/components/ui/status";
import { DataTable, Tabs, type Column } from "@/components/ui/table";
import { toggleStrategyAction } from "@/lib/actions";
import { tryGet } from "@/lib/api";
import { MARKET, STRATEGY_MODE } from "@/lib/labels";
import { canAct } from "@/lib/nav";
import { keepQuery, requestContext } from "@/lib/request";
import type { StrategyDetail, StrategyRunRow } from "@/lib/types";

const TABS = [
  { id: "overview", label: "개요" },
  { id: "config", label: "설정" },
  { id: "validation", label: "검증" },
  { id: "runs", label: "실행 기록" },
];

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function StrategyDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ strategyId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const context = await requestContext();
  const { strategyId } = await params;
  const tab = one((await searchParams).tab) ?? "overview";
  const allowed = canAct(context.role);

  if (context.state === "loading") return <SkeletonPage title="전략 상세" />;

  const result = await tryGet<StrategyDetail>(`/console/v1/strategies/${strategyId}`, {
    state: context.state,
  });
  if (!result.ok) {
    if (result.error.status === 403) return <ForbiddenState />;
    if (result.error.status === 404) notFound();
    return (
      <ErrorState
        title="전략 상세를 불러오지 못했습니다"
        body={`${result.error.message} 실행 중인 전략에는 영향이 없습니다.`}
        retryHref={keepQuery(`/strategies/${strategyId}`, context, { tab })}
      />
    );
  }

  const detail = result.data;
  const row = detail.row;

  const runColumns: Column<StrategyRunRow>[] = [
    { key: "ran", header: "실행 시각", render: (item) => <Timestamp value={item.ran_at} /> },
    {
      key: "signals",
      header: "신호",
      numeric: true,
      render: (item) => <span className="num">{item.signals}</span>,
    },
    {
      key: "errors",
      header: "오류",
      numeric: true,
      render: (item) => (
        <span className={item.errors > 0 ? "num text-warn" : "num"}>{item.errors}</span>
      ),
    },
    {
      key: "duration",
      header: "처리시간",
      numeric: true,
      render: (item) => <span className="num">{item.duration_ms}ms</span>,
    },
    { key: "note", header: "비고", render: (item) => item.note },
  ];

  return (
    <>
      <PageHeader
        title={`${row.name} ${row.version}`}
        description={`${MARKET[row.market]} · ${row.timeframe} · 실행 계좌 ${row.account_count}개`}
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge status={row.status} showTime={false} />
            <Chip>{STRATEGY_MODE[row.mode]}</Chip>
            <LinkButton href={keepQuery("/strategies", context)} dense>
              목록으로
            </LinkButton>
            {allowed && (
              <form action={toggleStrategyAction}>
                <input type="hidden" name="strategy_id" value={row.strategy_id} />
                <Button type="submit" dense variant={row.paused ? "primary" : "critical"}>
                  {row.paused ? "재개" : "일시정지"}
                </Button>
              </form>
            )}
          </div>
        }
      />

      <NoticeList notices={detail.notices} />

      <Panel>
        <Tabs
          items={TABS}
          current={tab}
          hrefFor={(id) => keepQuery(`/strategies/${strategyId}`, context, { tab: id })}
        />

        {tab === "overview" && (
          <div className="flex flex-col gap-4 p-4">
            <p className="text-sm text-secondary">{detail.description}</p>
            <DefinitionList
              columns={3}
              items={[
                { term: "버전", value: row.version },
                { term: "대상 시장", value: MARKET[row.market] },
                { term: "주기", value: row.timeframe },
                { term: "운영 모드", value: STRATEGY_MODE[row.mode] },
                { term: "최근 실행", value: <Timestamp value={row.last_run_at} /> },
                { term: "최근 10거래일 오류", value: `${row.error_count_10d}건` },
              ]}
            />
            <div>
              <p className="mb-1.5 text-xs text-secondary">데이터 요구조건</p>
              <ul className="list-disc space-y-0.5 pl-5 text-sm">
                {detail.data_requirements.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {tab === "config" && (
          <div className="flex flex-col gap-4 p-4">
            <p className="text-xs text-secondary">
              저장하면 변경 전후 값을 보여주고 다음 봉부터 적용됩니다. 전략 버전을 바꾸면 기존
              포지션에 미치는 영향을 안내하고 다시 승인받습니다.
            </p>
            <div className="flex flex-col gap-3">
              {detail.settings.map((setting) => (
                <label key={setting.key} className="flex flex-col gap-1">
                  <span className="text-sm font-medium">
                    {setting.label}
                    {setting.unit && (
                      <span className="ml-1 text-xs text-secondary">({setting.unit})</span>
                    )}
                  </span>
                  <input
                    defaultValue={setting.value}
                    readOnly={!allowed}
                    className="num h-10 w-full max-w-xs rounded border border-line bg-surface px-3 text-sm"
                  />
                  <span className="text-xs text-secondary">
                    허용 범위 {setting.allowed_range} · {setting.description}
                  </span>
                </label>
              ))}
            </div>
            {allowed && (
              <div>
                <Button variant="primary">설정 저장</Button>
              </div>
            )}
          </div>
        )}

        {tab === "validation" && (
          <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">
            {detail.validation.map((tile) => (
              <MetricSummary key={tile.key} tile={tile} />
            ))}
          </div>
        )}

        {tab === "runs" && (
          <DataTable<StrategyRunRow>
            caption="전략 실행 기록"
            columns={runColumns}
            rows={detail.runs}
            rowKey={(item) => item.run_id}
          />
        )}
      </Panel>
    </>
  );
}
