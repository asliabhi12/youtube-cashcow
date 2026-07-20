"use client";

import { useId } from "react";

import type { Option } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ExportQualitySelectorProps {
  /** Available export qualities, as returned by the backend. */
  options: Option[];
  /** Currently selected quality slug. */
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
}

/**
 * An accessible radio group for choosing export quality. Rendered as a real
 * radiogroup of radios so arrow-key navigation and screen-reader semantics work
 * out of the box. Options come from the backend.
 */
export function ExportQualitySelector({
  options,
  value,
  onChange,
  disabled = false,
  className,
}: ExportQualitySelectorProps) {
  const groupName = useId();

  return (
    <fieldset className={cn("flex flex-col gap-2", className)} disabled={disabled}>
      <legend className="mb-1 text-sm font-medium">Export Quality</legend>
      <div role="radiogroup" className="flex flex-col gap-2">
        {options.map((option) => {
          const checked = option.value === value;
          return (
            <label
              key={option.value}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-md border px-4 py-3 shadow-sm shadow-[var(--shadow-color)] transition-all duration-200",
                checked
                  ? "border-primary/50 bg-accent/70 ring-1 ring-primary/20"
                  : "border-input bg-background/50 hover:border-primary/30 hover:bg-accent/35",
                disabled && "cursor-not-allowed opacity-50",
              )}
            >
              <input
                type="radio"
                name={groupName}
                value={option.value}
                checked={checked}
                onChange={() => onChange(option.value)}
                disabled={disabled}
                className="mt-0.5 size-4 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <span className="flex flex-col gap-0.5">
                <span className="text-sm font-medium leading-none">{option.label}</span>
                <span className="text-xs text-muted-foreground">{option.description}</span>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
