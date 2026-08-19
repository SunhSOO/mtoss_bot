import type { Metadata, Viewport } from "next";

import { pretendard } from "./fonts";
import { readTheme } from "@/lib/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: "시스템 트레이딩 콘솔",
  description: "MT5·토스증권 자동매매 운영 콘솔",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const theme = await readTheme();
  return (
    <html lang="ko" data-theme={theme === "system" ? undefined : theme}>
      <body className={pretendard.variable}>{children}</body>
    </html>
  );
}
