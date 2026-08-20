import { WeightCompareBars } from "@/components/charts/charts";
import { DetailDrawer, DrawerSection } from "@/components/ui/drawer";
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
  EmptyState,
  ErrorState,
  ForbiddenState,
  NoticeList,
  SkeletonPage,
  StatusBadge,
} from "@/components/ui/status";
import { DataTable, Tabs, type Column } from "@/components/ui/table";
import { toggleSourceAction } from "@/lib/actions";
import { tryGet } from "@/lib/api";
import { ratioToPercent } from "@/lib/format";
import { APPROVAL_MODE } from "@/lib/labels";
import { canAct } from "@/lib/nav";
import { keepQuery, requestContext } from "@/lib/request";
import type { CopySourceDetail, CopySourceRow, SourceType } from "@/lib/types";

const TABS: { id: string; label: string; type: SourceType }[] = [
  { id: "leader", label: "리더 계좌", type: "LEADER" },
  { id: "external", label: "외부 신호", type: "EXTERNAL" },
  { id: "form13f", label: "13F 기관", type: "FORM_13F" },
];

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function CopyTradingPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const context = await requestContext();
  const params = await searchParams;
  const tab = one(params.tab) ?? "leader";
  const detailId = one(params.detail);
  const allowed = canAct(context.role);
  const activeType = TABS.find((item) => item.id === tab)?.type ?? "LEADER";

  if (context.state === "loading") return <SkeletonPage title="카피트레이딩" />;

  const result = await tryGet<CopySourceRow[]>("/console/v1/copy-sources", {
    state: context.state,
  });
  if (!result.ok) {
    if (result.error.status === 403) return <ForbiddenState />;
    return (
      <ErrorState
        title="신호원 목록을 불러오지 못했습니다"
        body={`${result.error.message} 구독 설정은 바뀌지 않았습니다. 잠시 후 다시 시도해 주세요.`}
        retryHref={keepQuery("/copy", context, { tab })}
      />
    );
  }

  const all = result.data;
  const rows = all.filter((row) => row.source_type === activeType);
  const detail = detailId
    ? await tryGet<CopySourceDetail>(`/console/v1/copy-sources/${detailId}`, {
        state: context.state,
      })
    : null;

  const columns: Column<CopySourceRow>[] = [
    {
      key: "name",
      header: "소스 이름",
      render: (row) => (
        <span>
          {row.name}
          <span className="ml-1.5 text-xs text-secondary">{row.kind_label}</span>
        </span>
      ),
    },
    {
      key: "signal",
      header: "마지막 정상 신호",
      render: (row) => <Timestamp value={row.last_signal_at} />,
    },
    {
      key: "status",
      header: "연결 상태",
      render: (row) => <StatusBadge status={row.status} showTime={false} />,
    },
    {
      key: "accounts",
      header: "구독 계좌",
      secondary: true,
      render: (row) => row.subscribed_accounts.join(", "),
    },
    {
      key: "target",
      header: "목표 투자 비중",
      numeric: true,
      render: (row) => <span className="num">{ratioToPercent(row.target_weight)}%</span>,
    },
    {
      key: "mode",
      header: "승인 모드",
      render: (row) => <Chip>{APPROVAL_MODE[row.approval_mode]}</Chip>,
    },
    {
      key: "drift",
      header: "현재 드리프트",
      numeric: true,
      render: (row) => (
        <span className="num text-warn">{ratioToPercent(row.drift)}%</span>
      ),
    },
    {
      key: "actions",
      header: "행동",
      render: (row) =>
        allowed ? (
          <form action={toggleSourceAction}>
            <input type="hidden" name="source_id" value={row.source_id} />
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
        title="카피트레이딩"
        description="리더 주문 수량이 아니라 확인된 포지션의 목표 비중 차이로 주문을 만듭니다."
      />

      <Panel>
        <Tabs
          items={TABS.map((item) => ({
            id: item.id,
            label: item.label,
            count: all.filter((row) => row.source_type === item.type).length,
          }))}
          current={tab}
          hrefFor={(id) => keepQuery("/copy", context, { tab: id, detail: undefined })}
        />
        <DataTable<CopySourceRow>
          caption="신호원 목록"
          columns={columns}
          rows={rows}
          rowKey={(row) => row.source_id}
          detailHref={(row) =>
            keepQuery("/copy", context, { tab, detail: row.source_id })
          }
          empty={
            <EmptyState
              title="구독 중인 신호원이 없습니다"
              body="리더 계좌, 외부 Webhook, 13F 기관 중 하나를 구독하면 목표 비중이 계좌에 반영됩니다."
            />
          }
        />
      </Panel>

      {detail && detail.ok && (
        <CopySourceDrawer
          detail={detail.data}
          closeHref={keepQuery("/copy", context, { tab, detail: undefined })}
        />
      )}
    </>
  );
}

function CopySourceDrawer({
  detail,
  closeHref,
}: {
  detail: CopySourceDetail;
  closeHref: string;
}) {
  const row = detail.row;
  return (
    <DetailDrawer title={row.name} subtitle={row.kind_label} closeHref={closeHref}>
      <NoticeList notices={detail.notices} />

      <DrawerSection title="소스 정보">
        <DefinitionList
          items={detail.facts.map((fact) => ({ term: fact.label, value: fact.value }))}
        />
      </DrawerSection>

      <DrawerSection title="구독과 승인">
        <DefinitionList
          items={[
            { term: "구독 계좌", value: row.subscribed_accounts.join(", ") || "—" },
            { term: "목표 투자 비중", value: `${ratioToPercent(row.target_weight)}%` },
            { term: "승인 모드", value: APPROVAL_MODE[row.approval_mode] },
            { term: "현재 드리프트", value: `${ratioToPercent(row.drift)}%` },
          ]}
        />
      </DrawerSection>

      {detail.weights.length > 0 && (
        <DrawerSection title="목표 비중과 내 계좌 현재 비중">
          <WeightCompareBars rows={detail.weights} asOf={row.last_signal_at} />
          <p className="mt-2 text-xs text-secondary">
            핵심 정보는 리더의 주문 수량이 아니라 목표 비중과의 차이입니다.
          </p>
        </DrawerSection>
      )}

      {detail.excluded.length > 0 && (
        <DrawerSection title="제외·매핑 실패 종목">
          <ul className="flex flex-col gap-2">
            {detail.excluded.map((item) => (
              <li key={item.issue_id} className="rounded border border-line p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium">
                    {item.symbol_name}
                    <span className="num ml-1.5 text-xs text-secondary">{item.symbol}</span>
                  </p>
                  <Chip tone="warning">{item.status}</Chip>
                </div>
                <p className="num mt-1 text-xs text-secondary">
                  {item.internal_value} · {item.broker_value}
                </p>
                <p className="mt-1 text-xs text-secondary">{item.guidance}</p>
              </li>
            ))}
          </ul>
        </DrawerSection>
      )}

      <DrawerSection title="연결 상태">
        <StatusBadge status={row.status} />
        <p className="num mt-2 text-xs text-secondary">
          마지막 정상 신호 {row.last_signal_at}
        </p>
        <div className="mt-3">
          <LinkButton href="/approvals" dense>
            이 신호원의 승인 요청 보기
          </LinkButton>
        </div>
      </DrawerSection>
    </DetailDrawer>
  );
}
