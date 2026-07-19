import { redirect } from "next/navigation";

/**
 * The old Presets page has been superseded by the creative-profile system.
 * Redirect any lingering links to the new Profiles manager.
 */
export default function PresetsPage() {
  redirect("/profiles");
}
