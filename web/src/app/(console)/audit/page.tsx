import { DetailDrawer, DrawerSection, OrderStatusTimeline } from "@/components/ui/drawer";
import { Chip, PageHeader, Panel, Timestamp } from "@/components/ui/primitives";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  NoticeList,
  SkeletonPage,
} from "@/components/ui/status";
import { DataTable, FilterRow, type Column } from "@/components/ui/table";
import { tryGet } from "@/lib/api";
import { canAdminister } from "@/lib/nav";
import { keepQuery, requestContext } from "@/lib/request";
import type { AuditDetail, AuditPayload, AuditRow } from "@/lib/types";

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function AuditPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const context = await requestContext();
  const detailId = one((await searchParams).detail);

  if (context.state === "loading") return <SkeletonPage title="감사 기록" />;

  const result = await tryGet<AuditPayload>("/console/v1/audit", { state: context.state });
  if (!result.ok) {
    if (result.error.status === 403) return <ForbiddenState />;
    return (
      <ErrorState
        title="감사 기록을 불러오지 못했습니다"
        body={`${result.error.message} 기록 자체는 보존됩니다. 잠시 후 다시 시도해 주세요.`}
        retryHref={keepQuery("/audit", context)}
      />
    );
  }

  const data = result.data;
  const detail = detailId
    ? await tryGet<AuditDetail>(`/console/v1/audit/${detailId}`)
    : null;

  const columns: Column<AuditRow>[] = [
    { key: "time", header: "시각", render: (row) => <Timestamp value={row.occurred_at} /> },
    { key: "actor", header: "행위자", render: (row) => row.actor },
    { key: "action", header: "행위", render: (row) => row.action },
    { key: "target", header: "대상", render: (row) => row.target },
    { key: "result", header: "결과", render: (row) => row.result },
    {
      key: "trace",
      header: "trace ID",
      secondary: true,
      render: (row) => <span className="num text-xs text-secondary">{row.trace_id}</span>,
    },
  ];

  return (
    <>
      <PageHeader
        title="감사 기록"
        description="신호 → 위험검사 → 승인 → 주문 → 체결의 관계를 시간순으로 추적합니다."
        actions={<Timestamp value={`기준 ${data.as_of}`} />}
      />

      <NoticeList notices={data.notices} />

      <Panel>
        <FilterRow>
          <span className="text-xs text-secondary">필터</span>
          <Chip>사용자 · 전체</Chip>
          <Chip>계좌 · 전체</Chip>
          <Chip>전략 · 전체</Chip>
          <Chip>행위 · 전체</Chip>
          <Chip>기간 · 최근 24시간</Chip>
        </FilterRow>
        <DataTable<AuditRow>
          caption="감사 기록 목록"
          columns={columns}
          rows={data.events}
          rowKey={(row) => row.event_id}
          detailHref={(row) => keepQuery("/audit", context, { detail: row.event_id })}
          dense
          empty={
            <EmptyState
              title="기록이 없습니다"
              body="선택한 기간에 해당하는 감사 기록이 없습니다. 기간을 넓혀 보세요."
            />
          }
        />
      </Panel>

      {detail && detail.ok && (
        <DetailDrawer
          title={detail.data.row.action}
          subtitle={`${detail.data.row.actor} · ${detail.data.row.target}`}
          closeHref={keepQuery("/audit", context, { detail: undefined })}
        >
          <DrawerSection title="관계 추적">
            <OrderStatusTimeline steps={detail.data.chain} />
          </DrawerSection>
          <DrawerSection title="결과">
            <p className="text-sm">{detail.data.row.result}</p>
            <p className="num mt-1 text-xs text-secondary">
              trace {detail.data.row.trace_id} · {detail.data.row.occurred_at}
            </p>
          </DrawerSection>
          {canAdminister(context.role) && (
            <DrawerSection title="원본 JSON">
              <details>
                <summary className="cursor-pointer text-xs text-secondary">
                  관리자 전용 · 읽기 전용 · 비밀값은 마스킹됩니다
                </summary>
                <pre className="num mt-2 overflow-x-auto rounded border border-line bg-subtle p-3 text-xs">
                  {detail.data.payload_json}
                </pre>
              </details>
            </DrawerSection>
          )}
        </DetailDrawer>
      )}
    </>
  );
}
