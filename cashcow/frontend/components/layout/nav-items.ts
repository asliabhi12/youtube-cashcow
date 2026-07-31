import {
  Home,
  ListChecks,
  Settings,
  Sparkles,
  Waypoints,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

/** Sidebar navigation entries, in display order. */
export const NAV_ITEMS: readonly NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: Home },
  { label: "Jobs", href: "/jobs", icon: ListChecks },
  { label: "Profiles", href: "/profiles", icon: Sparkles },
  { label: "Destinations", href: "/destinations", icon: Waypoints },
  { label: "Settings", href: "/settings", icon: Settings },
];
