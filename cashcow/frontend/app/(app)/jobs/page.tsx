"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Clipboard, Download, ExternalLink, RotateCw, ScrollText, Square, UploadCloud, X } from "lucide-react";

import { DemoModeBanner } from "@/components/demo-mode/demo-mode-banner";
import { useDemoMode } from "@/components/demo-mode/use-demo-mode";

import { Button, buttonVariants } from "@/components/ui/button";
import { LogsDrawer } from "@/features/job-logs/logs-drawer";
import {
  JobDestinationStatusBadge,
  PlatformBadge,
} from "@/features/destinations/platforms";
import {
  createJob,
  cancelJob,
  deleteJob,
  fetchJobMetadata,
  jobDownloadUrl,
  jobLogsEventsUrl,
  listJobs,
  retryPublish,
  type Job,
  type JobMetadata,
  type JobStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; jobs: Job[] };

type MetadataState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; metadata: JobMetadata }
  | { kind: "unavailable" };

type MetadataField = "title" | "description" | "tags";

/** How often to refresh the job list while any job is queued or running. */
const REFRESH_INTERVAL_MS = 2000;
const COPIED_TIMEOUT_MS = 1400;

function metadataCopyText(metadata: JobMetadata, field: MetadataField): string {
  if (field === "tags") {
    return metadata.tags.join(", ");
  }
  return metadata[field];
}

/** Format an ISO timestamp for display, falling back to the raw value. */
function formatCreatedAt(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

/** Tailwind classes for the status pill, by status. */
const STATUS_STYLES: Record<JobStatus, string> = {
  pending: "border-warning-border text-warning-foreground",
  queued: "border-info-border text-info-foreground",
  running: "border-info-border text-info-foreground",
  cancelling: "border-warning-border text-warning-foreground",
  cancelled: "border-muted-foreground/40 text-muted-foreground",
  completed: "border-success-border text-success-foreground",
  failed: "border-danger-border text-danger-foreground",
  upload_failed: "border-warning-border text-warning-foreground",
};

export default function JobsPage() {
  const { isDemoMode } = useDemoMode();
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
        job.status === "running" ||
        job.status === "cancelling",
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
        destination_ids: job.destinations.map((destination) => destination.destinationId),
      });
      await load();
    } catch {
      setActionError("Could not start the job. Is the server running?");
    }
  }

  async function handleRetryUpload(job: Job): Promise<void> {
    setActionError(null);
    try {
      await retryPublish(job.id);
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not retry the upload.");
    }
  }

  async function handleCancel(job: Job): Promise<void> {
    setActionError(null);
    if (!window.confirm("Stop this job? Completed work will be preserved where possible.")) {
      return;
    }
    try {
      await cancelJob(job.id);
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not stop the job.");
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

  if (isDemoMode) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:py-8">
        <DemoModeBanner />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:py-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">
            Queue
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Jobs</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            One job runs at a time; the rest wait in a simple queue.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          <RotateCw />
          Refresh
        </Button>
      </div>

      {actionError !== null && (
        <p className="mt-5 rounded-lg border border-danger-border bg-danger-surface px-4 py-3 text-sm text-danger-foreground">
          {actionError}
        </p>
      )}

      <div className="mt-6">
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
            onRetryUpload={handleRetryUpload}
            onCancel={handleCancel}
            onRemove={handleRemove}
            onOpenLogs={setOpenJob}
            onRefresh={load}
          />
        )}
      </div>

      <LogsDrawer job={openJob} onClose={() => setOpenJob(null)} />
    </div>
  );
}

function EmptyPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-56 items-center justify-center rounded-xl border border-dashed bg-card/55 shadow-sm">
      <p className="text-sm text-muted-foreground">{children}</p>
    </div>
  );
}

/** Format elapsed running time (excluding waiting time in queue). */
function formatElapsedTime(startedAt: string | null, finishedAt: string | null, now: Date): string {
  if (!startedAt) return "00:00";
  const start = new Date(startedAt).getTime();
  const end = finishedAt ? new Date(finishedAt).getTime() : now.getTime();
  const totalMs = Math.max(0, end - start);
  const totalSecs = Math.floor(totalMs / 1000);
  const hours = Math.floor(totalSecs / 3600);
  const mins = Math.floor((totalSecs % 3600) / 60);
  const secs = totalSecs % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  if (hours > 0) {
    return `${pad(hours)}:${pad(mins)}:${pad(secs)}`;
  }
  return `${pad(mins)}:${pad(secs)}`;
}

