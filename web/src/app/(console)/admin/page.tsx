import {
  Button,
  Chip,
  PageHeader,
  Panel,
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
} from "@/components/ui/status";
import { DataTable, Tabs, type Column } from "@/components/ui/table";
import {
  emergencyStopAction,
  liquidateAllAction,
  resetConsoleAction,
  resumeAllAction,
} from "@/lib/actions";
import { tryGet } from "@/lib/api";
import { ratioToPercent } from "@/lib/format";
import { APPROVAL_MODE, MARKET, ROLE, STRATEGY_MODE } from "@/lib/labels";
import { canAdminister } from "@/lib/nav";
import { keepQuery, requestContext } from "@/lib/request";
import type {
  AdminPayload,
  AdminUserRow,
  ControlsPayload,
  CopySourceRow,
  ReconciliationRow,
  StrategyRow,
} from "@/lib/types";

const TABS = [
  { id: "users", label: "사용자·역할" },
  { id: "deployments", label: "전략 배포" },
  { id: "providers", label: "신호 공급자" },
  { id: "mappings", label: "13F·CUSIP 검토" },
  { id: "system", label: "시스템 상태" },
  { id: "emergency", label: "전체 긴급 제어" },
];

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function AdminPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const context = await requestContext();
  const params = await searchParams;
  const tab = one(params.tab) ?? "users";
  const step = one(params.step);

  if (!canAdminister(context.role)) return <ForbiddenState />;
  if (context.state === "loading") return <SkeletonPage title="관리자" />;

  const [adminResult, controlsResult] = await Promise.all([
    tryGet<AdminPayload>("/console/v1/admin", { state: context.state }),
    tryGet<ControlsPayload>("/console/v1/controls", { state: context.state }),
  ]);

  if (!adminResult.ok) {
    if (adminResult.error.status === 403) return <ForbiddenState />;
    return (
      <ErrorState
        title="관리자 정보를 불러오지 못했습니다"
        body={`${adminResult.error.message} 설정은 바뀌지 않았습니다.`}
        retryHref={keepQuery("/admin", context, { tab })}
      />
    );
  }

  const data = adminResult.data;
  const controls = controlsResult.ok ? controlsResult.data : null;

  return (
    <>
      <PageHeader
        title="관리자"
        description="일상적인 관리 기능과 전체 긴급 제어는 같은 비중으로 섞지 않습니다."
        actions={
          <form action={resetConsoleAction}>
            <Button type="submit" dense>
              목업 상태 초기화
            </Button>
          </form>
        }
      />

      <NoticeList notices={data.notices} />

      <Panel>
        <Tabs
          items={TABS}
          current={tab}
          hrefFor={(id) => keepQuery("/admin", context, { tab: id, step: undefined })}
        />

        {tab === "users" && (
          <DataTable<AdminUserRow>
            caption="사용자와 역할"
            columns={userColumns}
            rows={data.users}
            rowKey={(row) => row.user_id}
          />
        )}
        {tab === "deployments" && (
          <DataTable<StrategyRow>
            caption="전략 배포"
            columns={deploymentColumns}
            rows={data.deployments}
            rowKey={(row) => row.strategy_id}
          />
        )}
        {tab === "providers" && (
          <DataTable<CopySourceRow>
            caption="신호 공급자"
            columns={providerColumns}
            rows={data.providers}
            rowKey={(row) => row.source_id}
          />
        )}
        {tab === "mappings" &&
          (data.mappings.length === 0 ? (
            <EmptyState title="검토할 매핑이 없습니다" body="새 13F 공시가 들어오면 표시됩니다." />
          ) : (
            <DataTable<ReconciliationRow>
              caption="13F CUSIP 매핑 검토"
              columns={mappingColumns}
              rows={data.mappings}
              rowKey={(row) => row.issue_id}
            />
          ))}
        {tab === "system" && (
          <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-4">
            {data.system.map((tile) => (
              <MetricSummary key={tile.key} tile={tile} />
            ))}
          </div>
        )}
        {tab === "emergency" && controls && (
          <EmergencyControls controls={controls} context={context} step={step} />
        )}
      </Panel>
    </>
  );
}

