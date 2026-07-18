"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createJob } from "@/lib/api";

/** URL entry field with a Run action. Submitting creates a job, then routes to Jobs. */
export function UrlForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = url.trim();
  const canRun = trimmed.length > 0 && !submitting;

  async function handleRun(): Promise<void> {
    if (trimmed.length === 0 || submitting) {
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await createJob(trimmed);
      router.push("/jobs");
    } catch {
      setError("Could not create the job. Is the server running?");
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <label htmlFor="youtube-url" className="text-sm font-medium">
        Paste YouTube URL
      </label>
      <Input
        id="youtube-url"
        inputMode="url"
        placeholder="https://www.youtube.com/watch?v=…"
        value={url}
        disabled={submitting}
        onChange={(event) => setUrl(event.target.value)}
      />
      {error !== null && <p className="text-sm text-red-500">{error}</p>}
      <div className="flex justify-end">
        <Button size="lg" disabled={!canRun} onClick={() => void handleRun()}>
          {submitting ? "Running…" : "Run"}
        </Button>
      </div>
    </div>
  );
}
