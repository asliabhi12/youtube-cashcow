"use client";

import type { MaskConfig, MaskType } from "@/lib/api";
import { CheckboxField, DropdownField, NumberField } from "@/components/ui/fields";
import { SliderControl } from "@/components/ui/slider-control";

import { MASK_TYPES } from "./defaults";

export interface MaskSettingsProps {
  value: MaskConfig;
  onChange: (value: MaskConfig) => void;
  disabled?: boolean;
}

/**
 * The overlay mask editor. Only the two mask shapes the engine implements
 * (circle, ellipse) are offered — there is no "none" (omit the mask to skip it)
 * and no rectangle. `feather` softens the edge, `width`/`height` size the shape
 * (defaulting to the overlay's own size when unset), and `invert` keeps the
 * region outside the shape instead of inside.
 */
export function MaskSettings({ value, onChange, disabled = false }: MaskSettingsProps) {
  return (
    <div className="flex flex-col gap-4">
      <DropdownField
        label="Shape"
        value={value.type}
        options={MASK_TYPES}
        disabled={disabled}
        onChange={(next) => onChange({ ...value, type: next as MaskType })}
      />

      <SliderControl
        label="Feather"
        value={value.feather}
        min={0}
        max={200}
        step={1}
        unit="px"
        defaultValue={0}
        disabled={disabled}
        onChange={(feather) => onChange({ ...value, feather })}
      />

      <div className="grid grid-cols-2 gap-4">
        <NumberField
          label="Width"
          value={value.width ?? null}
          min={1}
          step={1}
          unit="px"
          placeholder="auto"
          disabled={disabled}
          onChange={(width) => onChange({ ...value, width })}
        />
        <NumberField
          label="Height"
          value={value.height ?? null}
          min={1}
          step={1}
          unit="px"
          placeholder="auto"
          disabled={disabled}
          onChange={(height) => onChange({ ...value, height })}
        />
      </div>

      <SliderControl
        label="Rotation"
        value={value.rotation}
        min={-180}
        max={180}
        step={1}
        unit="°"
        defaultValue={0}
        disabled={disabled}
        onChange={(rotation) => onChange({ ...value, rotation })}
      />

      <CheckboxField
        label="Invert"
        hint="Keep the area outside the shape instead of inside."
        checked={value.invert}
        disabled={disabled}
        onChange={(invert) => onChange({ ...value, invert })}
      />
    </div>
  );
}
