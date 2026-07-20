"use client";

import { useEffect, useLayoutEffect, useRef } from "react";
import { X } from "lucide-react";

import { type Job, type JobLogEntry, type JobLogLevel } from "@/lib/api";
import { cn } from "@/lib/utils";

import { type LogStreamStatus, useJobLogs } from "./use-job-logs";

/** Tailwind text color per log level. */
const LEVEL_COLOR: Record<JobLogLevel, string> = {
  INFO: "text-info-foreground",
  WARNING: "text-warning-foreground",
  ERROR: "text-danger-foreground",
};

/** Render an entry's timestamp as HH:MM:SS, falling back to the raw value. */
function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

/** Short human-readable label for the stream's connection state. */
function statusLabel(status: LogStreamStatus): string {
  switch (status) {
    case "connecting":
      return "Connecting…";
    case "streaming":
      return "Live";
    case "done":
      return "Finished";
    case "error":
      return "Disconnected";
  }
}

interface LogsDrawerProps {
  /** The job whose logs to show, or null when the drawer is closed. */
  job: Job | null;
  onClose: () => void;
}

/**
 * Right-side drawer that streams a job's logs live, GitHub Actions style.
 *
 * Auto-scrolls to the newest entry unless the user has scrolled up to read
 * history, colors entries by level, and keeps the full history visible after
 * the job reaches a terminal state.
 */
export function LogsDrawer({ job, onClose }: LogsDrawerProps) {
  const jobId = job?.id ?? null;
  const { entries, status } = useJobLogs(jobId);

  const scrollRef = useRef<HTMLDivElement>(null);
  // Whether the view is pinned to the bottom; stays true until the user scrolls
  // up, so incoming entries don't yank them away from what they're reading.
  const pinnedRef = useRef(true);

  // Close on Escape while open.
  useEffect(() => {
    if (job === null) {
      return;
    }
    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [job, onClose]);

  // Reset the auto-scroll pin whenever a different job is opened.
  useEffect(() => {
    pinnedRef.current = true;
  }, [jobId]);

  // Auto-scroll to the bottom as entries arrive, but only while pinned.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el !== null && pinnedRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [entries]);

  function handleScroll(): void {
    const el = scrollRef.current;
    if (el === null) {
      return;
    }
    // Treat "within 24px of the bottom" as pinned to tolerate sub-pixel rounding.
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    pinnedRef.current = distanceFromBottom < 24;
  }

  const open = job !== null;

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden={!open}
        onClick={onClose}
        className={cn(
          "fixed inset-0 z-40 bg-foreground/35 backdrop-blur-sm transition-opacity duration-200",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      {/* Drawer panel */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Job logs"
        aria-hidden={!open}
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l bg-background shadow-xl shadow-[var(--shadow-color)] transition-transform duration-200",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        {open && job !== null && (
          <>
            <header className="flex items-start justify-between gap-4 border-b px-5 py-4">
              <div className="flex min-w-0 flex-col gap-1">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold tracking-tight">Logs</h2>
                  <StatusDot status={status} />
                  <span className="text-xs text-muted-foreground">
                    {statusLabel(status)}
                  </span>
                </div>
                <span className="truncate text-xs text-muted-foreground">
                  {job.url}
                </span>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close logs"
                className="-mr-1 rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                <X className="size-4" />
              </button>
            </header>

            <div
              ref={scrollRef}
              onScroll={handleScroll}
              className="flex-1 overflow-y-auto bg-surface px-4 py-3 font-mono text-xs leading-relaxed text-foreground"
            >
              {entries.length === 0 ? (
                <p className="text-muted-foreground">Waiting for logs…</p>
              ) : (
                entries.map((entry, index) => (
                  <LogLine key={index} entry={entry} />
                ))
              )}
            </div>
          </>
        )}
      </aside>
    </>
  );
}

/** One log line: timestamp, level, message, colored by severity. */
function LogLine({ entry }: { entry: JobLogEntry }) {
  return (
    <div className="flex gap-3 whitespace-pre-wrap break-words py-0.5">
      <span className="shrink-0 text-muted-foreground">{formatTime(entry.timestamp)}</span>
      <span className={cn("w-16 shrink-0 font-semibold", LEVEL_COLOR[entry.level])}>
        {entry.level}
      </span>
      <span className="min-w-0 flex-1 text-foreground">{entry.message}</span>
    </div>
  );
}

/** Small colored dot reflecting the live connection state. */
function StatusDot({ status }: { status: LogStreamStatus }) {
  const color =
    status === "streaming"
      ? "bg-success"
      : status === "done"
        ? "bg-muted-foreground"
        : status === "error"
          ? "bg-danger"
          : "bg-warning";
  return (
    <span
      className={cn(
        "size-2 rounded-full",
        color,
        status === "streaming" && "animate-pulse",
      )}
    />
  );
}
