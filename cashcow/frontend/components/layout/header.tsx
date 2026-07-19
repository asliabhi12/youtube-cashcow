"use client";

import { useDemoMode } from "@/components/demo-mode/use-demo-mode";
import { ServerStatusIndicator } from "@/features/server-status/server-status-indicator";

/** Top application bar. Server status is pinned to the right. */
export function Header() {
  const { isDemoMode } = useDemoMode();

  return (
    <header className="flex h-14 shrink-0 items-center justify-end gap-3 border-b bg-background px-6">
      {isDemoMode && (
        <span className="rounded-full bg-purple-500/10 px-3 py-0.5 text-xs font-medium text-purple-400">
          Demo Mode
        </span>
      )}
      <ServerStatusIndicator />
    </header>
  );
}
