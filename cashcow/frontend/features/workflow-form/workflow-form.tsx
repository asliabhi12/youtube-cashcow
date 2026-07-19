"use client";

import { useEffect } from "react";

import { ExportQualitySelector } from "@/components/export-quality-selector";
import { ProfileActions } from "@/components/profile-actions";
import { ProfileSelector } from "@/components/profile-selector";
import { TrimRangeSlider, formatDuration } from "@/components/trim-range-slider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ProfileEditor } from "@/features/profile-editor/profile-editor";

import { useWorkflowForm } from "./use-workflow-form";

/**
 * The Home page's workflow configuration form: a URL, a trim range, and a fully
 * editable creative profile (selector + actions + category editors), plus a
 * per-job export quality. All state and side effects live in
 * {@link useWorkflowForm}; this component stays declarative.
 *
 * Ctrl/Cmd+S saves the active profile from anywhere in the form.
 */
export function WorkflowForm() {
  const form = useWorkflowForm();
  const { editor } = form;

  // Ctrl/Cmd+S saves the active profile without submitting the browser's own
  // save dialog.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (editor.dirty && !editor.saving) {
          void form.saveProfile();
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [editor.dirty, editor.saving, form]);

  return (
    <div className="flex w-full flex-col gap-8">
      {/* URL */}
      <div className="flex flex-col gap-2">
        <label htmlFor="youtube-url" className="text-sm font-medium">
          YouTube URL
        </label>
        <Input
          id="youtube-url"
          inputMode="url"
          placeholder="https://www.youtube.com/watch?v=…"
          value={form.url}
          disabled={form.submitting}
          onChange={(event) => form.setUrl(event.target.value)}
        />
        {form.loadingMetadata && (
          <p className="text-xs text-muted-foreground">Fetching video details…</p>
        )}
        {form.videoTitle !== null && !form.loadingMetadata && (
          <p className="truncate text-xs text-muted-foreground">{form.videoTitle}</p>
        )}
      </div>

      {/* Trim */}
      <div className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-medium">Trim Range</span>
          <span className="text-xs text-muted-foreground">
            Duration {formatDuration(form.trim.end - form.trim.start)}
          </span>
        </div>
        <TrimRangeSlider
          start={form.trim.start}
          end={form.trim.end}
          max={form.maxDuration}
          onChange={form.setTrim}
          disabled={form.submitting}
        />
      </div>

      {/* Creative profile: selector, actions, and the full editor */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-2">
          <ProfileSelector
            options={form.profiles}
            value={editor.activeId ?? ""}
            onChange={(id) => void form.selectProfile(id)}
            disabled={form.submitting || editor.saving}
            className="flex-1"
          />
        </div>
        <div className="flex items-center justify-between gap-2">
          <ProfileActions
            isBuiltin={editor.isBuiltin}
            canDelete={!editor.isBuiltin && editor.activeId !== null}
            disabled={form.submitting || editor.saving}
            onNew={() => form.newProfile()}
            onSave={() => void form.saveProfile()}
            onSaveAs={() => void form.saveProfileAs()}
            onDelete={() => void form.removeProfile()}
          />
          {editor.dirty && (
            <span className="text-xs text-amber-600 dark:text-amber-500">
              ● Unsaved changes
            </span>
          )}
        </div>

        <ProfileEditor
          editor={editor}
          qualities={form.qualities}
          disabled={form.submitting}
        />

        {editor.error !== null && (
          <p className="text-sm text-red-500">{editor.error}</p>
        )}
      </div>

      {/* Per-job export quality (starts from the profile's default, overridable) */}
      <ExportQualitySelector
        options={form.qualities}
        value={form.exportQuality}
        onChange={form.setExportQuality}
        disabled={form.submitting}
      />

      {form.error !== null && <p className="text-sm text-red-500">{form.error}</p>}

      <div className="flex justify-end">
        <Button size="lg" disabled={!form.canRun} onClick={() => void form.submit()}>
          {form.submitting ? "Running…" : "Run Workflow"}
        </Button>
      </div>
    </div>
  );
}
