import type {
  AudioEffectType,
  ColorConfig,
  MaskConfig,
  MaskType,
  OverlayAnchor,
  OverlayConfig,
  ResizeConfig,
  ResizePreset,
} from "@/lib/api";

/**
 * Engine identity defaults and range metadata for the editor sections. Every
 * value here mirrors `src/processor/models.py` (and the backend profile model),
 * so the controls can never offer something the engine would reject.
 */

/** Colour grade with every field at its no-op identity value. */
export const COLOR_DEFAULTS: ColorConfig = {
  brightness: 0,
  contrast: 1,
  saturation: 1,
  gamma: 1,
  hue: 0,
  temperature: 0,
  tint: 0,
  vibrance: 0,
};

/** Per-field range + default metadata driving the colour sliders. */
export const COLOR_FIELDS: {
  key: keyof ColorConfig;
  label: string;
  min: number;
  max: number;
  step: number;
  unit?: string;
}[] = [
  { key: "brightness", label: "Brightness", min: -1, max: 1, step: 0.01 },
  { key: "contrast", label: "Contrast", min: 0, max: 3, step: 0.01 },
  { key: "saturation", label: "Saturation", min: 0, max: 3, step: 0.01 },
  { key: "gamma", label: "Gamma", min: 0, max: 10, step: 0.01 },
  { key: "hue", label: "Hue", min: -360, max: 360, step: 1, unit: "°" },
  { key: "temperature", label: "Temperature", min: -1, max: 1, step: 0.01 },
  { key: "tint", label: "Tint", min: -1, max: 1, step: 0.01 },
  { key: "vibrance", label: "Vibrance", min: -2, max: 2, step: 0.01 },
];

/** Resize section defaults (a centred vertical short, the common case). */
export const RESIZE_DEFAULTS: ResizeConfig = {
  preset: "shorts",
  zoom: 1,
  padding: false,
};

export const RESIZE_PRESETS: { value: ResizePreset; label: string }[] = [
  { value: "youtube", label: "YouTube (16:9)" },
  { value: "shorts", label: "Shorts (9:16)" },
  { value: "tiktok", label: "TikTok (9:16)" },
  { value: "instagram", label: "Instagram (1:1)" },
  { value: "1080x1920", label: "1080×1920" },
  { value: "1920x1080", label: "1920×1080" },
  { value: "1080x1080", label: "1080×1080" },
  { value: "720p", label: "720p" },
  { value: "4k", label: "4K" },
];

/** Overlay defaults matching the engine's `OverlayConfig` field defaults. */
export const OVERLAY_DEFAULTS: Omit<OverlayConfig, "asset"> = {
  x: "center",
  y: "center",
  scale: 1,
  width: null,
  height: null,
  opacity: 1,
  rotation: 0,
  layer: 0,
  color: null,
  mask: null,
};

export const OVERLAY_ANCHORS: { value: OverlayAnchor; label: string }[] = [
  { value: "center", label: "Center" },
  { value: "top_left", label: "Top left" },
  { value: "top_right", label: "Top right" },
  { value: "bottom_left", label: "Bottom left" },
  { value: "bottom_right", label: "Bottom right" },
  { value: "top", label: "Top" },
  { value: "bottom", label: "Bottom" },
  { value: "left", label: "Left" },
  { value: "right", label: "Right" },
];

/** Mask defaults matching the engine's `MaskConfig` field defaults. */
export const MASK_DEFAULTS: MaskConfig = {
  type: "ellipse",
  feather: 0,
  width: null,
  height: null,
  rotation: 0,
  invert: false,
};

export const MASK_TYPES: { value: MaskType; label: string }[] = [
  { value: "ellipse", label: "Ellipse" },
  { value: "circle", label: "Circle" },
];

/**
 * The nine audio-effect types with their editable parameter spec. Only the
 * parameters an effect actually uses are listed, so the row renders exactly the
 * controls the engine accepts for that type (`normalize` has none).
 */
export interface AudioParamSpec {
  key: "gain" | "factor" | "semitones" | "delay" | "decay";
  label: string;
  min: number;
  max: number;
  step: number;
  default: number;
  unit?: string;
}

export const AUDIO_EFFECTS: {
  type: AudioEffectType;
  label: string;
  params: AudioParamSpec[];
}[] = [
  { type: "normalize", label: "Normalize", params: [] },
  {
    type: "volume",
    label: "Volume",
    params: [{ key: "gain", label: "Gain", min: -60, max: 60, step: 0.5, default: 0, unit: "dB" }],
  },
  {
    type: "bass",
    label: "Bass",
    params: [{ key: "gain", label: "Gain", min: -60, max: 60, step: 0.5, default: 0, unit: "dB" }],
  },
  {
    type: "treble",
    label: "Treble",
    params: [{ key: "gain", label: "Gain", min: -60, max: 60, step: 0.5, default: 0, unit: "dB" }],
  },
  {
    type: "speed",
    label: "Playback Speed",
    params: [{ key: "factor", label: "Factor", min: 0.5, max: 100, step: 0.01, default: 1, unit: "×" }],
  },
  {
    type: "pitch",
    label: "Pitch",
    params: [
      { key: "semitones", label: "Semitones", min: -24, max: 24, step: 1, default: 0 },
    ],
  },
  {
    type: "deep_voice",
    label: "Deep Voice",
    params: [
      { key: "semitones", label: "Semitones", min: -24, max: 24, step: 1, default: -4 },
    ],
  },
  {
    type: "chipmunk",
    label: "Chipmunk",
    params: [
      { key: "semitones", label: "Semitones", min: -24, max: 24, step: 1, default: 4 },
    ],
  },
  {
    type: "echo",
    label: "Echo",
    params: [
      { key: "delay", label: "Delay", min: 1, max: 5000, step: 1, default: 500, unit: "ms" },
      { key: "decay", label: "Decay", min: 0.01, max: 1, step: 0.01, default: 0.5 },
    ],
  },
];
