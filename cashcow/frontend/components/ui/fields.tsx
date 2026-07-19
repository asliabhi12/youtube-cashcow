"use client";

import { useId } from "react";

import { cn } from "@/lib/utils";

/**
 * Small labelled form-field primitives shared by the profile editor's category
 * sections. Each keeps the same styling as the existing {@link Input} and
 * profile selector so the editor reads as one system. They are controlled
 * components: value in, change out.
 */

export interface CheckboxFieldProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Optional helper text shown beneath the label. */
  hint?: string;
  disabled?: boolean;
  className?: string;
}

/** A labelled checkbox with an optional hint line. */
export function CheckboxField({
  label,
  checked,
  onChange,
  hint,
  disabled = false,
  className,
}: CheckboxFieldProps) {
  const id = useId();
  return (
    <div className={cn("flex items-start gap-3", className)}>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 size-4 accent-primary disabled:cursor-not-allowed disabled:opacity-50"
      />
      <label htmlFor={id} className="flex flex-col gap-0.5">
        <span className="text-sm font-medium leading-none">{label}</span>
        {hint !== undefined && (
          <span className="text-xs text-muted-foreground">{hint}</span>
        )}
      </label>
    </div>
  );
}

export interface DropdownOption {
  value: string;
  label: string;
}

export interface DropdownFieldProps {
  label: string;
  value: string;
  options: DropdownOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
}

/** A labelled native `<select>` matching the profile selector's styling. */
export function DropdownField({
  label,
  value,
  options,
  onChange,
  disabled = false,
  className,
}: DropdownFieldProps) {
  const id = useId();
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export interface NumberFieldProps {
  label: string;
  /** Current value, or null for an empty field (an unset optional param). */
  value: number | null;
  onChange: (value: number | null) => void;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  unit?: string;
  disabled?: boolean;
  className?: string;
}

/**
 * A labelled number input that supports an *empty* state (null) for optional
 * parameters. Values are clamped to `[min, max]` on change when bounds are
 * given, so an out-of-range number can't be produced.
 */
export function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step,
  placeholder,
  unit,
  disabled = false,
  className,
}: NumberFieldProps) {
  const id = useId();
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          id={id}
          type="number"
          inputMode="decimal"
          min={min}
          max={max}
          step={step}
          value={value ?? ""}
          placeholder={placeholder}
          disabled={disabled}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw.trim() === "") {
              onChange(null);
              return;
            }
            const parsed = Number(raw);
            if (Number.isNaN(parsed)) {
              return;
            }
            let next = parsed;
            if (min !== undefined) next = Math.max(min, next);
            if (max !== undefined) next = Math.min(max, next);
            onChange(next);
          }}
          className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm tabular-nums shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
        />
        {unit !== undefined && (
          <span className="shrink-0 text-xs text-muted-foreground">{unit}</span>
        )}
      </div>
    </div>
  );
}

export interface TextFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  /** Render a multi-line textarea instead of a single-line input. */
  multiline?: boolean;
  disabled?: boolean;
  className?: string;
}

/** A labelled single-line input or textarea, matching the shared Input style. */
export function TextField({
  label,
  value,
  onChange,
  placeholder,
  multiline = false,
  disabled = false,
  className,
}: TextFieldProps) {
  const id = useId();
  const shared =
    "w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50";
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {multiline ? (
        <textarea
          id={id}
          value={value}
          placeholder={placeholder}
          disabled={disabled}
          rows={2}
          onChange={(e) => onChange(e.target.value)}
          className={cn(shared, "min-h-16 resize-y")}
        />
      ) : (
        <input
          id={id}
          type="text"
          value={value}
          placeholder={placeholder}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className={cn(shared, "h-10")}
        />
      )}
    </div>
  );
}
