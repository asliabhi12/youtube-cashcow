"use client";

import { useCallback, useEffect, useState } from "react";
import { Copy, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  deleteProfile,
  duplicateProfile,
  fetchProfiles,
  type ProfileSummary,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; profiles: ProfileSummary[] };

/**
 * Creative-profile manager: lists built-in and custom profiles and lets the
 * user duplicate any profile or delete their custom ones. Editing individual
 * parameters happens on the Home page's form (and, in Milestone B, a dedicated
 * editor); this page is the library view.
 */
export default function ProfilesPage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  const load = useCallback(async (signal?: AbortSignal): Promise<void> => {
    try {
      const profiles = await fetchProfiles(signal);
      setState({ kind: "ready", profiles });
    } catch {
      if (!signal?.aborted) {
        setState({ kind: "error" });
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function handleDuplicate(profile: ProfileSummary): Promise<void> {
    const label = window.prompt("Name for the copy:", `${profile.label} (copy)`)?.trim();
    if (!label) {
      return;
    }
    try {
      await duplicateProfile(profile.id, label);
      await load();
    } catch {
      setState({ kind: "error" });
    }
  }

  async function handleDelete(profile: ProfileSummary): Promise<void> {
    if (!window.confirm(`Delete profile "${profile.label}"?`)) {
      return;
    }
    try {
      await deleteProfile(profile.id);
      await load();
    } catch {
      setState({ kind: "error" });
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-xl font-semibold tracking-tight">Profiles</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Reusable creative profiles you can apply to any video.
      </p>

      <div className="mt-8">
        {state.kind === "loading" && (
          <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed">
            <p className="text-sm text-muted-foreground">Loading profiles…</p>
          </div>
        )}

        {state.kind === "error" && (
          <div className="flex min-h-40 items-center justify-center rounded-lg border border-dashed">
            <p className="text-sm text-muted-foreground">
              Could not load profiles. Is the server running?
            </p>
          </div>
        )}

        {state.kind === "ready" && (
          <ul className="flex flex-col gap-2">
            {state.profiles.map((profile) => (
              <li
                key={profile.id}
                className="flex items-center justify-between gap-4 rounded-lg border px-4 py-3"
              >
                <div className="flex min-w-0 flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">{profile.label}</span>
                    <span
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-xs font-medium",
                        profile.builtin
                          ? "border-input text-muted-foreground"
                          : "border-primary/40 text-primary",
                      )}
                    >
                      {profile.builtin ? "Built-in" : "Custom"}
                    </span>
                  </div>
                  {profile.description !== "" && (
                    <span className="truncate text-xs text-muted-foreground">
                      {profile.description}
                    </span>
                  )}
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => void handleDuplicate(profile)}
                    title="Duplicate this profile"
                  >
                    <Copy />
                    Duplicate
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={profile.builtin}
                    onClick={() => void handleDelete(profile)}
                    title={
                      profile.builtin
                        ? "Built-in profiles can't be deleted"
                        : "Delete this profile"
                    }
                  >
                    <Trash2 />
                    Delete
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
