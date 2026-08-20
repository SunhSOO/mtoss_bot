export const dynamic = "force-dynamic";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="flex h-16 items-center border-b border-line bg-surface px-6">
        <span className="text-sm font-bold tracking-tight">시스템 트레이딩 콘솔</span>
      </header>
      <main className="flex flex-1 items-start justify-center px-4 py-10">{children}</main>
    </div>
  );
}
