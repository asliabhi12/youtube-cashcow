"use client";

import { useCallback, useEffect, useState } from "react";
import { Copy, FilePlus2, Save, SaveAll, Trash2 } from "lucide-react";

import { DemoModeBanner } from "@/components/demo-mode/demo-mode-banner";
import { useDemoMode } from "@/components/demo-mode/use-demo-mode";

import { Button } from "@/components/ui/button";
import { ProfileEditor } from "@/features/profile-editor/profile-editor";
import { useProfileEditor } from "@/features/profile-editor/use-profile-editor";
import {
  fetchExportQualities,
  fetchProfiles,
  type Option,
  type ProfileSummary,
} from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Creative-profile manager: a scrollable library list on the left and the full
 * profile editor on the right. Selecting a profile loads it into the editor;
 * New starts a blank draft; Save persists (creating a copy for a built-in),
 * Save As always creates a new profile, and Delete removes the active custom
 * profile.
 *
 * The page fills the viewport: the list scrolls independently while its "New"
 * button and the editor's action bar stay fixed, so it reads like a desktop
 * app. The editor state is shared with the Home form via
 * {@link useProfileEditor}. Ctrl/Cmd+S saves.
 */
export default function ProfilesPage() {
  const { isDemoMode } = useDemoMode();
  const editor = useProfileEditor();
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [qualities, setQualities] = useState<Option[]>([]);
  const [loadError, setLoadError] = useState(false);

  const reload = useCallback(async (signal?: AbortSignal): Promise<ProfileSummary[]> => {
    const list = await fetchProfiles(signal);
    setProfiles(list);
    return list;
  }, []);

  // Load the list + qualities once, and open the first profile.
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const [list, q] = await Promise.all([
          reload(controller.signal),
          fetchExportQualities(controller.signal),
        ]);
        setQualities(q);
        if (list[0] !== undefined) {
          await editor.loadProfile(list[0].id);
        }
      } catch {
        if (!controller.signal.aborted) {
          setLoadError(true);
        }
      }
    })();
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Ctrl/Cmd+S saves the active profile.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (editor.dirty && !editor.saving) {
          void handleSave();
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor.dirty, editor.saving]);

  async function selectProfile(id: string): Promise<void> {
    if (id === editor.activeId) {
      return;
    }
    if (editor.dirty && !window.confirm("Discard unsaved changes?")) {
      return;
    }
    await editor.loadProfile(id);
  }

  function handleNew(): void {
    if (editor.dirty && !window.confirm("Discard unsaved changes?")) {
      return;
    }
    editor.newProfile();
  }

  async function handleSave(): Promise<void> {
    if (editor.isBuiltin) {
      await handleSaveAs();
      return;
    }
    const id = await editor.save();
    if (id !== null) {
      await reload();
    }
  }

  async function handleSaveAs(): Promise<void> {
    const label = window.prompt("Name for the new profile:", editor.draft.label)?.trim();
    if (!label) {
      return;
    }
    const id = await editor.saveAs(label);
    if (id !== null) {
      await reload();
    }
  }

  async function handleDelete(): Promise<void> {
    if (editor.activeId === null || editor.isBuiltin) {
      return;
    }
    const label = profiles.find((p) => p.id === editor.activeId)?.label ?? editor.draft.label;
    if (!window.confirm(`Delete profile "${label}"?`)) {
      return;
    }
    const ok = await editor.remove();
    if (ok) {
      const list = await reload();
      if (list[0] !== undefined) {
        await editor.loadProfile(list[0].id);
      } else {
        editor.newProfile();
      }
    }
  }

  if (isDemoMode) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:py-8">
        <DemoModeBanner />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col md:overflow-hidden">
      {/* Page header (fixed) */}
      <header className="shrink-0 border-b bg-card/45 px-4 py-5 sm:px-6">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">
              Library
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">Profiles</h1>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Reusable creative profiles you can apply to any video.
            </p>
          </div>
          {editor.dirty && (
            <span className="shrink-0 rounded-full border border-warning-border bg-warning-surface px-3 py-1 text-xs font-medium text-warning-foreground">
              ● Unsaved changes
            </span>
          )}
        </div>
      </header>

      {loadError ? (
        <div className="flex flex-1 items-center justify-center p-6">
          <p className="text-sm text-muted-foreground">
            Could not load profiles. Is the server running?
          </p>
        </div>
      ) : (
        <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col md:min-h-0 md:grid md:grid-cols-[minmax(15rem,30%)_minmax(0,1fr)]">
          {/* Library list — independently scrollable */}
          <aside className="flex flex-col bg-card/30 md:min-h-0 md:border-r">
            <div className="shrink-0 px-4 pt-4 md:px-5">
              <Button
                variant="outline"
                size="sm"
                onClick={handleNew}
                className="w-full justify-start"
              >
                <FilePlus2 />
                New Profile
              </Button>
            </div>
            <ul className="flex max-h-72 flex-col gap-1.5 overflow-y-auto p-4 md:max-h-none md:flex-1 md:px-5">
              {profiles.map((profile) => (
                <li key={profile.id}>
                  <ProfileCard
                    profile={profile}
                    active={profile.id === editor.activeId}
                    onSelect={() => void selectProfile(profile.id)}
                  />
                </li>
              ))}
            </ul>
          </aside>

          {/* Editor — fixed action bar, scrollable body */}
          <section className="flex flex-col md:min-h-0">
            <div className="flex shrink-0 flex-wrap items-center gap-2 border-b bg-card/35 px-4 py-3 sm:px-6">
              {editor.isBuiltin ? (
                <Button
                  size="sm"
                  disabled={editor.saving}
                  onClick={() => void handleSaveAs()}
                >
                  <Copy />
                  Duplicate
                </Button>
              ) : (
                <>
                  <Button
                    size="sm"
                    disabled={editor.saving || !editor.dirty}
                    onClick={() => void handleSave()}
                  >
                    <Save />
                    Save
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={editor.saving}
                    onClick={() => void handleSaveAs()}
                  >
                    <SaveAll />
                    Save As
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={editor.saving || editor.activeId === null}
                    onClick={() => void handleDelete()}
                    className="ml-auto text-danger-foreground hover:text-danger"
                    title="Delete this profile"
                  >
                    <Trash2 />
                    Delete
                  </Button>
                </>
              )}
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
              {editor.loading ? (
                <div className="flex min-h-40 items-center justify-center rounded-xl border border-dashed bg-card/55">
                  <p className="text-sm text-muted-foreground">Loading profile…</p>
                </div>
              ) : (
                <div className="mx-auto max-w-2xl">
                  <ProfileEditor
                    editor={editor}
                    qualities={qualities}
                    disabled={editor.saving}
                  />
                  {editor.error !== null && (
                    <p className="mt-4 text-sm text-danger-foreground">{editor.error}</p>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

/**
 * A single profile in the library list. Fixed layout so long descriptions never
 * escape the card: the name row keeps the badge pinned top-right, and the
 * description is clamped to two lines. The selected state is a filled accent
 * with a left rail so the active profile is unmistakable.
 */
function ProfileCard({
  profile,
  active,
  onSelect,
}: {
  profile: ProfileSummary;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={active}
      className={cn(
        "flex w-full flex-col gap-1.5 rounded-lg border px-3 py-2.5 text-left shadow-sm shadow-[var(--shadow-color)] transition-all duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        active
          ? "border-primary/45 bg-accent/70 ring-1 ring-primary/20"
          : "border-input bg-background/45 hover:border-primary/30 hover:bg-accent/35",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 flex-1 truncate text-sm font-medium leading-tight">
          {profile.label}
        </span>
        <span
          className={cn(
            "shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-medium leading-none",
            profile.builtin
              ? "border-input text-muted-foreground"
              : "border-primary/40 text-primary",
          )}
        >
          {profile.builtin ? "Built-in" : "Custom"}
        </span>
      </div>
      {profile.description !== "" && (
        <span className="line-clamp-2 text-xs leading-snug text-muted-foreground">
          {profile.description}
        </span>
      )}
    </button>
  );
}
