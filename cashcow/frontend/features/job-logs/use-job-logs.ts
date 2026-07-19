"use client";

import { useEffect, useRef, useState } from "react";

import { type JobLogEntry, jobLogsEventsUrl } from "@/lib/api";

/** Connection state of a job's live log stream. */
export type LogStreamStatus = "connecting" | "streaming" | "done" | "error";

export interface JobLogsState {
  entries: JobLogEntry[];
  status: LogStreamStatus;
}

/**
 * Subscribe to a job's Server-Sent Events log stream.
 *
 * The backend replays the job's existing history on connect and then pushes
 * each new entry, so a single ``EventSource`` yields both the backlog and live
 * updates with no polling and no duplicates. A named ``end`` event signals the
 * job reached a terminal state; we close the connection on it so the browser
 * does not reconnect, while the accumulated entries stay in state.
 *
 * Pass ``null`` to stay idle (e.g. while the drawer is closed).
 */
export function useJobLogs(jobId: string | null): JobLogsState {
  const [entries, setEntries] = useState<JobLogEntry[]>([]);
  const [status, setStatus] = useState<LogStreamStatus>("connecting");
  // Once the stream has ended cleanly, ignore the connection-drop error the
  // browser may raise as the server closes the response.
  const endedRef = useRef(false);

  useEffect(() => {
    if (jobId === null) {
      return;
    }

    // Reset for a fresh subscription; a reused hook may have prior entries.
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
        // Ignore frames that are not valid JSON log entries.
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
      // EventSource retries transient failures on its own while CONNECTING; a
      // CLOSED socket is a hard failure worth surfacing.
      if (source.readyState === EventSource.CLOSED) {
        setStatus("error");
      }
    };

    return () => {
      source.close();
    };
  }, [jobId]);

  return { entries, status };
}
