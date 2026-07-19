"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  createJob,
  createProfile,
  deleteProfile,
  duplicateProfile,
  fetchAppSettings,
  fetchExportQualities,
  fetchProfiles,
  fetchVideoMetadata,
  type Option,
  type ProfileSummary,
} from "@/lib/api";

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

  trim: { start: number; end: number };
  setTrim: (range: { start: number; end: number }) => void;
  maxDuration: number;

  profiles: ProfileSummary[];
  profileId: string;
  setProfileId: (value: string) => void;
  /** Whether the selected profile is a read-only built-in. */
  isBuiltinProfile: boolean;

  qualities: Option[];
  exportQuality: string;
  setExportQuality: (value: string) => void;

  /** Video title from the metadata lookup, when available. */
  videoTitle: string | null;
  /** True while the metadata lookup is in flight. */
  loadingMetadata: boolean;

  /** Profile actions. Milestone A operates on the selected profile as a whole. */
  newProfile: () => Promise<void>;
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
 * On mount it loads the creative-profile list, the export-quality options, and
 * the app settings — pre-selecting the last-used profile so the page reopens
 * where the user left off. As the URL changes it looks up the video's
 * duration/title (debounced) so the trim slider spans the real clip, falling
 * back to a fixed maximum when the lookup fails. Submitting posts the full
 * creative profile (url, trim, profile id, export quality) and routes to Jobs.
 *
 * Profile management (New / Save As / Delete) lives here in Milestone A because
 * there is no field-level editor yet; Milestone B introduces a dedicated
 * `useProfileEditor` hook for editing individual parameters.
 */
export function useWorkflowForm(): WorkflowFormState {
  const router = useRouter();

  const [url, setUrl] = useState("");
  const [trim, setTrim] = useState({ start: DEFAULT_START, end: DEFAULT_END });
  const [maxDuration, setMaxDuration] = useState(FALLBACK_MAX_SECONDS);

  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [profileId, setProfileId] = useState("");
  const [qualities, setQualities] = useState<Option[]>([]);
  const [exportQuality, setExportQuality] = useState(DEFAULT_QUALITY);

  const [videoTitle, setVideoTitle] = useState<string | null>(null);
  const [loadingMetadata, setLoadingMetadata] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isBuiltinProfile =
    profiles.find((p) => p.id === profileId)?.builtin ?? false;

  // Load profiles, export qualities, and the last-used profile once. If a fetch
  // fails, the selectors stay empty; the page still renders and defaults apply.
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
        // Prefer the last-used profile when it still resolves; else first item.
        const last = settings.last_profile;
        const initial =
          (last !== null && profileList.some((p) => p.id === last) ? last : undefined) ??
          profileList[0]?.id ??
          "";
        setProfileId(initial);
      } catch {
        // Ignore; defaults still apply.
      }
    })();
    return () => controller.abort();
  }, []);

  const trimmedUrl = url.trim();

  // Debounced metadata lookup keyed on the URL. Sets the slider max to the real
  // duration on success; falls back silently otherwise.
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
            // Clamp the current selection into the real duration.
            setTrim((prev) => {
              const end = Math.min(prev.end, duration);
              const start = Math.min(prev.start, Math.max(0, end - 1));
              return { start, end };
            });
          }
        } catch {
          // Invalid URL or blocked upstream: keep the fallback max.
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

  // Reload the profile list and select a specific id (used after mutations).
  const reloadProfiles = useCallback(async (selectId?: string): Promise<void> => {
    const list = await fetchProfiles();
    setProfiles(list);
    if (selectId !== undefined && list.some((p) => p.id === selectId)) {
      setProfileId(selectId);
    }
  }, []);

  const newProfile = useCallback(async (): Promise<void> => {
    const label = window.prompt("Name for the new profile:")?.trim();
    if (!label) {
      return;
    }
    setError(null);
    try {
      // A fresh profile carries no creative sections — the bare pipeline —
      // ready for Milestone B's editor to fill in.
      const created = await createProfile({ label });
      await reloadProfiles(created.id);
    } catch {
      setError("Could not create the profile.");
    }
  }, [reloadProfiles]);

  const saveProfileAs = useCallback(async (): Promise<void> => {
    if (profileId === "") {
      return;
    }
    const label = window.prompt("Name for the new profile:")?.trim();
    if (!label) {
      return;
    }
    setError(null);
    try {
      const created = await duplicateProfile(profileId, label);
      await reloadProfiles(created.id);
    } catch {
      setError("Could not save the profile.");
    }
  }, [profileId, reloadProfiles]);

  // In Milestone A there is no field editor, so "Save" on a built-in is not
  // shown and on a custom profile there is nothing changed to persist yet;
  // Save As covers creating a copy. This becomes a real update in Milestone B.
  const saveProfile = useCallback(async (): Promise<void> => {
    if (isBuiltinProfile) {
      await saveProfileAs();
    }
    // Custom profile: no editable field state in Milestone A — no-op.
  }, [isBuiltinProfile, saveProfileAs]);

  const removeProfile = useCallback(async (): Promise<void> => {
    if (profileId === "" || isBuiltinProfile) {
      return;
    }
    const summary = profiles.find((p) => p.id === profileId);
    if (!window.confirm(`Delete profile "${summary?.label ?? profileId}"?`)) {
      return;
    }
    setError(null);
    try {
      await deleteProfile(profileId);
      const list = await fetchProfiles();
      setProfiles(list);
      setProfileId(list[0]?.id ?? "");
    } catch {
      setError("Could not delete the profile.");
    }
  }, [profileId, isBuiltinProfile, profiles]);

  const canRun = trimmedUrl.length > 0 && profileId !== "" && !submitting;

  const submit = useCallback(async () => {
    if (trimmedUrl.length === 0 || profileId === "" || submitting) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await createJob({
        url: trimmedUrl,
        trim: { start: trim.start, end: trim.end },
        profile_id: profileId,
        export_quality: exportQuality,
      });
      router.push("/jobs");
    } catch {
      setError("Could not create the job. Is the server running?");
      setSubmitting(false);
    }
  }, [trimmedUrl, profileId, submitting, trim, exportQuality, router]);

  return {
    url,
    setUrl,
    trim,
    setTrim,
    maxDuration,
    profiles,
    profileId,
    setProfileId,
    isBuiltinProfile,
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
