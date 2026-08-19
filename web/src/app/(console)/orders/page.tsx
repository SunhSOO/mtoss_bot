import { DetailDrawer, DrawerSection, OrderStatusTimeline } from "@/components/ui/drawer";
import {
  Button,
  Chip,
  DefinitionList,
  Money,
  PageHeader,
  Panel,
  Quantity,
  SignedMoney,
  Timestamp,
  cx,
} from "@/components/ui/primitives";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  NoticeBanner,
  NoticeList,
  RiskUsageBar,
  SkeletonPage,
  StatusBadge,
  ToneBadge,
} from "@/components/ui/status";
import { DataTable, FilterRow, Tabs, type Column } from "@/components/ui/table";
import { recheckBrokerAction } from "@/lib/actions";
import { tryGet } from "@/lib/api";
import {
  ORDER_SIDE,
  ORDER_STATE,
  ORDER_STATE_TONE,
  SOURCE_TYPE,
} from "@/lib/labels";
import { canAct } from "@/lib/nav";
import { keepQuery, requestContext } from "@/lib/request";
import { ratioToPercent } from "@/lib/format";
import type {
  FillRow,
  OrderDetail,
  OrderRow,
  OrdersPayload,
  PositionRow,
  ReconciliationRow,
} from "@/lib/types";

const TABS = [
  { id: "orders", label: "주문" },
  { id: "fills", label: "체결" },
  { id: "positions", label: "포지션" },
  { id: "reconciliation", label: "정합성 이슈" },
];

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function OrdersPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const context = await requestContext();
  const params = await searchParams;
  const tab = one(params.tab) ?? "orders";
  const detailId = one(params.detail);

  if (context.state === "loading") return <SkeletonPage title="주문·포지션" />;

  const result = await tryGet<OrdersPayload>("/console/v1/orders", { state: context.state });
  if (!result.ok) {
    if (result.error.status === 403) return <ForbiddenState />;
    return (
      <ErrorState
        title="주문 정보를 불러오지 못했습니다"
        body={`${result.error.message} 이미 접수된 주문에는 영향이 없습니다. 잠시 후 다시 시도해 주세요.`}
        retryHref={keepQuery("/orders", context, { tab })}
      />
    );
  }

  const data = result.data;
  const detail = detailId
    ? await tryGet<OrderDetail>(`/console/v1/orders/${detailId}`, { state: context.state })
    : null;

  return (
    <>
      <PageHeader
        title="주문·포지션"
        description="브로커 확인값이 최종 사실입니다. 결과가 정해지지 않은 주문은 실패와 다르게 표시합니다."
        actions={<Timestamp value={`기준 ${data.as_of}`} />}
      />

      <NoticeList notices={data.notices} />

      <Panel>
        <Tabs
          items={[
            { id: "orders", label: "주문", count: data.orders.length },
            { id: "fills", label: "체결", count: data.fills.length },
            { id: "positions", label: "포지션", count: data.positions.length },
            {
              id: "reconciliation",
              label: "정합성 이슈",
              count: data.reconciliation.length,
            },
          ]}
          current={tab}
          hrefFor={(id) => keepQuery("/orders", context, { tab: id, detail: undefined })}
        />
        <FilterRow>
          <span className="text-xs text-secondary">필터</span>
          <Chip>계좌 · 전체</Chip>
          <Chip>신호원 · 전체</Chip>
          <Chip>기간 · 오늘</Chip>
          <span className="ml-auto text-xs text-secondary">숫자는 오른쪽 정렬</span>
        </FilterRow>

        {tab === "orders" && (
          <DataTable<OrderRow>
            caption="주문 목록"
            columns={orderColumns}
            rows={data.orders}
            rowKey={(row) => row.order_id}
            detailHref={(row) =>
              keepQuery("/orders", context, { tab: "orders", detail: row.order_id })
            }
            empty={<EmptyState title="주문이 없습니다" body="승인된 신호가 생기면 주문이 표시됩니다." />}
          />
        )}
        {tab === "fills" && (
          <DataTable<FillRow>
            caption="체결 목록"
            columns={fillColumns}
            rows={data.fills}
            rowKey={(row) => row.fill_id}
            empty={<EmptyState title="체결이 없습니다" body="체결이 발생하면 여기에 기록됩니다." />}
          />
        )}
        {tab === "positions" && (
          <DataTable<PositionRow>
            caption="포지션 목록"
            columns={positionColumns}
            rows={data.positions}
            rowKey={(row) => row.position_id}
            empty={<EmptyState title="보유 포지션이 없습니다" body="브로커 확인값 기준입니다." />}
          />
        )}
        {tab === "reconciliation" && (
          <ReconciliationList rows={data.reconciliation} />
        )}
      </Panel>

      {detail && detail.ok && (
        <OrderDrawer
          detail={detail.data}
          closeHref={keepQuery("/orders", context, { tab, detail: undefined })}
          canAct={canAct(context.role)}
        />
      )}
    </>
  );
}

