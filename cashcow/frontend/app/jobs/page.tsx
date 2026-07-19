"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, ExternalLink, RotateCw, ScrollText, X } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { LogsDrawer } from "@/features/job-logs/logs-drawer";
import {
  createJob,
  deleteJob,
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

/** How often to refresh the job list while any job is queued or running. */
const REFRESH_INTERVAL_MS = 2000;

/** Format an ISO timestamp for display, falling back to the raw value. */
function formatCreatedAt(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

/** Tailwind classes for the status pill, by status. */
const STATUS_STYLES: Record<JobStatus, string> = {
  pending: "border-amber-500/40 text-amber-600 dark:text-amber-400",
  queued: "border-violet-500/40 text-violet-600 dark:text-violet-400",
  running: "border-sky-500/40 text-sky-600 dark:text-sky-400",
  completed: "border-emerald-500/40 text-emerald-600 dark:text-emerald-400",
  failed: "border-red-500/40 text-red-600 dark:text-red-400",
};

export default function JobsPage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [openJob, setOpenJob] = useState<Job | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

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

  // Poll for status transitions while any job is pending, queued, or running,
  // so a job auto-starting from the queue shows up without a manual refresh.
  useEffect(() => {
    if (state.kind !== "ready") {
      return;
    }
    const hasActive = state.jobs.some(
      (job) =>
        job.status === "pending" ||
        job.status === "queued" ||
        job.status === "running",
    );
    if (!hasActive) {
      return;
    }
    const timer = setInterval(() => void load(), REFRESH_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [state, load]);

  // Keep the open drawer's job in sync with refreshed data.
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
    setActionError(null);
    try {
      // Re-run preserves the original job's creative profile.
      await createJob({
        url: job.url,
        profile_id: job.profile_id,
        export_quality: job.export_quality,
      });
      await load();
    } catch {
      setActionError("Could not start the job. Is the server running?");
    }
  }

  async function handleRemove(job: Job): Promise<void> {
    setActionError(null);
    try {
      await deleteJob(job.id);
      if (openJob?.id === job.id) {
        setOpenJob(null);
      }
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not remove the job.");
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-xl font-semibold tracking-tight">Jobs</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        One job runs at a time; the rest wait in a simple queue.
      </p>

      {actionError !== null && (
        <p className="mt-4 rounded-md border border-red-500/40 bg-red-500/5 px-3 py-2 text-sm text-red-600 dark:text-red-400">
          {actionError}
        </p>
      )}

      <div className="mt-8">
        {state.kind === "loading" && (
          <EmptyPanel>Loading jobs…</EmptyPanel>
        )}

        {state.kind === "error" && (
          <EmptyPanel>Could not load jobs. Is the server running?</EmptyPanel>
        )}

        {state.kind === "ready" && state.jobs.length === 0 && (
          <EmptyPanel>No jobs yet.</EmptyPanel>
        )}

        {state.kind === "ready" && state.jobs.length > 0 && (
          <JobSections
            jobs={state.jobs}
            onRerun={handleRerun}
            onRemove={handleRemove}
            onOpenLogs={setOpenJob}
          />
        )}
      </div>

      <LogsDrawer job={openJob} onClose={() => setOpenJob(null)} />
    </div>
  );
}

function EmptyPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed">
      <p className="text-sm text-muted-foreground">{children}</p>
    </div>
  );
}

/**
 * Groups jobs into the four queue sections and renders each as its own titled
 * block. "pending" is folded into Running (it is the brief pre-start state), and
 * queued jobs are ordered by their live queue position so #1 is next up.
 */
function JobSections({
  jobs,
  onRerun,
  onRemove,
  onOpenLogs,
}: {
  jobs: Job[];
  onRerun: (job: Job) => void;
  onRemove: (job: Job) => void;
  onOpenLogs: (job: Job) => void;
}) {
  const running = jobs.filter((j) => j.status === "running" || j.status === "pending");
  const queued = jobs
    .filter((j) => j.status === "queued")
    .sort((a, b) => (a.queue_position ?? 0) - (b.queue_position ?? 0));
  const completed = jobs.filter((j) => j.status === "completed");
  const failed = jobs.filter((j) => j.status === "failed");

  return (
    <div className="flex flex-col gap-8">
      <Section title="Running" count={running.length}>
        {running.map((job) => (
          <JobRow key={job.id} job={job} onRerun={onRerun} onRemove={onRemove} onOpenLogs={onOpenLogs} />
        ))}
      </Section>
      <Section title="Queued" count={queued.length}>
        {queued.map((job) => (
          <JobRow key={job.id} job={job} onRerun={onRerun} onRemove={onRemove} onOpenLogs={onOpenLogs} />
        ))}
      </Section>
      <Section title="Completed" count={completed.length}>
        {completed.map((job) => (
          <JobRow key={job.id} job={job} onRerun={onRerun} onRemove={onRemove} onOpenLogs={onOpenLogs} />
        ))}
      </Section>
      <Section title="Failed" count={failed.length}>
        {failed.map((job) => (
          <JobRow key={job.id} job={job} onRerun={onRerun} onRemove={onRemove} onOpenLogs={onOpenLogs} />
        ))}
      </Section>
    </div>
  );
}

/** A titled section with a count badge; hidden entirely when it has no jobs. */
function Section({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  if (count === 0) {
    return null;
  }
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
        <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
          {count}
        </span>
      </div>
      <ul className="flex flex-col gap-2">{children}</ul>
    </section>
  );
}

/** A single job row. Actions shown adapt to the job's status. */
function JobRow({
  job,
  onRerun,
  onRemove,
  onOpenLogs,
}: {
  job: Job;
  onRerun: (job: Job) => void;
  onRemove: (job: Job) => void;
  onOpenLogs: (job: Job) => void;
}) {
  const isQueued = job.status === "queued";
  const isRunning = job.status === "running" || job.status === "pending";
  const isFinished = job.status === "completed" || job.status === "failed";

  return (
    <li className="flex items-center justify-between gap-4 rounded-lg border px-4 py-3">
      <div className="flex min-w-0 items-center gap-3">
        {isQueued && job.queue_position !== null && (
          <span
            className="flex size-7 shrink-0 items-center justify-center rounded-full border border-violet-500/40 text-xs font-semibold text-violet-600 tabular-nums dark:text-violet-400"
            title={`Position ${job.queue_position} in the queue`}
          >
            #{job.queue_position}
          </span>
        )}
        <div className="flex min-w-0 flex-col gap-1">
          <span className="truncate text-sm font-medium">{job.url}</span>
          <span className="text-xs text-muted-foreground">
            {formatCreatedAt(job.created_at)}
          </span>
          {job.status === "failed" && job.error !== null && (
            <span className="truncate text-xs text-red-600 dark:text-red-400" title={job.error}>
              {job.error}
            </span>
          )}
        </div>
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

        {/* Re-run: useful for finished jobs. Hidden for active ones. */}
        {isFinished && (
          <Button size="sm" variant="ghost" onClick={() => onRerun(job)} title="Re-run this URL">
            <RotateCw />
            Run
          </Button>
        )}

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

        <Button size="sm" variant="ghost" onClick={() => onOpenLogs(job)} title="View live logs">
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

        {/* Remove: queued jobs leave the queue; finished jobs clear from
            history. The running job has no remove control (it can't be cancelled
            mid-pipeline). */}
        {!isRunning && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onRemove(job)}
            title={isQueued ? "Remove from queue" : "Remove from history"}
            className="text-muted-foreground hover:text-red-600 dark:hover:text-red-400"
          >
            <X />
          </Button>
        )}
      </div>
    </li>
  );
}
