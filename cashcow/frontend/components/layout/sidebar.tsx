"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/components/layout/nav-items";

/** Fixed left navigation rail. */
export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden h-full w-64 shrink-0 flex-col border-r bg-sidebar backdrop-blur-xl md:flex">
      <div className="flex h-16 items-center px-5">
        <Link
          href="/"
          className="group flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="grid size-8 place-items-center rounded-md border border-primary/25 bg-primary/10 text-xs font-semibold text-primary shadow-sm">
            CC
          </span>
          <span className="flex flex-col">
            <span className="text-sm font-semibold tracking-tight text-foreground">
              CashCow
            </span>
            <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              AI workflow
            </span>
          </span>
        </Link>
      </div>

      <nav className="flex flex-col gap-1 px-3 py-3">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const isActive =
            href === "/" ? pathname === "/" : pathname.startsWith(href);

          return (
            <Link
              key={href}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive
                  ? "bg-accent/80 text-accent-foreground shadow-sm ring-1 ring-primary/15"
                  : "text-muted-foreground hover:bg-accent/45 hover:text-accent-foreground",
              )}
            >
              <Icon className="size-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto border-t px-5 py-4">
        <p className="text-xs font-medium text-foreground">Local-first stack</p>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          Run the backend locally to process videos, metadata, and uploads.
        </p>
      </div>
    </aside>
  );
}