const orderColumns: Column<OrderRow>[] = [
  {
    key: "time",
    header: "시각",
    render: (row) => <Timestamp value={row.occurred_at} />,
  },
  { key: "account", header: "계좌", render: (row) => row.account_alias },
  {
    key: "source",
    header: "신호원",
    secondary: true,
    render: (row) => (
      <span>
        {SOURCE_TYPE[row.source_type]}
        <span className="ml-1 text-xs text-secondary">{row.source_name}</span>
      </span>
    ),
  },
  {
    key: "symbol",
    header: "종목",
    render: (row) => (
      <span>
        {row.symbol_name}
        <span className="num ml-1.5 text-xs text-secondary">{row.symbol}</span>
      </span>
    ),
  },
  {
    key: "side",
    header: "매수·매도",
    render: (row) => (
      <span className={cx(row.side === "BUY" ? "text-up" : "text-down")}>
        {ORDER_SIDE[row.side]}
      </span>
    ),
  },
  {
    key: "quantity",
    header: "주문 수량",
    numeric: true,
    render: (row) => <Quantity value={row.quantity} />,
  },
  {
    key: "filled",
    header: "체결 수량",
    numeric: true,
    render: (row) => <Quantity value={row.filled_quantity} />,
  },
  {
    key: "average",
    header: "평균 체결가",
    numeric: true,
    render: (row) =>
      row.average_price ? (
        <Money value={row.average_price} currency={row.currency} />
      ) : (
        <span className="text-secondary">—</span>
      ),
  },
  {
    key: "state",
    header: "상태",
    render: (row) => (
      <ToneBadge tone={ORDER_STATE_TONE[row.state]}>{ORDER_STATE[row.state]}</ToneBadge>
    ),
  },
  {
    key: "broker",
    header: "브로커 요청 ID",
    secondary: true,
    render: (row) => <span className="num text-xs text-secondary">{row.broker_request_id}</span>,
  },
];

const fillColumns: Column<FillRow>[] = [
  { key: "time", header: "시각", render: (row) => <Timestamp value={row.occurred_at} /> },
  { key: "account", header: "계좌", render: (row) => row.account_alias },
  {
    key: "symbol",
    header: "종목",
    render: (row) => `${row.symbol_name} (${row.symbol})`,
  },
  {
    key: "side",
    header: "매수·매도",
    render: (row) => (
      <span className={cx(row.side === "BUY" ? "text-up" : "text-down")}>
        {ORDER_SIDE[row.side]}
      </span>
    ),
  },
  {
    key: "quantity",
    header: "체결 수량",
    numeric: true,
    render: (row) => <Quantity value={row.quantity} />,
  },
  {
    key: "price",
    header: "체결가",
    numeric: true,
    render: (row) => <Money value={row.price} currency={row.currency} />,
  },
  {
    key: "fee",
    header: "수수료",
    numeric: true,
    secondary: true,
    render: (row) => <Money value={row.fee} currency={row.currency} />,
  },
];

const positionColumns: Column<PositionRow>[] = [
  { key: "account", header: "계좌", render: (row) => row.account_alias },
  {
    key: "symbol",
    header: "종목",
    render: (row) => (
      <span>
        {row.symbol_name}
        <span className="num ml-1.5 text-xs text-secondary">{row.symbol}</span>
      </span>
    ),
  },
  {
    key: "quantity",
    header: "수량",
    numeric: true,
    render: (row) => <Quantity value={row.quantity} />,
  },
  {
    key: "average",
    header: "평균 단가",
    numeric: true,
    render: (row) => <Money value={row.average_price} currency={row.currency} />,
  },
  {
    key: "last",
    header: "현재가",
    numeric: true,
    render: (row) => <Money value={row.last_price} currency={row.currency} />,
  },
  {
    key: "pnl",
    header: "평가 손익",
    numeric: true,
    render: (row) => <SignedMoney value={row.unrealised_pnl} currency={row.currency} />,
  },
  {
    key: "weight",
    header: "비중",
    numeric: true,
    render: (row) => <span className="num">{ratioToPercent(row.weight)}%</span>,
  },
  {
    key: "confirmed",
    header: "확인",
    secondary: true,
    render: (row) => <span className="text-xs text-secondary">{row.confirmed_note}</span>,
  },
];