const userColumns: Column<AdminUserRow>[] = [
  { key: "name", header: "이름", render: (row) => row.name },
  {
    key: "email",
    header: "이메일",
    secondary: true,
    render: (row) => <span className="text-secondary">{row.email}</span>,
  },
  { key: "role", header: "역할", render: (row) => <Chip>{ROLE[row.role]}</Chip> },
  { key: "mfa", header: "MFA", render: (row) => row.mfa },
  {
    key: "login",
    header: "마지막 로그인",
    render: (row) => <Timestamp value={row.last_login} />,
  },
  { key: "status", header: "상태", render: (row) => row.status },
];

const deploymentColumns: Column<StrategyRow>[] = [
  { key: "name", header: "전략", render: (row) => row.name },
  { key: "version", header: "버전", render: (row) => <span className="num">{row.version}</span> },
  { key: "market", header: "시장", render: (row) => MARKET[row.market] },
  { key: "mode", header: "운영 모드", render: (row) => STRATEGY_MODE[row.mode] },
  {
    key: "accounts",
    header: "실행 계좌",
    numeric: true,
    render: (row) => <span className="num">{row.account_count}</span>,
  },
  {
    key: "status",
    header: "상태",
    render: (row) => <StatusBadge status={row.status} showTime={false} />,
  },
];

const providerColumns: Column<CopySourceRow>[] = [
  { key: "name", header: "공급자", render: (row) => row.name },
  { key: "kind", header: "유형", render: (row) => row.kind_label },
  {
    key: "signal",
    header: "마지막 신호",
    render: (row) => <Timestamp value={row.last_signal_at} />,
  },
  {
    key: "status",
    header: "상태",
    render: (row) => <StatusBadge status={row.status} showTime={false} />,
  },
  { key: "mode", header: "승인 모드", render: (row) => APPROVAL_MODE[row.approval_mode] },
  {
    key: "weight",
    header: "목표 비중",
    numeric: true,
    render: (row) => <span className="num">{ratioToPercent(row.target_weight)}%</span>,
  },
];

const mappingColumns: Column<ReconciliationRow>[] = [
  { key: "kind", header: "유형", render: (row) => row.kind },
  { key: "symbol", header: "대상", render: (row) => row.symbol_name },
  { key: "internal", header: "내부", render: (row) => row.internal_value },
  { key: "broker", header: "브로커", render: (row) => row.broker_value },
  { key: "status", header: "상태", render: (row) => <Chip tone="warning">{row.status}</Chip> },
  {
    key: "guidance",
    header: "안내",
    secondary: true,
    render: (row) => <span className="text-secondary">{row.guidance}</span>,
  },
];

/**
 * 긴급 정지와 전량 청산은 다른 흐름이다. 같은 화면에 있되 시각적으로 분리하고,
 * 전량 청산은 확인 문구 입력과 재인증을 모두 요구한다 (§8 흐름 D).
 */
