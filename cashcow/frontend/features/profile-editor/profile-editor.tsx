"use client";

import { useState } from "react";

import type { ColorConfig, Option } from "@/lib/api";

import type { ProfileEditorState } from "./use-profile-editor";
import { AudioSettings } from "./sections/audio-settings";
import { ColorSettings } from "./sections/color-settings";
import { EditorSection } from "./sections/section";
import { ExportSettings } from "./sections/export-settings";
import { GeneralSettings } from "./sections/general-settings";
import { OverlaySettings } from "./sections/overlay-settings";
import { ResizeSettings } from "./sections/resize-settings";
import {
  COLOR_DEFAULTS,
  OVERLAY_DEFAULTS,
  RESIZE_DEFAULTS,
  RESIZE_PRESETS,
} from "./sections/defaults";

export interface ProfileEditorProps {
  editor: ProfileEditorState;
  /** Export-quality options for the Export Defaults section. */
  qualities: Option[];
  /** Disable every control (e.g. while a job submit is in flight). */
  disabled?: boolean;
}

type SectionKey = "general" | "resize" | "audio" | "color" | "overlay" | "export";

/** A colour summary for a collapsed grade section (how many fields differ). */
function colorSummary(color: ColorConfig | null): string {
  if (color === null) {
    return "";
  }
  const changed = (Object.keys(COLOR_DEFAULTS) as (keyof ColorConfig)[]).filter(
    (k) => color[k] !== COLOR_DEFAULTS[k],
  ).length;
  return changed === 0
    ? "Defaults (no change)"
    : `${changed} adjustment${changed === 1 ? "" : "s"}`;
}

/**
 * The full creative-profile editor: General plus one collapsible section per
 * engine category (Resize, Audio, Colour, Overlay, Export). Each creative
 * section has an enable toggle that switches its config block on or off
 * (present → the pipeline step runs; absent → it is skipped), and its expansion
 * state is remembered here while editing so opening a section and tweaking
 * another doesn't collapse it.
 *
 * All state lives in the passed {@link ProfileEditorState}; this component only
 * renders it and forwards edits, so the Home form and the profiles manager can
 * share one editor.
 */
export function ProfileEditor({ editor, qualities, disabled = false }: ProfileEditorProps) {
  const { draft, update, isBuiltin, activeId, issues } = editor;

  // Human-readable one-liners for each collapsed section header.
  const resizeSummary = (() => {
    if (draft.resize === null) return "";
    if (draft.resize.preset) {
      return RESIZE_PRESETS.find((p) => p.value === draft.resize?.preset)?.label ?? draft.resize.preset;
    }
    if (draft.resize.width != null && draft.resize.height != null) {
      return `${draft.resize.width}×${draft.resize.height}`;
    }
    return "Custom size";
  })();

  const audioSummary = (() => {
    if (draft.audio === null) return "";
    const n = draft.audio.effects.length;
    return n === 0 ? "No effects yet" : `${n} effect${n === 1 ? "" : "s"} active`;
  })();

  const overlaySummary = (() => {
    if (draft.overlay === null) return "";
    return draft.overlay.asset ? `Image: ${draft.overlay.asset}` : "No asset selected";
  })();

  const exportSummary =
    draft.exportQuality === null
      ? "Chosen per job"
      : (qualities.find((q) => q.value === draft.exportQuality)?.label ??
        draft.exportQuality);

  // Remembered expansion state. General starts open; the rest collapsed.
  const [open, setOpen] = useState<Set<SectionKey>>(new Set<SectionKey>(["general"]));
  const toggle = (key: SectionKey) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });

  const issueFor = (section: string) =>
    issues.find((i) => i.section === section)?.message;

  return (
    <div className="flex flex-col gap-3">
      <EditorSection
        title="General"
        open={open.has("general")}
        onToggleOpen={() => toggle("general")}
      >
        <GeneralSettings
          label={draft.label}
          description={draft.description}
          isBuiltin={isBuiltin}
          isNew={activeId === null}
          disabled={disabled}
          onLabelChange={(label) => update({ label })}
          onDescriptionChange={(description) => update({ description })}
        />
        {issueFor("general") !== undefined && (
          <p className="text-xs text-danger-foreground">{issueFor("general")}</p>
        )}
      </EditorSection>

      <EditorSection
        title="Resize"
        open={open.has("resize")}
        onToggleOpen={() => toggle("resize")}
        enabled={draft.resize !== null}
        onToggleEnabled={(on) => update({ resize: on ? { ...RESIZE_DEFAULTS } : null })}
        summary={resizeSummary}
      >
        {draft.resize !== null && (
          <ResizeSettings
            value={draft.resize}
            disabled={disabled}
            onChange={(resize) => update({ resize })}
          />
        )}
        {issueFor("resize") !== undefined && (
          <p className="text-xs text-danger-foreground">{issueFor("resize")}</p>
        )}
      </EditorSection>

      <EditorSection
        title="Audio"
        open={open.has("audio")}
        onToggleOpen={() => toggle("audio")}
        enabled={draft.audio !== null}
        onToggleEnabled={(on) => update({ audio: on ? { effects: [] } : null })}
        summary={audioSummary}
      >
        {draft.audio !== null && (
          <AudioSettings
            value={draft.audio}
            disabled={disabled}
            onChange={(audio) => update({ audio })}
          />
        )}
      </EditorSection>

      <EditorSection
        title="Colour Grading"
        open={open.has("color")}
        onToggleOpen={() => toggle("color")}
        enabled={draft.color !== null}
        onToggleEnabled={(on) => update({ color: on ? { ...COLOR_DEFAULTS } : null })}
        summary={colorSummary(draft.color)}
      >
        {draft.color !== null && (
          <ColorSettings
            value={draft.color}
            disabled={disabled}
            onChange={(color) => update({ color })}
          />
        )}
      </EditorSection>

      <EditorSection
        title="Overlay"
        open={open.has("overlay")}
        onToggleOpen={() => toggle("overlay")}
        enabled={draft.overlay !== null}
        onToggleEnabled={(on) =>
          update({ overlay: on ? { asset: "", ...OVERLAY_DEFAULTS } : null })
        }
        summary={overlaySummary}
      >
        {draft.overlay !== null && (
          <OverlaySettings
            value={draft.overlay}
            disabled={disabled}
            onChange={(overlay) => update({ overlay })}
          />
        )}
        {issueFor("overlay") !== undefined && (
          <p className="text-xs text-danger-foreground">{issueFor("overlay")}</p>
        )}
      </EditorSection>

      <EditorSection
        title="Export Defaults"
        open={open.has("export")}
        onToggleOpen={() => toggle("export")}
        summary={exportSummary}
      >
        <ExportSettings
          options={qualities}
          value={draft.exportQuality}
          disabled={disabled}
          onChange={(exportQuality) => update({ exportQuality })}
        />
      </EditorSection>
    </div>
  );
}
