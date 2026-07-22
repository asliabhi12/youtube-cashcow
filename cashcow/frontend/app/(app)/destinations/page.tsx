"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Cable, Pencil, Plus, Search, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  createDestination,
  deleteDestination,
  fetchDestinations,
  updateDestination,
  type Destination,
  type DestinationInput,
  type DestinationPlatform,
  type DestinationStatus,
} from "@/lib/api";
import {
  DestinationStatusBadge,
  PLATFORM_LABELS,
  PLATFORM_OPTIONS,
  PlatformBadge,
  PlatformIcon,
  destinationInitials,
} from "@/features/destinations/platforms";

type DialogState =
  | { kind: "closed" }
  | { kind: "add" }
  | { kind: "edit"; destination: Destination };

const EMPTY_INPUT: DestinationInput = {
  name: "",
  platform: "youtube",
  channelId: "",
  thumbnail: "",
  description: "",
  connectionStatus: "disconnected",
  oauthStatus: "not_configured",
  defaultVisibility: "private",
  defaultPlaylist: "",
  defaultLanguage: "en",
};

export default function DestinationsPage() {
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState<"all" | DestinationPlatform>("all");
  const [status, setStatus] = useState<"all" | DestinationStatus>("all");
  const [dialog, setDialog] = useState<DialogState>({ kind: "closed" });

  const load = useCallback(async (signal?: AbortSignal) => {
    setError(null);
    try {
      setDestinations(await fetchDestinations(signal));
    } catch {
      if (!signal?.aborted) {
        setError("Could not load destinations. Is the server running?");
      }
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return destinations.filter((destination) => {
      const matchesQuery =
        normalized.length === 0 ||
        destination.name.toLowerCase().includes(normalized) ||
        destination.description.toLowerCase().includes(normalized) ||
        destination.channelId.toLowerCase().includes(normalized);
      const matchesPlatform = platform === "all" || destination.platform === platform;
      const matchesStatus = status === "all" || destination.connectionStatus === status;
      return matchesQuery && matchesPlatform && matchesStatus;
    });
  }, [destinations, platform, query, status]);

  async function handleSave(input: DestinationInput, id?: string): Promise<void> {
    if (id === undefined) {
      await createDestination(input);
    } else {
      await updateDestination(id, input);
    }
    setDialog({ kind: "closed" });
    await load();
  }

  async function handleDelete(destination: Destination): Promise<void> {
    if (!window.confirm(`Delete destination "${destination.name}"?`)) {
      return;
    }
    await deleteDestination(destination.id);
    await load();
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">
            Publishing
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Destinations</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Manage where rendered videos can be published.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => window.alert("YouTube connection setup is not implemented yet.")}>
            <Cable />
            Connect YouTube
          </Button>
          <Button onClick={() => setDialog({ kind: "add" })}>
            <Plus />
            Add Destination
          </Button>
        </div>
      </div>

      <div className="mt-6 grid gap-3 rounded-xl border bg-card/55 p-3 shadow-sm md:grid-cols-[minmax(0,1fr)_12rem_12rem]">
        <label className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search destinations"
            className="pl-9"
          />
        </label>
        <select
          value={platform}
          onChange={(event) => setPlatform(event.target.value as "all" | DestinationPlatform)}
          className="h-11 rounded-md border border-input bg-background/70 px-3 text-sm shadow-sm"
        >
          <option value="all">All platforms</option>
          {PLATFORM_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {PLATFORM_LABELS[option]}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value as "all" | DestinationStatus)}
          className="h-11 rounded-md border border-input bg-background/70 px-3 text-sm shadow-sm"
        >
          <option value="all">All statuses</option>
          <option value="connected">Connected</option>
          <option value="disconnected">Disconnected</option>
          <option value="expired">Expired</option>
          <option value="error">Error</option>
        </select>
      </div>

      {error !== null && (
        <p className="mt-4 rounded-lg border border-danger-border bg-danger-surface px-4 py-3 text-sm text-danger-foreground">
          {error}
        </p>
      )}

      <div className="mt-6">
        {loading ? (
          <EmptyPanel>Loading destinations...</EmptyPanel>
        ) : filtered.length === 0 ? (
          <EmptyPanel>No destinations match your filters.</EmptyPanel>
        ) : (
          <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((destination) => (
              <li key={destination.id}>
                <DestinationCard
                  destination={destination}
                  onEdit={() => setDialog({ kind: "edit", destination })}
                  onDelete={() => void handleDelete(destination)}
                />
              </li>
            ))}
          </ul>
        )}
      </div>

      {dialog.kind !== "closed" && (
        <DestinationDialog
          destination={dialog.kind === "edit" ? dialog.destination : undefined}
          onClose={() => setDialog({ kind: "closed" })}
          onSave={handleSave}
        />
      )}
    </div>
  );
}

