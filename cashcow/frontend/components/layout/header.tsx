"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useDemoMode } from "@/components/demo-mode/use-demo-mode";
import { NAV_ITEMS } from "@/components/layout/nav-items";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { ServerStatusIndicator } from "@/features/server-status/server-status-indicator";
import { cn } from "@/lib/utils";

/** Top application bar. Server status is pinned to the right. */
export function Header() {
  const { isDemoMode } = useDemoMode();
  const pathname = usePathname();

  return (
    <header className="shrink-0 border-b bg-background/85 backdrop-blur-xl">
      <div className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6">
        <div className="min-w-0 md:hidden">
          <p className="truncate text-sm font-semibold tracking-tight">CashCow</p>
          <p className="text-xs text-muted-foreground">AI workflow platform</p>
        </div>
        <div className="hidden min-w-0 md:block">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Production console
          </p>
        </div>
        <div className="flex items-center gap-3">
          {isDemoMode && (
            <span className="rounded-full border border-primary/25 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              Demo Mode
            </span>
          )}
          <ThemeToggle />
          <ServerStatusIndicator />
        </div>
      </div>
      <nav className="flex gap-1 overflow-x-auto border-t px-3 py-2 md:hidden" aria-label="Primary">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const isActive =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "inline-flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive
                  ? "bg-accent/80 text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/45 hover:text-accent-foreground",
              )}
            >
              <Icon className="size-3.5" />
              {label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
