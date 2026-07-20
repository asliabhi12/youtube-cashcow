export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:py-8">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">
        Workspace
      </p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">Settings</h1>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        Application configuration.
      </p>

      <div className="mt-6 flex min-h-56 items-center justify-center rounded-xl border border-dashed bg-card/55 shadow-sm">
        <div className="text-center">
          <p className="text-sm font-medium text-foreground">No settings yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Configuration controls will appear here when available.</p>
        </div>
      </div>
    </div>
  );
}
