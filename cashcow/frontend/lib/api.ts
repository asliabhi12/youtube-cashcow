import { API_BASE_URL } from "@/lib/config";

/** Payload returned by the backend's GET /health endpoint. */
export interface HealthResponse {
  status: string;
  version: string;
}

/**
 * Fetch backend health. Resolves with the parsed payload, or throws if the
 * server is unreachable or responds with a non-OK status.
 */
export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    signal,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }

  return (await response.json()) as HealthResponse;
}

/**
 * Lifecycle state of a job. "queued" means it is waiting its turn in the FIFO
 * queue; only one job is ever "running" at a time.
 */
export type JobStatus =
  | "pending"
  | "queued"
  | "running"
  | "cancelling"
  | "cancelled"
  | "completed"
  | "failed"
  | "upload_failed";
export type MetadataStatus = "idle" | "generating" | "available" | "unavailable";
export type YouTubeUploadStatus = "idle" | "uploading" | "uploaded" | "failed";

/** A processing job as returned by the backend. */
export interface Job {
  id: string;
  url: string;
  status: JobStatus;
  /** ISO 8601 timestamp of when the job was created. */
  created_at: string;
  /** ISO 8601 timestamp of when the job actually started running; null otherwise. */
  started_at: string | null;
  /** ISO 8601 timestamp of when the job reached a terminal state; null otherwise. */
  finished_at: string | null;
  /** Creative profile id the job was created with. */
  profile_id: string;
  /** Export-quality slug the job was created with. */
  export_quality: string;
  /** Overall progress percentage (0-100). */
  progress: number;
  /** Friendly, human-readable status line describing current operation. */
  status_message: string;
  /** Path to the produced file once the workflow completes; null otherwise. */
  output_file: string | null;
  /** Title-derived download filename, once the video title is known; null otherwise. */
  output_name: string | null;
  /** Failure detail when the workflow fails; null otherwise. */
  error: string | null;
  /** 1-based place in the FIFO queue while "queued"; null otherwise. */
  queue_position: number | null;
  /** Whether AI metadata has been generated and stored for this job. */
  has_metadata: boolean;
  /** AI metadata generation state for completed jobs. */
  metadata_status: MetadataStatus;
  /** YouTube upload state for the final workflow stage. */
  youtube_upload_status: YouTubeUploadStatus;
  youtube_video_id: string | null;
  youtube_video_url: string | null;
  youtube_uploaded_at: string | null;
  youtube_upload_error: string | null;
  upload_attempts: number;
}

/** A clip range in seconds. `end` must be greater than `start`. */
export interface TrimRange {
  start: number;
  end: number;
}

/** A selectable option (editing preset or export quality) from the backend. */
export interface Option {
  value: string;
  label: string;
  description: string;
}

/** Minimal video metadata used to pre-fill the trim slider. */
export interface VideoMetadata {
  title: string | null;
  /** Duration in seconds; null when the source does not report one. */
  duration: number | null;
}

/** AI-generated YouTube metadata stored for a completed job. */
export interface JobMetadata {
  title: string;
  description: string;
  tags: string[];
  generated_at: string;
  provider: string;
  model: string;
  editable: boolean;
}

/** Body for creating a job: a URL plus its creative profile. */
export interface CreateJobInput {
  url: string;
  title_seed?: string;
  trim?: TrimRange;
  profile_id: string;
  export_quality: string;
}

/**
 * Named platform presets and dimensional shorthands the engine's resize step
 * accepts. Mirrors `ResizePreset` in the backend profile model.
 */
export type ResizePreset =
  | "youtube"
  | "shorts"
  | "tiktok"
  | "instagram"
  | "1080x1920"
  | "1920x1080"
  | "1080x1080"
  | "720p"
  | "4k";

/** Resize options: a named preset OR explicit width+height, plus zoom/padding. */
export interface ResizeConfig {
  preset?: ResizePreset | null;
  width?: number | null;
  height?: number | null;
  /** Centred punch-in; >= 1.0 (1.0 is a no-op). */
  zoom?: number | null;
  /** Letterbox to the target instead of cropping. */
  padding?: boolean | null;
}

/** The nine audio-effect types the engine implements. */
export type AudioEffectType =
  | "normalize"
  | "volume"
  | "bass"
  | "treble"
  | "speed"
  | "pitch"
  | "deep_voice"
  | "chipmunk"
  | "echo";

/**
 * A single audio effect in a chain. Only the fields relevant to `type` should
 * be set; ranges mirror the engine (gain -60..60 dB, factor 0.5..100,
 * semitones -24..24, delay ms > 0, decay 0..1).
 */
export interface AudioEffectItem {
  type: AudioEffectType;
  gain?: number | null;
  factor?: number | null;
  semitones?: number | null;
  delay?: number | null;
  decay?: number | null;
}

/** A chain of audio effects, applied in order. */
export interface AudioConfig {
  effects: AudioEffectItem[];
}

/**
 * Global colour grade. Every field defaults to its identity value; ranges
 * mirror the engine (brightness -1..1, contrast/saturation 0..3, gamma 0..10,
 * hue -360..360, temperature/tint -1..1, vibrance -2..2).
 */
