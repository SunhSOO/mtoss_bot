import {
  Button,
  Chip,
  LinkButton,
  PageHeader,
  Panel,
  Timestamp,
} from "@/components/ui/primitives";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  SkeletonPage,
  StatusBadge,
} from "@/components/ui/status";
import { DataTable, FilterRow, type Column } from "@/components/ui/table";
import { toggleStrategyAction } from "@/lib/actions";
import { tryGet } from "@/lib/api";
import { MARKET, STRATEGY_MODE } from "@/lib/labels";
import { canAct, canAdminister } from "@/lib/nav";
import { keepQuery, requestContext } from "@/lib/request";
import type { StrategyRow } from "@/lib/types";

export default async function StrategiesPage() {
  const context = await requestContext();
  const allowed = canAct(context.role);

  if (context.state === "loading") return <SkeletonPage title="전략" />;

  const result = await tryGet<StrategyRow[]>("/console/v1/strategies", {
    state: context.state,
  });
  if (!result.ok) {
    if (result.error.status === 403) return <ForbiddenState />;
    return (
      <ErrorState
        title="전략 목록을 불러오지 못했습니다"
        body={`${result.error.message} 실행 중인 전략에는 영향이 없습니다. 잠시 후 다시 시도해 주세요.`}
        retryHref={keepQuery("/strategies", context)}
      />
    );
  }

  const columns: Column<StrategyRow>[] = [
    {
      key: "name",
      header: "전략명",
      render: (row) => (
        <span>
          {row.name}
          <span className="num ml-1.5 text-xs text-secondary">{row.version}</span>
        </span>
      ),
    },
    {
      key: "market",
      header: "대상 시장·주기",
      render: (row) => `${MARKET[row.market]} · ${row.timeframe}`,
    },
    {
      key: "accounts",
      header: "실행 계좌",
      numeric: true,
      render: (row) => <span className="num">{row.account_count}</span>,
    },
    {
      key: "mode",
      header: "운영 모드",
      render: (row) => (
        <Chip tone={row.mode === "AUTO" ? "warning" : "neutral"}>
          {STRATEGY_MODE[row.mode]}
        </Chip>
      ),
    },
    {
      key: "last",
      header: "최근 실행",
      render: (row) => <Timestamp value={row.last_run_at} />,
    },
    {
      key: "status",
      header: "상태",
      render: (row) => (
        <span className="flex flex-wrap items-center gap-1.5">
          <StatusBadge status={row.status} showTime={false} />
          {row.paused && <Chip tone="warning">일시정지</Chip>}
        </span>
      ),
    },
    {
      key: "errors",
      header: "최근 10거래일 오류",
      numeric: true,
      secondary: true,
      render: (row) => (
        <span className={row.error_count_10d > 0 ? "num text-warn" : "num"}>
          {row.error_count_10d}건
        </span>
      ),
    },
    {
      key: "actions",
      header: "행동",
      render: (row) =>
        allowed ? (
          <form action={toggleStrategyAction}>
            <input type="hidden" name="strategy_id" value={row.strategy_id} />
            <Button type="submit" dense variant={row.paused ? "primary" : "secondary"}>
              {row.paused ? "재개" : "일시정지"}
            </Button>
          </form>
        ) : (
          <span className="text-xs text-secondary">—</span>
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="전략"
        description="관리자가 배포한 전략만 실행됩니다. 사용자는 허용된 설정값만 바꿀 수 있습니다."
        actions={
          canAdminister(context.role) ? (
            <LinkButton href={keepQuery("/admin", context, { tab: "deployments" })}>
              새 버전 배포
            </LinkButton>
          ) : undefined
        }
      />

      <Panel>
        <FilterRow>
          <span className="text-xs text-secondary">필터</span>
          <Chip>시장 · 전체</Chip>
          <Chip>운영 모드 · 전체</Chip>
          <Chip>상태 · 전체</Chip>
        </FilterRow>
        <DataTable<StrategyRow>
          caption="전략 목록"
          columns={columns}
          rows={result.data}
          rowKey={(row) => row.strategy_id}
          detailHref={(row) => keepQuery(`/strategies/${row.strategy_id}`, context)}
          empty={
            <EmptyState
              title="배포된 전략이 없습니다"
              body="관리자가 전략 버전을 배포하면 이 목록에 표시됩니다. 실거래 전에는 섀도 모드로 검증하세요."
            />
          }
        />
      </Panel>
    </>
  );
}
