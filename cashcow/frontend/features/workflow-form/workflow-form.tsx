"use client";

import { AdvancedOptions } from "@/components/advanced-options";
import { ExportQualitySelector } from "@/components/export-quality-selector";
import { ProfileActions } from "@/components/profile-actions";
import { ProfileSelector } from "@/components/profile-selector";
import { TrimRangeSlider, formatDuration } from "@/components/trim-range-slider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { useWorkflowForm } from "./use-workflow-form";

/**
 * The Home page's workflow configuration form: a URL, a trim range, an editing
 * preset, and an export quality. This composes small presentational components
 * and delegates all state and side effects to {@link useWorkflowForm}, so the
 * form itself stays declarative.
 */
export function WorkflowForm() {
  const form = useWorkflowForm();

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
          <p className="truncate text-xs text-muted-foreground">
            {form.videoTitle}
          </p>
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

      {/* Creative profile */}
      <div className="flex flex-col gap-3">
        <ProfileSelector
          options={form.profiles}
          value={form.profileId}
          onChange={form.setProfileId}
          disabled={form.submitting}
        />
        <ProfileActions
          isBuiltin={form.isBuiltinProfile}
          canDelete={!form.isBuiltinProfile && form.profileId !== ""}
          disabled={form.submitting}
          onNew={() => void form.newProfile()}
          onSave={() => void form.saveProfile()}
          onSaveAs={() => void form.saveProfileAs()}
          onDelete={() => void form.removeProfile()}
        />
      </div>

      {/* Export quality */}
      <ExportQualitySelector
        options={form.qualities}
        value={form.exportQuality}
        onChange={form.setExportQuality}
        disabled={form.submitting}
      />

      {/* Advanced (placeholder) */}
      <AdvancedOptions />

      {form.error !== null && <p className="text-sm text-red-500">{form.error}</p>}

      <div className="flex justify-end">
        <Button
          size="lg"
          disabled={!form.canRun}
          onClick={() => void form.submit()}
        >
          {form.submitting ? "Running…" : "Run Workflow"}
        </Button>
      </div>
    </div>
  );
}
