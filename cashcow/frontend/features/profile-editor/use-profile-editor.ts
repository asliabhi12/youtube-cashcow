"use client";

import { useCallback, useMemo, useRef, useState } from "react";

import {
  createProfile,
  deleteProfile,
  fetchProfile,
  updateProfile,
  type AudioConfig,
  type ColorConfig,
  type OverlayConfig,
  type ProfileInput,
  type ResizeConfig,
} from "@/lib/api";

/**
 * Editable state for a single creative profile — every field the engine
 * accepts, each creative section nullable so "section absent" (that step is
 * skipped) is distinct from "section present with defaults".
 */
export interface ProfileDraft {
  label: string;
  description: string;
  resize: ResizeConfig | null;
  audio: AudioConfig | null;
  color: ColorConfig | null;
  overlay: OverlayConfig | null;
  exportQuality: string | null;
  allowedDestinationIds: string[];
}

const EMPTY_DRAFT: ProfileDraft = {
  label: "",
  description: "",
  resize: null,
  audio: null,
  color: null,
  overlay: null,
  exportQuality: null,
  allowedDestinationIds: [],
};

/** Build the API payload from a draft, dropping absent (null) sections. */
function toInput(draft: ProfileDraft): ProfileInput {
  const input: ProfileInput = { label: draft.label, description: draft.description };
  if (draft.resize !== null) input.resize = draft.resize;
  if (draft.audio !== null) input.audio = draft.audio;
  if (draft.color !== null) input.color = draft.color;
  if (draft.overlay !== null) input.overlay = draft.overlay;
  if (draft.exportQuality !== null) input.export_quality = draft.exportQuality;
  input.allowed_destination_ids = draft.allowedDestinationIds;
  return input;
}

/** Stable serialization used for dirty comparison (key order is fixed above). */
function fingerprint(draft: ProfileDraft): string {
  return JSON.stringify(draft);
}

/** A client-side validation problem, keyed to the section it belongs to. */
export interface ValidationIssue {
  section: string;
  message: string;
}

/**
 * Validate a draft against the engine's structural rules before a save, so the
 * user sees an inline problem instead of a 422. Range limits are enforced by
 * the field controls themselves; this catches cross-field rules the controls
 * can't (a label is required, an overlay needs an asset, scale and width/height
 * are mutually exclusive).
 */
export function validateDraft(draft: ProfileDraft): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (draft.label.trim() === "") {
    issues.push({ section: "general", message: "A profile name is required." });
  }
  if (draft.resize !== null) {
    const { preset, width, height } = draft.resize;
    const hasDims = width != null && height != null;
    if (!preset && !hasDims) {
      issues.push({
        section: "resize",
        message: "Choose a preset or set both width and height.",
      });
    }
  }
  if (draft.overlay !== null) {
    if (draft.overlay.asset.trim() === "") {
      issues.push({ section: "overlay", message: "Select an overlay asset." });
    }
    const { scale, width, height } = draft.overlay;
    if (scale != null && (width != null || height != null)) {
      issues.push({
        section: "overlay",
        message: "Use either scale or width/height, not both.",
      });
    }
  }
  return issues;
}

export interface ProfileEditorState {
  draft: ProfileDraft;
  /** Id of the profile being edited, or null for an unsaved new draft. */
  activeId: string | null;
  /** Whether the loaded profile is a read-only built-in. */
  isBuiltin: boolean;
  /** Whether the draft differs from the last loaded/saved state. */
  dirty: boolean;
  saving: boolean;
  loading: boolean;
  error: string | null;
  /** Structural problems that would fail a save (empty until a save is tried). */
  issues: ValidationIssue[];

  /** Patch one or more draft fields. */
  update: (patch: Partial<ProfileDraft>) => void;
  /** Load a stored profile by id into the editor (discards unsaved edits). */
  loadProfile: (id: string) => Promise<void>;
  /** Reset the editor to a blank new draft. */
  newProfile: () => void;
  /**
   * Persist the draft. Updates the profile in place when it is an existing
   * custom one; otherwise creates a new custom profile (new draft or a built-in
   * being "saved as"). Returns the resulting id, or null if validation failed.
   */
  save: () => Promise<string | null>;
  /** Create a new custom profile from the draft under a new label ("Save As"). */
  saveAs: (label: string) => Promise<string | null>;
  /** Delete the active custom profile. Returns true on success. */
  remove: () => Promise<boolean>;
}

