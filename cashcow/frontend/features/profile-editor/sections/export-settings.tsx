"use client";

import type { Option } from "@/lib/api";
import { ExportQualitySelector } from "@/components/export-quality-selector";
import { CheckboxField } from "@/components/ui/fields";

export interface ExportSettingsProps {
  /** Available export qualities from the backend. */
  options: Option[];
  /** The profile's default export quality, or null when it has no default. */
  value: string | null;
  onChange: (value: string | null) => void;
  disabled?: boolean;
}

/** Fallback quality selected when a profile first gains an export default. */
const DEFAULT_QUALITY = "balanced";

/**
 * The profile's default export quality. A profile may leave this unset (the
 * Home page then picks its own default), or pin a quality that the Home page
 * pre-selects and can still override per job. Reuses the shared
 * {@link ExportQualitySelector} so the choices match the job form exactly.
 */
export function ExportSettings({
  options,
  value,
  onChange,
  disabled = false,
}: ExportSettingsProps) {
  const hasDefault = value !== null;

  return (
    <div className="flex flex-col gap-4">
      <CheckboxField
        label="Set a default export quality"
        hint="Pre-selected on the Home page for this profile; still overridable per job."
        checked={hasDefault}
        disabled={disabled}
        onChange={(on) => onChange(on ? (value ?? DEFAULT_QUALITY) : null)}
      />
      {hasDefault && (
        <ExportQualitySelector
          options={options}
          value={value ?? DEFAULT_QUALITY}
          disabled={disabled}
          onChange={onChange}
        />
      )}
    </div>
  );
}
