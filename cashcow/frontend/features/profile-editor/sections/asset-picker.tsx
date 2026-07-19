"use client";

import { Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import {
  deleteOverlayAsset,
  fetchOverlayAssets,
  uploadOverlayAsset,
  type AssetSummary,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface AssetPickerProps {
  /** Bare filename of the selected asset, or empty when none is chosen. */
  value: string;
  onChange: (assetName: string) => void;
  disabled?: boolean;
}

/**
 * A unified overlay-asset picker: one dropdown listing built-in and uploaded
 * assets (grouped), an Upload button that stores a new asset and selects it,
 * and a Delete button for the selected user asset. Assets are referenced only
 * by bare filename — the backend resolves the filesystem path — so no path is
 * ever exposed here.
 */
export function AssetPicker({ value, onChange, disabled = false }: AssetPickerProps) {
  const selectId = useId();
  const fileRef = useRef<HTMLInputElement>(null);
  const [assets, setAssets] = useState<AssetSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal): Promise<AssetSummary[]> => {
    const list = await fetchOverlayAssets(signal);
    setAssets(list);
    return list;
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).catch(() => {
      if (!controller.signal.aborted) {
        setError("Could not load assets.");
      }
    });
    return () => controller.abort();
  }, [load]);

  const builtins = assets.filter((a) => a.builtin);
  const uploads = assets.filter((a) => !a.builtin);
  const selected = assets.find((a) => a.name === value);
  const canDelete = selected !== undefined && !selected.builtin;

  async function handleUpload(file: File): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const created = await uploadOverlayAsset(file);
      await load();
      onChange(created.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(): Promise<void> {
    if (!canDelete) {
      return;
    }
    if (!window.confirm(`Delete asset "${value}"? This cannot be undone.`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await deleteOverlayAsset(value);
      const list = await load();
      // If the deleted asset was selected, fall back to the first available.
      if (!list.some((a) => a.name === value)) {
        onChange(list[0]?.name ?? "");
      }
    } catch {
      setError("Could not delete the asset.");
    } finally {
      setBusy(false);
    }
  }

  const controlsDisabled = disabled || busy;

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={selectId} className="text-sm font-medium">
        Overlay Asset
      </label>
      <div className="flex items-center gap-2">
        <select
          id={selectId}
          value={value}
          disabled={controlsDisabled || assets.length === 0}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
        >
          {value === "" && (
            <option value="" disabled>
              Select an asset…
            </option>
          )}
          {builtins.length > 0 && (
            <optgroup label="Built-in">
              {builtins.map((a) => (
                <option key={a.name} value={a.name}>
                  {a.name}
                </option>
              ))}
            </optgroup>
          )}
          {uploads.length > 0 && (
            <optgroup label="My Assets">
              {uploads.map((a) => (
                <option key={a.name} value={a.name}>
                  {a.name}
                </option>
              ))}
            </optgroup>
          )}
        </select>

        <Button
          size="icon"
          variant="outline"
          disabled={controlsDisabled}
          title="Upload a new asset"
          onClick={() => fileRef.current?.click()}
          className="shrink-0"
        >
          <Upload />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          disabled={controlsDisabled || !canDelete}
          title={
            canDelete ? "Delete this uploaded asset" : "Built-in assets can't be deleted"
          }
          onClick={() => void handleDelete()}
          className="shrink-0"
        >
          <Trash2 />
        </Button>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/*,video/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            void handleUpload(file);
          }
          // Reset so selecting the same file again re-triggers change.
          e.target.value = "";
        }}
      />

      {busy && <p className="text-xs text-muted-foreground">Working…</p>}
      {error !== null && <p className={cn("text-xs text-red-500")}>{error}</p>}
    </div>
  );
}