export interface ColorConfig {
  brightness: number;
  contrast: number;
  saturation: number;
  gamma: number;
  hue: number;
  temperature: number;
  tint: number;
  vibrance: number;
}

/** Position anchors the engine accepts for overlay x/y (numbers also allowed). */
export type OverlayAnchor =
  | "center"
  | "top_left"
  | "top_right"
  | "bottom_left"
  | "bottom_right"
  | "top"
  | "bottom"
  | "left"
  | "right";

/** The two mask shapes the engine implements. */
export type MaskType = "circle" | "ellipse";

/**
 * Overlay mask. Omit the whole object to skip masking (there is no "none"
 * type). `invert` keeps the region outside the shape instead of inside.
 */
export interface MaskConfig {
  type: MaskType;
  feather: number;
  width?: number | null;
  height?: number | null;
  rotation: number;
  invert: boolean;
}

/**
 * Image/video overlay compositing options. `asset` is a bare filename resolved
 * by the adapter. `scale` and `width`/`height` are mutually exclusive.
 */
export interface OverlayConfig {
  asset: string;
  x: number | OverlayAnchor;
  y: number | OverlayAnchor;
  scale?: number | null;
  width?: number | null;
  height?: number | null;
  opacity: number;
  rotation: number;
  layer: number;
  color?: ColorConfig | null;
  mask?: MaskConfig | null;
}

/** A creative profile's editable creative parameters (mirrors the backend). */
export interface ProfileInput {
  label: string;
  description?: string;
  /** Creative sections; a section left undefined/null means that step is skipped. */
  resize?: ResizeConfig | null;
  audio?: AudioConfig | null;
  color?: ColorConfig | null;
  overlay?: OverlayConfig | null;
  /** Optional per-profile default export quality. */
  export_quality?: string | null;
}

/** A selectable overlay asset for the picker. */
export interface AssetSummary {
  /** Bare filename a profile stores. */
  name: string;
  /** True for bundled read-only assets; false for user uploads. */
  builtin: boolean;
}

/** A stored creative profile as returned by the backend. */
export interface Profile extends ProfileInput {
  id: string;
  /** True for bundled read-only profiles; false for user-created ones. */
  builtin: boolean;
}

/** Lightweight profile entry for the selector list. */
export interface ProfileSummary {
  id: string;
  label: string;
  description: string;
  builtin: boolean;
}

/** Application-level settings surfaced by the backend. */
export interface AppSettings {
  /** Id of the last profile used to run a job; null when unset or stale. */
  last_profile: string | null;
}

/** Severity of a per-job log entry. */
export type JobLogLevel = "INFO" | "WARNING" | "ERROR";

/** A single high-level log line for a job's workflow execution. */
export interface JobLogEntry {
  /** ISO 8601 timestamp of when the entry was recorded. */
  timestamp: string;
  level: JobLogLevel;
  message: string;
}

/** Create a job from a URL and creative profile. Throws on a non-OK response. */
export async function createJob(input: CreateJobInput): Promise<Job> {
  const response = await fetch(`${API_BASE_URL}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(`Failed to create job: ${response.status}`);
  }

  return (await response.json()) as Job;
}

/** Fetch every creative profile as a summary. Throws on a non-OK response. */
export async function fetchProfiles(signal?: AbortSignal): Promise<ProfileSummary[]> {
  const response = await fetch(`${API_BASE_URL}/profiles`, { signal, cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load profiles: ${response.status}`);
  }
  return (await response.json()) as ProfileSummary[];
}

/** Fetch a single full profile by id. Throws on a non-OK response. */
export async function fetchProfile(id: string, signal?: AbortSignal): Promise<Profile> {
  const response = await fetch(`${API_BASE_URL}/profiles/${encodeURIComponent(id)}`, {
    signal,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load profile: ${response.status}`);
  }
  return (await response.json()) as Profile;
}

/** Create a new custom profile. Throws on a non-OK response. */
export async function createProfile(input: ProfileInput): Promise<Profile> {
  const response = await fetch(`${API_BASE_URL}/profiles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`Failed to create profile: ${response.status}`);
  }
  return (await response.json()) as Profile;
}

/** Overwrite an existing custom profile. Throws on a non-OK response. */
export async function updateProfile(id: string, input: ProfileInput): Promise<Profile> {
  const response = await fetch(`${API_BASE_URL}/profiles/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`Failed to update profile: ${response.status}`);
  }
  return (await response.json()) as Profile;
}

/** Delete a custom profile. Throws on a non-OK response. */
export async function deleteProfile(id: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/profiles/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to delete profile: ${response.status}`);
  }
}

/** Duplicate any profile into a new editable custom profile ("Save As"). */
export async function duplicateProfile(id: string, label?: string): Promise<Profile> {
  const response = await fetch(
    `${API_BASE_URL}/profiles/${encodeURIComponent(id)}/duplicate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: label ?? null }),
    },
  );
  if (!response.ok) {
    throw new Error(`Failed to duplicate profile: ${response.status}`);
  }
  return (await response.json()) as Profile;
}

/** Fetch application settings (e.g. the last-used profile). Throws on non-OK. */
export async function fetchAppSettings(signal?: AbortSignal): Promise<AppSettings> {
  const response = await fetch(`${API_BASE_URL}/settings`, { signal, cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load settings: ${response.status}`);
  }
  return (await response.json()) as AppSettings;
}

