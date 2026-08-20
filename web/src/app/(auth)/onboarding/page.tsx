import Link from "next/link";

import { Button, Chip, Panel, cx } from "@/components/ui/primitives";
import { NoticeBanner } from "@/components/ui/status";

const STEPS = [
  { id: "1", title: "계정 보안", description: "MFA 등록" },
  { id: "2", title: "거래 연결", description: "토스 또는 MT5 선택" },
  { id: "3", title: "위험 한도", description: "필수 한도 5종" },
  { id: "4", title: "첫 운영 모드", description: "섀도 모드로 시작" },
];

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function OnboardingPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const step = one((await searchParams).step) ?? "1";
  const current = STEPS.find((item) => item.id === step) ?? STEPS[0];

  return (
    <div className="w-full max-w-[720px]">
      <ol className="mb-5 flex flex-wrap gap-2">
        {STEPS.map((item) => {
          const done = Number(item.id) < Number(step);
          const active = item.id === step;
          return (
            <li key={item.id} className="flex-1">
              <Link
                href={`/onboarding?step=${item.id}`}
                className={cx(
                  "flex min-h-[56px] flex-col justify-center rounded-panel border px-3 py-2",
                  active
                    ? "border-action bg-surface"
                    : done
                      ? "border-ok/45 bg-surface"
                      : "border-line bg-surface/60",
                )}
              >
                <span className="text-xs text-secondary">
                  {item.id}단계 {done && "· 완료"}
                </span>
                <span className={cx("text-sm", active && "font-semibold")}>{item.title}</span>
              </Link>
            </li>
          );
        })}
      </ol>

      <Panel title={`${current.id}. ${current.title}`} description={current.description}>
        <div className="flex flex-col gap-4 p-5">
          {step === "1" && (
            <>
              <p className="text-sm text-secondary">
                인증 앱을 등록하면 승인·정지 같은 중요한 작업에서 재인증을 사용할 수 있습니다.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="primary">TOTP 등록</Button>
                <Button>패스키 등록</Button>
              </div>
            </>
          )}

          {step === "2" && (
            <>
              <p className="text-sm text-secondary">
                연결할 브로커를 선택하세요. 나중에 둘 다 추가할 수 있습니다.
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-panel border border-line p-4">
                  <h3>토스증권</h3>
                  <p className="mt-1 text-xs text-secondary">
                    국내·미국 주식. client ID와 secret을 등록하고 연결 테스트를 진행합니다.
                  </p>
                  <div className="mt-3">
                    <Button variant="primary" dense>
                      토스 계좌 연결
                    </Button>
                  </div>
                </div>
                <div className="rounded-panel border border-line p-4">
                  <h3>MT5 노드</h3>
                  <p className="mt-1 text-xs text-secondary">
                    FX·CFD. Windows 서비스를 설치하고 pairing code를 입력합니다.
                  </p>
                  <div className="mt-3">
                    <Button dense>MT5 노드 등록</Button>
                  </div>
                </div>
              </div>
            </>
          )}

          {step === "3" && (
            <>
              <NoticeBanner
                notice={{
                  notice_id: "onboarding-risk",
                  tone: "warning",
                  title: "필수 위험 한도를 모두 채워야 다음 단계로 갈 수 있습니다",
                  body: "한도가 비어 있으면 실거래를 활성화할 수 없습니다.",
                  action_label: null,
                  action_href: null,
                  dismissible: false,
                }}
              />
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  { label: "투자금", unit: "KRW", value: "150000000" },
                  { label: "1회 주문 금액", unit: "KRW", value: "10000000" },
                  { label: "종목 비중", unit: "비중", value: "0.200" },
                  { label: "일일 손실", unit: "비율", value: "0.0300" },
                  { label: "최대 낙폭", unit: "비율", value: "0.1000" },
                ].map((field) => (
                  <label key={field.label} className="flex flex-col gap-1 text-sm">
                    {field.label} <span className="text-xs text-secondary">({field.unit})</span>
                    <input
                      defaultValue={field.value}
                      inputMode="decimal"
                      className="num h-10 rounded border border-line bg-surface px-3 text-sm"
                    />
                  </label>
                ))}
              </div>
            </>
          )}

          {step === "4" && (
            <>
              <p className="text-sm text-secondary">
                처음에는 섀도 모드로 시작합니다. 신호와 주문 계획은 만들어지지만 브로커로
                전송되지 않습니다.
              </p>
              <div className="flex flex-col gap-2">
                <label className="flex items-center gap-2 rounded-panel border border-action bg-surface p-3 text-sm">
                  <input type="radio" name="mode" defaultChecked />
                  <span>
                    섀도 모드 <Chip tone="ok">권장</Chip>
                    <span className="block text-xs text-secondary">
                      주문을 전송하지 않고 10거래일 검증합니다.
                    </span>
                  </span>
                </label>
                <label className="flex items-center gap-2 rounded-panel border border-line bg-surface/60 p-3 text-sm opacity-60">
                  <input type="radio" name="mode" disabled />
                  <span>
                    실거래
                    <span className="block text-xs text-secondary">
                      필수 위험 한도와 섀도 검증을 마친 뒤 관리자가 활성화합니다.
                    </span>
                  </span>
                </label>
              </div>
            </>
          )}

          <div className="flex justify-between gap-2 border-t border-line pt-4">
            <Link
              href={`/onboarding?step=${Math.max(1, Number(step) - 1)}`}
              className="inline-flex h-10 items-center rounded-md border border-line px-3 text-sm hover:bg-subtle"
            >
              이전
            </Link>
            {step === "4" ? (
              <Link href="/dashboard">
                <Button variant="primary">저장하고 콘솔 시작</Button>
              </Link>
            ) : (
              <Link href={`/onboarding?step=${Number(step) + 1}`}>
                <Button variant="primary">저장하고 다음</Button>
              </Link>
            )}
          </div>
          <p className="text-xs text-secondary">
            각 단계는 저장 후 다시 돌아올 수 있습니다.
          </p>
        </div>
      </Panel>
    </div>
  );
}
