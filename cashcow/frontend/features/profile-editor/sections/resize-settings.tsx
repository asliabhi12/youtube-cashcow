"use client";

import type { ResizeConfig, ResizePreset } from "@/lib/api";
import { CheckboxField, DropdownField, NumberField } from "@/components/ui/fields";
import { SliderControl } from "@/components/ui/slider-control";

import { RESIZE_PRESETS } from "./defaults";

export interface ResizeSettingsProps {
  value: ResizeConfig;
  onChange: (value: ResizeConfig) => void;
  disabled?: boolean;
}

// Sentinel select value for "no named preset — use explicit dimensions".
const CUSTOM = "__custom__";

/**
 * The resize editor. A profile resizes either by a named platform preset or by
 * explicit width/height (the two are mutually exclusive, matching the engine),
 * chosen via the size dropdown. `zoom` is a centred punch-in (>= 1.0) and
 * `padding` letterboxes instead of cropping. Only these four engine parameters
 * are exposed — there is no x/y, fit, or crop mode in the engine.
 */
export function ResizeSettings({ value, onChange, disabled = false }: ResizeSettingsProps) {
  const usingDimensions = !value.preset;

  return (
    <div className="flex flex-col gap-4">
      <DropdownField
        label="Target Size"
        value={value.preset ?? CUSTOM}
        disabled={disabled}
        options={[
          ...RESIZE_PRESETS,
          { value: CUSTOM, label: "Custom dimensions…" },
        ]}
        onChange={(next) => {
          if (next === CUSTOM) {
            // Switch to explicit dimensions; seed sensible defaults.
            onChange({
              ...value,
              preset: null,
              width: value.width ?? 1080,
              height: value.height ?? 1920,
            });
          } else {
            // A named preset excludes explicit dimensions.
            onChange({ ...value, preset: next as ResizePreset, width: null, height: null });
          }
        }}
      />

      {usingDimensions && (
        <div className="grid grid-cols-2 gap-4">
          <NumberField
            label="Width"
            value={value.width ?? null}
            min={1}
            step={1}
            unit="px"
            disabled={disabled}
            onChange={(next) => onChange({ ...value, width: next })}
          />
          <NumberField
            label="Height"
            value={value.height ?? null}
            min={1}
            step={1}
            unit="px"
            disabled={disabled}
            onChange={(next) => onChange({ ...value, height: next })}
          />
        </div>
      )}

      <SliderControl
        label="Zoom"
        value={value.zoom ?? 1}
        min={1}
        max={3}
        step={0.01}
        unit="×"
        defaultValue={1}
        disabled={disabled}
        onChange={(next) => onChange({ ...value, zoom: next })}
      />

      <CheckboxField
        label="Padding"
        hint="Letterbox to the target size instead of cropping."
        checked={value.padding ?? false}
        disabled={disabled}
        onChange={(checked) => onChange({ ...value, padding: checked })}
      />
    </div>
  );
}
