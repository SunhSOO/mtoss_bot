import localFont from "next/font/local";

// 외부 요청 없이 self-host 한다. 파일이 없으면 CSS의 시스템 폰트 스택으로 떨어진다.
export const pretendard = localFont({
  src: "../../public/fonts/PretendardVariable.woff2",
  variable: "--font-pretendard",
  display: "swap",
  weight: "45 920",
  fallback: ["system-ui", "Malgun Gothic", "Apple SD Gothic Neo", "sans-serif"],
});
