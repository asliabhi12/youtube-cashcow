"use client";

import { useDemoMode } from "@/components/demo-mode/use-demo-mode";
import { AlertCircle, MonitorCog, PlayCircle } from "lucide-react";

export function DemoModeBanner() {
  const { isDemoMode, status } = useDemoMode();

  if (status === "checking") {
    return (
      <div className="mb-6 rounded-lg border border-primary/20 bg-card/80 px-5 py-3 shadow-sm">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <MonitorCog className="size-4 text-primary" />
          Checking backend connection...
        </p>
      </div>
    );
  }

  if (isDemoMode) {
    return (
      <div className="mb-6 overflow-hidden rounded-xl border border-primary/20 bg-card/85 shadow-lg shadow-[var(--shadow-color)] backdrop-blur-sm">
        <div className="border-b bg-accent/30 px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-md border border-primary/25 bg-primary/10 text-primary">
              <PlayCircle className="size-4" />
            </span>
            <div>
              <p className="font-semibold tracking-tight text-foreground">Demo Mode</p>
              <p className="text-sm text-muted-foreground">
                This dashboard is running without a backend.
              </p>
            </div>
          </div>
        </div>
        <div className="grid gap-3 p-5 text-sm text-muted-foreground sm:grid-cols-3">
          <div className="rounded-lg border bg-background/45 p-3">
            <p className="font-medium text-foreground">Preview enabled</p>
            <p className="mt-1 text-xs leading-relaxed">Explore the interface and configuration flow.</p>
          </div>
          <div className="rounded-lg border bg-background/45 p-3">
            <p className="font-medium text-foreground">Backend offline</p>
            <p className="mt-1 text-xs leading-relaxed">Real downloads, AI metadata, and uploads are paused.</p>
          </div>
          <div className="rounded-lg border bg-background/45 p-3">
            <p className="flex items-center gap-1.5 font-medium text-foreground">
              <AlertCircle className="size-3.5 text-primary" />
              Start backend
            </p>
            <p className="mt-1 text-xs leading-relaxed">Start the backend to enable real workflows.</p>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
