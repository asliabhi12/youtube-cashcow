"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/** URL entry field with a Run action. Run stays disabled until a URL is entered. */
export function UrlForm() {
  const [url, setUrl] = useState("");
  const canRun = url.trim().length > 0;

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
        onChange={(event) => setUrl(event.target.value)}
      />
      <div className="flex justify-end">
        <Button size="lg" disabled={!canRun}>
          Run
        </Button>
      </div>
    </div>
  );
}
