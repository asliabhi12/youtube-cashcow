"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, ExternalLink, RotateCw, ScrollText } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { LogsDrawer } from "@/features/job-logs/logs-drawer";
import {
  createJob,
  jobDownloadUrl,
  listJobs,
  type Job,
  type JobStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; jobs: Job[] };

/** How often to refresh the job list while any job is still in flight. */
const REFRESH_INTERVAL_MS = 2000;

/** Format an ISO timestamp for display, falling back to the raw value. */
function formatCreatedAt(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

/** Tailwind classes for the status pill, by status. */
const STATUS_STYLES: Record<JobStatus, string> = {
  pending: "border-amber-500/40 text-amber-600 dark:text-amber-400",
  running: "border-sky-500/40 text-sky-600 dark:text-sky-400",
  completed: "border-emerald-500/40 text-emerald-600 dark:text-emerald-400",
  failed: "border-red-500/40 text-red-600 dark:text-red-400",
};

export default function JobsPage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [openJob, setOpenJob] = useState<Job | null>(null);

  const load = useCallback(async (signal?: AbortSignal): Promise<void> => {
    try {
      const jobs = await listJobs(signal);
      setState({ kind: "ready", jobs });
    } catch {
      // Ignore aborts from unmount/refresh cycles; surface real failures only.
      if (!signal?.aborted) {
        setState({ kind: "error" });
      }
    }
  }, []);

  // Initial load.
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  // Poll for status transitions while any job is pending or running. Log
  // streaming uses SSE; this lightweight poll only keeps the row status fresh.
  useEffect(() => {
    if (state.kind !== "ready") {
      return;
    }
    const hasActive = state.jobs.some(
      (job) => job.status === "pending" || job.status === "running",
    );
    if (!hasActive) {
      return;
    }
    const timer = setInterval(() => void load(), REFRESH_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [state, load]);

  // Keep the open drawer's job object in sync with refreshed data so the
  // drawer header reflects the latest status.
  useEffect(() => {
    if (openJob === null || state.kind !== "ready") {
      return;
    }
    const latest = state.jobs.find((job) => job.id === openJob.id);
    if (latest !== undefined && latest.status !== openJob.status) {
      setOpenJob(latest);
    }
  }, [state, openJob]);

  async function handleRerun(job: Job): Promise<void> {
    try {
      // Re-run preserves the original job's creative profile.
      await createJob({
        url: job.url,
        preset: job.preset,
        export_quality: job.export_quality,
      });
      await load();
    } catch {
      setState({ kind: "error" });
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-xl font-semibold tracking-tight">Jobs</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Your processing queue and completed videos.
      </p>

      <div className="mt-8">
        {state.kind === "loading" && (
          <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed">
            <p className="text-sm text-muted-foreground">Loading jobs…</p>
          </div>
        )}

        {state.kind === "error" && (
          <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed">
            <p className="text-sm text-muted-foreground">
              Could not load jobs. Is the server running?
            </p>
          </div>
        )}

        {state.kind === "ready" && state.jobs.length === 0 && (
          <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed">
            <p className="text-sm text-muted-foreground">No jobs yet.</p>
          </div>
        )}

        {state.kind === "ready" && state.jobs.length > 0 && (
          <ul className="flex flex-col gap-2">
            {state.jobs.map((job) => (
              <li
                key={job.id}
                className="flex items-center justify-between gap-4 rounded-lg border px-4 py-3"
              >
                <div className="flex min-w-0 flex-col gap-1">
                  <span className="truncate text-sm font-medium">{job.url}</span>
                  <span className="text-xs text-muted-foreground">
                    {formatCreatedAt(job.created_at)}
                  </span>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <span
                    className={cn(
                      "rounded-full border px-2.5 py-0.5 text-xs font-medium",
                      STATUS_STYLES[job.status],
                    )}
                  >
                    {job.status}
                  </span>

                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => void handleRerun(job)}
                    title="Re-run this URL"
                  >
                    <RotateCw />
                    Run
                  </Button>

                  <a
                    href={job.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Open source URL"
                    className={cn(buttonVariants({ size: "sm", variant: "ghost" }))}
                  >
                    <ExternalLink />
                    View
                  </a>

                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setOpenJob(job)}
                    title="View live logs"
                  >
                    <ScrollText />
                    Logs
                  </Button>

                  {job.status === "completed" && (
                    <a
                      href={jobDownloadUrl(job.id)}
                      title="Download output"
                      className={cn(buttonVariants({ size: "sm", variant: "outline" }))}
                    >
                      <Download />
                      Download
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <LogsDrawer job={openJob} onClose={() => setOpenJob(null)} />
    </div>
  );
}
