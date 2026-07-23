"use client";

import {
  BadgeCheck,
  CircleAlert,
  CircleDashed,
  Clock3,
  Play,
  type LucideIcon,
} from "lucide-react";

import type {
  Destination,
  DestinationPlatform,
  DestinationStatus,
  JobDestinationStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export const PLATFORM_LABELS: Record<DestinationPlatform, string> = {
  youtube: "YouTube",
};

export const PLATFORM_OPTIONS: DestinationPlatform[] = ["youtube"];

const PLATFORM_ICONS: Record<DestinationPlatform, LucideIcon> = {
  youtube: Play,
};

export function PlatformIcon({
  platform,
  className,
}: {
  platform: DestinationPlatform;
  className?: string;
}) {
  const Icon = PLATFORM_ICONS[platform];
  return <Icon className={cn("size-4", className)} />;
}

export function PlatformBadge({ platform }: { platform: DestinationPlatform }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border bg-background/65 px-2 py-0.5 text-xs font-medium text-muted-foreground">
      <PlatformIcon platform={platform} className="size-3.5" />
      {PLATFORM_LABELS[platform]}
    </span>
  );
}

const DESTINATION_STATUS_STYLES: Record<DestinationStatus, string> = {
  connected: "border-success-border bg-success-surface text-success-foreground",
  needs_reconnection: "border-warning-border bg-warning-surface text-warning-foreground",
  disconnected: "border-muted-foreground/25 bg-background/60 text-muted-foreground",
  error: "border-danger-border bg-danger-surface text-danger-foreground",
};

const JOB_STATUS_STYLES: Record<JobDestinationStatus, string> = {
  queued: "border-muted-foreground/25 bg-background/60 text-muted-foreground",
  uploading: "border-info-border bg-info-surface text-info-foreground",
  success: "border-success-border bg-success-surface text-success-foreground",
  failed: "border-danger-border bg-danger-surface text-danger-foreground",
  skipped: "border-warning-border bg-warning-surface text-warning-foreground",
};

const JOB_STATUS_ICONS: Record<JobDestinationStatus, LucideIcon> = {
  queued: Clock3,
  uploading: CircleDashed,
  success: BadgeCheck,
  failed: CircleAlert,
  skipped: CircleAlert,
};

export function DestinationStatusBadge({ status }: { status: DestinationStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
        DESTINATION_STATUS_STYLES[status],
      )}
    >
      {status.replace("_", " ")}
    </span>
  );
}

export function JobDestinationStatusBadge({ status }: { status: JobDestinationStatus }) {
  const Icon = JOB_STATUS_ICONS[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
        JOB_STATUS_STYLES[status],
      )}
    >
      <Icon className={cn("size-3.5", status === "uploading" && "animate-spin")} />
      {status}
    </span>
  );
}

export function destinationInitials(destination: Pick<Destination, "name" | "thumbnail">) {
  if (destination.thumbnail.trim()) {
    return destination.thumbnail.trim().slice(0, 3).toUpperCase();
  }
  return destination.name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
