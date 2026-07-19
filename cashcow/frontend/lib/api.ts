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

/** Lifecycle state of a job, mirroring the workflow's progress. */
export type JobStatus = "pending" | "running" | "completed" | "failed";

/** A processing job as returned by the backend. */
export interface Job {
  id: string;
  url: string;
  status: JobStatus;
  /** ISO 8601 timestamp of when the job was created. */
  created_at: string;
  /** Creative profile id the job was created with. */
  profile_id: string;
  /** Export-quality slug the job was created with. */
  export_quality: string;
  /** Path to the produced file once the workflow completes; null otherwise. */
  output_file: string | null;
  /** Title-derived download filename, once the video title is known; null otherwise. */
  output_name: string | null;
  /** Failure detail when the workflow fails; null otherwise. */
  error: string | null;
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

/** Body for creating a job: a URL plus its creative profile. */
export interface CreateJobInput {
  url: string;
  trim?: TrimRange;
  profile_id: string;
  export_quality: string;
}

/** A creative profile's editable creative parameters (mirrors the backend). */
export interface ProfileInput {
  label: string;
  description?: string;
  /** Creative sections; a section left undefined means that step is skipped. */
  resize?: Record<string, unknown> | null;
  audio?: { effects: Record<string, unknown>[] } | null;
  color?: Record<string, number> | null;
  overlay?: Record<string, unknown> | null;
  /** Optional per-profile default export quality. */
  export_quality?: string | null;
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
