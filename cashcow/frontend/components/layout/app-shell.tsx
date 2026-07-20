import type { ReactNode } from "react";

import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";

/** Application frame: sidebar + header wrapping scrollable page content. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top_left,var(--hero-wash),transparent_32rem)]">
          {children}
        </main>
      </div>
    </div>
  );
}
