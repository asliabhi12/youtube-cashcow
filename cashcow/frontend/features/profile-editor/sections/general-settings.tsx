"use client";

import { TextField } from "@/components/ui/fields";
import { cn } from "@/lib/utils";

export interface GeneralSettingsProps {
  label: string;
  description: string;
  onLabelChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  /** Whether the profile is a read-only built-in (shown as a badge). */
  isBuiltin: boolean;
  /** Whether the profile has been saved yet (a new draft has no badge). */
  isNew: boolean;
  disabled?: boolean;
}

/**
 * The General section: the profile's name and description, plus a badge showing
 * whether it is a built-in (read-only), a saved custom profile, or an unsaved
 * new draft. Editing a built-in's fields is allowed — saving routes to "Save
 * As", creating a custom copy — so the inputs stay enabled.
 */
export function GeneralSettings({
  label,
  description,
  onLabelChange,
  onDescriptionChange,
  isBuiltin,
  isNew,
  disabled = false,
}: GeneralSettingsProps) {
  const badge = isNew ? "New profile" : isBuiltin ? "Built-in profile" : "Custom profile";
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 rounded-lg bg-muted/40 px-4 py-3">
        <span
          className={cn(
            "flex size-10 shrink-0 items-center justify-center rounded-full text-base font-semibold",
            isBuiltin ? "bg-muted text-muted-foreground" : "bg-primary/10 text-primary",
          )}
          aria-hidden
        >
          {(label.trim()[0] ?? "?").toUpperCase()}
        </span>
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-base font-semibold leading-tight">
            {label.trim() === "" ? "Untitled profile" : label}
          </span>
          <span className="text-xs text-muted-foreground">{badge}</span>
        </div>
      </div>
      <TextField
        label="Profile Name"
        value={label}
        placeholder="e.g. Vivid Vertical"
        disabled={disabled}
        onChange={onLabelChange}
      />
      <TextField
        label="Description"
        value={description}
        placeholder="What this look is for…"
        multiline
        disabled={disabled}
        onChange={onDescriptionChange}
      />
    </div>
  );
}