function EmergencyControls({
  controls,
  context,
  step,
}: {
  controls: ControlsPayload;
  context: Awaited<ReturnType<typeof requestContext>>;
  step: string | undefined;
}) {
  const progress =
    controls.cancel_progress_total > 0
      ? Math.round((controls.cancel_progress_done / controls.cancel_progress_total) * 100)
      : 0;

  return (
    <div className="flex flex-col gap-5 p-4">
      <section className="rounded-panel border border-critical/55 p-4">
        <header className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-critical">전체 긴급 정지</h3>
            <p className="mt-0.5 text-xs text-secondary">
              적용 범위: 내 모든 계좌와 신호원
            </p>
          </div>
          <Chip tone={controls.emergency_stop ? "critical" : "neutral"}>
            {controls.emergency_stop ? "적용 중" : "해제됨"}
          </Chip>
        </header>

        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="rounded border border-line p-3">
            <p className="text-xs font-semibold">즉시 발생하는 일</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-secondary">
              <li>모든 신규 주문 생성과 제출이 차단됩니다.</li>
              <li>미체결 주문의 취소가 시작됩니다.</li>
              <li>모든 화면 상단에 닫을 수 없는 경고가 표시됩니다.</li>
            </ul>
          </div>
          <div className="rounded border border-line p-3">
            <p className="text-xs font-semibold">발생하지 않는 일</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-secondary">
              <li>보유 포지션을 청산하지 않습니다.</li>
              <li>계좌 연결이나 자격증명을 해제하지 않습니다.</li>
              <li>이미 체결된 주문을 되돌리지 않습니다.</li>
            </ul>
          </div>
        </div>

        {controls.emergency_stop && (
          <div className="mt-3">
            <p className="text-xs text-secondary">
              미체결 취소 진행률{" "}
              <span className="num">
                {controls.cancel_progress_done}/{controls.cancel_progress_total}
              </span>
              {controls.stopped_at && (
                <>
                  {" · 정지 시각 "}
                  <span className="num">{controls.stopped_at}</span>
                </>
              )}
            </p>
            <div
              className="mt-1 h-2 w-full overflow-hidden rounded-full bg-subtle"
              role="meter"
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="미체결 주문 취소 진행률"
            >
              <div className="h-full rounded-full bg-critical" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        <div className="mt-4">
          {controls.emergency_stop ? (
            <form action={resumeAllAction}>
              <Button type="submit" variant="primary">
                전체 긴급 정지 해제
              </Button>
            </form>
          ) : (
            <form action={emergencyStopAction} className="flex flex-col gap-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  name="reauthenticated"
                  className="h-4 w-4 rounded border-line"
                />
                MFA 또는 패스키로 재인증했습니다
              </label>
              <div>
                <Button type="submit" variant="critical">
                  전체 긴급 정지 실행
                </Button>
              </div>
              <p className="text-xs text-secondary">
                재인증 없이는 실행되지 않습니다. 포지션은 청산되지 않습니다.
              </p>
            </form>
          )}
        </div>
      </section>

      <hr className="border-line" />

      <section
        className={cx(
          "rounded-panel border-2 border-dashed border-critical p-4",
          "bg-critical/[0.04]",
        )}
      >
        <header>
          <h3 className="text-critical">전량 청산 — 긴급 정지와 별개입니다</h3>
          <p className="mt-1 text-xs text-secondary">
            보유 포지션을 시장에 매도합니다. 시장 폐장, 거래 정지, 유동성 부족으로 일부 청산이
            실패할 수 있으며 주문별로 결과를 추적해야 합니다.
          </p>
        </header>

        {step !== "confirm" ? (
          <div className="mt-4">
            <a
              href={keepQuery("/admin", context, { tab: "emergency", step: "confirm" })}
              className="inline-flex h-10 items-center rounded-md border border-critical px-3 text-sm font-medium text-critical hover:bg-critical/10"
            >
              전량 청산 절차 시작
            </a>
          </div>
        ) : (
          <form action={liquidateAllAction} className="mt-4 flex flex-col gap-3">
            <div className="rounded border border-line bg-surface p-3">
              <p className="text-xs font-semibold">대상 계좌</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-secondary">
                <li>국내주식 주계좌 — 현재 정규장 마감, 청산 실패 가능</li>
                <li>미국주식 장기계좌 — 정규장 진행 중</li>
                <li>MT5 FX 데모 — 거래 가능</li>
              </ul>
            </div>
            <label className="flex flex-col gap-1 text-sm">
              <span>
                확인 문구를 정확히 입력하세요:{" "}
                <span className="font-semibold">{controls.confirm_phrase}</span>
              </span>
              <input
                name="confirm_phrase"
                required
                autoComplete="off"
                placeholder={controls.confirm_phrase}
                className="h-10 w-full max-w-xs rounded border border-line bg-surface px-3 text-sm"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                name="reauthenticated"
                required
                className="h-4 w-4 rounded border-line"
              />
              MFA 또는 패스키로 재인증했습니다
            </label>
            <div className="flex gap-2">
              <Button type="submit" variant="critical">
                전량 청산 최종 실행
              </Button>
              <a
                href={keepQuery("/admin", context, { tab: "emergency", step: undefined })}
                className="inline-flex h-10 items-center rounded-md border border-line px-3 text-sm hover:bg-subtle"
              >
                취소
              </a>
            </div>
            <p className="text-xs text-secondary">
              확인 문구와 재인증이 모두 있어야 실행됩니다. Enter 한 번으로는 실행되지 않습니다.
            </p>
          </form>
        )}

        {controls.liquidation_running && (
          <div className="mt-4">
            <p className="text-xs font-semibold">주문별 결과</p>
            <ul className="mt-1.5 flex flex-col gap-1.5">
              {controls.liquidation_results.map((item) => (
                <li
                  key={item.issue_id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded border border-line bg-surface px-3 py-2 text-xs"
                >
                  <span>
                    {item.account_alias} · {item.symbol_name}
                    <span className="num ml-1.5 text-secondary">{item.internal_value}</span>
                  </span>
                  <Chip tone={item.status === "실패" ? "critical" : "warning"}>
                    {item.status}
                  </Chip>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
