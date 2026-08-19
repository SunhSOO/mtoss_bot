import Link from "next/link";

import { DailyPnlBars, DrawdownArea, NetAssetLine } from "@/components/charts/charts";
import {
  Chip,
  LinkButton,
  PageHeader,
  Panel,
  SignedMoney,
  SignedPercent,
  Money,
  Timestamp,
  cx,
} from "@/components/ui/primitives";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  MetricSummary,
  NoticeList,
  SkeletonPage,
  StatusBadge,
  ToneBadge,
} from "@/components/ui/status";
import { tryGet } from "@/lib/api";
import { AUTO_TRADING, ORDER_STATE, ORDER_STATE_TONE, SOURCE_TYPE } from "@/lib/labels";
import { keepQuery, requestContext } from "@/lib/request";
import type { DashboardPayload } from "@/lib/types";

export default async function DashboardPage() {
  const context = await requestContext();

  if (context.state === "loading") {
    return <SkeletonPage title="대시보드" />;
  }

  const result = await tryGet<DashboardPayload>("/console/v1/dashboard", {
    state: context.state,
  });

  if (!result.ok) {
    if (result.error.status === 403) return <ForbiddenState />;
    return (
      <ErrorState
        title="대시보드를 불러오지 못했습니다"
        body={`${result.error.message} 주문에는 영향이 없습니다. 잠시 후 다시 시도해 주세요.`}
        retryHref={keepQuery("/dashboard", context)}
      />
    );
  }

  const data = result.data;
  const hasAccounts = data.accounts.length > 0;

  return (
    <>
      <PageHeader
        title="대시보드"
        description="모든 계좌와 MT5 노드가 정상인지, 지금 무엇을 처리해야 하는지 먼저 보여줍니다."
        actions={<Timestamp value={`기준 ${data.as_of}`} />}
      />

      <NoticeList notices={data.notices} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.tiles.map((tile) => (
          <MetricSummary key={tile.key} tile={tile} />
        ))}
      </div>

      {!hasAccounts ? (
        <Panel>
          <EmptyState
            title="아직 연결된 계좌가 없습니다"
            body="토스 계좌나 MT5 노드를 연결하면 순자산, 손익, 노드 상태가 이 화면에 표시됩니다. 실거래는 섀도 모드를 거친 뒤 활성화하세요."
            actionLabel="토스 계좌 연결"
            actionHref={keepQuery("/connections", context)}
          />
        </Panel>
      ) : (
        <div className="grid gap-4 xl:grid-cols-3">
          <Panel
            title="계좌 합산 성과"
            description="예상값이 아닌 브로커 확인값입니다."
            className="xl:col-span-2"
          >
            <div className="flex flex-col gap-6 p-4">
              <NetAssetLine series={data.net_asset} />
              <DailyPnlBars series={data.daily_pnl} />
              <DrawdownArea series={data.drawdown} />
            </div>
          </Panel>

          <div className="flex flex-col gap-4">
            <Panel title="계좌 건강" description="계좌 범위 · 전체 내 계좌">
              <ul className="flex flex-col">
                {data.accounts.map((account) => (
                  <li
                    key={account.account_id}
                    className="border-b border-line px-4 py-3 last:border-0"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{account.alias}</p>
                        <p className="text-xs text-secondary">
                          {account.broker === "TOSS" ? "토스증권" : "MT5"} ·{" "}
                          {account.currency}
                        </p>
                      </div>
                      <StatusBadge status={account.status} showTime={false} />
                    </div>
                    <div className="mt-2 flex items-baseline justify-between gap-2 text-sm">
                      <Money value={account.net_asset} currency={account.currency} />
                      <span className="flex items-baseline gap-1.5">
                        <SignedMoney
                          value={account.daily_pnl}
                          currency={account.currency}
                        />
                        <SignedPercent value={account.daily_pnl_rate} />
                      </span>
                    </div>
                    {account.order_stopped && (
                      <p className="mt-1.5 text-xs text-critical">
                        이 계좌의 신규 주문이 정지되었습니다. 포지션은 유지됩니다.
                      </p>
                    )}
                    <p className="num mt-1 text-xs text-secondary">
                      {account.confirmed_note}
                    </p>
                  </li>
                ))}
              </ul>
            </Panel>

            <Panel title="MT5 노드 건강">
              <ul className="flex flex-col">
                {data.nodes.map((node) => (
                  <li key={node.node_id} className="border-b border-line px-4 py-3 last:border-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{node.name}</p>
                        <p className="text-xs text-secondary">{node.account_alias}</p>
                      </div>
                      <StatusBadge status={node.status} showTime={false} />
                    </div>
                    <p className="mt-1.5 text-xs text-secondary">
                      heartbeat {node.heartbeat_note} · {AUTO_TRADING[node.auto_trading]}
                    </p>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel
          title="승인 대기"
          description="만료 임박 순입니다. 목록에서 바로 승인하지 않습니다."
          actions={
            <LinkButton href={keepQuery("/approvals", context)} dense>
              승인함 열기
            </LinkButton>
          }
        >
          {data.approvals.length === 0 ? (
            <EmptyState
              title="승인할 요청이 없습니다"
              body="새 신호가 도착하면 만료 임박 순으로 이곳에 표시됩니다."
            />
          ) : (
            <ul className="flex flex-col">
              {data.approvals.map((approval) => (
                <li
                  key={approval.approval_id}
                  className="border-b border-line px-4 py-3 last:border-0"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {approval.symbol_name}
                        <span className="num ml-1.5 text-xs text-secondary">
                          {approval.symbol}
                        </span>
                      </p>
                      <p className="mt-0.5 text-xs text-secondary">
                        {SOURCE_TYPE[approval.source_type]} · {approval.source_name} ·{" "}
                        {approval.account_alias}
                      </p>
                    </div>
                    <Chip tone={approval.expires_in_seconds < 120 ? "critical" : "warning"}>
                      만료 {approval.expires_label}
                    </Chip>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span>
                      <span
                        className={cx(
                          "font-medium",
                          approval.side === "BUY" ? "text-up" : "text-down",
                        )}
                      >
                        {approval.side === "BUY" ? "매수" : "매도"}
                      </span>
                      <span className="num ml-1.5">{approval.quantity}주</span>
                      <span className="text-secondary"> · 예상 </span>
                      <Money value={approval.notional} currency={approval.currency} />
                    </span>
                    <LinkButton
                      href={keepQuery("/approvals", context, {
                        detail: approval.approval_id,
                      })}
                      dense
                    >
                      상세 검토
                    </LinkButton>
                  </div>
                  <p
                    className={cx(
                      "mt-1.5 text-xs",
                      approval.risk_passed ? "text-secondary" : "text-warn",
                    )}
                  >
                    {approval.risk_note}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel title="실행 중 전략·카피 소스">
            {data.running_sources.length === 0 ? (
              <EmptyState
                title="실행 중인 신호원이 없습니다"
                body="카피트레이딩 허브에서 리더 계좌나 13F 기관을 구독하면 여기에 표시됩니다."
              />
            ) : (
              <ul className="flex flex-col">
                {data.running_sources.map((source) => (
                  <li
                    key={source.source_id}
                    className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5 last:border-0"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm">
                        {source.name}
                        <span className="ml-1.5 text-xs text-secondary">
                          {source.kind_label}
                        </span>
                      </p>
                      <p className="num text-xs text-secondary">
                        마지막 정상 신호 {source.last_signal_at}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {source.paused && <Chip tone="warning">일시정지</Chip>}
                      <StatusBadge status={source.status} showTime={false} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel
            title="최근 주문·체결"
            actions={
              <LinkButton href={keepQuery("/orders", context)} dense>
                주문 전체 보기
              </LinkButton>
            }
          >
            {data.recent_orders.length === 0 ? (
              <EmptyState title="최근 주문이 없습니다" body="주문이 생성되면 여기에 표시됩니다." />
            ) : (
              <ul className="flex flex-col">
                {data.recent_orders.map((order) => (
                  <li
                    key={order.order_id}
                    className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5 last:border-0"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm">
                        <span
                          className={cx(order.side === "BUY" ? "text-up" : "text-down")}
                        >
                          {order.side === "BUY" ? "매수" : "매도"}
                        </span>{" "}
                        {order.symbol_name}
                        <span className="num ml-1.5 text-xs text-secondary">
                          {order.filled_quantity}/{order.quantity}
                        </span>
                      </p>
                      <p className="num text-xs text-secondary">{order.occurred_at}</p>
                    </div>
                    <ToneBadge tone={ORDER_STATE_TONE[order.state]}>
                      {ORDER_STATE[order.state]}
                    </ToneBadge>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      <Panel title="정합성 이슈와 알림" description="브로커 확인값과 내부 기록이 다른 항목입니다.">
        {data.issues.length === 0 ? (
          <EmptyState title="정합성 이슈가 없습니다" body="브로커 확인값과 내부 기록이 일치합니다." />
        ) : (
          <ul className="flex flex-col">
            {data.issues.map((issue) => (
              <li key={issue.issue_id} className="border-b border-line px-4 py-3 last:border-0">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="text-sm font-medium">
                    {issue.kind}
                    <span className="ml-1.5 text-xs font-normal text-secondary">
                      {issue.account_alias} · {issue.symbol_name}
                    </span>
                  </p>
                  <Chip tone="warning">{issue.status}</Chip>
                </div>
                <p className="num mt-1 text-xs text-secondary">
                  {issue.internal_value} ↔ {issue.broker_value} · {issue.detected_at}
                </p>
                <p className="mt-1 text-xs text-secondary">{issue.guidance}</p>
                <Link
                  href={keepQuery("/orders", context, { tab: "reconciliation" })}
                  className="mt-1.5 inline-block text-xs font-medium text-action underline underline-offset-2"
                >
                  정합성 이슈 열기
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </>
  );
}
