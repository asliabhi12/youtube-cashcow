"use client";

import { DemoModeBanner } from "@/components/demo-mode/demo-mode-banner";
import { useDemoMode } from "@/components/demo-mode/use-demo-mode";
import { WorkflowForm } from "@/features/workflow-form/workflow-form";
import { Bot, Clapperboard, FileText, UploadCloud, Workflow } from "lucide-react";

const WORKFLOW_CARDS = [
  { label: "Source", value: "YouTube URL", icon: Clapperboard },
  { label: "Profile", value: "Creative rules", icon: Workflow },
  { label: "AI", value: "Metadata", icon: Bot },
  { label: "Output", value: "Export or upload", icon: UploadCloud },
];

export default function DashboardPage() {
  const { isDemoMode } = useDemoMode();

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
      {isDemoMode && <DemoModeBanner />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="overflow-hidden rounded-xl border bg-card/85 shadow-xl shadow-[var(--shadow-color)]">
          <div className="border-b bg-accent/20 px-5 py-5 sm:px-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">
                  New workflow
                </p>
                <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
                  Turn a source video into a finished publishing asset.
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                  Configure the clip, creative profile, AI metadata, and export quality in one run.
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2 rounded-lg border bg-background/55 px-3 py-2 text-xs text-muted-foreground">
                <FileText className="size-4 text-primary" />
                Profile-aware
              </div>
            </div>
          </div>
          <div className="px-5 py-6 sm:px-6">
            <WorkflowForm isDemoMode={isDemoMode} />
          </div>
        </section>

        <aside className="flex flex-col gap-4">
          <section className="rounded-xl border bg-card/80 p-5 shadow-lg shadow-[var(--shadow-color)]">
            <p className="text-sm font-semibold tracking-tight">Pipeline</p>
            <div className="mt-4 grid gap-3">
              {WORKFLOW_CARDS.map((item) => (
                <div key={item.label} className="flex items-center gap-3 rounded-lg border bg-background/45 p-3">
                  <span className="grid size-9 place-items-center rounded-md bg-primary/10 text-primary">
                    <item.icon className="size-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      {item.label}
                    </p>
                    <p className="truncate text-sm font-medium">{item.value}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-xl border bg-card/80 p-5 shadow-lg shadow-[var(--shadow-color)]">
            <p className="text-sm font-semibold tracking-tight">Run status</p>
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Backend</span>
                <span className={isDemoMode ? "text-warning-foreground" : "text-success-foreground"}>
                  {isDemoMode ? "Demo only" : "Ready"}
                </span>
              </div>
              <div className="h-2 rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: isDemoMode ? "28%" : "100%" }}
                />
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {isDemoMode
                  ? "Start the backend to unlock downloads, processing, metadata, and upload actions."
                  : "The local backend is available for real workflow execution."}
              </p>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
