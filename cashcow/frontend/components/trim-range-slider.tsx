"use client";

import { useCallback, useId, useRef } from "react";

import { cn } from "@/lib/utils";

/** Format a number of seconds as `m:ss` (or `h:mm:ss` past an hour). */
export function formatDuration(totalSeconds: number): string {
  const secs = Math.max(0, Math.round(totalSeconds));
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export interface TrimRangeSliderProps {
  /** Selected start offset in seconds. */
  start: number;
  /** Selected end offset in seconds. */
  end: number;
  /** Maximum selectable value in seconds (the video duration, or a fallback). */
  max: number;
  /** Called with a validated, non-crossing `{start, end}` on any change. */
  onChange: (range: { start: number; end: number }) => void;
  /** Smallest gap kept between the two handles, in seconds. Defaults to 1. */
  minGap?: number;
  /** Step for keyboard arrow adjustments, in seconds. Defaults to 1. */
  step?: number;
  disabled?: boolean;
  className?: string;
}

type Handle = "start" | "end";

/**
 * A dual-handle range slider for choosing a clip's start and end, in seconds.
 *
 * The left thumb is the start, the right thumb is the end; they cannot cross and
 * always keep at least `minGap` seconds between them. Both thumbs are keyboard
 * accessible (arrows, Page Up/Down, Home/End) and expose the standard slider
 * ARIA attributes. Values are always reported in seconds via `onChange`.
 */
export function TrimRangeSlider({
  start,
  end,
  max,
  onChange,
  minGap = 1,
  step = 1,
  disabled = false,
  className,
}: TrimRangeSliderProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const groupId = useId();
  // Guard against a zero/negative max so percentage math stays finite.
  const safeMax = max > 0 ? max : 1;

  const clampStart = useCallback(
    (value: number) => Math.min(Math.max(0, value), end - minGap),
    [end, minGap],
  );
  const clampEnd = useCallback(
    (value: number) => Math.max(Math.min(safeMax, value), start + minGap),
    [safeMax, start, minGap],
  );

  const setHandle = useCallback(
    (handle: Handle, value: number) => {
      if (handle === "start") {
        onChange({ start: clampStart(value), end });
      } else {
        onChange({ start, end: clampEnd(value) });
      }
    },
    [clampStart, clampEnd, onChange, start, end],
  );

  // Map a clientX within the track to a value in seconds.
  const valueFromClientX = useCallback(
    (clientX: number): number => {
      const track = trackRef.current;
      if (track === null) {
        return 0;
      }
      const rect = track.getBoundingClientRect();
      const ratio = rect.width > 0 ? (clientX - rect.left) / rect.width : 0;
      return Math.round(Math.min(1, Math.max(0, ratio)) * safeMax);
    },
    [safeMax],
  );

  const startPct = (start / safeMax) * 100;
  const endPct = (end / safeMax) * 100;

  function handlePointerDown(handle: Handle) {
    return (event: React.PointerEvent<HTMLButtonElement>) => {
      if (disabled) {
        return;
      }
      event.preventDefault();
      const thumb = event.currentTarget;
      thumb.setPointerCapture(event.pointerId);

      const move = (e: PointerEvent) => setHandle(handle, valueFromClientX(e.clientX));
      const up = (e: PointerEvent) => {
        thumb.releasePointerCapture(e.pointerId);
        thumb.removeEventListener("pointermove", move);
        thumb.removeEventListener("pointerup", up);
      };
      thumb.addEventListener("pointermove", move);
      thumb.addEventListener("pointerup", up);
    };
  }

  function handleKeyDown(handle: Handle) {
    return (event: React.KeyboardEvent<HTMLButtonElement>) => {
      if (disabled) {
        return;
      }
      const current = handle === "start" ? start : end;
      const bigStep = Math.max(step, Math.round(safeMax / 10));
      let next: number | null = null;

      switch (event.key) {
        case "ArrowRight":
        case "ArrowUp":
          next = current + step;
          break;
        case "ArrowLeft":
        case "ArrowDown":
          next = current - step;
          break;
        case "PageUp":
          next = current + bigStep;
          break;
        case "PageDown":
          next = current - bigStep;
          break;
        case "Home":
          next = handle === "start" ? 0 : start + minGap;
          break;
        case "End":
          next = handle === "start" ? end - minGap : safeMax;
          break;
        default:
          return;
      }

      event.preventDefault();
      setHandle(handle, next);
    };
  }

  const thumbBase =
    "absolute top-1/2 size-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-primary bg-background shadow-md shadow-[var(--shadow-color)] transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 hover:scale-105 hover:bg-accent touch-none";

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div
        ref={trackRef}
        className={cn(
          "relative h-6 w-full select-none",
          disabled && "opacity-50",
        )}
      >
        {/* Full track */}
        <div className="absolute top-1/2 h-1.5 w-full -translate-y-1/2 rounded-full bg-muted" />
        {/* Selected region */}
        <div
          className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-primary"
          style={{ left: `${startPct}%`, width: `${Math.max(0, endPct - startPct)}%` }}
        />
        {/* Start thumb */}
        <button
          type="button"
          role="slider"
          aria-label="Clip start"
          aria-valuemin={0}
          aria-valuemax={Math.max(0, end - minGap)}
          aria-valuenow={start}
          aria-valuetext={formatDuration(start)}
          aria-orientation="horizontal"
          aria-controls={groupId}
          disabled={disabled}
          className={thumbBase}
          style={{ left: `${startPct}%` }}
          onPointerDown={handlePointerDown("start")}
          onKeyDown={handleKeyDown("start")}
        />
        {/* End thumb */}
        <button
          type="button"
          role="slider"
          aria-label="Clip end"
          aria-valuemin={Math.min(safeMax, start + minGap)}
          aria-valuemax={safeMax}
          aria-valuenow={end}
          aria-valuetext={formatDuration(end)}
          aria-orientation="horizontal"
          aria-controls={groupId}
          disabled={disabled}
          className={thumbBase}
          style={{ left: `${endPct}%` }}
          onPointerDown={handlePointerDown("end")}
          onKeyDown={handleKeyDown("end")}
        />
      </div>

      <div id={groupId} className="flex items-center justify-between text-sm">
        <span className="tabular-nums font-medium">{formatDuration(start)}</span>
        <span className="text-muted-foreground">
          {formatDuration(end - start)} selected
        </span>
        <span className="tabular-nums font-medium">{formatDuration(end)}</span>
      </div>
    </div>
  );
}