function ReconciliationList({ rows }: { rows: ReconciliationRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="정합성 이슈가 없습니다"
        body="내부 기록과 브로커 확인값이 일치합니다."
      />
    );
  }
  return (
    <ul className="flex flex-col">
      {rows.map((row) => (
        <li key={row.issue_id} className="border-b border-line p-4 last:border-0">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h3>{row.kind}</h3>
              <p className="mt-0.5 text-xs text-secondary">
                {row.account_alias} · {row.symbol_name}
                <span className="num ml-1.5">{row.symbol}</span>
              </p>
            </div>
            <Chip tone="warning">{row.status}</Chip>
          </div>
          <dl className="mt-2.5 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs text-secondary">내부 기록</dt>
              <dd className="num">{row.internal_value}</dd>
            </div>
            <div>
              <dt className="text-xs text-secondary">브로커 확인값</dt>
              <dd className="num">{row.broker_value}</dd>
            </div>
            <div>
              <dt className="text-xs text-secondary">감지 시각</dt>
              <dd className="num">{row.detected_at}</dd>
            </div>
          </dl>
          <p className="mt-2 text-sm text-secondary">{row.guidance}</p>
        </li>
      ))}
    </ul>
  );
}

function OrderDrawer({
  detail,
  closeHref,
  canAct: allowed,
}: {
  detail: OrderDetail;
  closeHref: string;
  canAct: boolean;
}) {
  const row = detail.row;
  return (
    <DetailDrawer
      title={`${row.symbol_name} ${ORDER_SIDE[row.side]} 주문`}
      subtitle={`${row.account_alias} · ${row.broker_request_id}`}
      closeHref={closeHref}
      footer={
        // UNKNOWN 주문에는 재주문 버튼을 만들지 않는다. 브로커 상태 재확인만 제공한다 (§7.8).
        detail.can_recheck_broker && allowed ? (
          <form action={recheckBrokerAction} className="flex flex-col gap-2">
            <input type="hidden" name="order_id" value={row.order_id} />
            <Button type="submit" variant="secondary" className="w-full">
              브로커 상태 다시 확인
            </Button>
            <p className="text-xs text-secondary">
              같은 주문을 다시 보내지 않습니다. 결과가 정해질 때까지 이 종목의 신규 주문은
              일시정지됩니다.
            </p>
          </form>
        ) : null
      }
    >
      {detail.guidance && <NoticeBanner notice={detail.guidance} />}

      <DrawerSection title="주문 상태">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <ToneBadge tone={ORDER_STATE_TONE[row.state]}>{ORDER_STATE[row.state]}</ToneBadge>
          <span className="num text-xs text-secondary">
            {row.filled_quantity}/{row.quantity} 체결
          </span>
        </div>
        <OrderStatusTimeline steps={detail.timeline} />
      </DrawerSection>

      <DrawerSection title="주문 내용">
        <DefinitionList
          items={[
            { term: "시각", value: <Timestamp value={row.occurred_at} /> },
            {
              term: "신호원",
              value: `${SOURCE_TYPE[row.source_type]} · ${row.source_name}`,
            },
            {
              term: "수량 · 체결",
              value: (
                <span className="num">
                  {row.quantity} · {row.filled_quantity}
                </span>
              ),
            },
            {
              term: "평균 체결가",
              value: row.average_price ? (
                <Money value={row.average_price} currency={row.currency} />
              ) : (
                "—"
              ),
            },
            { term: "승인자", value: detail.approved_by ?? "자동 승인" },
            {
              term: "브로커 요청 ID",
              value: <span className="num">{row.broker_request_id}</span>,
            },
          ]}
        />
      </DrawerSection>

      <DrawerSection title="위험검사">
        <ul className="flex flex-col gap-3">
          {detail.risk_checks.map((check) => (
            <li key={check.metric}>
              <div className="flex items-baseline justify-between gap-2 text-xs">
                <span>{check.label}</span>
                <span className="num text-secondary">
                  {check.actual} / {check.limit} {check.unit}
                </span>
              </div>
              <RiskUsageBar usage={check.usage_percent} label={check.label} />
            </li>
          ))}
        </ul>
      </DrawerSection>

      <DrawerSection title="원본 신호와 실행 의도">
        <p className="text-sm text-secondary">{detail.signal_summary}</p>
        <p className="mt-1.5 text-sm text-secondary">{detail.intent_summary}</p>
      </DrawerSection>

      <DrawerSection title="브로커 응답과 정합성">
        <p className="num text-sm">{detail.broker_response}</p>
        <p className="mt-1.5 text-sm text-secondary">{detail.reconciliation}</p>
      </DrawerSection>
    </DetailDrawer>
  );
}
