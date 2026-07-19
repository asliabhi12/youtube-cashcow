export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Application configuration.
      </p>

      <div className="mt-8 flex min-h-40 items-center justify-center rounded-lg border border-dashed">
        <p className="text-sm text-muted-foreground">No settings yet.</p>
      </div>
    </div>
  );
}
