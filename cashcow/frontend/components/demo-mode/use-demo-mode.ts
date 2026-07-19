"use client";

import { useContext } from "react";

import { DemoModeContext } from "@/components/demo-mode/demo-mode-provider";

export function useDemoMode() {
  return useContext(DemoModeContext);
}
