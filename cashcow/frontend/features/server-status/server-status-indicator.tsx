"use client";

import { cn } from "@/lib/utils";
import { useServerStatus } from "@/features/server-status/use-server-status";

const CONFIG = {
  checking: { label: "Checking…", dot: "bg-muted-foreground" },
  online: { label: "Server Running", dot: "bg-green-500" },
  offline: { label: "Server Offline", dot: "bg-red-500" },
} as const;

/** Header badge showing whether the local backend is reachable. */
export function ServerStatusIndicator() {
  const status = useServerStatus();
  const { label, dot } = CONFIG[status];

  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
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
