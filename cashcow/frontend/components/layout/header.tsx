import { ServerStatusIndicator } from "@/features/server-status/server-status-indicator";

/** Top application bar. Server status is pinned to the right. */
export function Header() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-end border-b bg-background px-6">
      <ServerStatusIndicator />
    </header>
  );
}
