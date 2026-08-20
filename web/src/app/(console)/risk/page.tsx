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
  NoticeList,
  RiskUsageBar,
  SkeletonPage,
  StatusBadge,
  SkeletonBlock,
} from "@/components/ui/status";
import { DataTable, FilterRow, type Column } from "@/components/ui/table";
import { updateRiskLimitAction } from "@/lib/actions";
import { tryGet } from "@/lib/api";
import { RISK_METRIC, RISK_SCOPE } from "@/lib/labels";
import { canAct } from "@/lib/nav";
import { keepQuery, requestContext } from "@/lib/request";
import { percent } from "@/lib/format";
import type { RiskPayload, RiskRuleRow, RiskScope } from "@/lib/types";

const SCOPES: (RiskScope | "ALL")[] = ["ALL", "SYSTEM", "USER", "ACCOUNT", "SOURCE", "SYMBOL"];

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function RiskPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const context = await requestContext();
  const params = await searchParams;
  const scope = one(params.scope) ?? "ALL";
  const editing = one(params.edit);
  const allowed = canAct(context.role);

  if (context.state === "loading") {
    return (
      <Panel title="위험 설정">
        <SkeletonBlock rows={6} />
      </Panel>
    );
  }

  const result = await tryGet<RiskPayload>("/console/v1/risk-rules", { state: context.state });
  if (!result.ok) {
    if (result.error.status === 403) return <ForbiddenState />;
    return (
      <ErrorState
        title="위험 규칙을 불러오지 못했습니다"
        body={`${result.error.message} 한도는 바뀌지 않았습니다. 잠시 후 다시 시도해 주세요.`}
        retryHref={keepQuery("/risk", context)}
      />
    );
  }

  const data = result.data;
  const rows = scope === "ALL" ? data.rules : data.rules.filter((rule) => rule.scope === scope);
  const target = editing ? data.rules.find((rule) => rule.rule_id === editing) : undefined;

  const columns: Column<RiskRuleRow>[] = [
    {
      key: "name",
      header: "이름",
      render: (row) => (
        <span>
          {row.name}
          <span className="ml-1.5 text-xs text-secondary">{RISK_METRIC[row.metric]}</span>
        </span>
      ),
    },
    {
      key: "actual",
      header: "현재값",
      numeric: true,
      render: (row) => (
        <span className="num">
          {row.actual} <span className="text-xs text-secondary">{row.unit}</span>
        </span>
      ),
    },
    {
      key: "limit",
      header: "한도",
      numeric: true,
      render: (row) => (
        <span className="num">
          {row.limit} <span className="text-xs text-secondary">{row.unit}</span>
        </span>
      ),
    },
    {
      key: "usage",
      header: "사용률",
      render: (row) => (
        <div className="min-w-[140px]">
          <RiskUsageBar usage={row.usage_percent} label={row.name} />
        </div>
      ),
    },
    { key: "status", header: "상태", render: (row) => <StatusBadge status={row.status} showTime={false} /> },
    {
      key: "scope",
      header: "적용 범위",
      render: (row) => <Chip>{row.scope_label}</Chip>,
    },
    {
      key: "changed",
      header: "마지막 변경",
      secondary: true,
      render: (row) => (
        <span className="text-xs text-secondary">
          {row.changed_by} · <span className="num">{row.changed_at}</span>
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="위험 설정"
        description="더 엄격하게 바꾸면 즉시 적용됩니다. 느슨하게 바꾸려면 재인증이 필요합니다."
        actions={<Timestamp value={`기준 ${data.as_of}`} />}
      />

      <NoticeList notices={data.notices} />

      <Panel>
        <FilterRow>
          <span className="text-xs text-secondary">범위</span>
          {SCOPES.map((item) => (
            <a
              key={item}
              href={keepQuery("/risk", context, { scope: item === "ALL" ? undefined : item })}
              className={cx(
                "rounded border px-2 py-1 text-xs",
                item === scope
                  ? "border-action font-semibold text-action"
                  : "border-line text-secondary hover:bg-subtle",
              )}
            >
              {item === "ALL" ? "전체" : RISK_SCOPE[item]}
            </a>
          ))}
        </FilterRow>
        <DataTable<RiskRuleRow>
          caption="위험 규칙 목록"
          columns={columns}
          rows={rows}
          rowKey={(row) => row.rule_id}
          detailHref={
            allowed ? (row) => keepQuery("/risk", context, { scope: scope === "ALL" ? undefined : scope, edit: row.rule_id }) : undefined
          }
          empty={
            <EmptyState
              title="이 범위에 설정된 규칙이 없습니다"
              body="다른 범위를 선택하거나 관리자에게 시스템 기본 한도를 요청하세요."
            />
          }
        />
      </Panel>

      {target && allowed && (
        <Panel
          title={`${target.name} 한도 변경`}
          description={`적용 범위 ${target.scope_label} · 단위 ${target.unit}`}
          tone="warning"
        >
          <form action={updateRiskLimitAction} className="flex flex-col gap-3 p-4">
            <input type="hidden" name="rule_id" value={target.rule_id} />
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-xs text-secondary">
                현재 한도
                <input
                  className="num h-10 rounded border border-line bg-subtle px-3 text-sm"
                  value={target.limit}
                  readOnly
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-secondary">
                새 한도 ({target.unit})
                <input
                  name="limit"
                  defaultValue={target.limit}
                  inputMode="decimal"
                  className="num h-10 rounded border border-line bg-surface px-3 text-sm"
                />
              </label>
            </div>
            <p className="text-xs text-secondary">
              현재값은 <span className="num">{target.actual}</span> {target.unit}이며 한도의{" "}
              <span className="num">{percent(target.usage_percent)}</span>를 사용하고 있습니다.
              한도를 현재값보다 낮추면 신규 주문이 즉시 차단됩니다.
            </p>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                name="reauthenticated"
                className="h-4 w-4 rounded border-line"
              />
              재인증을 완료했습니다 (한도를 느슨하게 바꿀 때만 필요)
            </label>
            <div className="flex gap-2">
              <Button type="submit" variant="primary">
                한도 변경
              </Button>
              <a
                href={keepQuery("/risk", context, {
                  scope: scope === "ALL" ? undefined : scope,
                  edit: undefined,
                })}
                className="inline-flex h-10 items-center rounded-md border border-line px-3 text-sm hover:bg-subtle"
              >
                취소
              </a>
            </div>
          </form>
        </Panel>
      )}

      <Panel title="한도 변경 이력">
        <ul className="flex flex-col">
          {data.history.map((change) => (
            <li
              key={change.change_id}
              className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5 last:border-0"
            >
              <div>
                <p className="text-sm">
                  {change.rule_name}
                  <span className="num ml-2 text-secondary">
                    {change.before} → {change.after}
                  </span>
                </p>
                <p className="num text-xs text-secondary">
                  {change.actor} · {change.changed_at}
                </p>
              </div>
              <Chip tone={change.direction === "TIGHTER" ? "ok" : "warning"}>
                {change.direction === "TIGHTER" ? "더 엄격하게" : "더 느슨하게 · 재인증"}
              </Chip>
            </li>
          ))}
        </ul>
      </Panel>
    </>
  );
}
