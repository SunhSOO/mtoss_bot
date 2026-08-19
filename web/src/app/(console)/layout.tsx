import { AppShell } from "@/components/shell/app-shell";
import { NoticeBanner } from "@/components/ui/status";
import { consoleGet, ConsoleApiError } from "@/lib/api";
import { requestContext } from "@/lib/request";
import type { SessionPayload } from "@/lib/types";

export const dynamic = "force-dynamic";

const OFFLINE_SESSION: SessionPayload = {
  user_name: "—",
  user_email: "—",
  role: "ADMIN",
  accounts: [],
  system_status: {
    level: "ACTION_REQUIRED",
    label: "작업 필요",
    detail: "스텁 API에 연결하지 못했습니다",
    as_of: "—",
  },
  emergency_stop: false,
  kst_time: "—",
  et_time: "—",
  pending_approvals: 0,
  risk_actions: 0,
};

export default async function ConsoleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const context = await requestContext();
  let session = OFFLINE_SESSION;
  let failure: ConsoleApiError | null = null;
  try {
    session = await consoleGet<SessionPayload>("/console/v1/session", {
      state: context.state,
      role: context.role,
    });
  } catch (error) {
    if (!(error instanceof ConsoleApiError)) throw error;
    failure = error;
  }
  return (
    <AppShell session={session} pathname={context.pathname} state={context.state}>
      {failure && (
        <NoticeBanner
          notice={{
            notice_id: "session-offline",
            tone: "critical",
            title: "스텁 API에 연결하지 못했습니다",
            body: `${failure.message} 주문에는 영향이 없습니다. uvicorn을 8100 포트에서 실행한 뒤 새로 고침해 주세요.`,
            action_label: null,
            action_href: null,
            dismissible: false,
          }}
        />
      )}
      {children}
    </AppShell>
  );
}
