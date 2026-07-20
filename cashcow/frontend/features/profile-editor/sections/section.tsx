"use client";

import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface EditorSectionProps {
  title: string;
  /** Whether the body is expanded. Controlled by the parent so state persists. */
  open: boolean;
  onToggleOpen: () => void;
  /**
   * Enablement toggle. When provided, a checkbox in the header switches the
   * section between "present" (its config block is emitted) and "absent" (the
   * pipeline step is skipped). Omit for always-present sections like General.
   */
  enabled?: boolean;
  onToggleEnabled?: (enabled: boolean) => void;
  /** Short summary shown in the header when collapsed (e.g. "Ellipse · 60px"). */
  summary?: string;
  children: ReactNode;
  className?: string;
}

/**
 * A collapsible editor section with an optional enable/disable toggle.
 *
 * The header row carries the title, an optional "enabled" checkbox (present vs
 * skipped), and a chevron that expands the body. Expansion is controlled by the
 * parent so the open/closed state of every section is remembered while editing.
 * A disabled section shows its body greyed so the user still sees what would
 * apply if re-enabled, without it being emitted.
 */
export function EditorSection({
  title,
  open,
  onToggleOpen,
  enabled,
  onToggleEnabled,
  summary,
  children,
  className,
}: EditorSectionProps) {
  const hasToggle = enabled !== undefined && onToggleEnabled !== undefined;
  const bodyDisabled = hasToggle && !enabled;
  // Status line beneath the title: enablement first (when the section can be
  // toggled), then the caller's summary. A disabled section reads "Disabled".
  const statusText = hasToggle && !enabled ? "Disabled" : summary;

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border bg-card/55 shadow-sm shadow-[var(--shadow-color)] transition-all duration-200",
        hasToggle && enabled ? "border-primary/25" : "border-input",
        className,
      )}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        {hasToggle && (
          <input
            type="checkbox"
            checked={enabled}
            aria-label={`Enable ${title}`}
            onChange={(e) => onToggleEnabled?.(e.target.checked)}
            className="size-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        )}
        <button
          type="button"
          onClick={onToggleOpen}
          aria-expanded={open}
          className="flex flex-1 cursor-pointer items-center gap-3 rounded-sm text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronRight
            className={cn(
              "size-4 shrink-0 text-muted-foreground transition-transform",
              open && "rotate-90",
            )}
          />
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="text-sm font-medium leading-tight text-foreground/95">{title}</span>
            {statusText !== undefined && statusText !== "" && (
              <span
                className={cn(
                  "truncate text-xs leading-tight",
                  bodyDisabled ? "text-muted-foreground/70" : "text-muted-foreground",
                )}
              >
                {statusText}
              </span>
            )}
          </span>
          {hasToggle && enabled && (
            <span className="shrink-0 rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-[10px] font-medium leading-none text-primary">
              Enabled
            </span>
          )}
        </button>
      </div>
      {open && (
        <div
          className={cn(
            "flex flex-col gap-4 border-t border-input bg-background/30 px-4 py-4",
            bodyDisabled && "pointer-events-none opacity-50",
          )}
          aria-disabled={bodyDisabled}
        >
          {children}
        </div>
      )}
    </div>
  );
}
