"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";

export type ServerStatus = "checking" | "online" | "offline";

const POLL_INTERVAL_MS = 5000;

/**
 * Poll the backend health endpoint and report connection status.
 * Checks on mount and then every {@link POLL_INTERVAL_MS}.
 */
export function useServerStatus(): ServerStatus {
  const [status, setStatus] = useState<ServerStatus>("checking");

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    async function check(): Promise<void> {
      try {
        await getHealth(controller.signal);
        if (active) {
          setStatus("online");
        }
      } catch {
        if (active) {
          setStatus("offline");
        }
      }
    }

    void check();
    const timer = setInterval(() => void check(), POLL_INTERVAL_MS);

    return () => {
      active = false;
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  return status;
}
