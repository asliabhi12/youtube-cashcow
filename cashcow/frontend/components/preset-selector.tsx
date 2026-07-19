"use client";

import { useId } from "react";

import type { Option } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface PresetSelectorProps {
  /** Available presets, as returned by the backend. */
  options: Option[];
  /** Currently selected preset slug. */
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
}

/**
 * A styled native `<select>` for choosing an editing preset, with the active
 * preset's description shown beneath. Options come from the backend so the list
 * always matches what `POST /jobs` accepts.
 */
export function PresetSelector({
  options,
  value,
  onChange,
  disabled = false,
  className,
}: PresetSelectorProps) {
  const selectId = useId();
  const active = options.find((option) => option.value === value);

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <label htmlFor={selectId} className="text-sm font-medium">
        Editing Preset
      </label>
      <select
        id={selectId}
        value={value}
        disabled={disabled || options.length === 0}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full rounded-md border border-input bg-background px-4 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {active !== undefined && (
        <p className="text-xs text-muted-foreground">{active.description}</p>
      )}
    </div>
  );
}
