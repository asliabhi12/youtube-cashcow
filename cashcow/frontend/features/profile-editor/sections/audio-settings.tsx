"use client";

import { Plus, Trash2 } from "lucide-react";

import type { AudioConfig, AudioEffectItem, AudioEffectType } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DropdownField } from "@/components/ui/fields";
import { SliderControl } from "@/components/ui/slider-control";

import { AUDIO_EFFECTS } from "./defaults";

export interface AudioSettingsProps {
  value: AudioConfig;
  onChange: (value: AudioConfig) => void;
  disabled?: boolean;
}

const EFFECT_OPTIONS = AUDIO_EFFECTS.map((e) => ({ value: e.type, label: e.label }));

/** Build a fresh effect of a given type, seeding its params to their defaults. */
function makeEffect(type: AudioEffectType): AudioEffectItem {
  const spec = AUDIO_EFFECTS.find((e) => e.type === type);
  const effect: AudioEffectItem = { type };
  spec?.params.forEach((p) => {
    effect[p.key] = p.default;
  });
  return effect;
}

/**
 * The audio-effects editor: an ordered chain of effect rows, each a type
 * dropdown plus the sliders that type accepts. Effects apply in list order;
 * rows can be added, removed, and their type switched (which re-seeds that
 * row's parameters). Only the nine engine effect types are offered, and each
 * shows exactly the parameters the engine accepts for it (`normalize` has none).
 */
export function AudioSettings({ value, onChange, disabled = false }: AudioSettingsProps) {
  const effects = value.effects;

  function updateEffect(index: number, next: AudioEffectItem) {
    onChange({ effects: effects.map((e, i) => (i === index ? next : e)) });
  }

  function removeEffect(index: number) {
    onChange({ effects: effects.filter((_, i) => i !== index) });
  }

  function addEffect() {
    onChange({ effects: [...effects, makeEffect("volume")] });
  }

  return (
    <div className="flex flex-col gap-3">
      {effects.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No effects yet. Add one to shape the audio.
        </p>
      )}

      {effects.map((effect, index) => {
        const spec = AUDIO_EFFECTS.find((e) => e.type === effect.type);
        return (
          <div
            key={index}
            className="flex flex-col gap-3 rounded-md border border-input bg-muted/30 p-3"
          >
            <div className="flex items-end gap-2">
              <DropdownField
                label={`Effect ${index + 1}`}
                value={effect.type}
                options={EFFECT_OPTIONS}
                disabled={disabled}
                className="flex-1"
                onChange={(next) => updateEffect(index, makeEffect(next as AudioEffectType))}
              />
              <Button
                size="icon"
                variant="ghost"
                disabled={disabled}
                title="Remove this effect"
                onClick={() => removeEffect(index)}
                className="mb-0.5 shrink-0"
              >
                <Trash2 />
              </Button>
            </div>

            {spec !== undefined && spec.params.length > 0 && (
              <div className="flex flex-col gap-3">
                {spec.params.map((param) => (
                  <SliderControl
                    key={param.key}
                    label={param.label}
                    value={effect[param.key] ?? param.default}
                    min={param.min}
                    max={param.max}
                    step={param.step}
                    unit={param.unit}
                    defaultValue={param.default}
                    disabled={disabled}
                    onChange={(next) =>
                      updateEffect(index, { ...effect, [param.key]: next })
                    }
                  />
                ))}
              </div>
            )}

            {spec !== undefined && spec.params.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No parameters — applied as-is.
              </p>
            )}
          </div>
        );
      })}

      <div>
        <Button size="sm" variant="outline" disabled={disabled} onClick={addEffect}>
          <Plus />
          Add Effect
        </Button>
      </div>
    </div>
  );
}
