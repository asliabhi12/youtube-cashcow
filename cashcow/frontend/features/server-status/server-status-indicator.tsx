"use client";

import { cn } from "@/lib/utils";
import { useServerStatus } from "@/features/server-status/use-server-status";

const CONFIG = {
  checking: { label: "Checking…", dot: "bg-muted-foreground" },
  online: { label: "Server Running", dot: "bg-success" },
  offline: { label: "Server Offline", dot: "bg-warning" },
} as const;

/** Header badge showing whether the local backend is reachable. */
export function ServerStatusIndicator() {
  const status = useServerStatus();
  const { label, dot } = CONFIG[status];

  return (
    <div className="flex items-center gap-2 rounded-full border bg-card/70 px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-sm">
      <span
        className={cn(
          "size-2 rounded-full",
          dot,
          status === "checking" && "animate-pulse",
        )}
        aria-hidden
      />
      <span>{label}</span>
    </div>
  );
}
