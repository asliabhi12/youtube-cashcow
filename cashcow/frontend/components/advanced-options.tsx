"use client";

import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

export interface AdvancedOptionsProps {
  className?: string;
}

/**
 * A collapsible "Advanced Options" section. It is a placeholder for future
 * settings; the body intentionally has no controls yet. Built on the native
 * `<details>`/`<summary>` element so it is keyboard-accessible and needs no
 * open/closed state of its own.
 */
export function AdvancedOptions({ className }: AdvancedOptionsProps) {
  return (
    <details className={cn("group rounded-md border border-input", className)}>
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium [&::-webkit-details-marker]:hidden">
        <ChevronRight className="size-4 shrink-0 transition-transform group-open:rotate-90" />
        Advanced Options
      </summary>
      <div className="border-t border-input px-4 py-3 text-sm text-muted-foreground">
        No advanced options yet.
      </div>
    </details>
  );
}
