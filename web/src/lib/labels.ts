// 백엔드 도메인 enum → 한국어 라벨. 새 enum을 만들지 않고 값에 1:1로 붙인다.
// 대응하는 파이썬 정의: src/mtoss/domain/{enums,approvals,risk}.py

import type {
  ApprovalMode,
  ApprovalStatus,
  AutoTrading,
  Broker,
  HealthLevel,
  Market,
  OrderSide,
  OrderState,
  RiskMetric,
  RiskScope,
  Role,
  SourceType,
} from "./types";

export const ORDER_STATE: Record<OrderState, string> = {
  CREATED: "생성",
  PENDING_APPROVAL: "승인 대기",
  QUEUED: "실행 대기",
  SUBMITTED: "브로커 접수",
  PARTIALLY_FILLED: "부분 체결",
  FILLED: "체결",
  CANCELED: "취소",
  REJECTED: "거절",
  EXPIRED: "만료",
  UNKNOWN: "확인 필요",
};

/** UNKNOWN은 실패가 아니다 (§7.8). 상태별로 톤을 다르게 준다. */
export const ORDER_STATE_TONE: Record<OrderState, "neutral" | "ok" | "warning" | "critical"> = {
  CREATED: "neutral",
  PENDING_APPROVAL: "warning",
  QUEUED: "neutral",
  SUBMITTED: "neutral",
  PARTIALLY_FILLED: "warning",
  FILLED: "ok",
  CANCELED: "neutral",
  REJECTED: "critical",
  EXPIRED: "neutral",
  UNKNOWN: "warning",
};

export const ORDER_SIDE: Record<OrderSide, string> = { BUY: "매수", SELL: "매도" };

export const SOURCE_TYPE: Record<SourceType, string> = {
  STRATEGY: "전략",
  LEADER: "리더 계좌",
  EXTERNAL: "외부 신호",
  FORM_13F: "13F 기관",
};

export const APPROVAL_MODE: Record<ApprovalMode, string> = {
  AUTO: "자동",
  MANUAL: "수동 승인",
  CONDITIONAL: "조건부 자동",
};

export const APPROVAL_STATUS: Record<ApprovalStatus, string> = {
  APPROVED: "승인됨",
  PENDING: "승인 대기",
  REJECTED: "거절됨",
  EXPIRED: "만료됨",
};

export const RISK_SCOPE: Record<RiskScope, string> = {
  SYSTEM: "시스템",
  USER: "사용자",
  ACCOUNT: "계좌",
  SOURCE: "전략·신호원",
  SYMBOL: "종목",
};

export const RISK_METRIC: Record<RiskMetric, string> = {
  ORDER_NOTIONAL: "1회 주문 금액",
  ACCOUNT_CAPITAL: "계좌 투자금",
  SYMBOL_WEIGHT: "종목 비중",
  DAILY_LOSS: "일일 손실",
  MAX_DRAWDOWN: "최대 낙폭",
};

export const HEALTH_LEVEL: Record<HealthLevel, string> = {
  OK: "정상",
  WARNING: "주의",
  ACTION_REQUIRED: "작업 필요",
  STOPPED: "중단됨",
};

export const MARKET: Record<Market, string> = { KR: "국내", US: "미국", FX: "FX" };
export const BROKER: Record<Broker, string> = { TOSS: "토스증권", MT5: "MT5" };
export const ROLE: Record<Role, string> = {
  ADMIN: "관리자",
  TRADER: "트레이더",
  VIEWER: "조회 전용",
};

export const AUTO_TRADING: Record<AutoTrading, string> = {
  RUNNING: "자동매매 실행 중",
  STOPPED_BY_OFFLINE: "연결 끊김으로 정지",
  PAUSED_BY_USER: "사용자 일시정지",
  SHADOW: "섀도 모드",
};

export const STRATEGY_MODE: Record<"SHADOW" | "MANUAL" | "AUTO", string> = {
  SHADOW: "섀도",
  MANUAL: "수동 승인",
  AUTO: "자동",
};

export function levelTone(level: HealthLevel): "neutral" | "ok" | "warning" | "critical" {
  if (level === "OK") return "ok";
  if (level === "WARNING") return "warning";
  return "critical";
}
