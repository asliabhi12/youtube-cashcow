"use client";

import { useEffect, useState } from "react";

import { listJobs, type Job } from "@/lib/api";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; jobs: Job[] };

/** Format an ISO timestamp for display, falling back to the raw value. */
function formatCreatedAt(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

export default function JobsPage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    async function load(): Promise<void> {
      try {
        const jobs = await listJobs(controller.signal);
        if (active) {
          setState({ kind: "ready", jobs });
        }
      } catch {
        if (active) {
          setState({ kind: "error" });
        }
      }
    }

    void load();

    return () => {
      active = false;
      controller.abort();
    };
  }, []);

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
                <span className="shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                  {job.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
