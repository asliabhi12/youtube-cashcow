"use client";

import { useId } from "react";

import type { ProfileSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ProfileSelectorProps {
  /** Available profiles, as returned by the backend (built-ins first). */
  options: ProfileSummary[];
  /** Currently selected profile id. */
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
}

/**
 * A styled native `<select>` for choosing a creative profile, with the active
 * profile's description shown beneath. Built-in and custom profiles are grouped
 * so users can tell which ones they can edit. Options come from the backend so
 * the list always matches what `POST /jobs` accepts.
 */
export function ProfileSelector({
  options,
  value,
  onChange,
  disabled = false,
  className,
}: ProfileSelectorProps) {
  const selectId = useId();
  const active = options.find((option) => option.id === value);

  const builtins = options.filter((o) => o.builtin);
  const custom = options.filter((o) => !o.builtin);

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <label htmlFor={selectId} className="text-sm font-medium">
        Creative Profile
      </label>
      <select
        id={selectId}
        value={value}
        disabled={disabled || options.length === 0}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full rounded-md border border-input bg-background px-4 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
      >
        <optgroup label="Built-in">
          {builtins.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </optgroup>
        {custom.length > 0 && (
          <optgroup label="Custom">
            {custom.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </optgroup>
        )}
      </select>
      {active !== undefined && active.description !== "" && (
        <p className="text-xs text-muted-foreground">{active.description}</p>
      )}
    </div>
  );
}
