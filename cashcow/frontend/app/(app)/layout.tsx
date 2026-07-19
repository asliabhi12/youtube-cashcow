import type { ReactNode } from "react";

import { DemoModeProvider } from "@/components/demo-mode/demo-mode-provider";
import { AppShell } from "@/components/layout/app-shell";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <DemoModeProvider>
      <AppShell>{children}</AppShell>
    </DemoModeProvider>
  );
}
