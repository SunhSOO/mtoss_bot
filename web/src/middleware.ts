import { NextResponse, type NextRequest } from "next/server";

// 레이아웃(서버 컴포넌트)은 pathname과 searchParams를 직접 받지 못한다.
// 현재 URL을 헤더로 넘겨 AppShell이 활성 메뉴와 상태 시뮬레이터를 그릴 수 있게 한다.
export function middleware(request: NextRequest) {
  const headers = new Headers(request.headers);
  headers.set("x-url", `${request.nextUrl.pathname}${request.nextUrl.search}`);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
