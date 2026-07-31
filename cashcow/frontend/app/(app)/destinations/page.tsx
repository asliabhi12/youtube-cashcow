"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Cable, RefreshCw, Search, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  connectDestination,
  deleteDestination,
  fetchDestinations,
  type Destination,
} from "@/lib/api";
import {
  DestinationStatusBadge,
  PlatformBadge,
} from "@/features/destinations/platforms";

export default function DestinationsPage() {
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await fetchDestinations(signal);
      setDestinations(data);
      if (data.length > 0) {
        setError(null);
      }
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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const err = params.get("error");
    if (err) {
      setError(decodeURIComponent(err));
      const url = new URL(window.location.href);
      url.searchParams.delete("error");
      window.history.replaceState({}, "", url.toString());
    }
  }, []);

  async function handleConnect(): Promise<void> {
    setConnecting(true);
    setError(null);
    try {
      const authUrl = await connectDestination();
      window.location.href = authUrl;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start OAuth connect");
      setConnecting(false);
    }
  }

  async function handleDelete(destination: Destination): Promise<void> {
    if (!window.confirm(`Disconnect "${destination.channelTitle}"?`)) {
      return;
    }
    await deleteDestination(destination.id);
    await load();
  }

  async function handleReconnect(): Promise<void> {
    await handleConnect();
  }

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (normalized.length === 0) return destinations;
    return destinations.filter(
      (d) =>
        d.channelTitle.toLowerCase().includes(normalized) ||
        d.channelId.toLowerCase().includes(normalized) ||
        d.description.toLowerCase().includes(normalized),
    );
  }, [destinations, query]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">
            Publishing
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Destinations</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Manage connected YouTube channels for video publishing.
          </p>
        </div>
        <Button onClick={() => void handleConnect()} disabled={connecting}>
          <Cable className={connecting ? "animate-pulse" : undefined} />
          {connecting ? "Connecting..." : "Connect YouTube"}
        </Button>
      </div>

      <div className="mt-6">
        <label className="relative mb-4 block max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search channels"
            className="pl-9"
          />
        </label>
      </div>

      {error !== null && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-danger-border bg-danger-surface px-4 py-3 text-sm text-danger-foreground">
          <p className="flex-1">{error}</p>
          <button
            onClick={() => setError(null)}
            className="mt-0.5 shrink-0 opacity-60 hover:opacity-100"
            aria-label="Dismiss"
          >
            <X className="size-4" />
          </button>
        </div>
      )}

      <div>
        {loading ? (
          <EmptyPanel>Loading destinations...</EmptyPanel>
        ) : filtered.length === 0 && query.trim().length > 0 ? (
          <EmptyPanel>No channels match your search.</EmptyPanel>
        ) : filtered.length === 0 ? (
          <EmptyPanel>
            <div className="flex flex-col items-center gap-3">
              <p className="text-sm text-muted-foreground">
                No YouTube channels connected yet.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleConnect()}
                disabled={connecting}
              >
                <Cable />
                Connect your first channel
              </Button>
            </div>
          </EmptyPanel>
        ) : (
          <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((destination) => (
              <li key={destination.id}>
                <ChannelCard
                  destination={destination}
                  onDelete={() => void handleDelete(destination)}
                  onReconnect={() => void handleReconnect()}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ChannelCard({
  destination,
  onDelete,
  onReconnect,
}: {
  destination: Destination;
  onDelete: () => void;
  onReconnect: () => void;
}) {
  const needsReconnect = destination.connectionStatus === "needs_reconnection";

  return (
    <article className="flex min-h-56 flex-col rounded-xl border bg-card/75 p-4 shadow-lg shadow-[var(--shadow-color)]">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          {destination.thumbnail ? (
            <img
              src={destination.thumbnail}
              alt={destination.channelTitle}
              className="size-11 shrink-0 rounded-full border object-cover"
            />
          ) : (
            <div className="grid size-11 shrink-0 place-items-center rounded-full border border-primary/25 bg-primary/10 text-xs font-bold text-primary">
              {destinationInitials(destination)}
            </div>
          )}
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold tracking-tight">
              {destination.channelTitle}
            </h2>
            <div className="mt-1 flex items-center gap-2">
              <PlatformBadge platform={destination.platform} />
              <DestinationStatusBadge status={destination.connectionStatus} />
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 space-y-2 text-xs">
        <Info label="Channel ID" value={destination.channelId || "-"} />
        {destination.lastSyncedAt && (
          <Info
            label="Last Synced"
            value={new Date(destination.lastSyncedAt).toLocaleString()}
          />
        )}
      </div>

      {destination.description && (
        <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
          {destination.description}
        </p>
      )}

      <div className="mt-auto flex items-center justify-end gap-1.5 border-t pt-3">
        {needsReconnect && (
          <Button size="sm" variant="outline" onClick={onReconnect}>
            <RefreshCw />
            Reconnect
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          onClick={onDelete}
          className="text-danger-foreground hover:text-danger"
        >
          <Trash2 />
          Disconnect
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
      {typeof children === "string" ? (
        <p className="text-sm text-muted-foreground">{children}</p>
      ) : (
        children
      )}
    </div>
  );
}

function destinationInitials(destination: Pick<Destination, "channelTitle" | "thumbnail">) {
  if (destination.thumbnail.trim()) {
    return destination.thumbnail.trim().slice(0, 3).toUpperCase();
  }
  return destination.channelTitle
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
