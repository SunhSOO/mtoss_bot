import {
  Button,
  Chip,
  DefinitionList,
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
  SkeletonPage,
  StatusBadge,
  ToneBadge,
} from "@/components/ui/status";
import { Tabs } from "@/components/ui/table";
import { resumeAccountAction, resumeNodeAction, stopAccountAction, testTossAction } from "@/lib/actions";
import { tryGet } from "@/lib/api";
import { AUTO_TRADING, MARKET } from "@/lib/labels";
import { canAct } from "@/lib/nav";
import { keepQuery, requestContext } from "@/lib/request";
import type { ConnectionCheck, ConnectionsPayload } from "@/lib/types";

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function ConnectionsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const context = await requestContext();
  const params = await searchParams;
  const tab = one(params.tab) ?? "toss";
  const allowed = canAct(context.role);

  if (context.state === "loading") return <SkeletonPage title="연결" />;

  const result = await tryGet<ConnectionsPayload>("/console/v1/connections", {
    state: context.state,
  });
  if (!result.ok) {
    if (result.error.status === 403) return <ForbiddenState />;
    return (
      <ErrorState
        title="연결 정보를 불러오지 못했습니다"
        body={`${result.error.message} 계좌 설정은 바뀌지 않았습니다. 잠시 후 다시 시도해 주세요.`}
        retryHref={keepQuery("/connections", context, { tab })}
      />
    );
  }

  const data = result.data;

  return (
    <>
      <PageHeader
        title="연결"
        description="토스 계좌 자격증명과 MT5 노드 상태를 관리합니다. 저장된 비밀값은 다시 표시되지 않습니다."
        actions={<Timestamp value={`기준 ${data.as_of}`} />}
      />

      <NoticeList notices={data.notices} />

      <Panel>
        <Tabs
          items={[
            { id: "toss", label: "토스 계좌", count: data.toss_accounts.length },
            { id: "mt5", label: "MT5 노드", count: data.mt5_nodes.length },
          ]}
          current={tab}
          hrefFor={(id) => keepQuery("/connections", context, { tab: id })}
        />

        {tab === "toss" &&
          (data.toss_accounts.length === 0 ? (
            <EmptyState
              title="연결된 계좌가 없습니다"
              body="토스증권 Open API의 client ID와 secret을 등록하면 잔고와 주문 상태를 확인할 수 있습니다."
              actionLabel="토스 계좌 연결"
              actionHref={keepQuery("/onboarding", context)}
            />
          ) : (
            <ul className="flex flex-col">
              {data.toss_accounts.map((account) => (
                <li key={account.account_id} className="border-b border-line p-4 last:border-0">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <h3>{account.alias}</h3>
                      <p className="mt-0.5 text-xs text-secondary">
                        {MARKET[account.market]} 시장 · 마지막 동기화{" "}
                        <span className="num">{account.last_sync}</span>
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={account.status} />
                      {account.order_stopped && <Chip tone="critical">주문 정지</Chip>}
                    </div>
                  </div>

                  <p className="mt-2 text-xs text-secondary">{account.secret_note}</p>

                  <CheckGrid title="연결 테스트 결과" checks={account.checks} />

                  {allowed && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <form action={testTossAction}>
                        <input type="hidden" name="scenario" value="" />
                        <Button type="submit" dense>
                          연결 테스트
                        </Button>
                      </form>
                      {account.order_stopped ? (
                        <form action={resumeAccountAction}>
                          <input type="hidden" name="account_id" value={account.account_id} />
                          <Button type="submit" variant="primary" dense>
                            계좌 주문 재개
                          </Button>
                        </form>
                      ) : (
                        <form action={stopAccountAction}>
                          <input type="hidden" name="account_id" value={account.account_id} />
                          <Button type="submit" variant="critical" dense>
                            계좌 주문 정지
                          </Button>
                        </form>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          ))}

        {tab === "mt5" &&
          (data.mt5_nodes.length === 0 ? (
            <EmptyState
              title="등록된 MT5 노드가 없습니다"
              body="Windows 서비스를 설치하고 pairing code를 입력하면 노드가 연결됩니다."
            />
          ) : (
            <ul className="flex flex-col">
              {data.mt5_nodes.map((node) => {
                const offline = node.auto_trading === "STOPPED_BY_OFFLINE";
                return (
                  <li key={node.node_id} className="border-b border-line p-4 last:border-0">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <h3>{node.name}</h3>
                        <p className="mt-0.5 text-xs text-secondary">{node.account_alias}</p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge status={node.status} />
                        <ToneBadge tone={offline ? "critical" : "neutral"}>
                          {AUTO_TRADING[node.auto_trading]}
                        </ToneBadge>
                      </div>
                    </div>

                    <div className="mt-3">
                      <DefinitionList
                        columns={3}
                        items={[
                          { term: "heartbeat", value: node.heartbeat_note },
                          { term: "버전", value: node.version },
                          {
                            term: "마지막 포지션 동기화",
                            value: <Timestamp value={node.last_position_sync} />,
                          },
                          {
                            term: "pairing code",
                            value: <span className="num">{node.pairing_code}</span>,
                            hint: "개인 코드입니다. 공유하지 마세요.",
                          },
                        ]}
                      />
                    </div>

                    <CheckGrid title="설치 체크리스트" checks={data.mt5_checks} />

                    {offline && (
                      <div className="mt-3 rounded border border-critical/55 bg-critical/5 p-3">
                        <p className="text-sm font-semibold text-critical">
                          이 계좌의 자동매매가 정지되었습니다
                        </p>
                        <ol className="mt-1.5 list-decimal space-y-0.5 pl-5 text-xs text-secondary">
                          <li>Windows 서비스가 실행 중인지 확인합니다.</li>
                          <li>MT5 터미널 로그인 상태를 확인합니다.</li>
                          <li>방화벽에서 아웃바운드 WSS 연결을 허용합니다.</li>
                          <li>heartbeat가 복구되면 아래 버튼으로 직접 재개합니다.</li>
                        </ol>
                        <p className="mt-1.5 text-xs text-secondary">
                          노드가 다시 연결되어도 자동으로 매매를 재개하지 않습니다.
                        </p>
                      </div>
                    )}

                    {allowed && offline && (
                      <form action={resumeNodeAction} className="mt-3">
                        <input type="hidden" name="node_id" value={node.node_id} />
                        <Button type="submit" variant="primary" dense>
                          자동매매 재개 승인
                        </Button>
                      </form>
                    )}
                  </li>
                );
              })}
            </ul>
          ))}
      </Panel>

      {tab === "toss" && allowed && <TossTestScenarios context={context} />}
    </>
  );
}

function CheckGrid({ title, checks }: { title: string; checks: ConnectionCheck[] }) {
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-xs text-secondary">{title}</p>
      <ul className="grid gap-1.5 sm:grid-cols-2 xl:grid-cols-3">
        {checks.map((check) => (
          <li
            key={check.key}
            className={cx(
              "flex items-center justify-between gap-2 rounded border px-2.5 py-1.5 text-xs",
              check.passed ? "border-line" : "border-critical/55",
            )}
          >
            <span className="flex items-center gap-1.5">
              <ToneBadge tone={check.passed ? "ok" : "critical"}>
                {check.passed ? "통과" : "실패"}
              </ToneBadge>
              {check.label}
            </span>
            <span className="text-secondary">{check.detail}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** 연결 테스트 실패는 원인별로 구분해야 한다 (§8 흐름 A). */
function TossTestScenarios({
  context,
}: {
  context: Awaited<ReturnType<typeof requestContext>>;
}) {
  const scenarios = [
    { value: "", label: "정상 통과" },
    { value: "auth", label: "인증 실패" },
    { value: "no-account", label: "계좌 없음" },
    { value: "terms", label: "약관 미동의" },
    { value: "rate-limit", label: "호출 제한" },
  ];
  return (
    <Panel
      title="연결 테스트 시나리오"
      description="실패 원인을 구분해 보여주기 위한 목업 시나리오입니다. 실제 브로커를 호출하지 않습니다."
    >
      <div className="flex flex-wrap gap-2 p-4">
        {scenarios.map((scenario) => (
          <form action={testTossAction} key={scenario.value || "ok"}>
            <input type="hidden" name="scenario" value={scenario.value} />
            <Button type="submit" dense variant={scenario.value ? "secondary" : "primary"}>
              {scenario.label}
            </Button>
          </form>
        ))}
      </div>
      <p className="px-4 pb-4 text-xs text-secondary">
        현재 화면 상태: {context.state === "toss-auth-expired" ? "토스 인증 만료" : "정상"}
      </p>
    </Panel>
  );
}
