"use client";

import { DemoModeBanner } from "@/components/demo-mode/demo-mode-banner";
import { useDemoMode } from "@/components/demo-mode/use-demo-mode";
import { WorkflowForm } from "@/features/workflow-form/workflow-form";

export default function DashboardPage() {
  const { isDemoMode } = useDemoMode();

  return (
    <div className="mx-auto max-w-xl px-6 py-12">
      {isDemoMode && <DemoModeBanner />}
      <h1 className="text-xl font-semibold tracking-tight">New Workflow</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Configure a creative profile, then run it through the pipeline.
      </p>
      <div className="mt-8">
        <WorkflowForm isDemoMode={isDemoMode} />
      </div>
    </div>
  );
}
