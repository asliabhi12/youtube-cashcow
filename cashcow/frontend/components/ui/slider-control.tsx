"use client";

import { RotateCcw } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { cn } from "@/lib/utils";

export interface SliderControlProps {
  label: string;
  value: number;
  /** Inclusive range bounds, matching the engine's own validation. */
  min: number;
  max: number;
  /** Slider/number step. Defaults to 0.01 for fine control. */
  step?: number;
  /** Value the reset button restores (the engine's identity/default). */
  defaultValue: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  /** Short unit shown after the number input (e.g. "dB", "×", "°"). */
  unit?: string;
  className?: string;
}

/** Round to at most 4 decimals so float math never shows 1.2000000001. */
function tidy(value: number): number {
  return Math.round(value * 10000) / 10000;
}

/**
 * A labelled numeric control: a range slider and a number input kept in sync,
 * with a reset-to-default button. Both inputs drive the same value and clamp to
 * `[min, max]`, so an out-of-range value can never be produced. Built on native
 * inputs (no slider library), mirroring {@link TrimRangeSlider}.
 *
 * The number field keeps its own text state while focused so the user can clear
 * it and type freely (including a lone "-" or "."); the value is parsed and
 * clamped live, and normalised on blur.
 */
export function SliderControl({
  label,
  value,
  min,
  max,
  step = 0.01,
  defaultValue,
  onChange,
  disabled = false,
  unit,
  className,
}: SliderControlProps) {
  const id = useId();
  // Local text mirror of the number input so intermediate states ("", "-",
  // "1.") don't fight the numeric value or snap the cursor around.
  const [text, setText] = useState(String(tidy(value)));

  // Keep the text in sync when the value changes from outside (slider drag,
  // reset, loading a different profile) — but not while the user is mid-edit.
  useEffect(() => {
    setText(String(tidy(value)));
  }, [value]);

  const clamp = (n: number) => Math.min(max, Math.max(min, n));
  const isDefault = tidy(value) === tidy(defaultValue);

  function commitText(raw: string) {
    const parsed = Number(raw);
    if (raw.trim() === "" || Number.isNaN(parsed)) {
      // Reject unparseable input by snapping back to the current value.
      setText(String(tidy(value)));
      return;
    }
    const next = clamp(parsed);
    onChange(next);
    setText(String(tidy(next)));
  }

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        <button
          type="button"
          onClick={() => onChange(clamp(defaultValue))}
          disabled={disabled || isDefault}
          title={`Reset to ${tidy(defaultValue)}`}
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-accent/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-40"
        >
          <RotateCcw className="size-3" />
          Reset
        </button>
      </div>
      <div className="flex items-center gap-3">
        <input
          id={id}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(clamp(Number(e.target.value)))}
          className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-muted accent-primary disabled:cursor-not-allowed disabled:opacity-50"
        />
        <div className="flex items-center gap-1">
          <input
            type="number"
            inputMode="decimal"
            min={min}
            max={max}
            step={step}
            value={text}
            disabled={disabled}
            aria-label={`${label} value`}
            onChange={(e) => {
              setText(e.target.value);
              // Live-commit when the current text parses to a real number, so
              // the slider tracks typing; blur normalises the display.
              const parsed = Number(e.target.value);
              if (e.target.value.trim() !== "" && !Number.isNaN(parsed)) {
                onChange(clamp(parsed));
              }
            }}
            onBlur={(e) => commitText(e.target.value)}
            className="h-8 w-20 rounded-md border border-input bg-background/70 px-2 py-1 text-right text-sm tabular-nums shadow-sm shadow-[var(--shadow-color)] transition-all duration-200 hover:border-primary/35 focus-visible:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70 focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
          />
          {unit !== undefined && (
            <span className="w-6 shrink-0 text-xs text-muted-foreground">{unit}</span>
          )}
        </div>
      </div>
    </div>
  );
}
