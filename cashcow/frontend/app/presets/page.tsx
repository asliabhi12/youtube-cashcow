export default function PresetsPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-xl font-semibold tracking-tight">Presets</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Saved workflow configurations you can reuse across videos.
      </p>

      <div className="mt-8 flex min-h-40 items-center justify-center rounded-lg border border-dashed">
        <p className="text-sm text-muted-foreground">No presets yet.</p>
      </div>
    </div>
  );
}
