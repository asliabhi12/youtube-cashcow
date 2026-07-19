import { WorkflowForm } from "@/features/workflow-form/workflow-form";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-xl px-6 py-12">
      <h1 className="text-xl font-semibold tracking-tight">New Workflow</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Configure a creative profile, then run it through the pipeline.
      </p>
      <div className="mt-8">
        <WorkflowForm />
      </div>
    </div>
  );
}
