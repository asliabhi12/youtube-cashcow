"use client";

import { createContext, type ReactNode } from "react";

import { useServerStatus } from "@/features/server-status/use-server-status";
import type { ServerStatus } from "@/features/server-status/use-server-status";

export const DemoModeContext = createContext<{
  status: ServerStatus;
  isDemoMode: boolean;
}>({ status: "checking", isDemoMode: false });

export function DemoModeProvider({ children }: { children: ReactNode }) {
  const status = useServerStatus();
  const isDemoMode = status === "offline";

  return (
    <DemoModeContext.Provider value={{ status, isDemoMode }}>
      {children}
    </DemoModeContext.Provider>
  );
}