/**
 * Single source of truth for the creative profile being edited.
 *
 * Holds the full editable draft plus load/save/delete actions, and derives a
 * `dirty` flag by comparing the draft to a baseline snapshot taken on load,
 * new, or save. It is deliberately UI-agnostic so both the Home workflow form
 * and the `/profiles` manager compose it, wiring the same draft into the
 * category editor sections.
 */
export function useProfileEditor(): ProfileEditorState {
  const [draft, setDraft] = useState<ProfileDraft>(EMPTY_DRAFT);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isBuiltin, setIsBuiltin] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issues, setIssues] = useState<ValidationIssue[]>([]);

  // Baseline the draft is compared against for dirty tracking. Updated whenever
  // the editor loads, resets, or successfully saves.
  const baseline = useRef<string>(fingerprint(EMPTY_DRAFT));
  const [dirty, setDirty] = useState(false);

  const setBaseline = useCallback((next: ProfileDraft) => {
    baseline.current = fingerprint(next);
    setDirty(false);
  }, []);

  const update = useCallback((patch: Partial<ProfileDraft>) => {
    setDraft((prev) => {
      const next = { ...prev, ...patch };
      setDirty(fingerprint(next) !== baseline.current);
      return next;
    });
    setIssues([]);
  }, []);

  const loadProfile = useCallback(
    async (id: string): Promise<void> => {
      setLoading(true);
      setError(null);
      setIssues([]);
      try {
        const profile = await fetchProfile(id);
        const next: ProfileDraft = {
          label: profile.label,
          description: profile.description ?? "",
          resize: profile.resize ?? null,
          audio: profile.audio ?? null,
          color: profile.color ?? null,
          overlay: profile.overlay ?? null,
          exportQuality: profile.export_quality ?? null,
          allowedDestinationIds: profile.allowed_destination_ids ?? [],
        };
        setDraft(next);
        setActiveId(profile.id);
        setIsBuiltin(profile.builtin);
        setBaseline(next);
      } catch {
        setError("Could not load the profile.");
      } finally {
        setLoading(false);
      }
    },
    [setBaseline],
  );

  const newProfile = useCallback(() => {
    setDraft(EMPTY_DRAFT);
    setActiveId(null);
    setIsBuiltin(false);
    setError(null);
    setIssues([]);
    setBaseline(EMPTY_DRAFT);
  }, [setBaseline]);

  const save = useCallback(async (): Promise<string | null> => {
    const found = validateDraft(draft);
    if (found.length > 0) {
      setIssues(found);
      return null;
    }
    setSaving(true);
    setError(null);
    try {
      const input = toInput(draft);
      // Update in place only for an existing custom profile; a new draft or a
      // built-in being edited becomes a fresh custom profile.
      const saved =
        activeId !== null && !isBuiltin
          ? await updateProfile(activeId, input)
          : await createProfile(input);
      setActiveId(saved.id);
      setIsBuiltin(false);
      setBaseline(draft);
      return saved.id;
    } catch {
      setError("Could not save the profile.");
      return null;
    } finally {
      setSaving(false);
    }
  }, [draft, activeId, isBuiltin, setBaseline]);

  const saveAs = useCallback(
    async (label: string): Promise<string | null> => {
      const candidate: ProfileDraft = { ...draft, label };
      const found = validateDraft(candidate);
      if (found.length > 0) {
        setIssues(found);
        return null;
      }
      setSaving(true);
      setError(null);
      try {
        const saved = await createProfile(toInput(candidate));
        setDraft(candidate);
        setActiveId(saved.id);
        setIsBuiltin(false);
        setBaseline(candidate);
        return saved.id;
      } catch {
        setError("Could not save the profile.");
        return null;
      } finally {
        setSaving(false);
      }
    },
    [draft, setBaseline],
  );

  const remove = useCallback(async (): Promise<boolean> => {
    if (activeId === null || isBuiltin) {
      return false;
    }
    setSaving(true);
    setError(null);
    try {
      await deleteProfile(activeId);
      return true;
    } catch {
      setError("Could not delete the profile.");
      return false;
    } finally {
      setSaving(false);
    }
  }, [activeId, isBuiltin]);

  return useMemo(
    () => ({
      draft,
      activeId,
      isBuiltin,
      dirty,
      saving,
      loading,
      error,
      issues,
      update,
      loadProfile,
      newProfile,
      save,
      saveAs,
      remove,
    }),
    [
      draft,
      activeId,
      isBuiltin,
      dirty,
      saving,
      loading,
      error,
      issues,
      update,
      loadProfile,
      newProfile,
      save,
      saveAs,
      remove,
    ],
  );
}
