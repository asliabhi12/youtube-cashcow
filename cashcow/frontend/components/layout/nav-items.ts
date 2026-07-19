import { Home, ListChecks, Settings, Sparkles, type LucideIcon } from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

/** Sidebar navigation entries, in display order. */
export const NAV_ITEMS: readonly NavItem[] = [
  { label: "Home", href: "/", icon: Home },
  { label: "Jobs", href: "/jobs", icon: ListChecks },
  { label: "Profiles", href: "/profiles", icon: Sparkles },
  { label: "Settings", href: "/settings", icon: Settings },
];
