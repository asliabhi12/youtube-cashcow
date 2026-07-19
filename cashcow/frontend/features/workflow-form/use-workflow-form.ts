"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  createJob,
  fetchAppSettings,
  fetchExportQualities,
  fetchProfile,
  fetchProfiles,
  fetchVideoMetadata,
  type Option,
  type ProfileSummary,
} from "@/lib/api";

import { useProfileEditor, type ProfileEditorState } from "@/features/profile-editor/use-profile-editor";

/** Fallback slider max (seconds) when the video duration is unknown. */
const FALLBACK_MAX_SECONDS = 600;
/** Default selected trim range (seconds) on first load. */
const DEFAULT_START = 10;
const DEFAULT_END = 40;
/** Debounce for the metadata lookup after the URL stops changing. */
const METADATA_DEBOUNCE_MS = 600;
const DEFAULT_QUALITY = "balanced";

export interface WorkflowFormState {
  url: string;
  setUrl: (url: string) => void;

  titleSeed: string;
  setTitleSeed: (titleSeed: string) => void;

  trim: { start: number; end: number };
  setTrim: (range: { start: number; end: number }) => void;
  maxDuration: number;

  /** Full profile editor — the single source of truth for the active profile. */
  editor: ProfileEditorState;
  /** Profile summaries for the selector (built-ins first). */
  profiles: ProfileSummary[];
  /** Load a profile into the editor (used by the selector). */
  selectProfile: (id: string) => Promise<void>;

  qualities: Option[];
  exportQuality: string;
  setExportQuality: (value: string) => void;

  /** Video title from the metadata lookup, when available. */
  videoTitle: string | null;
  /** True while the metadata lookup is in flight. */
  loadingMetadata: boolean;

  /** Profile actions, delegated to the editor then reflected in the list. */
  newProfile: () => void;
  saveProfile: () => Promise<void>;
  saveProfileAs: () => Promise<void>;
  removeProfile: () => Promise<void>;

  submitting: boolean;
  error: string | null;
  canRun: boolean;
  submit: () => Promise<void>;
}

/**
 * State and side effects for the Home page's workflow configuration form.
 *
 * The active creative profile is owned by an embedded {@link useProfileEditor},
 * so the selector, the field editor, and job submission all read one source of
 * truth. On mount it loads the profile list, export qualities, and app settings,
 * then opens the last-used profile (falling back to the first). As the URL
 * changes it looks up the video's duration/title (debounced) for the trim
 * slider.
 *
 * Because a job carries only a `profile_id` (never inline config), unsaved edits
 * must be persisted before a run: a dirty custom profile is saved in place, a
 * dirty built-in is "saved as" a new custom profile (the engine never sees a
 * transient, only a stored profile), and a clean selection runs as-is.
 */
