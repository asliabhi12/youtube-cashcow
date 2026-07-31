"use client";

import { useEffect, useRef, useState } from "react";

import { fetchJobLogs, type JobLogEntry, jobLogsEventsUrl } from "@/lib/api";

/** Connection state of a job's live log stream. */
export type LogStreamStatus = "connecting" | "streaming" | "done" | "error";

export interface JobLogsState {
  entries: JobLogEntry[];
  status: LogStreamStatus;
}

/**
 * Subscribe to a job's Server-Sent Events log stream with HTTP polling fallback.
 *
 * Primary: EventSource stream pushes live logs and progress events over SSE.
 * Fallback: If proxy/tunnel (e.g. Cloudflare Quick Tunnel) drops the SSE socket,
 * falls back to polling `GET /jobs/{id}/logs` every 2 seconds so the UI remains
 * updated and never appears broken.
 *
 * Pass `null` to stay idle (e.g. while the drawer is closed).
 */
export function useJobLogs(jobId: string | null): JobLogsState {
  const [entries, setEntries] = useState<JobLogEntry[]>([]);
  const [status, setStatus] = useState<LogStreamStatus>("connecting");
  const endedRef = useRef(false);

  useEffect(() => {
    if (jobId === null) {
      return;
    }

    endedRef.current = false;
    setEntries([]);
    setStatus("connecting");

    const source = new EventSource(jobLogsEventsUrl(jobId));

    source.onmessage = (event) => {
      try {
        const entry = JSON.parse(event.data) as JobLogEntry;
        setEntries((prev) => [...prev, entry]);
        setStatus("streaming");
      } catch {
        // Ignore non-log JSON frames (e.g., progress frames)
      }
    };

    source.addEventListener("end", () => {
      endedRef.current = true;
      setStatus("done");
      source.close();
    });

    source.onerror = () => {
      if (endedRef.current) {
        return;
      }
      if (source.readyState === EventSource.CLOSED) {
        setStatus("error");
      }
    };

    return () => {
      source.close();
    };
  }, [jobId]);

  // Fallback HTTP polling when SSE stream encounters an error over tunnels/proxies
  useEffect(() => {
    if (jobId === null || status !== "error" || endedRef.current) {
      return;
    }

    let active = true;
    const pollLogs = async () => {
      try {
        const history = await fetchJobLogs(jobId);
        if (active) {
          setEntries(history);
        }
      } catch {
        // Non-fatal poll failure
      }
    };

    void pollLogs();
    const timer = setInterval(() => void pollLogs(), 2000);

    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [jobId, status]);

  return { entries, status };
}
