"use client";

import { FilePlus2, Save, SaveAll, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ProfileActionsProps {
  /** Whether the active profile is a read-only built-in. */
  isBuiltin: boolean;
  /** Whether a custom profile is currently selected (enables Delete). */
  canDelete: boolean;
  /** Disable every action (e.g. while a save is in flight). */
  disabled?: boolean;
  onNew: () => void;
  onSave: () => void;
  onSaveAs: () => void;
  onDelete: () => void;
  className?: string;
}

/**
 * The New / Save / Save As / Delete row for the creative-profile editor.
 *
 * Built-in profiles are read-only, so Save is hidden for them (the user "Saves
 * As" a new custom profile instead) and Delete is only enabled for custom
 * profiles. This mirrors the backend, which returns 403 on a write or delete
 * against a built-in.
 */
export function ProfileActions({
  isBuiltin,
  canDelete,
  disabled = false,
  onNew,
  onSave,
  onSaveAs,
  onDelete,
  className,
}: ProfileActionsProps) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <Button size="sm" variant="outline" disabled={disabled} onClick={onNew}>
        <FilePlus2 />
        New
      </Button>
      {!isBuiltin && (
        <Button size="sm" variant="outline" disabled={disabled} onClick={onSave}>
          <Save />
          Save
        </Button>
      )}
      <Button size="sm" variant="outline" disabled={disabled} onClick={onSaveAs}>
        <SaveAll />
        Save As
      </Button>
      <Button
        size="sm"
        variant="ghost"
        disabled={disabled || !canDelete}
        onClick={onDelete}
        title={canDelete ? "Delete this custom profile" : "Built-in profiles can't be deleted"}
      >
        <Trash2 />
        Delete
      </Button>
    </div>
  );
}
