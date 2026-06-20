import Link from "next/link";
import { Box, LayoutDashboard, Plus } from "lucide-react";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-ink/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <Link href="/" className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-md border border-brand/40 bg-brand/10">
              <Box size={18} className="text-brand" />
            </span>
            <span>
              <span className="block text-sm font-semibold tracking-wide text-white">Structura AI</span>
              <span className="block text-xs text-slate-400">External photogrammetry readiness</span>
            </span>
          </Link>
          <nav className="flex items-center gap-2 text-sm text-slate-300">
            <Link className="flex items-center gap-2 rounded-md px-3 py-2 hover:bg-white/10" href="/dashboard">
              <LayoutDashboard size={16} /> Dashboard
            </Link>
            <Link className="flex items-center gap-2 rounded-md bg-brand px-3 py-2 font-medium text-ink hover:bg-cyan-200" href="/projects/new">
              <Plus size={16} /> New Scan
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-5 py-8">{children}</main>
    </div>
  );
}
