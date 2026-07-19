"use client";

import type {
  ColorConfig,
  MaskConfig,
  OverlayAnchor,
  OverlayConfig,
} from "@/lib/api";
import { CheckboxField, DropdownField, NumberField } from "@/components/ui/fields";
import { SliderControl } from "@/components/ui/slider-control";

import { AssetPicker } from "./asset-picker";
import { ColorSettings } from "./color-settings";
import { MaskSettings } from "./mask-settings";
import {
  COLOR_DEFAULTS,
  MASK_DEFAULTS,
  OVERLAY_ANCHORS,
} from "./defaults";

export interface OverlaySettingsProps {
  value: OverlayConfig;
  onChange: (value: OverlayConfig) => void;
  disabled?: boolean;
}

// Sentinel select value for "numeric pixel offset" vs a named anchor.
const NUMERIC = "__numeric__";

/** Whether an x/y position value is a named anchor (vs a pixel number). */
function isAnchor(v: number | OverlayAnchor): v is OverlayAnchor {
  return typeof v === "string";
}

/** A single position axis: anchor dropdown, with a number input when numeric. */
function PositionAxis({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: number | OverlayAnchor;
  onChange: (value: number | OverlayAnchor) => void;
  disabled?: boolean;
}) {
  const numeric = !isAnchor(value);
  return (
    <div className="flex flex-col gap-2">
      <DropdownField
        label={label}
        value={numeric ? NUMERIC : (value as string)}
        disabled={disabled}
        options={[...OVERLAY_ANCHORS, { value: NUMERIC, label: "Custom (px)…" }]}
        onChange={(next) => {
          onChange(next === NUMERIC ? 0 : (next as OverlayAnchor));
        }}
      />
      {numeric && (
        <NumberField
          label={`${label} offset`}
          value={value as number}
          step={1}
          unit="px"
          disabled={disabled}
          onChange={(next) => onChange(next ?? 0)}
        />
      )}
    </div>
  );
}

/**
 * The overlay editor. Picks an asset (built-in or uploaded), positions it by
 * anchor or pixel offset, and sizes it by either a uniform scale or explicit
 * width/height (mutually exclusive, matching the engine). Opacity, rotation and
 * layer follow, then two optional nested blocks the engine supports on an
 * overlay: a colour grade and a mask (circle/ellipse). Only engine-supported
 * overlay parameters are exposed.
 */
export function OverlaySettings({ value, onChange, disabled = false }: OverlaySettingsProps) {
  // Size mode: scale is exclusive with width/height, so a radio picks one.
  const usingDimensions = value.scale == null && (value.width != null || value.height != null);

  function setColor(color: ColorConfig | null) {
    onChange({ ...value, color });
  }
  function setMask(mask: MaskConfig | null) {
    onChange({ ...value, mask });
  }

  return (
    <div className="flex flex-col gap-5">
      <AssetPicker
        value={value.asset}
        disabled={disabled}
        onChange={(asset) => onChange({ ...value, asset })}
      />

      {/* Position */}
      <div className="grid grid-cols-2 gap-4">
        <PositionAxis
          label="Horizontal (X)"
          value={value.x}
          disabled={disabled}
          onChange={(x) => onChange({ ...value, x })}
        />
        <PositionAxis
          label="Vertical (Y)"
          value={value.y}
          disabled={disabled}
          onChange={(y) => onChange({ ...value, y })}
        />
      </div>

      {/* Size mode */}
      <div className="flex flex-col gap-3">
        <span className="text-sm font-medium">Size</span>
        <div className="flex gap-4 text-sm">
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="overlay-size-mode"
              checked={!usingDimensions}
              disabled={disabled}
              onChange={() =>
                onChange({ ...value, scale: value.scale ?? 1, width: null, height: null })
              }
              className="size-4 accent-primary"
            />
            Scale
          </label>
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="overlay-size-mode"
              checked={usingDimensions}
              disabled={disabled}
              onChange={() =>
                onChange({
                  ...value,
                  scale: null,
                  width: value.width ?? 200,
                  height: value.height ?? 200,
                })
              }
              className="size-4 accent-primary"
            />
            Width / Height
          </label>
        </div>

        {!usingDimensions ? (
          <SliderControl
            label="Scale"
            value={value.scale ?? 1}
            min={0.1}
            max={5}
            step={0.05}
            unit="×"
            defaultValue={1}
            disabled={disabled}
            onChange={(scale) => onChange({ ...value, scale, width: null, height: null })}
          />
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <NumberField
              label="Width"
              value={value.width ?? null}
              min={1}
              step={1}
              unit="px"
              disabled={disabled}
              onChange={(width) => onChange({ ...value, width, scale: null })}
            />
            <NumberField
              label="Height"
              value={value.height ?? null}
              min={1}
              step={1}
              unit="px"
              disabled={disabled}
              onChange={(height) => onChange({ ...value, height, scale: null })}
            />
          </div>
        )}
      </div>

      <SliderControl
        label="Opacity"
        value={value.opacity}
        min={0}
        max={1}
        step={0.01}
        defaultValue={1}
        disabled={disabled}
        onChange={(opacity) => onChange({ ...value, opacity })}
      />
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
      <NumberField
        label="Layer"
        value={value.layer}
        step={1}
        disabled={disabled}
        onChange={(layer) => onChange({ ...value, layer: layer ?? 0 })}
      />

      {/* Nested colour grade for the overlay itself. */}
      <div className="rounded-md border border-input p-3">
        <CheckboxField
          label="Colour-grade the overlay"
          hint="Apply a separate colour grade to just the overlay image."
          checked={value.color != null}
          disabled={disabled}
          onChange={(on) => setColor(on ? { ...COLOR_DEFAULTS } : null)}
        />
        {value.color != null && (
          <div className="mt-4">
            <ColorSettings value={value.color} disabled={disabled} onChange={setColor} />
          </div>
        )}
      </div>

      {/* Nested mask (circle/ellipse). */}
      <div className="rounded-md border border-input p-3">
        <CheckboxField
          label="Mask the overlay"
          hint="Clip the overlay to a circle or ellipse."
          checked={value.mask != null}
          disabled={disabled}
          onChange={(on) => setMask(on ? { ...MASK_DEFAULTS } : null)}
        />
        {value.mask != null && (
          <div className="mt-4">
            <MaskSettings value={value.mask} disabled={disabled} onChange={setMask} />
          </div>
        )}
      </div>
    </div>
  );
}