function DestinationCard({
  destination,
  onEdit,
  onDelete,
}: {
  destination: Destination;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <article className="flex min-h-64 flex-col rounded-xl border bg-card/75 p-4 shadow-lg shadow-[var(--shadow-color)]">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid size-11 shrink-0 place-items-center rounded-lg border border-primary/25 bg-primary/10 text-xs font-bold text-primary">
            {destinationInitials(destination)}
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold tracking-tight">
              {destination.name}
            </h2>
            <div className="mt-1">
              <PlatformBadge platform={destination.platform} />
            </div>
          </div>
        </div>
        <DestinationStatusBadge status={destination.connectionStatus} />
      </div>

      <p className="mt-4 line-clamp-3 min-h-14 text-sm leading-relaxed text-muted-foreground">
        {destination.description || "No description added."}
      </p>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <Info label="Channel ID" value={destination.channelId || "-"} />
        <Info label="Visibility" value={destination.defaultVisibility} />
        <Info label="Playlist" value={destination.defaultPlaylist || "-"} />
        <Info label="Language" value={destination.defaultLanguage} />
      </div>

      <div className="mt-auto flex justify-end gap-1.5 border-t pt-3">
        <Button size="sm" variant="ghost" onClick={onEdit}>
          <Pencil />
          Edit
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onDelete}
          className="text-danger-foreground hover:text-danger"
        >
          <Trash2 />
          Delete
        </Button>
      </div>
    </article>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-background/45 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 truncate text-xs font-medium text-foreground" title={value}>
        {value}
      </p>
    </div>
  );
}

function EmptyPanel({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-56 items-center justify-center rounded-xl border border-dashed bg-card/55">
      <p className="text-sm text-muted-foreground">{children}</p>
    </div>
  );
}

function DestinationDialog({
  destination,
  onClose,
  onSave,
}: {
  destination?: Destination;
  onClose: () => void;
  onSave: (input: DestinationInput, id?: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState<DestinationInput>(
    destination === undefined
      ? EMPTY_INPUT
      : {
          name: destination.name,
          platform: destination.platform,
          channelId: destination.channelId,
          thumbnail: destination.thumbnail,
          description: destination.description,
          connectionStatus: destination.connectionStatus,
          oauthStatus: destination.oauthStatus,
          defaultVisibility: destination.defaultVisibility,
          defaultPlaylist: destination.defaultPlaylist,
          defaultLanguage: destination.defaultLanguage,
        },
  );
  const [saving, setSaving] = useState(false);
  const canSave = draft.name.trim().length > 0 && !saving;

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!canSave) {
      return;
    }
    setSaving(true);
    try {
      await onSave({ ...draft, name: draft.name.trim() }, destination?.id);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-background/80 p-4 backdrop-blur-sm">
      <form
        onSubmit={(event) => void submit(event)}
        className="w-full max-w-2xl rounded-xl border bg-card p-5 shadow-2xl shadow-[var(--shadow-color)]"
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">
              {destination === undefined ? "Add Destination" : "Edit Destination"}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Platform settings are stored with the destination, not with profiles.
            </p>
          </div>
          <Button size="icon" variant="ghost" onClick={onClose} title="Close">
            <X />
          </Button>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <Field label="Name">
            <Input
              value={draft.name}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              placeholder="Ramayani Rides"
              required
            />
          </Field>
          <Field label="Platform">
            <select
              value={draft.platform}
              onChange={(event) =>
                setDraft({ ...draft, platform: event.target.value as DestinationPlatform })
              }
              className="h-11 w-full rounded-md border border-input bg-background/70 px-3 text-sm shadow-sm"
            >
              {PLATFORM_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {PLATFORM_LABELS[option]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Channel ID">
            <Input
              value={draft.channelId}
              onChange={(event) => setDraft({ ...draft, channelId: event.target.value })}
              placeholder="External channel or account id"
            />
          </Field>
          <Field label="Thumbnail">
            <Input
              value={draft.thumbnail}
              onChange={(event) => setDraft({ ...draft, thumbnail: event.target.value })}
              placeholder="Initials or image URL later"
            />
          </Field>
          <Field label="Connection Status">
            <select
              value={draft.connectionStatus}
              onChange={(event) =>
                setDraft({ ...draft, connectionStatus: event.target.value as DestinationStatus })
              }
              className="h-11 w-full rounded-md border border-input bg-background/70 px-3 text-sm shadow-sm"
            >
              <option value="connected">Connected</option>
              <option value="disconnected">Disconnected</option>
              <option value="expired">Expired</option>
              <option value="error">Error</option>
            </select>
          </Field>
          <Field label="Default Visibility">
            <Input
              value={draft.defaultVisibility}
              onChange={(event) => setDraft({ ...draft, defaultVisibility: event.target.value })}
              placeholder="private"
            />
          </Field>
          <Field label="Default Playlist">
            <Input
              value={draft.defaultPlaylist}
              onChange={(event) => setDraft({ ...draft, defaultPlaylist: event.target.value })}
            />
          </Field>
          <Field label="Default Language">
            <Input
              value={draft.defaultLanguage}
              onChange={(event) => setDraft({ ...draft, defaultLanguage: event.target.value })}
              placeholder="en"
            />
          </Field>
          <label className="flex flex-col gap-2 sm:col-span-2">
            <span className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
              Description
            </span>
            <textarea
              value={draft.description}
              onChange={(event) => setDraft({ ...draft, description: event.target.value })}
              className="min-h-24 rounded-md border border-input bg-background/70 px-4 py-3 text-sm shadow-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>
        </div>

        <div className="mt-5 flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
            <PlatformIcon platform={draft.platform} />
            {PLATFORM_LABELS[draft.platform]} connection setup is a future backend step.
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={!canSave}>
              {saving ? "Saving..." : "Save Destination"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}