/** Update application settings. Throws on a non-OK response. */
export async function updateAppSettings(input: AppSettings): Promise<AppSettings> {
  const response = await fetch(`${API_BASE_URL}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(`Failed to update settings: ${response.status}`);
  }
  return (await response.json()) as AppSettings;
}

/** Fetch overlay assets (built-ins first, then user uploads). Throws on non-OK. */
export async function fetchOverlayAssets(signal?: AbortSignal): Promise<AssetSummary[]> {
  const response = await fetch(`${API_BASE_URL}/assets?type=overlay`, {
    signal,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load assets: ${response.status}`);
  }
  return (await response.json()) as AssetSummary[];
}

/**
 * Upload an overlay asset. Returns its summary, whose `name` is the
 * (possibly de-duplicated) bare filename a profile should reference. Throws
 * with the server's validation detail on a non-OK response.
 */
export async function uploadOverlayAsset(file: File): Promise<AssetSummary> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${API_BASE_URL}/assets/upload`, {
    method: "POST",
    body,
  });
  if (!response.ok) {
    let detail = `Failed to upload asset: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // Non-JSON error body; keep the status-based message.
    }
    throw new Error(detail);
  }
  return (await response.json()) as AssetSummary;
}

/** Delete a user-uploaded overlay asset. Throws on a non-OK response. */
export async function deleteOverlayAsset(name: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/assets/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to delete asset: ${response.status}`);
  }
}

/** Fetch the available export-quality options. Throws on a non-OK response. */
export async function fetchExportQualities(signal?: AbortSignal): Promise<Option[]> {
  const response = await fetch(`${API_BASE_URL}/export-qualities`, {
    signal,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load export qualities: ${response.status}`);
  }
  return (await response.json()) as Option[];
}

/**
 * Fetch a video's title and duration without downloading it. Throws on a
 * non-OK response (e.g. invalid URL or upstream extraction failure), so callers
 * can fall back to a default trim range.
 */
export async function fetchVideoMetadata(
  url: string,
  signal?: AbortSignal,
): Promise<VideoMetadata> {
  const response = await fetch(
    `${API_BASE_URL}/videos/metadata?url=${encodeURIComponent(url)}`,
    { signal, cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Failed to load video metadata: ${response.status}`);
  }
  return (await response.json()) as VideoMetadata;
}

/** List all jobs. Throws if the server is unreachable or responds non-OK. */
export async function listJobs(signal?: AbortSignal): Promise<Job[]> {
  const response = await fetch(`${API_BASE_URL}/jobs`, {
    signal,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to load jobs: ${response.status}`);
  }

  return (await response.json()) as Job[];
}

/** Fetch a single job's current state. Throws on a non-OK response. */
export async function getJob(jobId: string, signal?: AbortSignal): Promise<Job> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
    signal,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to load job: ${response.status}`);
  }

  return (await response.json()) as Job;
}

/** Fetch generated AI metadata for a job. Throws on 404/unavailable. */
export async function fetchJobMetadata(
  jobId: string,
  signal?: AbortSignal,
): Promise<JobMetadata> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/metadata`, {
    signal,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to load job metadata: ${response.status}`);
  }

  return (await response.json()) as JobMetadata;
}

/**
 * Delete a job, or remove it from the queue if it is still queued. The backend
 * refuses to delete the running job (409); this surfaces that as a clear error
 * so callers can tell the user why nothing happened.
 */
export async function deleteJob(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    if (response.status === 409) {
      throw new Error("The running job can't be removed; wait for it to finish.");
    }
    throw new Error(`Failed to delete job: ${response.status}`);
  }
}

/** Request cooperative cancellation for a queued or running job. */
export async function cancelJob(jobId: string): Promise<Job> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/cancel`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Failed to cancel job: ${response.status}`);
  }
  return (await response.json()) as Job;
}

/** Retry only the YouTube upload stage for a processed job. */
export async function retryYouTubeUpload(jobId: string): Promise<Job> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/youtube/retry`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Failed to retry YouTube upload: ${response.status}`);
  }
  return (await response.json()) as Job;
}

/** Fetch a job's log history. Throws if the server is unreachable or non-OK. */
export async function fetchJobLogs(
  jobId: string,
  signal?: AbortSignal,
): Promise<JobLogEntry[]> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/logs`, {
    signal,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to load logs: ${response.status}`);
  }

  return (await response.json()) as JobLogEntry[];
}

/** URL of a job's live log stream (Server-Sent Events). */
export function jobLogsEventsUrl(jobId: string): string {
  return `${API_BASE_URL}/jobs/${jobId}/logs/events`;
}

/** URL to download a completed job's output file. */
export function jobDownloadUrl(jobId: string): string {
  return `${API_BASE_URL}/jobs/${jobId}/download`;
}
