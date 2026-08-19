import type { Role } from "./types";

export interface NavItem {
  id: string;
  href: string;
  label: string;
  description: string;
  /** 이 역할에게만 보인다. 권한이 없으면 비활성화가 아니라 숨긴다 (§3). */
  roles: Role[];
  mobile: boolean;
}

/** 좌측 내비 순서는 화면 설계서 §5를 따른다. */
export const NAV_ITEMS: NavItem[] = [
  {
    id: "dashboard",
    href: "/dashboard",
    label: "대시보드",
    description: "계좌·노드 건강과 오늘의 운영 상태",
    roles: ["ADMIN", "TRADER", "VIEWER"],
    mobile: true,
  },
  {
    id: "strategies",
    href: "/strategies",
    label: "전략",
    description: "배포된 전략의 운영 모드와 실행 상태",
    roles: ["ADMIN", "TRADER", "VIEWER"],
    mobile: false,
  },
  {
    id: "copy",
    href: "/copy",
    label: "카피트레이딩",
    description: "리더 계좌·외부 신호·13F 기관 구독",
    roles: ["ADMIN", "TRADER", "VIEWER"],
    mobile: false,
  },
  {
    id: "approvals",
    href: "/approvals",
    label: "승인함",
    description: "만료 임박 순 승인 요청",
    roles: ["ADMIN", "TRADER", "VIEWER"],
    mobile: true,
  },
  {
    id: "orders",
    href: "/orders",
    label: "주문·포지션",
    description: "주문, 체결, 포지션, 정합성 이슈",
    roles: ["ADMIN", "TRADER", "VIEWER"],
    mobile: true,
  },
  {
    id: "risk",
    href: "/risk",
    label: "위험 설정",
    description: "범위별 위험 한도와 변경 이력",
    roles: ["ADMIN", "TRADER"],
    mobile: false,
  },
  {
    id: "connections",
    href: "/connections",
    label: "연결",
    description: "토스 계좌와 MT5 노드",
    roles: ["ADMIN", "TRADER"],
    mobile: false,
  },
  {
    id: "audit",
    href: "/audit",
    label: "감사 기록",
    description: "신호부터 체결까지의 추적",
    roles: ["ADMIN", "TRADER", "VIEWER"],
    mobile: false,
  },
  {
    id: "admin",
    href: "/admin",
    label: "관리자",
    description: "사용자, 배포, 공급자, 전체 긴급 제어",
    roles: ["ADMIN"],
    mobile: false,
  },
];

export function navFor(role: Role): NavItem[] {
  return NAV_ITEMS.filter((item) => item.roles.includes(role));
}

/** 모바일 하단 내비는 홈·승인·주문·더보기 네 항목이다 (§5). */
export function mobileNavFor(role: Role): NavItem[] {
  return navFor(role).filter((item) => item.mobile);
}

export function findNav(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find(
    (item) => pathname === item.href || pathname.startsWith(`${item.href}/`),
  );
}

/** 조회 전용은 승인·정지·설정 변경을 할 수 없다 (§3). */
export function canAct(role: Role): boolean {
  return role !== "VIEWER";
}

export function canAdminister(role: Role): boolean {
  return role === "ADMIN";
}