export function useWorkflowForm(): WorkflowFormState {
  const router = useRouter();
  const editor = useProfileEditor();

  const [url, setUrl] = useState("");
  const [titleSeed, setTitleSeed] = useState("");
  const [trim, setTrim] = useState({ start: DEFAULT_START, end: DEFAULT_END });
  const [maxDuration, setMaxDuration] = useState(FALLBACK_MAX_SECONDS);

  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [qualities, setQualities] = useState<Option[]>([]);
  const [exportQuality, setExportQuality] = useState(DEFAULT_QUALITY);

  const [videoTitle, setVideoTitle] = useState<string | null>(null);
  const [loadingMetadata, setLoadingMetadata] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pull a profile's export-quality default into the form's quality selection,
  // so the per-job quality starts where the profile suggests but stays free to
  // override.
  const applyProfileQuality = useCallback((quality: string | null | undefined) => {
    if (quality) {
      setExportQuality(quality);
    }
  }, []);

  // Load profiles, export qualities, and the last-used profile once. If a fetch
  // fails, the form still renders with defaults.
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const [profileList, q, settings] = await Promise.all([
          fetchProfiles(controller.signal),
          fetchExportQualities(controller.signal),
          fetchAppSettings(controller.signal),
        ]);
        setProfiles(profileList);
        setQualities(q);
        const last = settings.last_profile;
        const initial =
          (last !== null && profileList.some((p) => p.id === last) ? last : undefined) ??
          profileList[0]?.id ??
          "";
        if (initial !== "") {
          await editor.loadProfile(initial);
          // Seed the quality from the freshly-loaded profile's default.
          try {
            const full = await fetchProfile(initial, controller.signal);
            applyProfileQuality(full.export_quality);
          } catch {
            // Non-fatal; keep the default quality.
          }
        }
      } catch {
        // Ignore; defaults still apply.
      }
    })();
    return () => controller.abort();
    // editor.loadProfile is stable (useCallback); run once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const trimmedUrl = url.trim();

  // Debounced metadata lookup keyed on the URL.
  useEffect(() => {
    if (trimmedUrl.length === 0) {
      setVideoTitle(null);
      setMaxDuration(FALLBACK_MAX_SECONDS);
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => {
      void (async () => {
        setLoadingMetadata(true);
        try {
          const meta = await fetchVideoMetadata(trimmedUrl, controller.signal);
          setVideoTitle(meta.title);
          if (meta.duration !== null && meta.duration > 0) {
            const duration = Math.round(meta.duration);
            setMaxDuration(duration);
            setTrim((prev) => {
              const end = Math.min(prev.end, duration);
              const start = Math.min(prev.start, Math.max(0, end - 1));
              return { start, end };
            });
          }
        } catch {
          setVideoTitle(null);
          setMaxDuration(FALLBACK_MAX_SECONDS);
        } finally {
          if (!controller.signal.aborted) {
            setLoadingMetadata(false);
          }
        }
      })();
    }, METADATA_DEBOUNCE_MS);

    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [trimmedUrl]);

  const reloadProfiles = useCallback(async (): Promise<ProfileSummary[]> => {
    const list = await fetchProfiles();
    setProfiles(list);
    return list;
  }, []);

  // Switch the editor to a different profile. Guards against silently dropping
  // unsaved edits.
  const selectProfile = useCallback(
    async (id: string): Promise<void> => {
      if (id === editor.activeId) {
        return;
      }
      if (
        editor.dirty &&
        !window.confirm("Discard unsaved changes to the current profile?")
      ) {
        return;
      }
      await editor.loadProfile(id);
      try {
        const full = await fetchProfile(id);
        applyProfileQuality(full.export_quality);
      } catch {
        // Non-fatal.
      }
    },
    [editor, applyProfileQuality],
  );

  const newProfile = useCallback(() => {
    if (editor.dirty && !window.confirm("Discard unsaved changes?")) {
      return;
    }
    editor.newProfile();
  }, [editor]);

  const saveProfile = useCallback(async (): Promise<void> => {
    setError(null);
    // A built-in can't be overwritten; saving it creates a copy instead.
    if (editor.isBuiltin) {
      await saveProfileAs();
      return;
    }
    const id = await editor.save();
    if (id !== null) {
      await reloadProfiles();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, reloadProfiles]);

  const saveProfileAs = useCallback(async (): Promise<void> => {
    const label = window.prompt("Name for the new profile:", editor.draft.label)?.trim();
    if (!label) {
      return;
    }
    setError(null);
    const id = await editor.saveAs(label);
    if (id !== null) {
      await reloadProfiles();
    }
  }, [editor, reloadProfiles]);

  const removeProfile = useCallback(async (): Promise<void> => {
    if (editor.activeId === null || editor.isBuiltin) {
      return;
    }
    const label = profiles.find((p) => p.id === editor.activeId)?.label ?? editor.draft.label;
    if (!window.confirm(`Delete profile "${label}"?`)) {
      return;
    }
    setError(null);
    const ok = await editor.remove();
    if (ok) {
      const list = await reloadProfiles();
      const next = list[0]?.id ?? "";
      if (next !== "") {
        await editor.loadProfile(next);
      } else {
        editor.newProfile();
      }
    }
  }, [editor, profiles, reloadProfiles]);

  const canRun = trimmedUrl.length > 0 && !submitting && !editor.saving;

  const submit = useCallback(async () => {
    if (trimmedUrl.length === 0 || submitting) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      // Ensure the engine runs a *stored* profile. Persist any unsaved edits
      // first, since a job carries only a profile id.
      let runId = editor.activeId;
      if (editor.dirty || runId === null) {
        if (editor.isBuiltin) {
          // Built-ins are read-only: an edited built-in must become a copy.
          const label = window.prompt(
            "You edited a built-in profile. Save changes as a new profile named:",
            `${editor.draft.label} (edited)`,
          )?.trim();
          if (!label) {
            setSubmitting(false);
            return;
          }
          runId = await editor.saveAs(label);
        } else {
          runId = await editor.save();
        }
        if (runId === null) {
          // Validation failed; the editor surfaces the issue inline.
          setError("Fix the highlighted profile settings before running.");
          setSubmitting(false);
          return;
        }
        await reloadProfiles();
      }

      await createJob({
        url: trimmedUrl,
        title_seed: titleSeed.trim() || undefined,
        trim: { start: trim.start, end: trim.end },
        profile_id: runId,
        export_quality: exportQuality,
      });
      router.push("/jobs");
    } catch {
      setError("Could not create the job. Is the server running?");
      setSubmitting(false);
    }
  }, [trimmedUrl, titleSeed, submitting, editor, trim, exportQuality, reloadProfiles, router]);

  return {
    url,
    setUrl,
    titleSeed,
    setTitleSeed,
    trim,
    setTrim,
    maxDuration,
    editor,
    profiles,
    selectProfile,
    qualities,
    exportQuality,
    setExportQuality,
    videoTitle,
    loadingMetadata,
    newProfile,
    saveProfile,
    saveProfileAs,
    removeProfile,
    submitting,
    error,
    canRun,
    submit,
  };
}
