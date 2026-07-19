"use client";

import { useDemoMode } from "@/components/demo-mode/use-demo-mode";

export function DemoModeBanner() {
  const { isDemoMode, status } = useDemoMode();

  if (status === "checking") {
    return (
      <div className="mb-6 rounded-lg border border-yellow-500/30 bg-yellow-500/5 px-5 py-3">
        <p className="text-sm text-yellow-400">Connecting to backend…</p>
      </div>
    );
  }

  if (isDemoMode) {
    return (
      <div className="mb-6 rounded-xl border border-purple-500/20 bg-purple-500/5 p-6 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <span className="relative flex size-3 shrink-0">
            <span className="absolute inline-flex size-3 animate-ping rounded-full bg-purple-400/75" />
            <span className="relative inline-flex size-3 rounded-full bg-purple-500" />
          </span>
          <span className="font-semibold text-purple-300">Demo Mode</span>
        </div>
        <div className="mt-3 space-y-1.5 text-sm text-muted-foreground">
          <p>
            <span className="font-medium text-foreground">Backend Status:</span>{" "}
            <span className="text-red-400">Offline</span>
          </p>
          <p>
            CashCow is an offline-first desktop application. This hosted demo
            showcases the interface only.
          </p>
          <p>
            To enable downloading, AI metadata generation, and YouTube
            publishing, start the local backend on your machine.
          </p>
        </div>
      </div>
    );
  }

  return null;
}
