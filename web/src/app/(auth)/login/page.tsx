import Link from "next/link";

import { Button, Panel } from "@/components/ui/primitives";
import { NoticeBanner } from "@/components/ui/status";

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const step = one(params.step) ?? "credentials";
  const failed = one(params.error) === "1";

  return (
    <div className="w-full max-w-[400px]">
      <Panel
        title={step === "mfa" ? "2단계 인증" : "로그인"}
        description={
          step === "mfa"
            ? "등록한 인증 앱의 6자리 코드나 패스키를 사용하세요."
            : "초대받은 내부 사용자만 접근할 수 있습니다."
        }
      >
        <div className="flex flex-col gap-4 p-5">
          {failed && (
            <NoticeBanner
              notice={{
                notice_id: "login-error",
                tone: "critical",
                title: "인증 정보가 올바르지 않습니다",
                body: "이메일과 비밀번호를 다시 확인해 주세요.",
                action_label: null,
                action_href: null,
                dismissible: false,
              }}
            />
          )}

          {step === "mfa" && (
            <NoticeBanner
              notice={{
                notice_id: "login-device",
                tone: "warning",
                title: "마지막 로그인과 다른 기기·지역입니다",
                body: "직전 로그인은 2026.08.18 08:41 KST 서울에서 이루어졌습니다. 본인이 아니라면 관리자에게 알려 주세요.",
                action_label: null,
                action_href: null,
                dismissible: false,
              }}
            />
          )}

          {step === "credentials" ? (
            <form className="flex flex-col gap-3">
              <label className="flex flex-col gap-1 text-sm">
                이메일
                <input
                  type="email"
                  name="email"
                  autoComplete="username"
                  defaultValue="kim.op@example.internal"
                  className="h-10 rounded border border-line bg-surface px-3 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                비밀번호
                <input
                  type="password"
                  name="password"
                  autoComplete="current-password"
                  className="h-10 rounded border border-line bg-surface px-3 text-sm"
                />
              </label>
              <Link href="/login?step=mfa" className="mt-1">
                <Button variant="primary" className="w-full">
                  로그인
                </Button>
              </Link>
            </form>
          ) : (
            <form className="flex flex-col gap-3">
              <label className="flex flex-col gap-1 text-sm">
                6자리 인증 코드
                <input
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="000000"
                  className="num h-10 rounded border border-line bg-surface px-3 text-center text-lg tracking-[0.4em]"
                />
              </label>
              <Link href="/dashboard">
                <Button variant="primary" className="w-full">
                  인증하고 계속
                </Button>
              </Link>
              <Link href="/dashboard">
                <Button className="w-full">패스키로 인증</Button>
              </Link>
            </form>
          )}

          <p className="text-xs text-secondary">
            이 화면은 목업입니다. 실제 자격증명을 입력하지 마세요.
          </p>
        </div>
      </Panel>

      <p className="mt-4 text-center text-xs text-secondary">
        처음 설정이라면{" "}
        <Link href="/onboarding" className="text-action underline underline-offset-2">
          첫 설정 온보딩
        </Link>
        을 먼저 진행하세요.
      </p>
    </div>
  );
}
