import { WeightCompareBars } from "@/components/charts/charts";
import { DetailDrawer, DrawerSection } from "@/components/ui/drawer";
import {
  Button,
  Chip,
  DefinitionList,
  LinkButton,
  Money,
  PageHeader,
  Panel,
  Quantity,
  Timestamp,
  cx,
} from "@/components/ui/primitives";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  NoticeList,
  RiskUsageBar,
  SkeletonPage,
  ToneBadge,
} from "@/components/ui/status";
import { FilterRow } from "@/components/ui/table";
import { tryGet } from "@/lib/api";
import { decideApprovalAction, recheckApprovalAction } from "@/lib/actions";
import { APPROVAL_MODE, APPROVAL_STATUS, ORDER_SIDE, SOURCE_TYPE } from "@/lib/labels";
import { canAct } from "@/lib/nav";
import { keepQuery, requestContext } from "@/lib/request";
import type { ApprovalDetail, ApprovalSummary } from "@/lib/types";

export default async function ApprovalsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const context = await requestContext();
  const params = await searchParams;
  const detailIdRaw = params.detail;
  const detailId = Array.isArray(detailIdRaw) ? detailIdRaw[0] : detailIdRaw;

  if (context.state === "loading") return <SkeletonPage title="승인함" />;

  const result = await tryGet<ApprovalSummary[]>("/console/v1/approvals", {
    state: context.state,
  });
  if (!result.ok) {
    if (result.error.status === 403) return <ForbiddenState />;
    return (
      <ErrorState
        title="승인 목록을 불러오지 못했습니다"
        body={`${result.error.message} 승인이나 주문은 진행되지 않았습니다. 잠시 후 다시 시도해 주세요.`}
        retryHref={keepQuery("/approvals", context)}
      />
    );
  }

  const rows = result.data;
  const detail = detailId
    ? await tryGet<ApprovalDetail>(`/console/v1/approvals/${detailId}`, {
        state: context.state,
      })
    : null;

  return (
    <>
      <PageHeader
        title="승인함"
        description="만료가 임박한 순서로 정렬됩니다. 목록에서 바로 승인하지 않고 상세에서 조건을 확인한 뒤 승인합니다."
        actions={<Timestamp value={`대기 ${rows.length}건`} />}
      />

      <Panel>
        <FilterRow>
          <span className="text-xs text-secondary">필터</span>
          <Chip>계좌 · 전체</Chip>
          <Chip>신호원 · 전체</Chip>
          <Chip>시장 · 전체</Chip>
          <Chip>상태 · 승인 대기</Chip>
          <span className="ml-auto text-xs text-secondary">정렬 · 만료 임박 순</span>
        </FilterRow>
        {rows.length === 0 ? (
          <EmptyState
            title="승인할 요청이 없습니다"
            body="신호가 도착하면 만료 임박 순으로 이곳에 쌓입니다. 자동 승인 범위는 위험 설정에서 조정할 수 있습니다."
            actionLabel="위험 설정 열기"
            actionHref={keepQuery("/risk", context)}
          />
        ) : (
          <ul className="flex flex-col">
            {rows.map((row) => (
              <li key={row.approval_id} className="border-b border-line p-4 last:border-0">
                <ApprovalCard
                  row={row}
                  detailHref={keepQuery("/approvals", context, { detail: row.approval_id })}
                />
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {detail && detail.ok && (
        <ApprovalDrawer
          detail={detail.data}
          closeHref={keepQuery("/approvals", context, { detail: undefined })}
          canAct={canAct(context.role)}
        />
      )}
      {detail && !detail.ok && (
        <DetailDrawer
          title="승인 상세"
          closeHref={keepQuery("/approvals", context, { detail: undefined })}
        >
          <ErrorState
            title="승인 상세를 불러오지 못했습니다"
            body={`${detail.error.message} 승인은 진행되지 않았습니다.`}
            retryHref={keepQuery("/approvals", context, { detail: detailId })}
          />
        </DetailDrawer>
      )}
    </>
  );
}

/**
 * 요약 카드. 기본 행동은 `상세 검토`이며 목록에서 즉시 승인하는 기능은 제공하지 않는다 (§6).
 */
function ApprovalCard({ row, detailHref }: { row: ApprovalSummary; detailHref: string }) {
  const urgent = row.expires_in_seconds < 120;
  return (
    <article className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="flex flex-wrap items-baseline gap-1.5">
            {row.symbol_name}
            <span className="num text-xs font-normal text-secondary">{row.symbol}</span>
            <span
              className={cx(
                "text-sm font-semibold",
                row.side === "BUY" ? "text-up" : "text-down",
              )}
            >
              {ORDER_SIDE[row.side]}
            </span>
          </h3>
          <p className="mt-0.5 text-xs text-secondary">
            {SOURCE_TYPE[row.source_type]} · {row.source_name} · {row.account_alias} ·{" "}
            {APPROVAL_MODE[row.approval_mode]}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Chip tone={row.status === "PENDING" ? "warning" : "neutral"}>
            {APPROVAL_STATUS[row.status]}
          </Chip>
          <Chip tone={urgent ? "critical" : "warning"}>만료 {row.expires_label}</Chip>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs text-secondary">예상 수량</dt>
          <dd>
            <Quantity value={row.quantity} unit={row.market === "FX" ? "랏" : "주"} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-secondary">예상 금액</dt>
          <dd>
            <Money value={row.notional} currency={row.currency} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-secondary">현재가</dt>
          <dd>
            <Money value={row.current_price} currency={row.currency} />
          </dd>
        </div>
        <div>
          <dt className="text-xs text-secondary">신호 당시</dt>
          <dd>
            <Money value={row.signal_price} currency={row.currency} />
          </dd>
        </div>
      </dl>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <ToneBadge tone={row.risk_passed ? "ok" : "warning"}>{row.risk_note}</ToneBadge>
        <LinkButton href={detailHref} variant="primary">
          상세 검토
        </LinkButton>
      </div>
    </article>
  );
}

function ApprovalDrawer({
  detail,
  closeHref,
  canAct: allowed,
}: {
  detail: ApprovalDetail;
  closeHref: string;
  canAct: boolean;
}) {
  const row = detail.summary;
  const decided = row.status !== "PENDING";
  const conditionsChanged = detail.notices.some((n) => n.notice_id === "n-recheck");
  const priceMoved = row.current_price !== row.signal_price;

  return (
    <DetailDrawer
      title={`${row.symbol_name} ${ORDER_SIDE[row.side]} 승인 검토`}
      subtitle={`${SOURCE_TYPE[row.source_type]} · ${row.source_name} · ${row.account_alias}`}
      closeHref={closeHref}
      footer={
        allowed ? (
          <div className="flex flex-col gap-2">
            {!decided && (
              <form action={recheckApprovalAction}>
                <input type="hidden" name="approval_id" value={row.approval_id} />
                <Button type="submit" variant="secondary" className="w-full">
                  가격·계좌 상태 재검사
                </Button>
              </form>
            )}
            <div className="flex gap-2">
              <form action={decideApprovalAction} className="flex-1">
                <input type="hidden" name="approval_id" value={row.approval_id} />
                <input type="hidden" name="decision" value="REJECT" />
                <Button type="submit" variant="critical" className="w-full" disabled={decided}>
                  거절
                </Button>
              </form>
              <form action={decideApprovalAction} className="flex-1">
                <input type="hidden" name="approval_id" value={row.approval_id} />
                <input type="hidden" name="decision" value="APPROVE" />
                <Button type="submit" variant="primary" className="w-full" disabled={decided}>
                  {conditionsChanged ? "새 값으로 승인" : "승인"}
                </Button>
              </form>
            </div>
            <p className="text-xs text-secondary">
              승인을 누르면 가격과 계좌 상태를 다시 검사합니다. 값이 바뀌면 새 값으로 다시
              확인받습니다.
            </p>
          </div>
        ) : (
          <p className="text-xs text-secondary">
            조회 전용 역할은 승인·거절을 할 수 없습니다.
          </p>
        )
      }
    >
      <NoticeList notices={detail.notices} />

      <DrawerSection title="신호와 유효시간">
        <DefinitionList
          items={[
            { term: "신호원", value: `${SOURCE_TYPE[row.source_type]} · ${row.source_name}` },
            { term: "생성 시각", value: <Timestamp value={detail.created_at} /> },
            { term: "만료 시각", value: <Timestamp value={detail.expires_at} /> },
            {
              term: "남은 시간",
              value: (
                <span className={row.expires_in_seconds < 120 ? "text-critical" : ""}>
                  {row.expires_label}
                </span>
              ),
            },
          ]}
        />
      </DrawerSection>

      <DrawerSection title="대상 계좌와 종목">
        <DefinitionList
          items={[
            { term: "계좌", value: row.account_alias },
            { term: "종목", value: `${row.symbol_name} (${row.symbol})` },
            {
              term: "현재 보유량 → 목표 보유량",
              value: (
                <span className="num">
                  {detail.current_quantity} → {detail.target_quantity}
                </span>
              ),
            },
            { term: "승인 모드", value: APPROVAL_MODE[row.approval_mode] },
          ]}
        />
      </DrawerSection>

      <DrawerSection title="예상 주문">
        <DefinitionList
          items={[
            {
              term: "수량",
              value: <Quantity value={row.quantity} unit={row.market === "FX" ? "랏" : "주"} />,
            },
            { term: "금액", value: <Money value={row.notional} currency={row.currency} /> },
            {
              term: "예상 수수료",
              value: <Money value={detail.estimated_fee} currency={row.currency} />,
            },
            {
              term: "현재가 · 신호 당시",
              value: (
                <span className={priceMoved ? "text-warn" : ""}>
                  <Money value={row.current_price} currency={row.currency} /> ·{" "}
                  <Money value={row.signal_price} currency={row.currency} />
                </span>
              ),
              hint: priceMoved ? "신호 생성 이후 가격이 움직였습니다." : undefined,
            },
          ]}
        />
      </DrawerSection>

      <DrawerSection title="위험검사와 한도 사용률">
        <ul className="flex flex-col gap-3">
          {detail.risk_checks.map((check) => (
            <li key={check.metric}>
              <div className="flex items-baseline justify-between gap-2 text-xs">
                <span>
                  {check.label}
                  <span className="ml-1.5 text-secondary">{check.scope}</span>
                </span>
                <span className="num text-secondary">
                  {check.actual} / {check.limit} {check.unit}
                </span>
              </div>
              <RiskUsageBar usage={check.usage_percent} label={check.label} />
            </li>
          ))}
        </ul>
      </DrawerSection>

      <DrawerSection title="주문 후 예상 포트폴리오">
        <WeightCompareBars rows={detail.portfolio_after} asOf={detail.created_at} />
      </DrawerSection>

      {detail.decided_reason && (
        <DrawerSection title="처리 결과">
          <p className="text-sm">
            {APPROVAL_STATUS[row.status]} · {detail.decided_reason}
          </p>
        </DrawerSection>
      )}
    </DetailDrawer>
  );
}