/**
 * Groups jobs into the four queue sections and renders each as its own titled
 * block. "pending" is folded into Running (it is the brief pre-start state), and
 * queued jobs are ordered by their live queue position so #1 is next up.
 */
function JobSections({
  jobs,
  onRerun,
  onRetryUpload,
  onCancel,
  onRemove,
  onOpenLogs,
  onRefresh,
}: {
  jobs: Job[];
  onRerun: (job: Job) => void;
  onRetryUpload: (job: Job) => void;
  onCancel: (job: Job) => void;
  onRemove: (job: Job) => void;
  onOpenLogs: (job: Job) => void;
  onRefresh: () => void;
}) {
  const running = jobs.filter((j) => j.status === "running" || j.status === "pending");
  const cancelling = jobs.filter((j) => j.status === "cancelling");
  const queued = jobs
    .filter((j) => j.status === "queued")
    .sort((a, b) => (a.queue_position ?? 0) - (b.queue_position ?? 0));
  const completed = jobs.filter((j) => j.status === "completed");
  const cancelled = jobs.filter((j) => j.status === "cancelled");
  const failed = jobs.filter((j) => j.status === "failed" || j.status === "upload_failed");

  return (
    <div className="flex flex-col gap-8">
      <Section title="Running" count={running.length}>
        {running.map((job) => (
          <JobRow key={job.id} job={job} onRerun={onRerun} onRetryUpload={onRetryUpload} onCancel={onCancel} onRemove={onRemove} onOpenLogs={onOpenLogs} onRefresh={onRefresh} />
        ))}
      </Section>
      <Section title="Cancelling" count={cancelling.length}>
        {cancelling.map((job) => (
          <JobRow key={job.id} job={job} onRerun={onRerun} onRetryUpload={onRetryUpload} onCancel={onCancel} onRemove={onRemove} onOpenLogs={onOpenLogs} onRefresh={onRefresh} />
        ))}
      </Section>
      <Section title="Queued" count={queued.length}>
        {queued.map((job) => (
          <JobRow key={job.id} job={job} onRerun={onRerun} onRetryUpload={onRetryUpload} onCancel={onCancel} onRemove={onRemove} onOpenLogs={onOpenLogs} onRefresh={onRefresh} />
        ))}
      </Section>
      <Section title="Completed" count={completed.length}>
        {completed.map((job) => (
          <JobRow key={job.id} job={job} onRerun={onRerun} onRetryUpload={onRetryUpload} onCancel={onCancel} onRemove={onRemove} onOpenLogs={onOpenLogs} onRefresh={onRefresh} />
        ))}
      </Section>
      <Section title="Cancelled" count={cancelled.length}>
        {cancelled.map((job) => (
          <JobRow key={job.id} job={job} onRerun={onRerun} onRetryUpload={onRetryUpload} onCancel={onCancel} onRemove={onRemove} onOpenLogs={onOpenLogs} onRefresh={onRefresh} />
        ))}
      </Section>
      <Section title="Failed" count={failed.length}>
        {failed.map((job) => (
          <JobRow key={job.id} job={job} onRerun={onRerun} onRetryUpload={onRetryUpload} onCancel={onCancel} onRemove={onRemove} onOpenLogs={onOpenLogs} onRefresh={onRefresh} />
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
    <section className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold tracking-tight text-foreground/95">{title}</h2>
        <span className="rounded-full border bg-card px-2 py-0.5 text-xs font-medium text-muted-foreground">
          {count}
        </span>
      </div>
      <ul className="flex flex-col gap-3">{children}</ul>
    </section>
  );
}

/** A single job row. Actions shown adapt to the job's status. */
function JobRow({
  job: initialJob,
  onRerun,
  onRetryUpload,
  onCancel,
  onRemove,
  onOpenLogs,
  onRefresh,
}: {
  job: Job;
  onRerun: (job: Job) => void;
  onRetryUpload: (job: Job) => void;
  onCancel: (job: Job) => void;
  onRemove: (job: Job) => void;
  onOpenLogs: (job: Job) => void;
  onRefresh: () => void;
}) {
  const [liveProgress, setLiveProgress] = useState(initialJob.progress);
  const [liveStatus, setLiveStatus] = useState(initialJob.status_message);
  const [metadataState, setMetadataState] = useState<MetadataState>({ kind: "idle" });
  const [busyAction, setBusyAction] = useState<"retry" | "cancel" | null>(null);
  const [now, setNow] = useState(() => new Date());

  const isQueued = initialJob.status === "queued";
  const isRunning =
    initialJob.status === "running" ||
    initialJob.status === "pending" ||
    initialJob.status === "cancelling";
  const canCancel =
    initialJob.status === "running" ||
    initialJob.status === "pending" ||
    initialJob.status === "queued";
  const isFinished =
    initialJob.status === "completed" ||
    initialJob.status === "failed" ||
    initialJob.status === "upload_failed" ||
    initialJob.status === "cancelled";

  async function runBusy(
    action: "retry" | "cancel",
    callback: (job: Job) => void | Promise<void>,
  ): Promise<void> {
    setBusyAction(action);
    try {
      await callback(initialJob);
    } finally {
      setBusyAction(null);
    }
  }

  // Sync state if initialJob changes (e.g. from polling).
  useEffect(() => {
    setLiveProgress((prev) => Math.max(prev, initialJob.progress));
    setLiveStatus(initialJob.status_message);
  }, [initialJob]);

  // Tick timer for running jobs.
  useEffect(() => {
    if (isRunning) {
      const timer = setInterval(() => {
        setNow(new Date());
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [isRunning]);

  // SSE subscription.
  useEffect(() => {
    if (!isRunning) {
      return;
    }

    const source = new EventSource(jobLogsEventsUrl(initialJob.id));

    source.addEventListener("progress", (event) => {
      try {
        const data = JSON.parse(event.data) as { progress: number; status: string };
        setLiveProgress((prev) => Math.max(prev, data.progress));
        setLiveStatus(data.status);
      } catch (err) {
        console.error("Failed to parse progress SSE event", err);
      }
    });

    source.addEventListener("end", () => {
      source.close();
      onRefresh();
    });

    source.onerror = () => {
      // Don't close, EventSource will retry automatically.
    };

    return () => {
      source.close();
    };
  }, [initialJob.id, isRunning, onRefresh]);

  useEffect(() => {
    if (initialJob.status !== "completed") {
      setMetadataState({ kind: "idle" });
      return;
    }

    if (initialJob.metadata_status === "generating" || initialJob.metadata_status === "idle") {
      setMetadataState({ kind: "loading" });
      return;
    }

    if (initialJob.metadata_status === "unavailable") {
      setMetadataState({ kind: "unavailable" });
      return;
    }

    const controller = new AbortController();
    setMetadataState({ kind: "loading" });
    fetchJobMetadata(initialJob.id, controller.signal)
      .then((metadata) => {
        setMetadataState({ kind: "ready", metadata });
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setMetadataState({ kind: "unavailable" });
        }
      });
    return () => controller.abort();
  }, [initialJob.id, initialJob.status, initialJob.metadata_status]);

  const displayTitle = initialJob.output_name
    ? initialJob.output_name.replace(/\.mp4$/, "")
    : initialJob.url;

  const elapsedStr = formatElapsedTime(initialJob.started_at, initialJob.finished_at, now);

  // Setup styles for progress bar color and layout theme
  let progressColor = "bg-info";
  let borderGlow = "border-muted/60";
  let bgGradient = "from-background via-muted/5 to-muted/5";

  if (
    initialJob.status === "running" ||
    initialJob.status === "pending" ||
    initialJob.status === "cancelling"
  ) {
    progressColor = "bg-info";
    borderGlow = "border-info-border shadow-sm";
    bgGradient = "from-background via-info-surface to-background";
  } else if (initialJob.status === "completed") {
    progressColor = "bg-success";
    borderGlow = "border-success-border";
    bgGradient = "from-background via-success-surface to-background";
  } else if (initialJob.status === "cancelled") {
    progressColor = "bg-muted-foreground";
    borderGlow = "border-muted-foreground/20";
    bgGradient = "from-background via-muted/10 to-background";
  } else if (initialJob.status === "failed") {
    progressColor = "bg-danger";
    borderGlow = "border-danger-border";
    bgGradient = "from-background via-danger-surface to-background";
  } else if (initialJob.status === "upload_failed") {
    progressColor = "bg-warning";
    borderGlow = "border-warning-border";
    bgGradient = "from-background via-warning-surface to-background";
  } else if (initialJob.status === "queued") {
    progressColor = "bg-info/60";
    borderGlow = "border-info-border";
    bgGradient = "from-background via-info-surface to-background";
  }

  return (
    <li className={cn(
      "relative overflow-hidden rounded-xl border bg-card/80 bg-gradient-to-br p-5 shadow-lg shadow-[var(--shadow-color)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl",
      borderGlow,
      bgGradient,
    )}>
      {/* Subtle background blur/glow for active elements */}
      {isRunning && (
        <>
          <div className="absolute -right-20 -top-20 -z-10 h-40 w-40 rounded-full bg-info-surface blur-3xl" />
          <div className="absolute -left-20 -bottom-20 -z-10 h-40 w-40 rounded-full bg-primary/10 blur-3xl" />
        </>
      )}

      <div className="flex flex-col gap-4">
        {/* Top Line: Title and Status Badge */}
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              {isQueued && initialJob.queue_position !== null && (
                <span
                  className="flex size-5 shrink-0 items-center justify-center rounded-full border border-info-border text-[10px] font-bold text-info-foreground tabular-nums"
                  title={`Position ${initialJob.queue_position} in the queue`}
                >
                  #{initialJob.queue_position}
                </span>
              )}
              <h3 className="truncate text-sm font-semibold tracking-tight text-foreground" title={initialJob.url}>
                {displayTitle}
              </h3>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {isQueued
                ? `Submitted: ${formatCreatedAt(initialJob.created_at)}`
                : initialJob.started_at
                  ? `Started: ${formatCreatedAt(initialJob.started_at)}`
                  : `Submitted: ${formatCreatedAt(initialJob.created_at)}`
              }
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className={cn("rounded-full border bg-background/55 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider", STATUS_STYLES[initialJob.status])}>
              {initialJob.status}
            </span>
          </div>
        </div>

        {/* ONE Overall Progress Bar, Percentage, and Status message */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className={cn(
              "font-medium text-muted-foreground truncate max-w-[80%] flex items-center gap-1.5",
              isRunning && "animate-pulse"
            )}>
              {liveStatus}
            </span>
            <span className="font-bold text-foreground tabular-nums text-sm">
              {liveProgress}%
            </span>
          </div>

          <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-secondary">
            <div
              className={cn("h-full rounded-full transition-all duration-500 ease-out", progressColor)}
              style={{ width: `${liveProgress}%` }}
            />
            {isRunning && (
              <div className="absolute inset-0 bg-[linear-gradient(90deg,transparent,color-mix(in_oklch,var(--primary)_25%,transparent),transparent)] bg-[length:200%_100%] animate-shimmer" />
            )}
          </div>
        </div>

        {initialJob.status === "completed" && (
          <JobMetadataPanel state={metadataState} />
        )}

        <JobWorkflow destinations={initialJob.destinations} />

        {/* Bottom Line: Elapsed time and action buttons */}
        <div className="flex flex-col gap-3 border-t border-muted/40 pt-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs font-medium text-muted-foreground">
            {!isQueued ? (
              <>
                Elapsed: <span className="text-foreground font-semibold tabular-nums">{elapsedStr}</span>
              </>
            ) : (
              <span className="italic text-muted-foreground/85">Waiting in queue...</span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            {canCancel && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => void runBusy("cancel", onCancel)}
                disabled={busyAction !== null}
                title="Stop this job"
                className="h-8 text-xs px-2.5 text-warning-foreground"
              >
                <Square className="size-3.5" />
                Stop
              </Button>
            )}

            {initialJob.status === "upload_failed" && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => void runBusy("retry", onRetryUpload)}
                disabled={busyAction !== null}
                title="Retry publish stage"
                className="h-8 text-xs px-2.5"
              >
                <UploadCloud className="size-3.5" />
                {busyAction === "retry" ? "Retrying..." : "Retry Publish"}
              </Button>
            )}

            {isFinished && initialJob.status !== "upload_failed" && (
              <Button size="sm" variant="ghost" onClick={() => onRerun(initialJob)} title="Re-run this URL" className="h-8 text-xs px-2.5">
                <RotateCw className="size-3.5" />
                Run
              </Button>
            )}

            <a
              href={initialJob.url}
              target="_blank"
              rel="noopener noreferrer"
              title="Open source URL"
              className={cn(buttonVariants({ size: "sm", variant: "ghost" }), "h-8 text-xs px-2.5")}
            >
              <ExternalLink className="size-3.5" />
              View
            </a>

            <Button size="sm" variant="ghost" onClick={() => onOpenLogs(initialJob)} title="View live logs" className="h-8 text-xs px-2.5">
              <ScrollText className="size-3.5" />
              Logs
            </Button>

            {initialJob.status === "completed" && (
              <a
                href={jobDownloadUrl(initialJob.id)}
                title="Download output"
                className={cn(buttonVariants({ size: "sm", variant: "outline" }), "h-8 text-xs px-2.5")}
              >
                <Download className="size-3.5" />
                Download
              </a>
            )}

            {!isRunning && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onRemove(initialJob)}
                title={isQueued ? "Remove from queue" : "Remove from history"}
                className="h-8 w-8 p-0 text-muted-foreground hover:text-danger-foreground"
              >
                <X className="size-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

function JobWorkflow({ destinations }: { destinations: Job["destinations"] }) {
  const steps = ["Download", "Edit", "Metadata", "Render"];
  return (
    <div className="rounded-lg border bg-background/55 p-3">
      <div className="flex flex-wrap items-center gap-2">
        {steps.map((step) => (
          <span
            key={step}
            className="rounded-full border border-success-border bg-success-surface px-2.5 py-1 text-xs font-medium text-success-foreground"
          >
            {step}
          </span>
        ))}
        <span className="rounded-full border border-info-border bg-info-surface px-2.5 py-1 text-xs font-medium text-info-foreground">
          Publish
        </span>
        <span className="rounded-full border bg-card px-2.5 py-1 text-xs font-medium text-muted-foreground">
          Done
        </span>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {destinations.length === 0 ? (
          <p className="rounded-md border border-dashed bg-card/45 px-3 py-2 text-xs text-muted-foreground sm:col-span-2 lg:col-span-3">
            No publishing destinations selected.
          </p>
        ) : (
          destinations.map((destination) => (
            <div
              key={destination.id}
              className="flex min-w-0 items-center justify-between gap-2 rounded-md border bg-card/55 px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-foreground">
                  {destination.name}
                </p>
                <div className="mt-1">
                  <PlatformBadge platform={destination.platform} />
                </div>
              </div>
              <JobDestinationStatusBadge status={destination.status} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function JobMetadataPanel({ state }: { state: MetadataState }) {
  const [copiedField, setCopiedField] = useState<MetadataField | null>(null);

  async function copyField(metadata: JobMetadata, field: MetadataField): Promise<void> {
    await navigator.clipboard.writeText(metadataCopyText(metadata, field));
    setCopiedField(field);
    window.setTimeout(() => setCopiedField(null), COPIED_TIMEOUT_MS);
  }

  if (state.kind === "loading" || state.kind === "idle") {
    return (
      <div className="rounded-lg border border-dashed border-muted-foreground/25 bg-background/60 px-3 py-2 text-xs text-muted-foreground">
        Generating AI metadata...
      </div>
    );
  }

  if (state.kind === "unavailable") {
    return (
      <div className="rounded-lg border border-muted-foreground/20 bg-background/60 px-3 py-2 text-xs text-muted-foreground">
        AI metadata unavailable.
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-success-border bg-success-surface px-3 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-success-foreground">
        AI Metadata
      </p>
      <div className="space-y-1">
        <MetadataFieldHeader
          label="Title"
          copied={copiedField === "title"}
          onCopy={() => void copyField(state.metadata, "title")}
        />
        <p className="mt-0.5 text-sm font-medium text-foreground">{state.metadata.title}</p>
      </div>
      <div className="space-y-1">
        <MetadataFieldHeader
          label="Description"
          copied={copiedField === "description"}
          onCopy={() => void copyField(state.metadata, "description")}
        />
        <p className="mt-0.5 whitespace-pre-wrap text-sm text-foreground/90">
          {state.metadata.description}
        </p>
      </div>
      <div className="space-y-1">
        <MetadataFieldHeader
          label="Tags"
          copied={copiedField === "tags"}
          onCopy={() => void copyField(state.metadata, "tags")}
        />
        <div className="mt-1 flex flex-wrap gap-1.5">
          {state.metadata.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-success-border bg-background px-2 py-0.5 text-[11px] text-foreground/80"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function MetadataFieldHeader({
  label,
  copied,
  onCopy,
}: {
  label: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="flex min-h-7 items-center justify-between gap-2">
      <p className="text-[11px] font-medium text-muted-foreground">{label}</p>
      <div className="flex items-center gap-2">
        {copied && (
          <span className="text-[11px] font-medium text-success-foreground">
            Copied!
          </span>
        )}
        <Button
          size="sm"
          variant="ghost"
          type="button"
          onClick={onCopy}
          title={`Copy ${label.toLowerCase()}`}
          className="h-7 px-2 text-[11px]"
        >
          {copied ? <Check className="size-3.5" /> : <Clipboard className="size-3.5" />}
          Copy
        </Button>
      </div>
    </div>
  );
}
