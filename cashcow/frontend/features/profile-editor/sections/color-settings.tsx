"use client";

import type { ColorConfig } from "@/lib/api";
import { SliderControl } from "@/components/ui/slider-control";

import { COLOR_DEFAULTS, COLOR_FIELDS } from "./defaults";

export interface ColorSettingsProps {
  value: ColorConfig;
  onChange: (value: ColorConfig) => void;
  disabled?: boolean;
}

/**
 * The colour-grade editor: one synced slider per engine colour field, each
 * bounded to the engine's own range and resettable to its identity value.
 * Reused both as the top-level Color section and nested inside the overlay
 * editor (overlays carry their own colour grade).
 */
export function ColorSettings({ value, onChange, disabled = false }: ColorSettingsProps) {
  return (
    <div className="flex flex-col gap-4">
      {COLOR_FIELDS.map((field) => (
        <SliderControl
          key={field.key}
          label={field.label}
          value={value[field.key]}
          min={field.min}
          max={field.max}
          step={field.step}
          unit={field.unit}
          defaultValue={COLOR_DEFAULTS[field.key]}
          disabled={disabled}
          onChange={(next) => onChange({ ...value, [field.key]: next })}
        />
      ))}
    </div>
  );
}
