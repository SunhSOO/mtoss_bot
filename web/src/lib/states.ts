// 화면 설계서 §9의 상태 목록. `?state=` 쿼리로 어느 화면에서든 재현할 수 있어야
// 스크린샷과 리뷰가 가능하다. 스텁 API가 같은 슬러그를 해석한다.

export const STATE_SLUGS = [
  "normal",
  "loading",
  "empty",
  "partial",
  "forbidden",
  "server-error",
  "market-data-stale",
  "rate-limited",
  "toss-auth-expired",
  "mt5-offline",
  "strategy-error",
  "emergency-stop",
  "position-mismatch",
] as const;

export type StateSlug = (typeof STATE_SLUGS)[number];

export const STATE_LABELS: Record<StateSlug, string> = {
  normal: "정상 데이터",
  loading: "최초 로딩",
  empty: "데이터 없음",
  partial: "일부 데이터만 성공",
  forbidden: "권한 없음",
  "server-error": "서버 오류",
  "market-data-stale": "시장 데이터 지연",
  "rate-limited": "브로커 호출 제한",
  "toss-auth-expired": "토스 인증 만료",
  "mt5-offline": "MT5 노드 offline",
  "strategy-error": "전략 오류로 정지",
  "emergency-stop": "긴급 정지",
  "position-mismatch": "포지션 불일치",
};

export function resolveState(value: string | string[] | undefined): StateSlug {
  const raw = Array.isArray(value) ? value[0] : value;
  return STATE_SLUGS.includes(raw as StateSlug) ? (raw as StateSlug) : "normal";
}

export function isSimulatorEnabled(): boolean {
  return process.env.NEXT_PUBLIC_STATE_SIM === "1";
}

/** 상태를 보존한 채 같은 화면의 다른 URL을 만든다. */
export function withState(href: string, state: StateSlug): string {
  if (state === "normal") return href;
  const separator = href.includes("?") ? "&" : "?";
  return `${href}${separator}state=${state}`;
}
